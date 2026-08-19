# ShipCrawler systemd deployment

Both the dashboard and the queue worker run as systemd services on the deployment host.

## Install

```bash
sudo cp shipcrawler-dashboard.service /etc/systemd/system/
sudo cp shipcrawler-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shipcrawler-dashboard.service
sudo systemctl enable --now shipcrawler-worker.service
```

## Services

| Service | Runs | Restart policy |
|---------|------|----------------|
| `shipcrawler-dashboard.service` | Flask app, port 5000 | always |
| `shipcrawler-worker.service` | worker.py, polls `queue/pending/` | always |

## Why both are supervised

The worker daemon historically ran manually (`python3 worker.py &`). If it died,
scans queued in `queue/pending/` but never executed — silently. `Restart=always`
plus the watchdog cron (`shipcrawler-dashboard-watchdog.sh`) keeps both alive.

## Dispatch check

```bash
systemctl is-active shipcrawler-dashboard.service shipcrawler-worker.service
```

If a run is queued but not starting, the worker service is down — restart it:

```bash
sudo systemctl restart shipcrawler-worker.service
```
