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
REPORT_BASE = Path("/root")

HERMES_BIN = "hermes"
POLL_INTERVAL = 5

PHASES = [
    (0, "Equasis — Vessel Identity", "vessel"),
    (1, "Target Identification", "vessel"),
    (2, "Attack Surface Discovery", "vessel"),
    (3, "Vulnerability Assessment", "vessel"),
    (4, "Threat Intelligence", "vessel"),
    (5, "Report Generation", "vessel"),
]

PERSON_PHASES = [
    (0, "Identity & Academic Sources", "person"),
    (1, "Research Impact Analysis", "person"),
    (2, "Social & Digital Footprint", "person"),
    (3, "Professional Network & Timeline", "person"),
    (4, "Targeting Scenarios", "person"),
    (5, "Report Generation", "person"),
]


def sanitize_name(name):
    name = re.sub(r'^(MMSI|IMO)\s*[:]?\s*', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'[^\w\s-]', '', name).strip()
    return name or "target"


def clean_for_filename(name):
    return name.lower().replace(" ", "-")


def build_phase_prompt(phase_num: int, phase_name: str, name: str, mode: str,
                       context: str, previous_findings: str = "") -> str:
    """Build a self-contained Hermes prompt for a specific shipcrawler phase."""

    base_context = f"Research context: {context}" if context else ""

    vessel_prompts = {
        0: (
            f"Using the shipcrawler OSINT framework, execute Phase 0 (Vessel Identity from Equasis) "
            f"on the vessel \"{name}\".\n\n"
            f"1. Use equasis-cli to look up the vessel's IMO number, name, flag, call sign, MMSI, "
            f"GT, DWT, vessel type, year built, status, management companies, and classification societies.\n"
            f"2. Present the findings in a clear structured format with field labels.\n"
            f"3. If Equasis is rate-limited, wait 30-60s and retry.\n"
            f"4. If you cannot determine the IMO, search for it first.\n\n"
            f"{base_context}\n\n"
            f"Focus only on vessel identity and registry data for this phase."
        ),
        1: (
            f"Using the shipcrawler OSINT framework, execute Phase 1 (Target Identification) "
            f"on the vessel \"{name}\".\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Search AIS sources (VesselFinder, MarineTraffic) for the vessel's current position, "
            f"speed, course, destination, navigation status, and ETA.\n"
            f"2. Find recent port calls (last 10-15) with dates, ports, and durations.\n"
            f"3. Use CloakBrowser for anti-bot sites (VesselFinder, MarineTraffic).\n"
            f"4. Present position data and port call history in a structured format.\n\n"
            f"Focus on real-time tracking and recent activity."
        ),
        2: (
            f"Using the shipcrawler OSINT framework, execute Phase 2 (Attack Surface Discovery) "
            f"on the vessel \"{name}\".\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Use Shodan to search for the vessel name, MMSI, and IMO.\n"
            f"2. Search for exposed maritime systems: Signal K servers (port 3000), "
            f"VSAT terminals (Cobham SAILOR, KVH), NMEA-over-IP gateways, ECDIS, AIS receivers.\n"
            f"3. Use Shodan host intelligence on any discovered IPs.\n"
            f"4. Document all open ports, services, versions, and organizations.\n"
            f"5. Even if zero results are found, report this explicitly (it's a finding).\n\n"
            f"Focus on internet-facing systems and exposed maritime protocols."
        ),
        3: (
            f"Using the shipcrawler OSINT framework, execute Phase 3 (Vulnerability Assessment) "
            f"on the vessel \"{name}\".\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Compare discovered services against known CVEs for maritime equipment.\n"
            f"2. Use Shodan exploit search for maritime-related exploits.\n"
            f"3. Check for default credentials on common maritime equipment.\n"
            f"4. Assess VSAT terminal security and Signal K server exposure.\n"
            f"5. Document risk level per finding (CRITICAL, HIGH, MODERATE, LOW).\n\n"
            f"Focus on vulnerability identification and risk classification."
        ),
        4: (
            f"Using the shipcrawler OSINT framework, execute Phase 4 (Threat Intelligence) "
            f"on the vessel \"{name}\".\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Search for maritime cyber incident reports related to this vessel, its operator, "
            f"or its vessel type.\n"
            f"2. Check for news articles, breach mentions, and dark web references.\n"
            f"3. Cross-reference findings against known threat actor TTPs for maritime targets.\n"
            f"4. Generate a risk assessment with geopolitical context if relevant.\n"
            f"5. Recommend detection and monitoring strategies.\n\n"
            f"Focus on threat context and risk positioning."
        ),
        5: (
            f"Using the shipcrawler OSINT framework, execute Phase 5 (Analysis & Reporting) "
            f"for the vessel \"{name}\".\n\n"
            f"All previous phase findings consolidated:\n{previous_findings}\n\n"
            f"Generate a COMPREHENSIVE FINAL REPORT with:\n\n"
            f"1. **Vessel Identity**: name, IMO, MMSI, flag, type, dimensions, year built\n"
            f"2. **Current Status**: position, speed, course, destination, navigation status\n"
            f"3. **Port Calls**: recent port call history with dates\n"
            f"4. **Shodan Attack Surface**: open ports, services, exposed systems\n"
            f"5. **Vulnerability Assessment**: findings, risk levels, CVEs\n"
            f"6. **Threat Intelligence**: risk assessment, geopolitical context\n"
            f"7. **Operational Pattern Analysis**: home zone, route patterns\n"
            f"8. **Confidence Assessment**: per-category (HIGH/MEDIUM/LOW)\n"
            f"9. **Red Team Playbook**: 2-3 attack vectors designed for this vessel\n"
            f"10. **Detection Rules**: Elastic SIEM rules, Zeek scripts, M-SOC runbook\n\n"
            f"Format the report with clear markdown headings and structured data where possible. "
            f"Be thorough and actionable."
        ),
    }

    person_prompts = {
        0: (
            f"Using the shipcrawler OSINT framework, research the person \"{name}\". "
            f"Execute the People OSINT methodology - Identity phase.\n\n"
            f"{base_context}\n\n"
            f"1. Search ORCID, Google Scholar, DBLP, institutional pages, LinkedIn, and GitHub.\n"
            f"2. Find their full name, aliases, current position, employer, location, and education.\n"
            f"3. Identify their ORCID ID, email addresses, and professional handles.\n"
            f"4. Present findings with confidence levels per data point.\n\n"
            f"Focus on basic identity and academic/professional affiliations."
        ),
        1: (
            f"Using the shipcrawler OSINT framework, research the person \"{name}\". "
            f"Execute Research Impact Analysis phase.\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Query ORCID works endpoint for publications with DOIs.\n"
            f"2. Query DBLP for computer science publication record.\n"
            f"3. Find Google Scholar profile with h-index, i10-index, total citations.\n"
            f"4. Extract top-5 most cited publications.\n"
            f"5. Identify co-authors for collaboration network.\n\n"
            f"Focus on research metrics and publication record."
        ),
        2: (
            f"Using the shipcrawler OSINT framework, research the person \"{name}\". "
            f"Execute Social & Digital Footprint phase.\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Search for social media profiles (Twitter/X, LinkedIn, GitHub, ResearchGate).\n"
            f"2. Check crt.sh for domains associated with their name.\n"
            f"3. Search for news articles, conference talks, and public appearances.\n"
            f"4. Check breach databases (Have I Been Pwned) for associated emails.\n"
            f"5. Document all digital footprint findings.\n\n"
            f"Focus on online presence and exposure."
        ),
        3: (
            f"Using the shipcrawler OSINT framework, research the person \"{name}\". "
            f"Execute Professional Network & Timeline phase.\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Map their career timeline: current positions, past positions, education.\n"
            f"2. Identify geographic mobility across their career.\n"
            f"3. Find collaboration network from co-authorship patterns.\n"
            f"4. Document key career transitions and achievements.\n\n"
            f"Focus on professional trajectory and network analysis."
        ),
        4: (
            f"Using the shipcrawler OSINT framework, research the person \"{name}\". "
            f"Execute Targeting Scenarios phase.\n\n"
            f"Previous phase findings:\n{previous_findings}\n\n"
            f"1. Design 2-3 attack vectors based on their digital footprint and profile.\n"
            f"2. Each vector: name, difficulty, cost, detection probability, equipment, steps.\n"
            f"3. Calculate exposure score (0-100) based on digital footprint.\n"
            f"4. Generate risk tier (LOW/MEDIUM/HIGH) with justification.\n"
            f"5. Provide recommendations to reduce exposure.\n\n"
            f"Focus on red-team attack surface and risk analysis."
        ),
        5: (
            f"Using the shipcrawler OSINT framework, generate the final report for \"{name}\".\n\n"
            f"All previous phase findings:\n{previous_findings}\n\n"
            f"Create a comprehensive people OSINT report with:\n"
            f"1. Person identity and aliases summary\n"
            f"2. Professional history with timeline\n"
            f"3. Research impact (publications, citations, h-index, co-authors)\n"
            f"4. Social media and digital footprint\n"
            f"5. Affiliation timeline with geographic mobility\n"
            f"6. Confidence assessment per category\n"
            f"7. Targeting scenarios with vectors, difficulty, and detection points\n"
            f"8. Exposure analysis with score and recommendations\n\n"
            f"Format with clear markdown headings and structured data."
        ),
    }

    prompts = person_prompts if mode == "person" else vessel_prompts
    return prompts.get(phase_num, f"Research {name} using shipcrawler OSINT framework.")


