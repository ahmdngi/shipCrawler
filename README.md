# ShipCrawler — Agentic Maritime OSINT Platform (1.x production line)

<p align="center">
  <img src="static/img/logo.png" alt="ShipCrawler Logo" width="400">
</p>

**v7.4** — The production vessel-OSINT dashboard. Real-time, phase-by-phase AI agent investigation of any vessel with SSE streaming — watch each OSINT phase execute live in the browser. Persists across page refreshes with automatic SSE reconnection. Per-scan Hermes agent profiles, each with its own model/provider configuration.

Built on the OSINT Maritime Framework methodology (IEEE Access 2026) — the peer-reviewed, validated pipeline (25-run stability study, IEEE Access manuscript 2026-38078).

> **This is the 1.x production line.** Development of ShipCrawler 2.0 (Geo-Watch — agentic maritime perimeter awareness for offshore wind) happens in [`ShipCrawler/shipcrawler-2.0`](https://github.com/ShipCrawler/shipcrawler-2.0). This repo carries the vessel-OSINT dashboard and the IEEE Access validation evidence tooling.

[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)]()
[![Language](https://img.shields.io/badge/language-Python-blue?style=flat-square)]()
[![Stars](https://img.shields.io/github/stars/ahmdngi/shipCrawler?style=flat-square)](https://github.com/ahmdngi/shipCrawler)

---

## Table of Contents

- [Quick Start](#quick-start)
- [What ShipCrawler Does](#what-shipcrawler-does)
- [Prerequisites & API Keys](#prerequisites--api-keys)
- [Configuration](#configuration)
- [Agent Profiles](#agent-profiles)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Production Deployment](#production-deployment)
- [IEEE Access Validation](#ieee-access-validation)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [Related](#related)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/ahmdngi/shipCrawler.git
cd shipcrawler

# 2. Python environment
python3 -m venv venv
source venv/bin/activate
pip install flask requests beautifulsoup4 shodan jinja2

# 3. Install Hermes Agent (the AI runtime) + the shipcrawler skill
pip install hermes-agent
hermes skills install shipcrawler

# 4. Start dashboard
python3 app.py

# 5. Start worker (new terminal)
python3 worker.py

# 6. Open browser
open http://localhost:9091
```

## What ShipCrawler Does

Submit a vessel (name / MMSI / IMO) and an autonomous Hermes agent executes the full OSINT investigation, streaming every phase live:

1. **Phase 0 — Vessel Identity** (Equasis registry: IMO, flag, ownership, PSC history)
2. **Phase 1 — Target Identification** (AIS position, port calls, route)
3. **Phase 2 — Attack Surface Discovery** (Shodan: satellite terminals, exposed services)
4. **Phase 3 — Vulnerability Assessment** (CVEs on exposed equipment)
5. **Phase 4 — Threat Intelligence** (web OSINT, sanctions, shadow-fleet indicators)
6. **Phase 5 — Report Generation** (analyst report, red-team playbook, SIEM detection rules)

Output is a risk-tiered intelligence package: analyst-report.md, red-team-playbook.md, indicators-and-detection.md (ES-native EQL/KQL), plus the full agent transcript. Risk tiers: CRITICAL / HIGH / MEDIUM / LOW via the deterministic tier rubric (sanctions breadth + five signatures + AIS-dark + attributable exposure — PSC detentions are explicitly NOT tier drivers).

The investigation methodology (phases, source chains, confidence protocol, ethical constraints) is published in [`skill/`](skill/) — the reproducible methodology artifact referenced by the IEEE Access paper.

## Prerequisites & API Keys

- **Python 3.10+**, **Hermes Agent** ([install guide](https://hermes-agent.nousresearch.com/docs))
- API keys in `~/.hermes/.env`:

| Key | Source | Used for |
|---|---|---|
| `SHODAN_API_KEY` | [shodan.io](https://account.shodan.io/) | Attack surface discovery |
| `EXA_API_KEY` | [exa.ai](https://exa.ai/) | Web search & extraction (primary backend) |
| `EQUASIS_USERNAME/PASSWORD` | [equasis.org](https://www.equasis.org/) | Vessel registry (free registration) |
| `FIRECRAWL_API_KEY` (opt) | [firecrawl.dev](https://firecrawl.dev/) | Fallback for JS-heavy sites |
| `TAVILY_API_KEY` (opt) | [tavily.com](https://tavily.com/) | Additional search fallback |

Set the web backend to Exa:

```bash
hermes config set web.backend exa
hermes config set web.search_backend exa
hermes config set web.extract_backend exa
```

## Configuration

- Dashboard default port: **9091** (`python3 app.py`, override with `--port`)
- Production (systemd): **port 5000** — see [Production Deployment](#production-deployment)
- Equasis CLI: `equasis configure --setup` once; test with `equasis vessel --imo 9237589`
- `profiles-models.json` maps profiles → models; edit live, no restart (API reads per request)

## Agent Profiles

Each scan picks a Hermes profile (model/provider per profile, defined in `~/.hermes/profiles/<name>/config.yaml`):

| Profile | Purpose | Model | Provider |
|---------|---------|-------|----------|
| `default` | General purpose | deepseek-v4-flash | deepseek |
| `local` | Local inference | qwen2.5:3b | custom:ollama |
| `research` | Research-grade | deepseek-v4-flash | deepseek |
| `shipcrawler` | Maritime OSINT | **glm-5.3** | custom:UT-GLM5.2 (UT HPC vLLM) |

Custom providers use the `custom:<name>` format in `profiles-models.json`. The `shipcrawler` profile is pinned to GLM-5.3 on the UT HPC endpoint.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/api/search` | POST | Submit search task |
| `/api/status/<task_id>` | GET | Check task status |
| `/api/stream/<task_id>` | GET | SSE stream of phase progress |
| `/api/report/<task_id>` | GET | Get full report data |
| `/api/report/by-name/<name>` | GET | Lookup report by vessel/person name |
| `/api/report/<task_id>` | DELETE | Delete a report |
| `/api/history` | GET | List all past reports |
| `/api/profiles/models` | GET | Available models per agent profile |
| `/api/health` | GET | Queue health check |

```bash
# Submit a scan
curl -X POST http://localhost:9091/api/search \
  -H "Content-Type: application/json" \
  -d '{"name": "EVA 316", "mode": "vessel", "model": "deepseek-v4-flash",
       "provider": "deepseek", "profile": "default"}'
# => {"task_id": "a1b2c3d4", "mode": "vessel", "status": "queued"}

# Watch it live (SSE): queued -> phase_start -> phase_output -> phase_complete -> done
curl -N http://localhost:9091/api/stream/a1b2c3d4
```

Reports land in `~/hermes-vault/osint-reports/<vessel>-<date>-<task_id>-report/`:
analyst-report.md · red-team-playbook.md · indicators-and-detection.md · raw-output.md (+ agent.log).

## Architecture

```
User submits search → queue/pending/
  └── Worker picks up task, runs phases sequentially:
       ├── Phase 0: Equasis Vessel Identity
       ├── Phase 1: Target Identification (AIS)
       ├── Phase 2: Attack Surface Discovery (Shodan)
       ├── Phase 3: Vulnerability Assessment
       ├── Phase 4: Threat Intelligence
       └── Phase 5: Report Generation

Each phase → AI agent with shipcrawler OSINT skills
  ├── Writes progress to queue/progress/<task_id>.log (JSON Lines)
  ├── Frontend reads via SSE at /api/stream/<task_id>
  └── Reports saved to ~/hermes-vault/osint-reports/
```

> **Interactive architecture diagram:** [`docs/shipcrawler-architecture.html`](docs/shipcrawler-architecture.html) — self-contained HTML (dark/light themes, pan/zoom, search, PNG/SVG export). Source spec: [`docs/shipcrawler-architecture.json`](docs/shipcrawler-architecture.json).

| Component | File | Role |
|-----------|------|------|
| **Flask Dashboard** | `app.py` | Web UI, API endpoints, SSE streaming |
| **API Routes** | `routes/api.py` | REST endpoints, report loading, profile models |
| **Queue Worker** | `worker.py` | Polls queue, spawns AI agents with `--profile` flag |
| **Progress Logger** | `worker_progress.py` | JSON Lines log writer/reader |
| **Report Renderer** | `renderer.py` | Structured report parser |
| **Template Renderer** | `template_renderer.py` | Jinja2 report skeleton renderer |
| **Stream Formatter** | `stream_formatter.py` | Cleans raw agent output into SSE events |
| **Frontend** | `static/js/shipcrawler-*.js` | SSE client, UI logic, theme switcher, globe |

## Production Deployment

Supervised via systemd (auto-restart, watchdog):

```bash
systemctl is-active shipcrawler-dashboard.service shipcrawler-worker.service
sudo systemctl restart shipcrawler-worker.service   # picks up pending queue
journalctl -u shipcrawler-worker -f                  # live worker log
```

Dashboard serves **port 5000** in production (`deploy/shipcrawler-dashboard.service`), worker polls `queue/pending/` every 2 s. Unit files tracked in `deploy/` — see `deploy/README.md`.

## IEEE Access Validation

This repo is the tool behind the OSINT Maritime Framework paper (IEEE Access, vol. 14, 2026, DOI [10.1109/ACCESS.2026.3673557](https://doi.org/10.1109/ACCESS.2026.3673557)):

- Manuscript + response: [`shipcrawler-paper`](https://github.com/ahmdngi/shipcrawler-paper) (Access-2026-38078)
- Reviewer evidence bundle (authoritative): `shipcrawler-review-evidence` — treatment/control/stability packages, validation ledger
- 25-run stability study: modal-exact 20/25, within-one-tier 25/25
- Quantization-pinned reruns: OpenRouter Decart endpoint serving the identical NVFP4 build

## Troubleshooting

- **Worker not picking up tasks** → the systemd worker service is down; `systemctl restart shipcrawler-worker.service`
- **Equasis "VESSEL NOT FOUND"** → usually rate-limiting, not missing data; wait 30-60 s and retry
- **Shodan returns no results** → a zero internet footprint IS a valid finding (low attack surface)
- **SSE stuck on "queued"** → worker busy with another task (one task at a time); check `queue/running/`
- **Report truncated by bash heredoc errors** → agent must use write_file (fixed in the worker prompt since v7.4)
- **Model list not updating** → edit `profiles-models.json`; the API reads it per request

## Changelog

Current: **v7.4.2** — full history in [CHANGELOG.md](CHANGELOG.md).

- **v7.4.2** — write_file tooling fix, subprocess kill on timeout, renderer/skeleton fixes
- **v7.4** — agent toolset includes `file` tools; heredocs banned
- **v7.3** — 3-column layout, theme system (Dark/Light/Classic), SSE replay, exec summary badges
- **v6.4** — queue states, PWA, mobile responsive, profile/model dropdowns

## Related

- **[ShipCrawler 2.0 (Geo-Watch)](https://github.com/ShipCrawler/shipcrawler-2.0)** — Agentic maritime perimeter awareness for offshore wind (Baltic Hackathon line)
- **[Sirb](https://github.com/ahmdngi/sirb)** — Agnostic N-agent swarm framework that orchestrates ShipCrawler investigations in parallel
- **[ShipCrawler-Worker](https://github.com/ahmdngi/shipcrawler-worker)** — Vessel OSINT worker package for Sirb
- **[ShipCrawler-MCP](https://github.com/ahmdngi/shipcrawler-mcp)** — MCP server exposing ShipCrawler OSINT tools as typed MCP tools
- **Project Haris** — Maritime edge security platform (defensive counterpart)
