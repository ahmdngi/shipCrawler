#!/usr/bin/env python3
"""
Shipcrawler v4 Phase Worker — runs sequential agent investigation phases,
emits structured progress events to the progress log for real-time SSE streaming.

Flow:
  queue/pending/<task_id>.json → worker processes phases one by one
  Each phase: run prompt with skill → write progress to queue/progress/<task_id>.log
  Frontend reads progress via SSE endpoint
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import worker_progress as wp
import stream_formatter as sf

try:
    import template_renderer
    _TEMPLATES_AVAILABLE = template_renderer.is_jinja_available()
except ImportError:
    _TEMPLATES_AVAILABLE = False

BASE_DIR = Path(__file__).parent
QUEUE_DIR = BASE_DIR / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
RUNNING_DIR = QUEUE_DIR / "running"
DONE_DIR = QUEUE_DIR / "done"
PROGRESS_DIR = QUEUE_DIR / "progress"
REPORT_BASE = Path("/root/hermes-vault/osint-reports")

HERMES_BIN = "hermes"
POLL_INTERVAL = 5


def sanitize_name(name):
    import unicodedata
    # Strip diacritics: Pärtel → Partel, Keskküla → Keskkula
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'^(MMSI|IMO)\s*[:]?\s*', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'[^\w\s-]', '', name).strip()
    return name or "target"


def clean_for_filename(name):
    return name.lower().replace(" ", "-")


def build_shipcrawler_prompt(name: str, mode: str, context: str, dir_suffix: str = "", report_dir: str = "") -> str:
    """Build a single comprehensive prompt using the shipcrawler skill.

    dir_suffix: optional suffix for the report directory (e.g. "-2026-07-15").
    """
    date_part = dir_suffix  # e.g. "-2026-07-15"

    def p(text):
        """Strip 'agent' branding references from text only (not paths)."""
        return text.replace("Hermes", "AI agent").replace("hermes", "AI agent").replace("HERMES", "AI")

    base_context = p(f"Research context: {context}") if context else ""

    if mode == "person":
        content = p(
            f"Using the shipcrawler OSINT framework, research the person \"{name}\".\n\n"
            f"{base_context}\n\n"
            f"Execute ALL phases of the people OSINT methodology:\n"
            f"1. Identity & Academic Sources — search ORCID, Google Scholar, DBLP, LinkedIn, GitHub\n"
            f"2. Research Impact Analysis — publications, citations, h-index, co-authors\n"
            f"3. Social & Digital Footprint — social media, crt.sh, breach data\n"
            f"4. Professional Network & Timeline — career history, education, geography\n"
            f"5. Targeting Scenarios — 2-3 attack vectors with difficulty, cost, detection probability\n\n"
            f"Generate a COMPREHENSIVE report with the following files saved to "
            f"{REPORT_BASE}/<name>{date_part}-report/:\n"
            f"- analyst-report.md (full narrative with identity, career, research, digital footprint, confidence)\n"
            f"- red-team-playbook.md (2-3 attack vectors with equipment, steps, detection points)\n"
            f"- indicators-and-detection.md (Elastic rules, Zeek scripts, runbook)\n\n"
            f"Be thorough — use multiple sources, cross-reference, and provide confidence levels per finding."
        )
        # Restore the path if p() mangled it
        content = content.replace("/root/AI agent-vault/osint-reports", "/root/hermes-vault/osint-reports")
        return content
    else:
        if _TEMPLATES_AVAILABLE and report_dir:
            report_instruction = (
                "\n"
                "⚠️ TEMPLATE SKELETONS HAVE BEEN WRITTEN to " + report_dir + "/ — "
                "analyst-report.md, red-team-playbook.md, indicators-and-detection.md. "
                "These are Jinja2 skeleton files with <!-- --> comment placeholders. "
                "FILL IN each section by READING the skeleton, researching the data, "
                "and OVERWRITING the placeholders with real findings. Do NOT discard "
                "the skeleton structure — complete it. Write the completed files using "
                "the write_file tool. Never use bash heredocs (cat > << EOF) — they "
                "truncate large markdown and corrupt special characters. If write_file "
                "is unavailable, use Python open().write() via terminal.\n"
            )
        else:
            report_instruction = (
                "Generate a COMPREHENSIVE 3-file report:\n"
                "1. analyst-report.md — full narrative with vessel identity, current "
                "status, port calls, Shodan findings, vulnerability assessment, threat "
                "intel, operational pattern analysis, confidence assessment per category "
                "(HIGH/MEDIUM/LOW/SPECULATIVE)\n"
                "2. red-team-playbook.md — 2-3 attack vectors with name, difficulty, "
                "cost, detection prob, equipment list, numbered execution steps, "
                "detection points table\n"
                "3. indicators-and-detection.md — indicator table (ID, type, phase, "
                "priority, description), Elastic SIEM rules, Zeek scripts, M-SOC runbook\n\n"
            )
        content = p(
            f"Using the shipcrawler OSINT framework, research the vessel \"{name}\".\n\n"
            f"{base_context}\n\n"
            f"Execute ALL phases of the vessel OSINT methodology:\n"
            f"Phase 0: Vessel Identity from Equasis — use equasis-cli (IMO lookup). "
            f"If rate-limited, wait 30-60s and retry.\n"
            f"Phase 1: Target Identification — AIS tracking, position, speed, destination, port calls "
            f"from VesselFinder, MarineTraffic, MyShipTracking\n"
            f"Phase 2: Attack Surface Discovery — Shodan search by name, MMSI, IMO, call sign; "
            f"maritime protocol search (Signal K, VSAT, NMEA, ECDIS)\n"
            f"Phase 3: Vulnerability Assessment — CVEs, misconfigurations, risk levels\n"
            f"Phase 4: Threat Intelligence — maritime cyber incidents, news, geopolitical context\n"
            f"Phase 5: Report Generation\n\n"
            f"{report_instruction}"
            f"CRITICAL: Write all report files using Python (open().write()) — NEVER use bash heredocs "
            f"(cat > << EOF). Bash heredocs truncate large markdown files with special characters.\n\n"
            f"Be thorough — use multiple independent AIS sources, cross-reference Equasis data, "
            f"and report zero findings explicitly (it's a finding). Provide confidence levels.\n\n"
            f"IMPORTANT: Save ALL 3 report files to the directory: {report_dir}/"
        )
        content = content.replace("/root/AI agent-vault/osint-reports", "/root/hermes-vault/osint-reports")
        return content


def worker_phase_output(task_id, phase, line, line_type="output"):
    """Write a line of phase output with type classification."""
    wp.write_event(task_id, "phase_output", phase=phase, line=line[:500], line_type=line_type)


def run_shipcrawler(task_id: str, name: str, mode: str, context: str, model: str = None, provider: str = None, profile: str = None) -> dict:
    """Run a single comprehensive Hermes shipcrawler session with real-time streaming."""
    from datetime import date

    today = date.today().isoformat()  # e.g. "2026-07-15"
    dir_suffix = f"-{today}"

    safe_name = sanitize_name(name)
    # Include task_id (UUID) so same-vessel same-day runs don't collide
    dir_name = clean_for_filename(safe_name) + dir_suffix + f"-{task_id[:8]}" + "-report"
    report_dir = REPORT_BASE / dir_name
    report_dir.mkdir(parents=True, exist_ok=True)

    # Write Jinja2 skeleton files for the agent to fill in (vessel mode)
    if mode != "person" and _TEMPLATES_AVAILABLE:
        try:
            template_renderer.write_skeleton_files(
                vessel_name=name,
                report_dir=report_dir,
                date=today,
            )
        except Exception:
            pass  # non-fatal — agent falls back to freeform generation

    prompt = build_shipcrawler_prompt(name, mode, context, dir_suffix=dir_suffix, report_dir=str(report_dir))

    start_total = time.time()
    output_lines = []
    current_tool = ""

    wp.phase_start(task_id, 0, "Investigating")
    print(f"[worker {task_id}] Starting shipcrawler research on \"{name}\" ({mode})...")
    sys.stdout.flush()

    # Emit filler frames so frontend shows progress immediately
    wp.structured_output(task_id, 0, "status", "⏳", "Initializing reconnaissance agents...")
    if mode == "vessel":
        wp.structured_output(task_id, 0, "status", "🔍", "Searching vessel registries and AIS sources...")
    else:
        wp.structured_output(task_id, 0, "status", "🔍", "Searching identity and academic sources...")

    # Counters for summary stats
    tool_calls = 0
    searches = 0
    source_fetches = 0
    shodan_hits = 0

    cmd = [
        HERMES_BIN, "chat",
        "-q", prompt,
        "--skills", "shipcrawler",
        "-t", "web,terminal,file",
        "--yolo",
        "--max-turns", "150",
        "--source", "tool",
    ]
    if provider:
        cmd.extend(["--provider", provider])
    if model:
        cmd.extend(["--model", model])
    if profile:
        cmd.insert(1, "--profile")
        cmd.insert(2, profile)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "HOME": os.path.expanduser("~")},
        )

        # Read stdout line by line in real-time — classify and structure
        for line in iter(proc.stdout.readline, ""):
            stripped = line.rstrip("\n\r")
            output_lines.append(line)

            if not stripped:
                continue

            # Process through the stream formatter — returns structured event or None
            event = sf.process_output_line(stripped)
            if event is None:
                continue

            # Count tool calls for summary stats — only actual tool executions,
            # not status messages or reasoning blocks
            icon = event.get("icon", "")
            msg_lower = (event.get("message") or "").lower()
            is_tool_exec = icon in ("💻", "🔍", "📄", "🌐", "📑") and "preparing" not in msg_lower
            if is_tool_exec:
                tool_calls += 1
                if icon == "🔍":
                    searches += 1
                if icon in ("📄", "🌐"):
                    source_fetches += 1
                # Shodan — only count actual terminal execs containing "shodan"
                if icon == "💻" and "shodan" in msg_lower:
                    shodan_hits += 1

            # Write as structured output event
            wp.structured_output(
                task_id, 0,
                event_subtype=event["type"],
                icon=event["icon"],
                message=event["message"],
            )

        proc.stdout.close()
        proc.wait(timeout=30)
        stderr = proc.stderr.read() if proc.stderr else ""
        exit_code = proc.returncode

    except subprocess.TimeoutExpired:
        stderr = "TIMEOUT: Shipcrawler took longer than 15 minutes"
        exit_code = -1
    except Exception as e:
        stderr = f"EXCEPTION: {e}"
        exit_code = -2

    output = "".join(output_lines)

    # Write full untruncated hermes log for stats parsing (like sirb)
    log_path = report_dir / "agent.log"
    if output.strip():
        log_path.write_text(output)
    else:
        log_path.write_text(f"AI agent returned no output.\n\n{stderr}")

    # Write truncated raw-output.md for dashboard display (100KB cap)
    raw_path = report_dir / "raw-output.md"
    if output.strip():
        raw_path.write_text(output[:100000])
    else:
        raw_path.write_text(f"AI agent returned no output.\n\n{stderr}")

    # Copy agent-created report files into the worker's report dir
    # Agent may have saved files to a different directory (derived from first word of name)
    # Only match dirs WITHOUT a date suffix (those are stale previous runs)
    first_word = safe_name.split()[0].lower() if safe_name.split() else safe_name.lower()
    agent_candidates = list(REPORT_BASE.glob(f"{first_word}*-report"))
    agent_dirs = [d for d in agent_candidates if not re.search(r'\d{4}-\d{2}-\d{2}', d.name)]
    for ad in agent_dirs:
        if ad == report_dir:
            continue
        if not ad.is_dir():
            continue
        for f in sorted(ad.glob("*.md")):
            dest = report_dir / f.name
            if not dest.exists() and f.name != "raw-output.md":
                dest.write_text(f.read_text())
                print(f"[worker {task_id}] Copied {f.name} from {ad.name}")
        import shutil
        shutil.rmtree(ad, ignore_errors=True)
        print(f"[worker {task_id}] Cleaned up agent dir: {ad.name}")
    sys.stdout.flush()

    duration = time.time() - start_total
    summary = f"Research complete ({duration:.0f}s, exit={exit_code})"

    if exit_code != 0 and not output.strip():
        wp.phase_error(task_id, 0, "AI Agent Researching", f"Exit {exit_code}: {stderr[:200]}")
        print(f"[worker {task_id}] ERROR exit={exit_code}: {stderr[:100]}")
    else:
        wp.phase_complete(task_id, 0, "AI Agent Researching", duration, summary)
        print(f"[worker {task_id}] Research done ({duration:.1f}s)")
    sys.stdout.flush()

    # Check what other files the agent may have written
    md_files = sorted(report_dir.glob("*.md"))
    if raw_path not in md_files:
        md_files.insert(0, raw_path)

    total_duration = time.time() - start_total

    # Override tool_calls with the real count from the hermes session summary
    # The live counter over-counts (includes status messages); the session
    # summary has the authoritative count: "Messages: N (1 user, M tool calls)"
    if output.strip():
        m = re.search(r'Messages:\s*\d+\s*\([^)]*?(\d+)\s+tool calls?\)', output)
        if m:
            tool_calls = int(m.group(1))

    wp.report_complete(task_id, str(report_dir), total_duration, [f.name for f in md_files], {
        "tool_calls": tool_calls,
        "searches": searches,
        "sources": source_fetches,
        "shodan": shodan_hits,
    }, model=model, provider=provider)

    print(f"[worker {task_id}] REPORT COMPLETE ({total_duration:.1f}s total)")
    print(f"[worker {task_id}]   Files: {[f.name for f in md_files]}")
    sys.stdout.flush()

    return {
        "task_id": task_id,
        "mode": mode,
        "model": model,
        "provider": provider,
        "status": "done" if exit_code == 0 or output.strip() else "error",
        "report_dir": str(report_dir),
        "report_files": [str(f) for f in md_files],
        "duration_total": round(total_duration, 1),
        "hermes_exit": exit_code,
        "stats": {
            "tool_calls": tool_calls,
            "searches": searches,
            "sources": source_fetches,
            "shodan": shodan_hits,
        },
    }


def process_queue():
    # Ensure all queue directories exist
    for d in (PENDING_DIR, RUNNING_DIR, DONE_DIR, PROGRESS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    tasks = sorted(PENDING_DIR.glob("*.json"), key=os.path.getmtime)
    if not tasks:
        return False

    task_path = tasks[0]
    try:
        with open(task_path) as f:
            task = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        done = {"task_id": "corrupt", "status": "error", "error": str(e)}
        done_path = DONE_DIR / (task_path.stem + ".json")
        with open(done_path, "w") as f:
            json.dump(done, f, indent=2)
        task_path.unlink(missing_ok=True)
        return True

    task.setdefault("task_id", task_path.stem)

    # Move to running
    running_path = RUNNING_DIR / task_path.name
    task_path.rename(running_path)

    print(f"[worker] Processing task {task['task_id']}: {task.get('name', '?')} ({task.get('mode', '?')})")
    sys.stdout.flush()

    result = run_shipcrawler(
        task["task_id"],
        task.get("name", ""),
        task.get("mode", "vessel"),
        task.get("context", ""),
        model=task.get("model"),
        provider=task.get("provider"),
        profile=task.get("profile"),
    )

    done_path = DONE_DIR / task_path.name
    with open(done_path, "w") as f:
        json.dump(result, f, indent=2)

    running_path.unlink(missing_ok=True)

    print(f"[worker] Task {task['task_id']} → {result['status']} ({result.get('duration_total', '?')}s)")
    sys.stdout.flush()
    return True


def main():
    print(f"Shipcrawler v4 Phase Worker — watching {PENDING_DIR}")
    print(f"  Hermes: {HERMES_BIN}")
    print(f"  Phases per task: 6")
    print(f"  Interval: {POLL_INTERVAL}s")
    sys.stdout.flush()

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        process_queue()
        return

    while True:
        try:
            process_queue()
        except Exception as e:
            print(f"[worker] Error: {e}")
            sys.stdout.flush()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