def run_hermes_phase(phase_num: int, phase_name: str, name: str, mode: str,
                     context: str, previous_findings: str) -> str:
    """Run a single Hermes agent phase, returning stdout."""
    prompt = build_phase_prompt(phase_num, phase_name, name, mode, context, previous_findings)

    cmd = [
        HERMES_BIN, "chat",
        "-q", prompt,
        "--skills", "shipcrawler",
        "-t", "web,terminal",
        "-Q",
        "--yolo",
        "--max-turns", "40",
        "--source", "tool",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min per phase max
            env={**os.environ, "HOME": os.path.expanduser("~")},
        )
        output = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode != 0 and not output:
            return f"[ERROR] Hermes exited {result.returncode}: {stderr[:500]}"

        return output

    except subprocess.TimeoutExpired:
        return "[ERROR] Phase timed out after 5 minutes"
    except Exception as e:
        return f"[ERROR] {e}"


def extract_summary(output: str, phase_num: int, mode: str) -> str:
    """Extract a brief summary from phase output."""
    if not output or output.startswith("[ERROR]"):
        return output or "No output"

    lines = output.strip().split("\n")
    # Take first 2 non-empty lines as summary
    meaningful = [l.strip() for l in lines if l.strip() and not l.startswith("#") and not l.startswith("```")]
    summary_lines = meaningful[:3]
    summary = " | ".join(summary_lines).strip()
    return summary[:200] if summary else f"Phase {phase_num} completed"


