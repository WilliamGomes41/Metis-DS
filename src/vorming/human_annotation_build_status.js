(() => {
  const status = document.getElementById('annotation-build-status');
  if (status?.dataset.buildState !== 'running') return;

  const started = document.getElementById('annotation-build-started');
  const duration = document.getElementById('annotation-build-duration');
  const feedback = document.getElementById('annotation-build-feedback');
  async function refresh() {
    let updated = false;
    try {
      const response = await fetch(status.dataset.statusUrl, {cache: 'no-store'});
      if (response.ok) {
        const result = await response.json();
        updated = Boolean(result.attempt_id);
        if (updated && result.state !== 'running') {
          window.location.reload();
          return;
        }
        if (updated) {
          if (status.textContent !== result.message) status.textContent = result.message;
          if (result.started_at && !started.querySelector('time')) {
            const time = document.createElement('time');
            time.dateTime = result.started_at;
            const iso = new Date(result.started_at).toISOString();
            time.textContent = iso.slice(8, 10) + '-' + iso.slice(5, 7) + '-' + iso.slice(0, 4)
              + ' ' + iso.slice(11, 16) + ' UTC';
            started.replaceChildren(time);
          }
          duration.textContent = result.duration_seconds === null
            ? 'Niet vastgelegd' : result.duration_seconds + ' s';
        }
      }
    } catch (_) {
      // Keep showing the last confirmed status until the next refresh succeeds.
    }
    feedback.hidden = updated;
    feedback.textContent = updated ? '' : 'Verversen lukt tijdelijk niet. De laatst bekende status blijft zichtbaar.';
    setTimeout(refresh, 2000);
  }
  setTimeout(refresh, 2000);
})();
