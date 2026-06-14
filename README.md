# Shipcrawler v5 — Phase Agent OSINT Dashboard

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
| `/api/health` | GET | Queue health check |

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
