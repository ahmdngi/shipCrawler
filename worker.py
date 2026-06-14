#!/usr/bin/env python3
"""
Shipcrawler v4 Worker — watches the task queue, spawns Hermes to do the research.

Flow:
  queue/pending/<task_id>.json  →  worker picks it up
                              →  queue/running/<task_id>.json
                              →  hermes --skills shipcrawler writes structured report files
                              →  queue/done/<task_id>.json  (with path to report dir)
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).parent
QUEUE_DIR = BASE_DIR / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
RUNNING_DIR = QUEUE_DIR / "running"
DONE_DIR = QUEUE_DIR / "done"
REPORT_BASE = Path("/root")

HERMES_BIN = "hermes"
POLL_INTERVAL = 5  # seconds between queue checks


def sanitize_name(name):
    """Strip MMSI:/IMO: prefixes and special chars for filesystem safety."""
    name = re.sub(r'^(MMSI|IMO)\s*[:]?\s*', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'[^\w\s-]', '', name).strip()
    return name or "vessel"


def clean_for_filename(name):
    """Turn a name into a safe lowercase-filename."""
    return name.lower().replace(" ", "-")


def generate_prompt(task):
    """Build the Hermes prompt."""
    name = task.get("name", "")
    mode = task.get("mode", "vessel")
    context = task.get("context", "")
    context_clause = f" with context: {context}" if context else ""

    if mode == "person":
        return (
            f'Use shipcrawler to research this person "{name}"{context_clause}. '
            f"Search ORCID, Google Scholar, DBLP, Bing, GitHub, and institutional pages. "
            f"Give me their identity, employment, education, research impact (h-index, citations), "
            f"publications, and social media presence. "
            f"Be thorough but concise."
        )
    else:
        return (
            f'Use shipcrawler to research this vessel "{name}"{context_clause}. '
            f"Search VesselFinder, AIS sources, and Shodan. "
            f"Give me the vessel identity (name, MMSI, IMO, flag, type, dimensions), "
            f"current status (position, speed, course, destination, navigation status), "
            f"port calls, and any Shodan findings. "
            f"Be thorough but concise."
        )


def run_hermes(task):
    """Run Hermes with the task's prompt, save stdout as structured report files."""
    prompt = generate_prompt(task)
    task_id = task["task_id"]

    # Create the report directory
    name = task.get("name", "")
    safe_name = sanitize_name(name)
    dir_name = clean_for_filename(safe_name) + "-report"
    report_dir = REPORT_BASE / dir_name
    report_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        HERMES_BIN, "chat",
        "-q", prompt,
        "--skills", "shipcrawler",
        "-t", "web,terminal",
        "-Q",  # quiet mode
        "--yolo",  # auto-approve
        "--max-turns", "30",  # limit iterations
        "--source", "tool",
    ]

    print(f"[worker {task_id}] Spawning Hermes...  report_dir={report_dir}")
    sys.stdout.flush()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,  # 3 min max
        )
        output = result.stdout
        hermes_stderr = result.stderr
    except subprocess.TimeoutExpired:
        output = "TIMEOUT: Hermes took longer than 2 minutes"
        hermes_stderr = ""
        result = subprocess.CompletedProcess(cmd, -1, output, "")

    # Save Hermes stdout as analyst-report.md in the report directory
    if output and output.strip():
        report_file = report_dir / "analyst-report.md"
        report_file.write_text(output[:50000])
    else:
        # Fallback: write error to a file so the renderer has something
        report_file = report_dir / "analyst-report.md"
        report_file.write_text(f"# {name} — OSINT Report\n\nHermes returned no output (exit={result.returncode}).\n\n{hermes_stderr}\n")

    # List report files
    md_files = sorted(report_dir.glob("*.md"))
    print(f"[worker {task_id}] Hermes exit={result.returncode}, written={report_file.name}, files={[f.name for f in md_files]}")

    status = "done" if result.returncode == 0 else ("done" if md_files else "error")

    return {
        "task_id": task_id,
        "mode": task.get("mode", "vessel"),
        "status": status,
        "report_dir": str(report_dir),
        "report_files": [str(f) for f in md_files],
        "hermes_exit": result.returncode,
    }


def process_queue():
    """Check pending queue, process one task."""
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

    # Run Hermes
    result = run_hermes(task)

    # Write done
    done_path = DONE_DIR / task_path.name
    with open(done_path, "w") as f:
        json.dump(result, f, indent=2)

    # Remove from running
    running_path.unlink(missing_ok=True)

    print(f"[worker] Task {task['task_id']} → {result['status']}")
    if result.get("report_files"):
        print(f"[worker]   Report: {result['report_dir']} ({len(result['report_files'])} files): {[Path(f).name for f in result['report_files']]}")
    sys.stdout.flush()

    return True


def main():
    print(f"Shipcrawler v4 Worker — watching {PENDING_DIR}")
    print(f"  Hermes: {HERMES_BIN}")
    print(f"  Interval: {POLL_INTERVAL}s")
    sys.stdout.flush()

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        process_queue()
        return

    # Daemon mode
    while True:
        try:
            process_queue()
        except Exception as e:
            print(f"[worker] Error: {e}")
            sys.stdout.flush()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
