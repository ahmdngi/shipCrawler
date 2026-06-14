#!/usr/bin/env python3
"""
Shipcrawler v4 Phase Worker — runs sequential Hermes agent phases,
emits progress events to the progress log for real-time SSE streaming.

Flow:
  queue/pending/<task_id>.json → worker processes phases one by one
  Each phase: run hermes chat -q → write progress to queue/progress/<task_id>.log
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

BASE_DIR = Path(__file__).parent
QUEUE_DIR = BASE_DIR / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
RUNNING_DIR = QUEUE_DIR / "running"
DONE_DIR = QUEUE_DIR / "done"
REPORT_BASE = Path("/root/hermes-vault/osint-reports")

HERMES_BIN = "hermes"
POLL_INTERVAL = 5


def sanitize_name(name):
    name = re.sub(r'^(MMSI|IMO)\s*[:]?\s*', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'[^\w\s-]', '', name).strip()
    return name or "target"


def clean_for_filename(name):
    return name.lower().replace(" ", "-")


def build_shipcrawler_prompt(name: str, mode: str, context: str) -> str:
    """Build a single comprehensive Hermes prompt using the full shipcrawler skill."""
    base_context = f"Research context: {context}" if context else ""

    if mode == "person":
        return (
            f"Using the shipcrawler OSINT framework, research the person \"{name}\".\n\n"
            f"{base_context}\n\n"
            f"Execute ALL phases of the people OSINT methodology:\n"
            f"1. Identity & Academic Sources — search ORCID, Google Scholar, DBLP, LinkedIn, GitHub\n"
            f"2. Research Impact Analysis — publications, citations, h-index, co-authors\n"
            f"3. Social & Digital Footprint — social media, crt.sh, breach data\n"
            f"4. Professional Network & Timeline — career history, education, geography\n"
            f"5. Targeting Scenarios — 2-3 attack vectors with difficulty, cost, detection probability\n\n"
            f"Generate a COMPREHENSIVE report with the following files saved to {REPORT_BASE}/<name>-report/:\n"
            f"- analyst-report.md (full narrative with identity, career, research, digital footprint, confidence)\n"
            f"- red-team-playbook.md (2-3 attack vectors with equipment, steps, detection points)\n"
            f"- indicators-and-detection.md (Elastic rules, Zeek scripts, runbook)\n\n"
            f"Be thorough — use multiple sources, cross-reference, and provide confidence levels per finding."
        )
    else:
        return (
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
            f"Generate a COMPREHENSIVE 3-file report:\n"
            f"1. analyst-report.md — full narrative with vessel identity, current status, port calls, "
            f"Shodan findings, vulnerability assessment, threat intel, operational pattern analysis, "
            f"confidence assessment per category (HIGH/MEDIUM/LOW/SPECULATIVE)\n"
            f"2. red-team-playbook.md — 2-3 attack vectors with name, difficulty, cost, detection prob, "
            f"equipment list, numbered execution steps, detection points table\n"
            f"3. indicators-and-detection.md — indicator table (ID, type, phase, priority, description), "
            f"Elastic SIEM rules, Zeek scripts, M-SOC runbook\n\n"
            f"Be thorough — use multiple independent AIS sources, cross-reference Equasis data, "
            f"and report zero findings explicitly (it's a finding). Provide confidence levels."
        )


def worker_phase_output(task_id, phase, line, line_type="output"):
    """Write a line of phase output with type classification."""
    wp.write_event(task_id, "phase_output", phase=phase, line=line[:500], line_type=line_type)


def run_shipcrawler(task_id: str, name: str, mode: str, context: str) -> dict:
    """Run a single comprehensive Hermes shipcrawler session with real-time streaming."""
    prompt = build_shipcrawler_prompt(name, mode, context)

    safe_name = sanitize_name(name)
    dir_name = clean_for_filename(safe_name) + "-report"
    report_dir = REPORT_BASE / dir_name
    report_dir.mkdir(parents=True, exist_ok=True)

    start_total = time.time()
    output_lines = []
    current_tool = ""

    wp.phase_start(task_id, 0, "AI Agent Researching")
    print(f"[worker {task_id}] Starting shipcrawler research on \"{name}\" ({mode})...")
    sys.stdout.flush()

    cmd = [
        HERMES_BIN, "chat",
        "-q", prompt,
        "--skills", "shipcrawler",
        "-t", "web,terminal",
        "--yolo",
        "--max-turns", "60",
        "--source", "tool",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "HOME": os.path.expanduser("~")},
        )

        # Read stdout line by line in real-time
        for line in iter(proc.stdout.readline, ""):
            stripped = line.rstrip("\n\r")
            output_lines.append(line)

            if not stripped:
                continue

            # Classify the line
            if "● [Tool:" in stripped:
                # Tool call start — extract tool name
                tool_match = re.search(r"● \[Tool:\s*(\w+)\]", stripped)
                current_tool = tool_match.group(1).lower() if tool_match else "agent"
                worker_phase_output(task_id, 0, stripped, "tool_start")
            elif "● [Error:" in stripped:
                worker_phase_output(task_id, 0, stripped, "tool_error")
            elif stripped.startswith("  ") and current_tool:
                # Indented line after a tool call — detail line
                detail = stripped.strip()
                if detail and not detail.startswith("─") and not detail.startswith("│"):
                    worker_phase_output(task_id, 0, detail[:300], "tool_detail")
            elif stripped.startswith("┌─") or stripped.startswith("│") or stripped.startswith("└─") or stripped.startswith("─"):
                # Thinking block markers — skip box-drawing chars
                text = stripped.replace("│", "").replace("┌─", "").replace("└─", "").replace("─", "").strip()
                if text:
                    worker_phase_output(task_id, 0, text[:300], "thinking")
            else:
                # Regular output
                worker_phase_output(task_id, 0, stripped[:300], "output")

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

    # Write the Hermes output as the analyst report
    analyst_path = report_dir / "analyst-report.md"
    if output.strip():
        analyst_path.write_text(output[:100000])
    else:
        analyst_path.write_text(f"# {name} — OSINT Report\n\nAI agent returned no output.\n\n{stderr}")

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
    if analyst_path not in md_files:
        md_files.insert(0, analyst_path)

    total_duration = time.time() - start_total
    wp.report_complete(task_id, str(report_dir), total_duration, [f.name for f in md_files])

    print(f"[worker {task_id}] REPORT COMPLETE ({total_duration:.1f}s total)")
    print(f"[worker {task_id}]   Files: {[f.name for f in md_files]}")
    sys.stdout.flush()

    return {
        "task_id": task_id,
        "mode": mode,
        "status": "done" if exit_code == 0 or output.strip() else "error",
        "report_dir": str(report_dir),
        "report_files": [str(f) for f in md_files],
        "duration_total": round(total_duration, 1),
        "hermes_exit": exit_code,
    }


def process_queue():
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

    result = run_shipcrawler(task["task_id"], task.get("name", ""), task.get("mode", "vessel"), task.get("context", ""))

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
