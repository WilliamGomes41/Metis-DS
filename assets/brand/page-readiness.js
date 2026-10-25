// Smallest task-specific evidence for the eight main pages. Shared by the
// user's hidden-frame check and the external Playwright section probe.
// No requests, mutations, private text, or new status authority.
(function (scope) {
  function readPageReadiness(path) {
    const visible = selector => [...document.querySelectorAll(selector)].some(node =>
      !node.closest('[hidden]') && node.getClientRects().length > 0);
    const requirements = {
      '/': ['navigation_available', '.home-tiles a[href="/ingest"]'],
      '/ingest': ['upload_form_available', 'form[action="/ingest"] input[type="file"]'],
      '/source-selection': ['document_choice_and_status', '#source-document'],
      '/review': ['review_inventory_or_empty', '.review-passage-inventory, .review-task-card, .review-empty, .doc-list .doc-card'],
      '/publish': ['publication_inventory_or_empty', '.doc-list .doc-card, .doc-list > p'],
      '/tree': ['document_inventory_or_empty', '#documents .document-row, #documents .document-empty'],
      '/settings': ['settings_navigation_available', '.room a[href="/accounts"]'],
      '/inzicht': ['document_inventory_loaded', '#d-table[data-readiness="ready"]'],
    };
    const [expected, selector] = requirements[path] || ['supported_page', '[data-never-ready]'];
    const result = {step: 'page_usability', expected, observed: 'pending', verdict: 'not_established'};
    if (path === '/inzicht') {
      const table = document.querySelector('#d-table');
      result.observed = table?.dataset.readiness || 'pending';
      result.request = {route: '/inzicht/api/documents', state: table?.dataset.requestState || 'not_observed',
        reference: /^[0-9a-f]{32}$/.test(table?.dataset.requestId || '') ? table.dataset.requestId : null};
      if (['partial', 'error'].includes(result.observed)) return result;
    }
    if (visible(selector)) {
      if (path === '/source-selection' && !visible('[data-source-document], [data-source-empty]')) return result;
      result.verdict = 'pass'; result.observed = 'ready';
    }
    return result;
  }
  if (typeof module !== 'undefined') module.exports = readPageReadiness;
  else scope.MetisPageReadiness = readPageReadiness;
})(typeof window !== 'undefined' ? window : globalThis);
