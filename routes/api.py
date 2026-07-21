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
            "profile": data.get("profile"),
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
                    dd_rd = dd.get("report_dir", "")
                    # Match exact or endswith (dir name may vary slightly)
                    if dd_rd == str(report_dir) or dd_rd.endswith(report_dir.name):
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

        # Fallback: extract stats from agent.log (full untruncated) if stats are missing
        stats = done_data.get("stats")
        if not stats:
            log_path = report_dir / "agent.log"
            raw_path = report_dir / "raw-output.md"
            stats_source = log_path if log_path.exists() else raw_path
            if stats_source and stats_source.exists():
                import re as _re
                log_text = stats_source.read_text(errors="replace")
                # Try session summary first: "Messages: N (1 user, M tool calls)"
                session_m = _re.search(r'Messages:\s*\d+\s*\([^)]*?(\d+)\s+tool calls?\)', log_text)
                if session_m:
                    tc = int(session_m.group(1))
                else:
                    tc = len(_re.findall(r'┊ 💻 \$(?!\s*preparing)', log_text)) + \
                         len(_re.findall(r'┊ 🔍(?!.*preparing)', log_text)) + \
                         len(_re.findall(r'┊ [📄🌐](?!.*preparing)', log_text))
                srch = len(_re.findall(r'┊ 🔍(?!.*preparing)', log_text))
                extr = len(_re.findall(r'┊ [📄🌐](?!.*preparing)', log_text))
                stats = {
                    "tool_calls": tc,
                    "searches": srch,
                    "sources": extr,
                    "shodan": len([l for l in _re.findall(r'┊ 💻 \$(?!.*preparing)(.*)', log_text)
                                  if _re.search(r'shodan', l, _re.IGNORECASE)]),
                }

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
            "stats": stats,
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

    # ─── Progress log: replay SSE history ──────────────────────

    @app.route("/api/progress/<path:task_id>")
    def get_progress(task_id):
        """Return the progress log as JSON lines for terminal replay."""
        # task_id may be the full directory name (e.g. 9229374-2026-07-21-dd5a6dd0-report)
        # extract the short hex task_id from it
        short_id = task_id
        m = re.search(r'([0-9a-f]{8})', task_id)
        if m:
            short_id = m.group(1)
        progress_path = PROGRESS_DIR / f"{short_id}.log"
        if not progress_path.exists():
            # Also try the full task_id
            progress_path = PROGRESS_DIR / f"{task_id}.log"
        if not progress_path.exists():
            return jsonify([])
        events = []
        for line in progress_path.read_text(errors="replace").strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                pass
        return jsonify(events)

    # ─── History: list all report directories ──────────────────

    @app.route("/api/history")
    def get_history():
        """List all available report directories with metadata.

        Deduplicates by vessel/person name — only the most recent run per
        vessel is shown. Names are parsed from the directory name with
        IMO/MMSI/date/task-id suffixes stripped.
        """
        from worker import REPORT_BASE
        # Build a lookup: report_dir -> {mode, model} from done files
        done_lookup = {}
        done_dir = QUEUE_DIR / "done"
        if done_dir.exists():
            for df in done_dir.glob("*.json"):
                try:
                    with open(df) as f:
                        dd = json.load(f)
                    rd = dd.get("report_dir")
                    if rd:
                        done_lookup[rd] = {
                            "mode": dd.get("mode", "vessel"),
                            "model": dd.get("model", ""),
                        }
                except (json.JSONDecodeError, OSError):
                    continue

        def _parse_dir_parts(dirname):
            """Parse a report directory name into (name, imo, mmsi, date, task_id).

            Examples:
              asana-imo-9035838-2026-07-20-8eebf748-report → ("asana", "9035838", None, "2026-07-20", "8eebf748")
              yaz-imo-9735323-2026-07-15-report → ("yaz", "9735323", None, "2026-07-15", None)
              9271585-heracles-2026-07-21-5eb733bf-report → ("heracles", "9271585", None, "2026-07-21", "5eb733bf")
              rina--imo-9152820-report → ("rina", "9152820", None, None, None)
              sinilind-mmsi-276014100-report → ("sinilind", None, "276014100", None, None)
              ahmed-nagi-nasr-report → ("ahmed-nagi-nasr", None, None, None, None)
              9354301-2026-07-21-78b9665b-report → (None, "9354301", None, "2026-07-21", "78b9665b")
            """
            raw = dirname.replace("-report", "")
            imo = None
            mmsi = None
            task_id = None
            date = None

            # Extract IMO/MMSI from explicit prefixes first
            m_imo = re.search(r'-?imo-?(\d{7,8})', raw, flags=re.IGNORECASE)
            if m_imo:
                imo = m_imo.group(1)
            m_mmsi = re.search(r'-?mmsi-?(\d{9})', raw, flags=re.IGNORECASE)
            if m_mmsi:
                mmsi = m_mmsi.group(1)

            # Fallback: if no explicit imo- prefix, check if dir starts with
            # a 7-8 digit number (bare-IMO dirs like "9354301-2026-07-21-78b9665b")
            # or 9-digit number (bare-MMSI dirs like "276014100-2026-07-21-report")
            if not imo and not mmsi:
                m_bare = re.match(r'^(\d{7,9})', raw)
                if m_bare:
                    num = m_bare.group(1)
                    if len(num) == 9:
                        mmsi = num
                    else:
                        imo = num

            # Extract date (YYYY-MM-DD)
            m_date = re.search(r'(\d{4}-\d{2}-\d{2})', raw)
            if m_date:
                date = m_date.group(1)

            # Extract trailing hex task_id (8+ hex chars at end, after stripping -report)
            # Pitfall: MMSI digits (9-digit, all hex-valid) can match the hex
            # regex. Skip if the match equals the already-extracted IMO/MMSI.
            m_hex = re.search(r'-([0-9a-f]{8,})$', raw, flags=re.IGNORECASE)
            if m_hex and m_hex.group(1) not in (imo, mmsi):
                task_id = m_hex.group(1)

            # Strip all parsed tokens to get the bare name
            name = raw
            # Strip date
            name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
            # Strip imo/mmsi + number
            name = re.sub(r'-?(imo|mmsi)-?\d+', '', name, flags=re.IGNORECASE)
            # Strip trailing hex
            name = re.sub(r'-[0-9a-f]{8,}$', '', name, flags=re.IGNORECASE)
            # Strip leading number prefix (e.g. "9271585-heracles" → "heracles")
            name = re.sub(r'^\d+-', '', name)
            # Strip bare trailing number (e.g. "asana-9035838" → "asana")
            name = re.sub(r'-\d+$', '', name)
            # Clean up: collapse multiple dashes, strip trailing/leading dash
            name = name.strip('-').replace('--', '-').strip('-')
            if not name:
                name = None

            return (name, imo, mmsi, date, task_id)

        def _resolve_name_from_report(report_dir, imo):
            """Try to resolve vessel name from the H1 of analyst-report.md.

            Returns (name, imo) tuple where name is lowercase, hyphen-joined
            or (None, imo) if resolution fails. If imo is None, tries to
            extract it from the H1 "(IMO XXXXXXX)" pattern.
            """
            report_path = report_dir / "analyst-report.md"
            if not report_path.exists():
                return (None, imo)
            try:
                with open(report_path, errors='replace') as f:
                    first_lines = f.read(2000)  # H1 is always in first few lines
            except OSError:
                return (None, imo)
            # Extract IMO from H1 if not already known
            resolved_imo = imo
            if not resolved_imo:
                m_imo_h1 = re.search(r'IMO[:\s]+(\d{7,8})', first_lines, re.IGNORECASE)
                if m_imo_h1:
                    resolved_imo = m_imo_h1.group(1)
            # Match H1 patterns:
            #   # VESSEL OSINT ANALYST REPORT — HERA (IMO 9326720)
            #   # Analyst Report: KOMANDER (ex-HERACLES) — IMO 9271585
            #   # OSINT Analyst Report — Vessel JAGGER (IMO 9354301)
            #   # Analyst Report: ASANA (IMO 9035838)
            #   # MT ASANA — Vessel OSINT Analyst Report
            #   # 9207027 (VERNAL) — Vessel OSINT Analyst Report
            #   # VESSEL OSINT ANALYST REPORT - ASTERI (IMO 9282493)
            # Capture the vessel name token(s) before "(IMO ...)" or "— IMO"
            # or "(ex-NAME)" (ex-name patterns). The non-greedy capture stops
            # at the first delimiter: paren-before-keyword or em-dash.
            # Also handle "(NAME)" pattern: "9207027 (VERNAL) — ..."
            m = re.search(
                r'^#+\s*(?:.*?[:\—\-]\s*)?(?:Vessel\s+|MT\s+|MSV\s+)?'
                r'([A-Z][A-Z0-9 \t\-]{1,40}?)'
                r'\s*(?:\(\s*ex-|\(?(?:IMO|MMSI)[:\s]|\—)',
                first_lines, re.MULTILINE)
            if m:
                name = m.group(1).strip().rstrip('-').strip()
                # Filter out generic words that shouldn't be vessel names
                if name.upper() in ('OSINT', 'ANALYST', 'VESSEL', 'REPORT', 'MT', 'MSV', 'FULL', 'EXECUTIVE-SUMMARY', 'EXECUTIVE', 'SUMMARY'):
                    name = None
                else:
                    # Lowercase, hyphen-join, collapse spaces
                    name = name.lower().replace(' ', '-').replace('--', '-').strip('-')
            else:
                name = None
            # Fallback: try "(NAME)" pattern — e.g. "9207027 (VERNAL) — ..."
            if not name:
                m2 = re.search(r'\(([A-Z][A-Za-z]{1,40})\)', first_lines)
                if m2:
                    candidate = m2.group(1)
                    if candidate.upper() not in ('IMO', 'MMSI', 'EX', 'OSINT'):
                        name = candidate.lower().replace(' ', '-').strip('-')
            if name:
                return (name, resolved_imo)
            return (None, resolved_imo)

        def _build_display_name(report_dir, dirname, imo, mmsi, date):
            """Build Linux-style display name: <name>-imo-<IMO>-<YYYYMMDD>.

            1. Try name + IMO from analyst-report.md H1
            2. Try name from directory name
            3. Fallback to bare imo-<IMO> or mmsi-<MMSI>
            """
            # Step 1: try report H1 (may also resolve IMO if missing)
            resolved_name, resolved_imo = _resolve_name_from_report(report_dir, imo)
            if resolved_name:
                name = resolved_name
                # Use IMO from H1 if dir didn't have it
                if not imo and resolved_imo:
                    imo = resolved_imo
                if not mmsi and not imo:
                    # Check H1 for MMSI too
                    pass  # H1 rarely has MMSI, skip
            else:
                # Step 2: try dir name
                dir_name, _, _, _, _ = _parse_dir_parts(dirname)
                name = dir_name
                if name:
                    # Already lowercase from _parse_dir_parts, just normalize
                    name = name.lower().replace(' ', '-').replace('--', '-').strip('-')

            # Step 3: assemble
            parts = []
            if name:
                parts.append(name)
            if imo:
                parts.append(f"imo-{imo}")
            elif mmsi:
                parts.append(f"mmsi-{mmsi}")
            if date:
                # Compact ISO date: 2026-07-21 → 20260721
                parts.append(date.replace('-', ''))

            return '-'.join(parts) if parts else dirname.replace("-report", "")

        def _extract_date(dirname):
            """Extract date (YYYY-MM-DD) from a report directory name."""
            m = re.search(r'(\d{4}-\d{2}-\d{2})', dirname)
            return m.group(1) if m else None

        all_reports = []
        for d in sorted(REPORT_BASE.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not d.is_dir() or not d.name.endswith("-report"):
                continue
            # Parse parts from dir name
            dir_name, imo, mmsi, date, task_id = _parse_dir_parts(d.name)
            # Build Linux-style display name: <name>-imo-<IMO>-<YYYYMMDD>
            display_name = _build_display_name(d, d.name, imo, mmsi, date)
            # Look up mode + model from done files (match by exact or endswith)
            info = done_lookup.get(str(d), {})
            if not info:
                for rd_path, di in done_lookup.items():
                    if rd_path.endswith(d.name):
                        info = di
                        break
            all_reports.append({
                "task_id": d.name,
                "name": display_name,
                "mode": info.get("mode", "vessel"),
                "model": info.get("model", ""),
                "timestamp": int(os.path.getmtime(d) * 1000),
                "_sort_name": display_name.lower(),
                "_task_id_short": task_id,  # short hex for disambiguation
            })

        # Disambiguation: if multiple runs share the same display name,
        # append the short task_id hash as a #<hex> suffix
        name_counts = {}
        for r in all_reports:
            name_counts[r["name"]] = name_counts.get(r["name"], 0) + 1

        for r in all_reports:
            if name_counts.get(r["name"], 0) > 1:
                if r.get("_task_id_short"):
                    r["name"] = f"{r['name']} #{r['_task_id_short']}"
                else:
                    # Fallback: use short mtime hash (MMDDHHMM) + dir suffix
                    # for disambiguation. If mtimes are identical (copied dirs),
                    # fall back to a short hash of the full task_id.
                    ts = r["timestamp"] / 1000
                    suffix = time.strftime('%m%d%H%M', time.localtime(ts))
                    # Check if this suffix+name combo is still duplicated
                    # by appending a incremental counter
                    r["name"] = f"{r['name']} #{suffix}"

        # Third pass: if still duplicated (same mtime), append dir-name hash
        name_counts3 = {}
        for r in all_reports:
            name_counts3[r["name"]] = name_counts3.get(r["name"], 0) + 1
        for r in all_reports:
            if name_counts3.get(r["name"], 0) > 1:
                import hashlib
                h = hashlib.md5(r["task_id"].encode()).hexdigest()[:6]
                r["name"] = f"{r['name']}-{h}"

        reports = sorted(all_reports, key=lambda r: -r["timestamp"])
        for r in reports:
            r.pop("_sort_name", None)
            r.pop("_task_id_short", None)
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

    # ─── Profile models: dynamic model list per agent profile ─────────

    @app.route("/api/profiles/models")
    def profile_models():
        profiles_path = BASE_DIR / "profiles-models.json"
        try:
            with open(profiles_path) as f:
                data = json.load(f)
            return jsonify(data)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return jsonify({"error": str(e)}), 500
