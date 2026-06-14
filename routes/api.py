#!/usr/bin/env python3
"""API routes for Shipcrawler v4 — queue-based, Hermes-powered research."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, request

from renderer import render as render_report

BASE_DIR = Path(__file__).parent.parent
QUEUE_DIR = BASE_DIR / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
RUNNING_DIR = QUEUE_DIR / "running"
DONE_DIR = QUEUE_DIR / "done"


def init_routes(app):

    @app.route("/")
    def index():
        from flask import render_template
        return render_template("index.html")

    # ─── Search: write to queue, return task_id ────────────────────────────────

    @app.route("/api/search", methods=["POST"])
    def start_search():
        """Submit a search task. Hermes worker picks it up from the queue."""
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

        # Write to pending queue
        task_path = PENDING_DIR / f"{task_id}.json"
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        with open(task_path, "w") as f:
            json.dump(task, f, indent=2)

        return jsonify({"task_id": task_id, "mode": mode, "status": "queued"})

    # ─── Poll status ═ check queue dirs ───────────────────────────────────────

    @app.route("/api/status/<task_id>")
    def get_status(task_id):
        """Check if a task is pending, running, or done."""
        if (DONE_DIR / f"{task_id}.json").exists():
            with open(DONE_DIR / f"{task_id}.json") as f:
                result = json.load(f)
            return jsonify({
                "task_id": task_id,
                "status": result.get("status", "done"),
                "hermes_exit": result.get("hermes_exit"),
                "report_dir": result.get("report_dir"),
                "report_files": result.get("report_files", []),
            })
        elif (RUNNING_DIR / f"{task_id}.json").exists():
            return jsonify({"task_id": task_id, "status": "running"})
        elif (PENDING_DIR / f"{task_id}.json").exists():
            return jsonify({"task_id": task_id, "status": "queued"})
        else:
            return jsonify({"task_id": task_id, "status": "unknown"}), 404

    # ─── Get report data ──────────────────────────────────────────────────────

    @app.route("/api/report/<task_id>")
    def get_report(task_id):
        """Read the Hermes output and return structured card data (via renderer) + raw markdown files."""
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

        # Collect all markdown files as raw content for fallback
        raw_markdown = {}
        for md_file in sorted(report_dir.glob("*.md")):
            raw_markdown[md_file.name] = md_file.read_text()
        content_text = "\n\n---\n\n".join(raw_markdown.values())

        # Use the shipcrawler renderer to build structured card data
        from renderer import render as render_report
        structured = render_report(report_dir, mode)

        response = {
            "task_id": task_id,
            "mode": mode,
            "status": done_data.get("status"),
            "content": content_text,
            "report_dir": str(report_dir),
        }
        # Merge structured fields into the response
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
