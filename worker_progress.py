#!/usr/bin/env python3
"""Progress log writer for Shipcrawler v4 real-time streaming.

Writes JSON Lines to queue/progress/<task_id>.log.
Single-writer (worker.py is the sole writer) — appends with fsync for durability.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROGRESS_DIR = BASE_DIR / "queue" / "progress"


def write_event(task_id: str, event_type: str, **fields):
    """Append a JSON line to the progress log.

    event_type: phase_start, phase_output, phase_complete, phase_error,
                report_complete, error
    Additional fields are merged into the JSON object.
    """
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = PROGRESS_DIR / f"{task_id}.log"

    record = {
        "event": event_type,
        "ts": time.time(),
        "iso": datetime.now(timezone.utc).isoformat(),
        **fields,
    }

    # Single-writer: direct append + fsync
    with open(log_path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def phase_start(task_id: str, phase: int, name: str):
    write_event(task_id, "phase_start", phase=phase, name=name)


def phase_output(task_id: str, phase: int, line: str):
    write_event(task_id, "phase_output", phase=phase, line=line)


def structured_output(task_id: str, phase: int, event_subtype: str, icon: str, message: str):
    """Write a clean, structured event (status, data_point, finding, etc.)
    instead of raw Hermes output."""
    write_event(
        task_id, "structured_output",
        phase=phase,
        structured_type=event_subtype,
        icon=icon,
        message=message[:500],
    )


def phase_complete(task_id: str, phase: int, name: str, duration: float, summary: str = "", findings: dict = None):
    write_event(
        task_id, "phase_complete",
        phase=phase, name=name, duration=round(duration, 1),
        summary=summary, findings=findings or {},
    )


def phase_error(task_id: str, phase: int, name: str, error: str):
    write_event(task_id, "phase_error", phase=phase, name=name, error=error)


def report_complete(task_id: str, report_dir: str, duration_total: float, files: list = None, stats: dict = None, model: str = None, provider: str = None):
    write_event(
        task_id, "report_complete",
        report_dir=report_dir, duration_total=round(duration_total, 1),
        files=files or [], stats=stats or {},
        model=model, provider=provider,
    )


def task_error(task_id: str, error: str):
    write_event(task_id, "error", error=error)


def read_progress(task_id: str, after_bytes: int = 0):
    """Read new lines from the progress log since after_bytes."""
    log_path = PROGRESS_DIR / f"{task_id}.log"
    if not log_path.exists():
        return [], 0

    with open(log_path) as f:
        f.seek(after_bytes)
        lines = f.readlines()

    events = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"event": "parse_error", "raw": line})

    new_size = log_path.stat().st_size
    return events, new_size
