#!/usr/bin/env node
// Read-only, external section probe. Never exports URL, cookies, DOM or errors.
const fs = require('node:fs');
const crypto = require('node:crypto');
const { performance } = require('node:perf_hooks');

const sections = {
  '/login': '.login-card a[href="/auth/microsoft"], .login-card button[type="submit"]',
  '/ingest': '#ingest-submit',
  '/tree': 'h1:text-is("Documenten")',
  '/source-selection': '#source-selection h1:text-is("Bronselectie")',
  '/review': 'h1:text-is("Review")',
  '/publish': 'h1:text-is("Publiceren")',
};

async function probe(browser, {url, storageState, timeout = 30000}) {
  const target = new URL(url);
  if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password || !sections[target.pathname]) {
    throw new Error('invalid_target');
  }
  if (!Number.isInteger(timeout) || timeout < 100 || timeout > 300000) throw new Error('invalid_timeout');
  const result = {
    schema: 'metis.section-probe.v1', attempt_id: crypto.randomBytes(16).toString('hex'),
    route: target.pathname, started_at: new Date().toISOString(), finished_at: null,
    navigation: 'probe_error', navigation_started: false, status: null, response_request_id: null,
    response_complete: false, final_location: 'other', assertion: 'section-visible-v1',
    usability: 'not_checked', page_errors: 0, blocked_requests: 0,
  };
  const started = performance.now();
  let context;
  try {
    context = await browser.newContext({storageState, serviceWorkers: 'block', acceptDownloads: false});
    // Stop websocket mutations as well as form/fetch writes. All cross-origin
    // traffic is blocked: this probe observes an existing session, not login.
    await context.routeWebSocket('**/*', socket => socket.close());
    let firstNavigation;
    await context.route('**/*', async route => {
      const request = route.request();
      const u = new URL(request.url());
      const mainNavigation = request.isNavigationRequest() && request.frame() === page.mainFrame();
      const redirect = request.redirectedFrom();
      if (!['GET', 'HEAD'].includes(request.method()) || u.origin !== target.origin ||
          (mainNavigation && firstNavigation && !redirect)) {
        result.blocked_requests++;
        return route.abort();
      }
      if (mainNavigation && !firstNavigation) firstNavigation = request;
      const headers = {...request.headers()};
      // Do not leak a caller-provided value or propagate it to unrelated reads.
      delete headers['x-metis-attempt-id'];
      if (mainNavigation && u.pathname === target.pathname) headers['x-metis-attempt-id'] = result.attempt_id;
      return route.continue({headers});
    });
    const page = await context.newPage();
    page.on('pageerror', () => { result.page_errors = Math.min(1000, result.page_errors + 1); });
    page.on('response', response => {
      if (response.request() !== firstNavigation) return;
      result.status = response.status();
      const rid = response.headers()['x-metis-request-id'];
      if (/^[0-9a-f]{32}$/.test(rid || '')) result.response_request_id = rid;
    });
    page.on('requestfinished', request => {
      if (request === firstNavigation) result.response_complete = true;
    });
    try {
      result.navigation_started = true;
      await page.goto(target.href, {waitUntil: 'load', timeout});
      result.navigation = 'loaded';
    } catch (error) {
      result.navigation = error.name === 'TimeoutError' ? 'timeout' : 'network_error';
    }
    const current = new URL(page.url());
    result.final_location = current.origin === target.origin && current.pathname === target.pathname ? 'target' :
      current.origin === target.origin && current.pathname === '/login' ? 'login' : 'other';
    if (result.navigation === 'loaded' && result.final_location === 'target' && result.status === 200) {
      // A bounded visible-section assertion, not proof of every control or task.
      try {
        await page.locator(sections[target.pathname]).first().waitFor({state: 'visible',
          timeout: Math.max(1, timeout - (performance.now() - started))});
        result.usability = result.response_complete ? 'passed' : 'failed';
      } catch (_) { result.usability = 'failed'; }
    }
  } catch (_) {
    result.navigation = 'probe_error';
  } finally {
    if (context) await context.close().catch(() => {});
    result.finished_at = new Date().toISOString();
  }
  return result;
}

module.exports = {probe, sections};
if (require.main === module) {
  (async () => {
    const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
    // Secret-bearing input remains in the operator environment/local state file.
    const url = process.env.METIS_PROBE_URL;
    const output = process.argv[2];
    if (!url || !output) throw new Error('missing_input');
    const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
    try {
      const result = await probe(browser, {url, storageState: process.env.METIS_PROBE_STORAGE_STATE,
        timeout: Number(process.env.METIS_PROBE_TIMEOUT_MS || 30000)});
      fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n', {flag: 'wx', mode: 0o600});
    } finally { await browser.close(); }
  })().catch(() => {
    console.error('Section probe failed: check browser installation, target, local session file and new output path.');
    process.exitCode = 2;
  });
}
