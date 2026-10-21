// Fixed scenario shared by CI and the scoped investigation worker. No login,
// evaluation of supplied code, domain POST, downloads, trace or HAR capture.
const crypto = require('node:crypto');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const equal = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());

function compareInventory(expected, observed, sourceIds) {
  const ids = expected.map(row => row.object_id);
  const visible = observed.map(row => row.id);
  const actualSource = observed.filter(row => row.source).map(row => row.id);
  const links = observed.filter(row => row.linked).length;
  return [
    {id:'inventory_identity', verdict:equal(ids, visible) ? 'pass':'fail', expected:ids.length, observed:visible.length},
    {id:'source_partition', verdict:equal(sourceIds, actualSource) ? 'pass':'fail', expected:sourceIds.length, observed:actualSource.length},
    {id:'review_links', verdict:links === ids.length ? 'pass':'fail', expected:ids.length, observed:links},
  ];
}

async function run(input) {
  const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE);
  const origin = new URL(input.origin).origin;
  if (origin !== input.origin) throw Error('invalid_origin');
  const browser = await chromium.launch({headless:true, executablePath:process.env.METIS_BROWSER_EXECUTABLE});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}, serviceWorkers:'block', acceptDownloads:false});
    await context.addCookies([{name:'metis_view_check',value:input.token,url:origin,
      httpOnly:true,secure:origin.startsWith('https:'),sameSite:'Strict'}]);
    await context.route('**/*', async route => {
      const request = route.request();
      const url = new URL(request.url());
      const paths = ['/source-selection','/review','/inzicht/document/passages'];
      if (url.origin !== origin || request.method() !== 'GET' ||
          !(paths.includes(url.pathname) || url.pathname.startsWith('/brand/'))) return route.abort();
      return route.continue();
    });
    await context.routeWebSocket('**/*', socket => socket.close());
    // Chromium networking still needs the origin's private network deployment
    // boundary. Its application capability independently rejects other routes.
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    let pageErrors = 0;
    page.on('pageerror', () => pageErrors++);
    const query = new URLSearchParams({document:input.document});
    const selection = await page.goto(origin+'/source-selection?'+query);
    if (selection.status() !== 200) throw Error('selection_unavailable');
    // The export intentionally has Content-Disposition: attachment. Navigation
    // would start a download, which this context forbids. Fetch its JSON from
    // the scoped same-origin page; browser routing and capability checks apply.
    const exported = await page.evaluate(async url => {
      const response = await fetch(url, {credentials:'same-origin', redirect:'error'});
      if (response.status !== 200) throw Error('export_unavailable');
      return response.json();
    }, origin+'/inzicht/document/passages?'+query+'&format=json');
    if (exported.snapshot_id !== input.document || exported.objects_revision !== input.revision || exported.rows.length>1000) throw Error('context_changed');
    const selected = await page.locator('[data-source-document][data-selected="true"]').getAttribute('data-source-document');
    const selectedValue = await page.locator('select[name=document]').inputValue();
    const review = await page.goto(origin+'/review?'+query+'&task=inventory');
    if (review.status() !== 200 || new URL(page.url()).pathname !== '/review') throw Error('review_unavailable');
    await page.locator('.review-passage-inventory').first().waitFor();
    // Disclosures contain source rows too. Open them before observing/capturing.
    await page.locator('details').evaluateAll(nodes => nodes.forEach(node => {node.open=true;}));
    const observed = await page.locator('[data-passage-id], [data-source-record]').evaluateAll((nodes, document) =>
      nodes.map(node => ({id:node.dataset.passageId || node.dataset.sourceRecord,
        source:!!node.dataset.sourceRecord, linked:[...node.querySelectorAll('a[href]')].some(a => {
          const url = new URL(a.href); return url.searchParams.get('document')===document &&
            url.searchParams.get('object')===(node.dataset.passageId || node.dataset.sourceRecord);
        })})), input.document);
    const checks = compareInventory(exported.rows, observed, input.source_ids);
    checks.push({id:'source_selection', verdict:selected===input.document && selectedValue===input.document?'pass':'fail',
      expected:1, observed:Number(selected===input.document && selectedValue===input.document)});
    checks.push({id:'browser_errors',verdict:pageErrors?'fail':'pass',expected:0,observed:pageErrors});
    const screenshot = await page.screenshot({type:'png',fullPage:false});
    return {checks,browser_version:browser.version(),screenshot:screenshot.toString('base64'),
      // Limits are explicit: these checks do not certify clinical correctness.
      coverage:{inventory:'all_rows', clinical:'not_established', source_text:'not_established'},
      scenario_sha256:hash(require('node:fs').readFileSync(__filename))};
  } finally { await browser.close(); }
}

module.exports = {compareInventory};
if (require.main === module) {
  let raw='';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => {raw+=chunk; if(raw.length>1024*1024) process.exit(2);});
  process.stdin.on('end', () => run(JSON.parse(raw)).then(result => process.stdout.write(JSON.stringify(result)))
    .catch(() => process.exit(1)));
}
