# Changelog

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
