/* Shipcrawler SSE — Real-time search progress */
const ShipcrawlerSSE = (() => {
  function connect(taskId, callbacks) {
    const evtSource = new EventSource(`/api/stream/${taskId}`);

    evtSource.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      if (callbacks.onProgress) callbacks.onProgress(data);
      if (data.status === 'done' && data.data && callbacks.onComplete) {
        callbacks.onComplete(data.data);
        evtSource.close();
      }
      if (data.status === 'error' && callbacks.onError) {
        callbacks.onError(data.message);
        evtSource.close();
      }
    });

    evtSource.addEventListener('error', () => {
      if (callbacks.onError) callbacks.onError('Connection lost');
      evtSource.close();
    });

    return evtSource;
  }

  return { connect };
})();
