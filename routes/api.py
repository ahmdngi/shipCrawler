#!/usr/bin/env python3
"""API routes for Shipcrawler v4 — queue-based, phase-streaming, Hermes-powered."""

import json
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

                # Read new progress events
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

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ─── Get report data ──────────────────────────────────────────────────────

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
        mode = done_data.get("mode", "vessel")

        # Read all phase files
        phase_files = sorted(report_dir.glob("phase-*.md"))
        phase_outputs = {}
        for pf in phase_files:
            phase_outputs[pf.stem] = pf.read_text()

        # Read the full report
        raw_markdown = {}
        for md_file in sorted(report_dir.glob("*.md")):
            raw_markdown[md_file.name] = md_file.read_text()

        content_text = "\n\n---\n\n".join(raw_markdown.values())

        # Use the shipcrawler renderer to build structured card data
        try:
            from renderer import render as render_report
            structured = render_report(report_dir, mode)
        except Exception as e:
            structured = {"error": str(e)}

        response = {
            "task_id": task_id,
            "mode": mode,
            "status": done_data.get("status"),
            "content": content_text,
            "report_dir": str(report_dir),
            "duration_total": done_data.get("duration_total"),
            "phase_files": list(phase_outputs.keys()),
        }
        if "error" not in structured:
            response.update(structured)
        return jsonify(response)

    # ─── Health ───────────────────────────────────────────────────────────────

    @app.route("/api/health")
    def health():
        pending = len(list(PENDING_DIR.glob("*.json"))) if PENDING_DIR.exists() else 0
        running = len(list(RUNNING_DIR.glob("*.json"))) if RUNNING_DIR.exists() else 0
        done = len(list(DONE_DIR.glob("*.json"))) if DONE_DIR.exists() else 0
        return jsonify({
            "status": "ok",
            "queue": {"pending": pending, "running": running, "done": done},
        })
