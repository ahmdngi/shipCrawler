#!/usr/bin/env bash
# Start claude-ds refactor session — runs claude inside a tmux session
# User attaches with: tmux attach -t shipcrawler-refactor

set -euo pipefail

TMUX_SESSION="shipcrawler-refactor"
PROXY_PORT=3800
KEY_FILE="/root/.deepseek-key"
PROXY_SCRIPT="/root/translator-proxy.mjs"

# Start proxy if not running
if ! curl -sf "http://localhost:${PROXY_PORT}/health" >/dev/null 2>&1; then
  echo "Starting DeepSeek proxy on :${PROXY_PORT}..."
  DEEPSEEK_API_KEY="$(cat "$KEY_FILE")" nohup node "$PROXY_SCRIPT" > /tmp/claude-proxy.log 2>&1 &
  for i in $(seq 1 10); do
    if curl -sf "http://localhost:${PROXY_PORT}/health" >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
fi

API_KEY=$(cat "$KEY_FILE")

# Create tmux session
tmux new-session -d -s "$TMUX_SESSION" -x 180 -y 50

# Send command to start claude in the session with the refactoring task
tmux send-keys -t "$TMUX_SESSION" \
  "cd /root/shipcrawler-v4 && \
   ANTHROPIC_BASE_URL=http://localhost:${PROXY_PORT} \
   ANTHROPIC_API_KEY='${API_KEY}' \
   claude 'Refactor the Shipcrawler v4 OSINT dashboard per REFACTOR_SPEC.md. 
   
   GOAL: Transform the static polling dashboard into a dynamic real-time website.
   
   KEY CHANGES:
   1. worker_progress.py — new module that writes JSON Lines progress to queue/progress/<task_id>.log
   2. worker.py — rewrite to run shipcrawler-parallel orchestrator scripts directly (not hermes CLI), emitting progress events. Use: from worker_progress import write_progress; write_progress(task_id, step, detail, source)
   3. routes/api.py — add GET /api/stream/<task_id> SSE endpoint that tails the progress log and sends events to the browser
   4. static/js/shipcrawler-sse.js — rewrite to use EventSource for real-time streaming of investigation steps
   5. static/js/shipcrawler-core.js — update doSearch() to use SSE instead of polling, add animated report transition
   6. static/js/shipcrawler-ui.js — add live terminal feed renderer, step badge colors, staggered card entrance animations
   7. static/css/shipcrawler.css — add styles for live terminal, colored step badges, report animations
   8. templates/index.html — replace static terminal-loader placeholder with dynamic live-feed area
   
   Use gstack skills (/plan, /spec, /review) as appropriate. Be thorough — test each change.
   Implement the changes in the order listed above.
   Do NOT break existing API contracts.
   Keep the queue-based architecture but add streaming on top.
   All dashboards bind to 100.72.133.89.
   After each file change, verify it makes sense before moving to the next.'" Enter

echo "✅ Started claude-ds in tmux session: ${TMUX_SESSION}"
echo "   Attach: tmux attach -t ${TMUX_SESSION}"
echo "   Detach: Ctrl+B D"
