// Controlled HTTP fixtures test the real browser probe, not production Azure.
const assert = require('node:assert/strict');
const http = require('node:http');
const {once} = require('node:events');
const {probe} = require('../scripts/probe_section.cjs');
const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  let writes = 0;
  const attempts = [];
  const server = http.createServer((req, res) => {
    if (req.method === 'POST') { writes++; res.end(); return; }
    const mode = new URL(req.url, 'http://local').searchParams.get('mode');
    attempts.push(req.headers['x-metis-attempt-id']);
    if (mode === 'stall') return setTimeout(() => {res.writeHead(200); res.end('late');}, 700);
    if (mode === 'gateway') { res.writeHead(502); res.end('gateway'); return; }
    if (mode === 'denied') { res.writeHead(403); res.end('denied'); return; }
    if (mode === 'login') { res.writeHead(303, {location:'/login'}); res.end(); return; }
    res.setHeader('x-metis-request-id', 'b'.repeat(32));
    res.setHeader('content-type', 'text/html');
    res.end(mode === 'empty' ? '<h1>Unrelated page</h1>' :
      '<section id="source-selection"><h1>Bronselectie</h1></section>' +
      '<script>fetch("/write",{method:"POST",body:"secret"});</script>');
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const port = server.address().port;
  let browser;
  try {
    browser = await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE});
    const base = `http://127.0.0.1:${port}/source-selection`;
    const good = await probe(browser, {url:base+'?private=never-export', timeout:3000});
    assert.equal(good.usability, 'passed');
    assert.equal(good.response_request_id, 'b'.repeat(32));
    assert.equal(good.response_complete, true);
    assert.ok(attempts.includes(good.attempt_id));
    assert.equal(writes, 0);
    assert.ok(good.blocked_requests >= 1);
    assert.ok(!JSON.stringify(good).includes('never-export'));
    const empty = await probe(browser, {url:base+'?mode=empty', timeout:300});
    assert.equal(empty.status, 200); assert.equal(empty.usability, 'failed');
    const denied = await probe(browser, {url:base+'?mode=denied', timeout:1000});
    assert.equal(denied.status, 403); assert.equal(denied.usability, 'not_checked');
    const login = await probe(browser, {url:base+'?mode=login', timeout:1000});
    assert.equal(login.final_location, 'login'); assert.equal(login.usability, 'not_checked');
    const gateway = await probe(browser, {url:base+'?mode=gateway', timeout:1000});
    assert.equal(gateway.status, 502); assert.equal(gateway.response_request_id, null);
    const stalled = await probe(browser, {url:base+'?mode=stall', timeout:150});
    assert.equal(stalled.navigation, 'timeout'); assert.equal(stalled.usability, 'not_checked');
    await new Promise(resolve => server.close(resolve));
    const unavailable = await probe(browser, {url:base, timeout:1000});
    assert.equal(unavailable.navigation, 'network_error'); assert.equal(unavailable.status, null);
    assert.equal(unavailable.usability, 'not_checked');
    console.log('7 real-browser scenarios passed; writes blocked; secrets excluded.');
  } finally {
    if (browser) await browser.close(); server.close();
  }
})().catch(error => { console.error(error); process.exitCode=1; });
