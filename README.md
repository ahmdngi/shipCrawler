# Shipcrawler v6.4c — AI Agent OSINT Dashboard

Maritime OSINT investigation platform that uses autonomous AI agents to identify vulnerabilities, exposed interfaces, and operational patterns on vessels worldwide. Built on the OSINT Maritime Framework methodology (IEEE Access 2026).

Real-time, phase-by-phase AI agent investigation with SSE streaming — watch each OSINT phase execute live in the browser.

---

## Overview

Shipcrawler automates the full maritime OSINT workflow. Submit a vessel name or MMSI, and an AI agent runs 6 sequential OSINT phases — pulling from Equasis, AIS tracking services, Shodan, web intelligence, and vulnerability databases — then produces a complete analyst report with red-team playbook and detection rules.

### What It Finds

| Category | Intelligence Collected |
|----------|----------------------|
| **Vessel Identity** | IMO, MMSI, call sign, flag, build year, owner, manager, classification society, P&I club |
| **Operational Status** | Current position, destination, ETA, port calls, route patterns |
| **Attack Surface** | Exposed services (VSAT, Signal K, SAILOR), open ports, misconfigured maritime protocols |
| **Vulnerabilities** | CVEs on discovered services, insecure configurations, default credentials |
| **Threat Context** | Sanctions flags, high-risk port calls, incident history, AIS gaps |
| **Compliance** | Detention rates, inspection history, Paris/Tokyo MoU status, flag performance |

### Report Outputs

Each investigation produces 4 files:

- **analyst-report.md** — Full narrative with vessel identity, status, port calls, Shodan findings, risk tier
- **red-team-playbook.md** — Attack vectors based on the vessel's specific profile and exposed services
- **indicators-and-detection.md** — Detection rules for SOC integration (Elastic, Zeek, Wazuh)
- **raw-output.md** — Full AI agent trace including tool calls, thinking, and raw findings

---

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

Each phase → AI agent with shipcrawler OSINT skills
  ├── Writes progress to queue/progress/<task_id>.log (JSON Lines)
  └── Frontend reads via SSE at /api/stream/<task_id>
