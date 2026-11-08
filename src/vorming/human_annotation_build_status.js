(() => {
  const status = document.getElementById('annotation-build-status');
  const query = new URLSearchParams(window.location.search);
  async function refresh() {
    if (status.dataset.buildState !== 'running') return;
    try {
      const response = await fetch('/annotations/build/api?' + query);
      if (!response.ok) return;
      const result = await response.json();
      status.textContent = result.message;
      status.dataset.buildState = result.state;
      document.getElementById('annotation-build-detail').textContent = result.detail;
      document.getElementById('annotation-build-review').hidden = result.state !== 'succeeded';
    } finally {
      if (status.dataset.buildState === 'running') setTimeout(() => refresh().catch(() => {}), 2000);
    }
  }
  refresh().catch(() => {});
})();
