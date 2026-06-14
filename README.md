# Shipcrawler V4 — Hermes-Powered OSINT Dashboard

Flask-based vessel OSINT dashboard with SSE real-time progress, Leaflet maps, Shodan integration, and Hermes agent-backed research queue.

**Port:** 9091 (Tailscale `100.72.133.89:9091`)

## Features

- Vessel research with real-time SSE progress from backend workers
- Leaflet map with AIS, satellite, marine traffic overlays
- Hermes cron-powered research queue (`worker.py` + queue/)
- No caching — every search runs fresh
- Systemd-managed: `shipcrawler-v4.service` + `shipcrawler-v4-worker.service`

## Quick Start

```bash
cd /root/shipcrawler-v4
source venv/bin/activate
python3 app.py
```

## Repo

`git@github.com:ahmdngi/shipcrawler-v4.git`
