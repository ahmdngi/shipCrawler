# Shipcrawler v4 — Hermes-Powered Architecture

## Problem with v3

v3 tried to replicate Hermes' OSINT workflow inside Flask using `requests`/`curl` — but these can't render JS SPAs, get blocked by anti-bot measures, and can't reach academic APIs reliably. The Hermes agent (with `web_search`, `web_extract`, browser tools) does this correctly. v4 aligns the tool with the tool that works.

## Architecture

```
Browser (user)
    │
    ▼
Flask Dashboard (port 9090)
    │  Shows: terminal loader (SSE) → renders markdown reports
    │
    ├─ POST /api/search ──→ queue/task file
    │
    ▼
Hermes Background Worker (cron or watchdog)
    │  Polls queue, runs: hermes run --prompt "..." --skills shipcrawler,shipcrawler-report-workflow
    │  Hermes uses real web_search, web_extract, browser tools
    │
    ├─ Generates /root/<name>-report/ (5 markdown files)
    │     README.md, analyst-report.md, research-impact-analysis.md,
    │     affiliation-timeline.md, targeting-scenarios.md
    │
    ├─ Writes status JSON to output/<task_id>.json
    │
    ▼
Flask Dashboard polls → reads markdown → renders as cards
```

## Components

### 1. Task Queue (`queue/` dir)
```
queue/
├── pending/          # Hermes picks tasks from here
│   └── <task_id>.json
├── running/          # Currently being worked on
└── done/             # Completed with pointer to report dir
    └── <task_id>.json → {"dir": "/root/name-report/", "mode": "person"}
```

### 2. Hermes Cron Worker

A cron job (every 30s) or systemd service:
```bash
hermes run --prompt "Use shipcrawler to research this person/vessel. Generate the full 5-file report." \
           --skills shipcrawler,shipcrawler-report-workflow \
           --from-file queue/pending/<task_id>.json
```

The cron job:
1. Checks `queue/pending/` for tasks
2. Moves task to `queue/running/`
3. Calls `hermes run` with the prompt + skills
4. Hermes generates the report folder using its tools
5. Creates status JSON in `queue/done/`

### 3. Flask Dashboard (simplified)

Routes:
```
GET  /              → index.html
POST /api/search    → writes task to queue/pending/, returns task_id
GET  /api/status/<task_id>  → checks queue/running/ or queue/done/
GET  /api/report/<task_id>  → reads markdown files, returns structured JSON
GET  /api/health    → ok
```

No more auto-search logic — the dashboard becomes a terminal + markdown renderer.

### 4. Markdown → Card Renderer

The 5 markdown files from the shipcrawler-report-workflow skill get parsed into dashboard cards:

```
analyst-report.md
  └── Section 1: Identity → Person Identity card
  └── Section 2: Current Positions → Professional History card
  └── Section 3: Education → Education card
  └── Section 8: Collaboration Network → Collaboration card
  └── Section 9: Digital Footprint → Digital Footprint card
  └── Section 13: Confidence Assessment → Confidence card

research-impact-analysis.md
  └── Section 1: Citation Metrics → Research Impact card
  └── Section 2: Top-5 Publications → Most Cited card
  └── Section 3: Publication Output by Year → chart
  └── Section 5: Collaboration Network Analysis → Collaboration card

affiliation-timeline.md
  └── Section 1: Timeline Overview → Timeline card
  └── Section 2: Geographic Mobility → Map pins
  └── Section 3: Key Career Transitions → Career card

targeting-scenarios.md
  └── Vector A/B/C → Targeting Scenarios cards
  └── Exposure Analysis → Analysis card
```

## Frontend Changes

The terminal loader stays for SSE-style progress, but the report cards are populated from markdown sections instead of raw JSON fields. A simple Python markdown parser on the backend reads the files and converts sections to structured data.

## What Gets Removed from v3

| File | What changes |
|------|-------------|
| `services/person_osint.py` | Delete — Hermes does the research |
| `services/vessel_scraper.py` | Delete — Hermes does the scraping |
| `services/shodan_search.py` | Delete — Hermes queries Shodan |
| `routes/api.py` | Simplify to queue-based endpoints |
| `services/analysis.py` | Keep — still generates playbooks + detection rules from seeded data |

## What Gets Added

| File | Purpose |
|------|---------|
| `worker.py` | Queue watcher, spawns Hermes CLI |
| `renderer.py` | Converts markdown sections → JSON for frontend cards |
| `queue/` | Task queue directory structure |
| `cron.sh` | Cron job script for periodic queue check |
