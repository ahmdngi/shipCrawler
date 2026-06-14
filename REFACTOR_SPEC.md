# Shipcrawler v4 Refactor — Dynamic Real-Time Dashboard

## Goal

Transform the current queue-based polling dashboard into a **dynamic real-time website** that:
1. Streams OSINT investigation steps live to the browser via SSE
2. Shows a live terminal feed of what the agent is doing moment-by-moment
3. Presents the final report in an interesting, animated, visually rich way

## Architecture Change

### Current
```
Browser → POST /api/search → queue/pending/ → worker spawns `hermes chat -q` → done
                                                                              ↓
Browser → poll /api/status → poll /api/report → static cards
```

### Target
```
Browser → POST /api/search → queue/pending/ → worker runs orchestrator
                                              ↓ (writes progress events to log)
                                              ↓
Browser → GET /api/stream/<task_id>  ← SSE ← tail progress log
                                              ↓ (worker finishes)
Browser → GET /api/report/<task_id> → animated final report
```

## Backend Changes

### 1. SSE Endpoint (`/api/stream/<task_id>`)
- Long-lived HTTP connection (EventSource)
- Tails a progress log file: `queue/progress/<task_id>.log`
- Sends `event: progress` with JSON payload: `{step: string, detail: string, timestamp: string, source: string, found: any|null}`
- Sends `event: complete` when done, with the report path
- Sends `event: error` on failure
- Uses simple file-based tailing (check file size, send new lines, sleep 0.5s)

### 2. Worker Change (`worker.py`)
- Instead of `hermes chat -q`, use `orchestrate.py` (from shipcrawler-parallel) directly
- **Before each phase**, write a progress line: `{"step": "equasis", "detail": "Querying Equasis registry...", "source": "equasis-cli"}`
- **After each phase result**, write: `{"step": "equasis", "detail": "Found: BOREALIS, IMO 9122552, flag Panama", "source": "equasis-cli", "found": {...}}`
- Progress log format: one JSON object per line (JSON Lines / NDJSON)
- Worker captures stdout/stderr from each sub-agent and writes progress
- **No more silent Hermes subprocess** — run the actual OSINT scripts with visible output

### 3. Progress Log Manager
- Simple module: `worker_progress.py`
- `write_progress(task_id, step, detail, source=None, found=None)`
- Appends one JSON line to `queue/progress/<task_id>.log`
- Handles file locking (atomics: write to .tmp, rename)

### 4. Queue Status Change
- PENDING → RUNNING (with phases: equasis, ais, shodan, analysis, report) → DONE
- Progress log captures per-phase status updates
- The done JSON includes timing info (started_at, completed_at, phase_timings)

## Frontend Changes

### 1. SSE Client (`shipcrawler-sse.js` — already exists, needs rewrite)
- Replace polling with `EventSource` connection to `/api/stream/<task_id>`
- On each `progress` event: append a line to the terminal feed
- On `complete`: switch from terminal feed to report view with animation
- Reconnection logic (EventSource auto-reconnects, but handle gracefully)

### 2. Live Terminal Feed
- The current `terminal-loader` becomes dynamic: real lines appear as events arrive
- Each line shows: timestamp, step badge (e.g., `[EQUASIS]`, `[AIS]`, `[SHODAN]`), detail message
- Color-coded badges per source
- When data is found, show a brief summary inline
- Terminal has a scroll-to-bottom button and auto-scroll

### 3. Animated Final Report
- When complete event fires, transition the terminal to a "Report Generated" state
- Reveal the report cards with staggered entrance animations (scale-in, fade-in from bottom)
- Add a summary bar at top: "X sources checked, Y data points found, completed in Z seconds"
- Keep all existing cards (vessel/person identity, status, map, port calls, Shodan, red-team, detection, analysis)
- Add a "timeline" view showing when each piece of data was collected (optional)

### 4. Visual Polish
- The terminal feed should look like a real terminal (green-on-black, monospace, cursor blink last line)
- Step badges have distinct colors: Equasis=blue, AIS=cyan, Shodan=orange, Web=green, Report=purple
- Loading state during SSE connection
- Error state with retry button

## Files to Modify

| File | Change |
|------|--------|
| `worker.py` | Rewrite: run shipcrawler-parallel scripts directly, emit progress events to log |
| `routes/api.py` | Add `/api/stream/<task_id>` SSE endpoint, update status endpoints |
| `static/js/shipcrawler-sse.js` | Rewrite: EventSource client for live terminal feed |
| `static/js/shipcrawler-core.js` | Update: wire SSE to UI, add animated report transitions |
| `static/js/shipcrawler-ui.js` | Update: add terminal feed rendering, step badge colors |
| `static/css/shipcrawler.css` | Add styles for live terminal, step badges, animations |
| `templates/index.html` | Update: replace terminal-loader placeholder with dynamic terminal area |
| `worker_progress.py` | **NEW**: progress log writer utility |
| `requirements.txt` | Add: `watchdog` (for file tailing if needed) or keep it simple with polling |

## Non-Goals
- No WebSocket (SSE is simpler and fits the unidirectional data flow)
- No Redis/DB — keep it file-based to match the existing queue architecture
- No user auth (Tailscale-bound, internal tool)
- No breaking existing API contracts (old polls still work)

## Implementation Order

1. Create `worker_progress.py` — progress log writer
2. Rewrite `worker.py` — run scripts directly, emit progress
3. Add SSE endpoint to `routes/api.py`
4. Rewrite frontend: SSE client, terminal feed, animated report
5. Test with a live vessel search