def run_phase(task_id: str, phase_num: int, phase_name: str, name: str,
              mode: str, context: str, previous_findings: str = "") -> tuple:
    """Run a phase and write progress events."""
    wp.phase_start(task_id, phase_num, phase_name)
    print(f"[worker {task_id}] Phase {phase_num}: {phase_name}...")
    sys.stdout.flush()

    start = time.time()

    try:
        output = run_hermes_phase(phase_num, phase_name, name, mode, context, previous_findings)

        # Write output lines as progress
        for line in output.split("\n"):
            if line.strip():
                wp.phase_output(task_id, phase_num, line.strip()[:500])

        if output.startswith("[ERROR]"):
            wp.phase_error(task_id, phase_num, phase_name, output)
            print(f"[worker {task_id}] Phase {phase_num} ERROR: {output[:100]}")
            return output, True  # return output, is_error=True

        duration = time.time() - start
        summary = extract_summary(output, phase_num, mode)
        wp.phase_complete(task_id, phase_num, phase_name, duration, summary)
        print(f"[worker {task_id}] Phase {phase_num} done ({duration:.1f}s)")
        sys.stdout.flush()
        return output, False

    except Exception as e:
        duration = time.time() - start
        wp.phase_error(task_id, phase_num, phase_name, str(e))
        print(f"[worker {task_id}] Phase {phase_num} EXCEPTION: {e}")
        return str(e), True


def process_task(task):
    """Process a single task through all phases."""
    task_id = task["task_id"]
    name = task.get("name", "")
    mode = task.get("mode", "vessel")
    context = task.get("context", "")

    safe_name = sanitize_name(name)
    dir_name = clean_for_filename(safe_name) + "-report"
    report_dir = REPORT_BASE / dir_name
    report_dir.mkdir(parents=True, exist_ok=True)

    start_total = time.time()

    phases = PERSON_PHASES if mode == "person" else PHASES
    all_outputs = []
    previous_findings = ""

    for phase_num, phase_name, _ in phases:
        output, is_error = run_phase(
            task_id, phase_num, phase_name, name, mode, context, previous_findings
        )

        # Save phase output
        phase_file = report_dir / f"phase-{phase_num}-{clean_for_filename(phase_name)}.md"
        phase_file.write_text(output[:50000])

        # Accumulate for next phase context (use last 3000 chars to stay concise)
        all_outputs.append(f"## Phase {phase_num}: {phase_name}\n\n{output[:5000]}")
        # Keep previous findings as the concatenation of all phase outputs
        # but limit total context to avoid max-token issues
        combined = "\n\n".join(all_outputs)
        previous_findings = combined[-8000:] if len(combined) > 8000 else combined

    # Compile final report
    wp.phase_start(task_id, 99, "Compiling Final Report")

    full_report = "\n\n---\n\n".join(all_outputs)
    report_file = report_dir / "analyst-report.md"
    report_file.write_text(full_report[:100000])

    total_duration = time.time() - start_total

    md_files = sorted(report_dir.glob("*.md"))
    wp.report_complete(task_id, str(report_dir), total_duration, [f.name for f in md_files])

    print(f"[worker {task_id}] ALL PHASES COMPLETE ({total_duration:.1f}s total)")
    sys.stdout.flush()

    return {
        "task_id": task_id,
        "mode": mode,
        "status": "done",
        "report_dir": str(report_dir),
        "report_files": [str(f) for f in md_files],
        "duration_total": round(total_duration, 1),
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

    result = process_task(task)

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
