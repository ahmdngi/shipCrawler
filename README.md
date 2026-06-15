# Shipcrawler v6.3 — AI Agent OSINT Dashboard

Real-time, phase-by-phase Hermes agent investigation with SSE streaming.

## Architecture

```
User submits search → queue/pending/
  └── Worker picks up task, runs 6 phases sequentially:
       ├── Phase 0: Equasis Vessel Identity
       ├── Phase 1: Target Identification (AIS)
       ├── Phase 2: Attack Surface Discovery (Shodan)
       ├── Phase 3: Vulnerability Assessment
       ├── Phase 4: Threat Intelligence
       └── Phase 5: Report Generation
       
Each phase → hermes chat -q --skills shipcrawler
  ├── Writes progress to queue/progress/<task_id>.log (JSON Lines)
  └── Frontend reads via SSE at /api/stream/<task_id>
```

Each phase runs as a full Hermes agent session with the shipcrawler skill. Phase outputs are accumulated and passed as context to subsequent phases.

## Setup

```bash
pip install flask requests beautifulsoup4 shodan
```

## Running

```bash
# Terminal 1: Dashboard
python3 app.py

# Terminal 2: Worker (daemon mode)
python3 worker.py

# Worker with --once for single task
python3 worker.py --once
```

Dashboard: `http://100.72.133.89:9091`

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/api/search` | POST | Submit search task |
| `/api/status/<task_id>` | GET | Check task status |
| `/api/stream/<task_id>` | GET | SSE stream of phase progress |
| `/api/report/<task_id>` | GET | Get full report data |
| `/api/report/by-name/<name>` | GET | Lookup report by vessel/person name |
| `/api/history` | GET | List all past report directories (sorted by recency) |
| `/api/health` | GET | Queue health check |

## Changelog

### v6.3b
- New `/api/history` endpoint — lists all past report directories sorted by modification time for search history without re-parsing files
- Worker raw vs clean separation — Hermes full output saved as `raw-output.md`, agent-created `.md` files copied into report dir separately and sorted. Prevents clean analyst reports from being overwritten by raw prompt/tool-call dumps
- Name sanitization fix — `/api/report/by-name/<name>` now uses `sanitize_name()` before `clean_for_filename()`, fixes edge cases with punctuation in vessel names
- `md-block` library added to templates — renders markdown directly in HTML for cleaner report file display

### v6.3
- Real-time tool-call streaming: worker now uses Popen to read Hermes output line-by-line
- Frontend shows live tool calls with colored badges (EQUASIS=blue, SHODAN=pink, WEB=green, BROWSER=purple, BASH=orange)
- Per-line classification: tool_start, tool_detail, thinking, output with distinct styling
- Live timer per phase (1s tick, pulses green)
- Pulsing badge animation for active phase
- Comprehensive single-session agent (full context → red-team + detection rules)

### v6.2
- Fixed phase completion UI: spinner now correctly flips to ✅ (used `.phase-start` selector instead of `lastChild`)
- Fixed sidebar: saves metadata only (~200 bytes per entry), fetches report data from API on click
- Added right panel for phase file browsing (collapsible, click to view raw phase output)
- Added phase file content to API response (`phase_contents` key in `/api/report/`)
- Increased per-phase timeout 300s → 600s (prevents Phase 1 AIS timeout)
- Rebranded "Hermes" → "AI Agent" in UI text
- Version bump to v6.2

### v6.1
- Added sidebar with search history (localStorage, persisted across sessions)
- Tabbed report section (Overview / Technical / Red Team / Detection / Assessment)
- Phases stay visible when report loads
- Fixed HOME env var not passed to Hermes subprocess (Shodan API key resolution)
- Defensive null-checks in all JS (no more "Cannot set properties of null" errors)
- Tab switching with active state highlighting

### v5
- Initial phase-agent architecture with 6 sequential Hermes phases
- SSE streaming of phase progress to browser
- worker_progress.py JSON Lines logger

## Phases

Each phase runs `hermes chat -q --skills shipcrawler` with a phase-specific prompt. Previous phase findings are injected as context. Progress is written to a JSON Lines file and streamed to the browser in real-time via Server-Sent Events.

### Vessel OSINT Phases
0. Equasis — Vessel Identity (registry data)
1. Target Identification (AIS position, port calls)
2. Attack Surface Discovery (Shodan, maritime protocols)
3. Vulnerability Assessment (CVEs, misconfigurations)
4. Threat Intelligence (incidents, risk context)
5. Report Generation (analyst report, red-team, detection rules)

### Person OSINT Phases
0. Identity & Academic Sources
1. Research Impact Analysis
2. Social & Digital Footprint
3. Professional Network & Timeline
4. Targeting Scenarios
5. Report Generation

## Frontend Flow

1. User enters query → POST /api/search → task queued
2. SSE connection opens to /api/stream/<task_id>
3. As each phase completes, a progress event is received:
   - `phase_start` → spinner appears in terminal feed
   - `phase_output` → detail lines appear under the phase
   - `phase_complete` → ✅ badge with summary and duration
   - `phase_error` → ❌ badge with error message
   - `report_complete` → summary bar with stats
   - `done` → load final report and animate cards
4. Report cards animate in with staggered entrance effects
5. Fallback: traditional polling if SSE connection drops