```

Each phase runs as a full AI agent session with the shipcrawler skill set. Phase outputs are accumulated and passed as context to subsequent phases, building depth progressively. The agent has access to:

- **Equasis API** — Registry data, ownership, classification, inspections, P&I
- **AIS tracking** — VesselFinder, MarineTraffic for position and port calls
- **Shodan API** — Port scanning, service discovery, CVE correlation
- **Web OSINT** — News, incident reports, company profiles
- **CloakBrowser** — Evades bot detection on AIS tracking sites

### Dual Mode

| Mode | Phases | Target |
|------|--------|--------|
| **Vessel OSINT** | Identity → AIS → Shodan → CVEs → Threat Intel → Report | Any vessel with IMO/MMSI |
| **Person OSINT** | Identity → Research Impact → Digital Footprint → Network → Scenarios → Report | Crew, owners, maritime professionals |

---

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
| `/api/search` | POST | Submit search task (vessel name, MMSI, or person name) |
| `/api/status/<task_id>` | GET | Check task status |
| `/api/stream/<task_id>` | GET | SSE stream of phase progress |
| `/api/report/<task_id>` | GET | Get full report data with phase contents |
| `/api/report/by-name/<name>` | GET | Lookup report by vessel/person name (deterministic path) |
| `/api/history` | GET | List all past report directories (sorted by recency) |
| `/api/health` | GET | Queue health check |

## Frontend

- **Live terminal** — Real-time phase output with colored tool-call badges (EQUASIS=blue, SHODAN=pink, WEB=green, BROWSER=purple, BASH=orange)
- **Tabbed report** — Overview / Technical / Red Team / Detection / Assessment
- **Sidebar** — Search history persisted in localStorage
- **Right panel** — Report file browser with inline markdown rendering
- **Map** — Leaflet integration with AIS, satellite, and marine traffic overlays
- **Dark theme** — Terminal-inspired UI built for extended investigation sessions

### Frontend Flow

1. User enters query → POST /api/search → task queued
2. SSE connection opens to /api/stream/<task_id>
3. As each phase completes, progress events stream to browser:
   - `phase_start` → spinner appears in terminal feed
   - `phase_output` → detail lines under the phase
   - `phase_complete` → ✅ badge with summary and duration
   - `phase_error` → ❌ badge with error message
   - `report_complete` → summary bar with stats
   - `done` → load final report and animate cards
4. Report cards animate in with staggered entrance effects
5. Fallback: traditional polling if SSE connection drops

## Vessel OSINT Phases

| Phase | Sources | Collects |
|-------|---------|----------|
| **0 — Equasis Identity** | Equasis registry | IMO, MMSI, flag, owner, manager, classification, P&I, build year, surveys |
| **1 — AIS Tracking** | VesselFinder, MarineTraffic | Position, speed, course, destination, ETA, port calls, route patterns |
| **2 — Attack Surface** | Shodan API | Exposed services (Signal K, VSAT, SAILOR, FTP, HTTP), open ports, geolocation |
| **3 — Vulnerability Assessment** | Shodan CVEs, NVD | CVE mapping to discovered services, misconfiguration analysis, risk scoring |
| **4 — Threat Intelligence** | Web OSINT, sanctions lists | Incident history, sanctions flags, high-risk zones, AIS manipulation indicators |
| **5 — Report Generation** | All prior phases | Consolidated analyst report, red-team playbook, detection rules |

## Person OSINT Phases

| Phase | Sources | Collects |
|-------|---------|----------|
| **0 — Identity & Academic** | ORCID, DBLP, Google Scholar | Name, affiliations, publication record, h-index |
| **1 — Research Impact** | Citation databases | Citation metrics, top works, co-author network |
| **2 — Digital Footprint** | Web OSINT, social media | Professional profiles, institutional pages, online presence |
| **3 — Network & Timeline** | Cross-referenced sources | Career timeline, geographic mobility, collaboration patterns |
| **4 — Targeting Scenarios** | All prior phases | Attack vectors based on digital footprint, phishing surface |
| **5 — Report Generation** | All prior phases | Consolidated person report with risk assessment |

## Changelog

### v6.4c
- **Fix: `/api/history` crash** — missing `import os` caused 500 error on every page load. Sidebar history never populated, auto-load was broken.
- **Fix: refresh loses everything** — history sidebar now auto-loads the most recent report on page refresh (from both localStorage and API). Report reappears without a new search.
- **Resilience** — auto-load deduplicated into shared `autoLoadLatest()` function, works from both localStorage cache and API fallback.

### v6.4b
- **Fix: missing shipcrawler-ui.js script tag** — `ShipcrawlerUI` was never loaded, causing `loadTheme()` to throw a ReferenceError that blocked `ShipcrawlerCore.init()`. Search button was unresponsive. Added the missing `<script>` tag.
- **Fix: phase lines rendered outside terminal body** — `appendChild` was targeting the outer `terminal-window` instead of the inner `terminal-body`. Stream content appeared below the blinking cursor with a gap. Moved all append/scroll to `feedBody`.
- **Fix: static $ prompt not removed on stream start** — the blinking cursor prompt stayed at the top while investigation content streamed below. Prompt is now removed when the first phase line arrives.
- **Worker: real-time filler frames** — search now shows 3 progress messages instantly ("AI agent initializing...", "Loading OSINT tools...", "Starting Phase...") before the AI agent subprocess even starts, eliminating dead air after clicking Search.
- **Resilience** — `ShipcrawlerUI.loadTheme()` wrapped in try/catch so UI module failure doesn't break core search functionality.

### v6.3b
- Repo renamed from `shipcrawler-v4` to `shipcrawler` (old v3 deprecated and removed)
- New `/api/history` endpoint — lists all past report directories sorted by modification time for search history without re-parsing files
- Worker raw vs clean separation — AI agent full output saved as `raw-output.md`, agent-created `.md` files copied into report dir separately and sorted. Prevents clean analyst reports from being overwritten by raw prompt/tool-call dumps
- Name sanitization fix — `/api/report/by-name/<name>` now uses `sanitize_name()` before `clean_for_filename()`, fixes edge cases with punctuation in vessel names
- `md-block` library added to templates — renders markdown directly in HTML for cleaner report file display

### v6.3
- Real-time tool-call streaming: worker reads AI agent output line-by-line via Popen
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
- Rebranded "AI Agent" throughout UI text
- Version bump to v6.2

### v6.1
- Added sidebar with search history (localStorage, persisted across sessions)
- Tabbed report section (Overview / Technical / Red Team / Detection / Assessment)
- Phases stay visible when report loads
- Fixed HOME env var not passed to subprocess (Shodan API key resolution)
- Defensive null-checks in all JS (no more "Cannot set properties of null" errors)
- Tab switching with active state highlighting

### v5
- Initial phase-agent architecture with 6 sequential phases
- SSE streaming of phase progress to browser
- worker_progress.py JSON Lines logger

---

## Related

- **Shipcrawler-Parallel** — Multi-agent variant for bulk vessel investigations (3 agents concurrent, ~2 min per vessel)
- **Project Haris** — Maritime edge security platform (defensive counterpart)
- **OSINT Maritime Framework** — IEEE Access 2026 methodology paper
