# Changelog

## v7.4 (2026-08-19)

### Changed
- **Agent toolset now includes `file`** — `worker.py` launches `hermes chat -t web,terminal,file`, so the agent gets the native `write_file` tool. Prompt now tells the agent to write reports via `write_file` (falls back to Python `open().write()` only if the tool is unavailable), and explicitly bans bash heredocs which truncated reports and corrupted `&` characters.

## v7.3d (2026-08-19)

### Added
- `deploy/` directory — tracked systemd unit files (`shipcrawler-dashboard.service`, `shipcrawler-worker.service`) with install README

### Fixed
- **Queue worker now supervised by systemd.** Previously run manually (`python3 worker.py &`), so a dead worker silently left queued scans in `pending/` forever (observed 2026-08-11 → 08-19). Now `shipcrawler-worker.service` polls the queue with `Restart=always`; the dashboard watchdog checks both services.
- README "Worker not picking up tasks" now documents the systemd workflow instead of the broken manual `python3 worker.py &` instructions.

## v7.3 (2026-07-16)

### Added
- SSE reconnection on page refresh — running task resumes automatically after refresh
- Live-task indicator in sidebar — warns when clicking history while a task is still running
- "Switch back" link in sidebar to restore live view without page refresh

### Fixed
- Page refresh no longer silently kills active SSE stream for running investigations
- Clicking old history entries no longer disconnects the current investigation's SSE feed
- Active task ID persisted in `localStorage` across page loads

### Changed
- Cache-buster bumped (core.js v26, sse.js v15)
- Version bumped to v7.3

## v7.2 (2026-07-15)

### Added
- Model and provider fields now persisted in `done.json` for every run
- Model value displayed in summary stats bar with icon
- Tool call counters (tool_calls, searches, sources, Shodan hits) in summary bar
- Icons on each summary stat for visual clarity
- Max-turns increased to 150 for complex vessel/person investigations

### Fixed
- Prompt now uses exact report directory path — agent no longer guesses
- Copy-back glob scoped to non-dated directories only (prevents deleting historical runs)
- `by-name` API endpoint now forwards `stats`, `model`, `provider` to frontend
- Frontend `renderToolCounts()` passes data correctly (was called with no argument)
- SSE `report_complete` event includes stats + model + provider
- Multiple glob match fallback picks most recent by mtime, not longest name
- Summary bar renders in single row with horizontal scroll on narrow screens

### Changed
- Renamed "OSINT Reconnaissance Terminal" → "Agentic OSINT Terminal"
- Dashboard-wide casing: "Shipcrawler" → "ShipCrawler"
- Badge: "Model Selection" label removed
- Version bumped to v7.2
