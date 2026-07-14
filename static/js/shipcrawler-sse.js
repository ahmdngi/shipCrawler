/* Shipcrawler SSE v7 — Real-time structured streaming client */
const ShipcrawlerSSE = (() => {
  function connect(taskId, callbacks) {
    const evtSource = new EventSource(`/api/stream/${taskId}`);

    evtSource.addEventListener('phase_start', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onPhaseStart) callbacks.onPhaseStart(data);
    });

    evtSource.addEventListener('phase_output', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onPhaseOutput) callbacks.onPhaseOutput(data);
    });

    evtSource.addEventListener('structured_output', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onStructuredOutput) callbacks.onStructuredOutput(data);
    });

    evtSource.addEventListener('phase_complete', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onPhaseComplete) callbacks.onPhaseComplete(data);
    });

    evtSource.addEventListener('phase_error', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onPhaseError) callbacks.onPhaseError(data);
    });

    evtSource.addEventListener('report_complete', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onReportComplete) callbacks.onReportComplete(data);
    });

    evtSource.addEventListener('queued', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onQueued) callbacks.onQueued(data);
    });

    evtSource.addEventListener('done', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onDone) callbacks.onDone(data);
      evtSource.close();
    });

    evtSource.addEventListener('error', () => {
      if (callbacks.onError) callbacks.onError('Connection lost');
      evtSource.close();
    });

    return evtSource;
  }

  function loadReport(taskId, callbacks) {
    fetch(`/api/report/${taskId}`)
      .then(r => r.json())
      .then(data => {
        if (callbacks.onReportData) callbacks.onReportData(data);
      })
      .catch(err => {
        if (callbacks.onError) callbacks.onError('Failed to load report: ' + err.message);
      });
  }

  return { connect, loadReport };
})();
