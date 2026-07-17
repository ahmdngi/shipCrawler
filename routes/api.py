#!/usr/bin/env python3
"""API routes for Shipcrawler v4 — queue-based, structured streaming, agent-powered."""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, request, Response, stream_with_context, render_template

BASE_DIR = Path(__file__).parent.parent
QUEUE_DIR = BASE_DIR / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
RUNNING_DIR = QUEUE_DIR / "running"
DONE_DIR = QUEUE_DIR / "done"
PROGRESS_DIR = QUEUE_DIR / "progress"

# Import worker_progress for reading the progress log
import sys
sys.path.insert(0, str(BASE_DIR))
import worker_progress as wp


def init_routes(app):

    @app.route("/")
    def index():
        return render_template("index.html")

    # ─── Search: write to queue, return task_id ────────────────────────────────

    @app.route("/api/search", methods=["POST"])
    def start_search():
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        mode = data.get("mode", "person").strip().lower()
        context = data.get("context", "").strip()

        if not name:
            return jsonify({"error": "name is required"}), 400

        task_id = str(uuid.uuid4())[:8]

        task = {
            "task_id": task_id,
            "name": name,
            "mode": mode,
            "context": context,
            "model": data.get("model"),
            "provider": data.get("provider"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        task_path = PENDING_DIR / f"{task_id}.json"
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        with open(task_path, "w") as f:
            json.dump(task, f, indent=2)

        return jsonify({"task_id": task_id, "mode": mode, "status": "queued"})

    # ─── Poll status ─────────────────────────────────────────────────────────

    @app.route("/api/status/<task_id>")
    def get_status(task_id):
        if (DONE_DIR / f"{task_id}.json").exists():
            with open(DONE_DIR / f"{task_id}.json") as f:
                result = json.load(f)
            return jsonify({
                "task_id": task_id,
                "status": result.get("status", "done"),
                "hermes_exit": result.get("hermes_exit"),
                "report_dir": result.get("report_dir"),
                "report_files": result.get("report_files", []),
                "duration_total": result.get("duration_total"),
            })
        elif (RUNNING_DIR / f"{task_id}.json").exists():
            return jsonify({"task_id": task_id, "status": "running"})
        elif (PENDING_DIR / f"{task_id}.json").exists():
            return jsonify({"task_id": task_id, "status": "queued"})
        else:
            return jsonify({"task_id": task_id, "status": "unknown"}), 404

    # ─── SSE Stream: tail the progress log ──────────────────────────────────

    @app.route("/api/stream/<task_id>")
    def stream_progress(task_id):
        def generate():
            """Read progress log line by line, send as SSE events."""
            after_bytes = 0
            last_activity = time.time()
            timeout = 600  # 10 min total timeout
            queued_sent = False

            while True:
                # Check if task is done or errored
                done_file = DONE_DIR / f"{task_id}.json"
                if done_file.exists():
                    # Send any remaining progress
                    events, _ = wp.read_progress(task_id, after_bytes)
                    for evt in events:
                        yield f"event: {evt['event']}\ndata: {json.dumps(evt)}\n\n"
                    # Send done event
                    with open(done_file) as f:
                        done_data = json.load(f)
                    yield f"event: done\ndata: {json.dumps(done_data)}\n\n"
                    break

                # ─── Queued state: task in pending, not picked up yet ─────
                pending_file = PENDING_DIR / f"{task_id}.json"
                progress_log = QUEUE_DIR / "progress" / f"{task_id}.log"

                if pending_file.exists():
                    if not queued_sent:
                        # Count position in queue
                        pending_files = sorted(PENDING_DIR.glob("*.json"))
                        position = next((i for i, p in enumerate(pending_files) if p.stem == task_id), 0)
                        total = len(pending_files)
                        yield f"event: queued\ndata: {json.dumps({'event': 'queued', 'task_id': task_id, 'position': position, 'total': total})}\n\n"
                        queued_sent = True
                    elif queued_sent:
                        # Re-check position every cycle
                        pending_files = sorted(PENDING_DIR.glob("*.json"))
                        position = next((i for i, p in enumerate(pending_files) if p.stem == task_id), 0)
                        total = len(pending_files)
                        yield f"event: queued\ndata: {json.dumps({'event': 'queued', 'task_id': task_id, 'position': position, 'total': total})}\n\n"
                    time.sleep(1)
                    continue

                # ─── Transition: just moved to running ────────────────
                if not queued_sent and progress_log.exists():
                    queued_sent = True

                # ─── Normal progress reading ──────────────────────────
                events, after_bytes = wp.read_progress(task_id, after_bytes)
                for evt in events:
                    yield f"event: {evt['event']}\ndata: {json.dumps(evt)}\n\n"
                    last_activity = time.time()

                # Timeout check
                if time.time() - last_activity > timeout:
                    yield f"event: error\ndata: {json.dumps({'event': 'error', 'error': 'Stream timeout'})}\n\n"
                    break

                # Heartbeat every 15s to keep connection alive
                time.sleep(0.5)

                # Send keepalive comment every 30 idle cycles (~15s)
                # to prevent browser SSE timeout
                if not events:
                    yield ": keepalive\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ─── Get report by name (fallback when done file is gone) ────

    @app.route("/api/report/by-name/<name>")
    def get_report_by_name(name):
        """Find report directory by vessel/person name (deterministic path)."""
        from worker import sanitize_name, clean_for_filename, REPORT_BASE
        safe = sanitize_name(name)
        cleaned = clean_for_filename(safe)
        # Avoid double "-report" if name already ends with it
        dir_name = cleaned + "-report" if not cleaned.endswith("-report") else cleaned
        report_dir = REPORT_BASE / dir_name

        # Fallback: sanitize_name strips diacritics (ä→a), but older reports
        # may have been created with them preserved. Try glob.
        if not report_dir.exists():
            first_word = safe.split()[0].lower() if safe.split() else safe.lower()
            matches = list(REPORT_BASE.glob(f"{first_word}*"))
            # Filter to only dirs ending with -report
            matches = [m for m in matches if m.is_dir() and m.name.endswith("-report")]
            if len(matches) == 1:
                report_dir = matches[0]
            elif len(matches) > 1:
                # Pick the most recently modified (most current run)
                report_dir = max(matches, key=lambda p: p.stat().st_mtime)
            else:
                return jsonify({"error": f"no report found for '{name}'"}), 404

        # Reconstruct minimal done_data
        mode = "vessel"
        done_data = {
            "task_id": name,
            "mode": mode,
            "status": "done",
            "report_dir": str(report_dir),
        }
        # Try to find duration from done files matching this report_dir
        done_dir = QUEUE_DIR / "done"
        if done_dir.exists():
            for df in done_dir.glob("*.json"):
                try:
                    with open(df) as f:
                        dd = json.load(f)
                    if dd.get("report_dir") == str(report_dir):
                        done_data["mode"] = dd.get("mode", mode)
                        done_data["duration_total"] = dd.get("duration_total")
                        done_data["report_files_list"] = dd.get("report_files", [])
                        done_data["stats"] = dd.get("stats")
                        done_data["model"] = dd.get("model")
                        done_data["provider"] = dd.get("provider")
                        break
                except (json.JSONDecodeError, OSError):
                    continue
        return _build_report_response(done_data, report_dir)

    def _build_report_response(done_data, report_dir):
        """Shared logic: read report dir and return structured JSON."""
        mode = done_data.get("mode", "vessel")

        phase_files = sorted(report_dir.glob("phase-*.md"))
        phase_data = {}
        for pf in phase_files:
            phase_data[pf.stem] = pf.read_text()

        raw_markdown = {}
        for md_file in sorted(report_dir.glob("*.md")):
            raw_markdown[md_file.name] = md_file.read_text()

        # Also send clean report files individually (not just concatenated)
        report_files = {}
        for clean_name in ["analyst-report.md", "red-team-playbook.md", "indicators-and-detection.md"]:
            clean_path = report_dir / clean_name
            if clean_path.exists():
                report_files[clean_name] = clean_path.read_text()

        content_text = "\n\n---\n\n".join(raw_markdown.values())

        try:
            from renderer import render as render_report
            structured = render_report(report_dir, mode)
        except Exception as e:
            structured = {"error": str(e)}

        response = {
            "task_id": done_data.get("task_id", "unknown"),
            "mode": mode,
            "status": done_data.get("status", "done"),
            "content": content_text,
            "report_dir": str(report_dir),
            "duration_total": done_data.get("duration_total"),
            "phase_files": list(phase_data.keys()),
            "phase_contents": phase_data,
            "report_files": report_files,
            "stats": done_data.get("stats"),
            "model": done_data.get("model"),
            "provider": done_data.get("provider"),
        }
        if "error" not in structured:
            response.update(structured)
        return jsonify(response)

    # ─── Get report data ──────────────────────────────────────

    @app.route("/api/report/<task_id>")
    def get_report(task_id):
        done_path = DONE_DIR / f"{task_id}.json"
        if not done_path.exists():
            return jsonify({"error": "task not found or not yet complete"}), 404

        with open(done_path) as f:
            done_data = json.load(f)

        report_dir = done_data.get("report_dir")
        if not report_dir:
            return jsonify({"error": "report not found"}), 404

        report_dir = Path(report_dir)
        return _build_report_response(done_data, report_dir)

    # ─── History: list all report directories ──────────────────

    @app.route("/api/history")
    def get_history():
        """List all available report directories with metadata."""
        from worker import REPORT_BASE
        # Build a lookup: report_dir -> mode from done files
        done_mode = {}
        done_dir = QUEUE_DIR / "done"
        if done_dir.exists():
            for df in done_dir.glob("*.json"):
                try:
                    with open(df) as f:
                        dd = json.load(f)
                    rd = dd.get("report_dir")
                    if rd:
                        done_mode[rd] = dd.get("mode", "vessel")
                except (json.JSONDecodeError, OSError):
                    continue
        reports = []
        for d in sorted(REPORT_BASE.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not d.is_dir() or not d.name.endswith("-report"):
                continue
            # Derive name from directory name: "rina--imo-9152820-report" → "RINA IMO 9152820"
            raw = d.name.replace("-report", "")
            # Convert back to a readable name (best effort)
            name = raw.replace("-", " ").strip()
            # Strip trailing date if present (YYYY-MM-DD from new dated format)
            name = re.sub(r'\s*\d{4}\s*\d{2}\s*\d{2}\s*$', '', name).strip()
            # Handle 'mmsi' prefix cleanup
            reports.append({
                "task_id": d.name,
                "name": name.title(),
                "mode": done_mode.get(str(d), "vessel"),
                "timestamp": int(os.path.getmtime(d) * 1000),
            })
        return jsonify(reports)

    @app.route("/api/report/<task_id>", methods=["DELETE"])
    def delete_report(task_id):
        """Delete a report by task_id (directory name)."""
        from worker import REPORT_BASE

        report_dir = REPORT_BASE / task_id
        if not report_dir.exists():
            # Try to find the done file matching this dir
            found = False
            for df in DONE_DIR.glob("*.json"):
                try:
                    with open(df) as f:
                        dd = json.load(f)
                    if dd.get("report_dir", "").endswith(task_id):
                        df.unlink(missing_ok=True)
                        found = True
                        break
                except (json.JSONDecodeError, OSError):
                    continue
            if not found:
                return jsonify({"error": f"report '{task_id}' not found"}), 404

        # Delete report directory
        import shutil
        if report_dir.exists():
            shutil.rmtree(report_dir)

        # Delete done file and progress log
        for df in DONE_DIR.glob("*.json"):
            try:
                with open(df) as f:
                    dd = json.load(f)
                if dd.get("report_dir", "").endswith(task_id):
                    df.unlink(missing_ok=True)
                    break
            except (json.JSONDecodeError, OSError):
                continue

        # Delete progress log if exists
        log_file = PROGRESS_DIR / f"{task_id}.log"
        log_file.unlink(missing_ok=True)

        return jsonify({"status": "deleted", "task_id": task_id})

    @app.route("/api/health")
    def health():
        pending = len(list(PENDING_DIR.glob("*.json"))) if PENDING_DIR.exists() else 0
        running = len(list(RUNNING_DIR.glob("*.json"))) if RUNNING_DIR.exists() else 0
        done = len(list(DONE_DIR.glob("*.json"))) if DONE_DIR.exists() else 0
        return jsonify({
            "status": "ok",
            "queue": {"pending": pending, "running": running, "done": done},
        })
