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

// HTML collapsible ASCII whitespace only; case, punctuation, Unicode, and
// sentence/condition ordering remain significant. Expected values come from
// the existing revision-pinned passage export, never re-materialisation.
const normalize = text => String(text ?? '').replace(/[\t\n\f\r ]+/g, ' ').replace(/^ | $/g, '');
function compareContent(expected, observed, sourceIds) {
  const source = new Set(sourceIds);
  const byId = new Map(observed.map(row => [row.id, row]));
  const supported = expected.filter(row => typeof row.content?.clean_text === 'string' && row.content.clean_text.length > 0);
  const matched = supported.filter(row => normalize(row.content.clean_text) === normalize(byId.get(row.object_id)?.text));
  const contexts = expected.filter(row => !source.has(row.object_id));
  const contextMatches = contexts.filter(row => normalize(row.source_label_hint?.label) === normalize(byId.get(row.object_id)?.sourceLabel));
  const ids = expected.filter(row => !source.has(row.object_id)).map(row => row.object_id);
  const visible = observed.filter(row => !row.source).map(row => row.id);
  return [
    {id:'rendered_text', verdict:matched.length !== supported.length ? 'fail' : supported.length === expected.length ? 'pass' : 'not_established', expected:supported.length, observed:matched.length},
    {id:'rendered_context', verdict:contextMatches.length === contexts.length ? 'pass':'fail', expected:contexts.length, observed:contextMatches.length},
    {id:'rendered_order', verdict:JSON.stringify(ids) === JSON.stringify(visible) ? 'pass':'fail', expected:ids.length, observed:visible.length},
  ];
}

async function run(input) {
  const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE);
  const origin = new URL(input.origin).origin;
  if (origin !== input.origin) throw Error('invalid_origin');
  const browser = await chromium.launch({headless:true, executablePath:process.env.METIS_BROWSER_EXECUTABLE});
  const started = Date.now();
  let step = 'browser_setup';
  let expectedState = 'restricted_context';
  const requests = [];
  const assets = [];
  let page;
  let coverage = {normalization:'HTML_ASCII_whitespace', fields:['content.clean_text','source_label_hint.label'],
    unchecked_fields:['structured_conditions', 'structured_exceptions', 'source_locators', 'source_context'],
    clinical:'not_established', source_extraction:'not_established'};
  const diagnose = observed => ({step, expected:expectedState, observed, elapsed_ms:Date.now()-started, requests:[...requests,...assets.filter(row=>row.state!=='completed').slice(0,4)].map(row=>({...row}))});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}, serviceWorkers:'block', acceptDownloads:false});
    await context.addCookies([{name:'metis_view_check',value:input.token,url:origin,
      httpOnly:true,secure:origin.startsWith('https:'),sameSite:'Strict'}]);
    await context.route('**/*', async route => {
      const request = route.request();
      const url = new URL(request.url());
      const paths = ['/source-selection','/review','/formation-problems','/inzicht/document/passages'];
      if (url.origin !== origin || request.method() !== 'GET' ||
          !(paths.includes(url.pathname) || url.pathname.startsWith('/brand/'))) return route.abort();
      return route.continue();
    });
    await context.routeWebSocket('**/*', socket => socket.close());
    // Chromium networking still needs the origin's private network deployment
    // boundary. Its application capability independently rejects other routes.
    page = await context.newPage();
    page.on('request', request => {
      const route = new URL(request.url()).pathname;
      const asset = route.startsWith('/brand/');
      if (asset ? assets.length >= 8 : !['/source-selection','/review','/formation-problems','/inzicht/document/passages'].includes(route) || requests.length >= 12) return;
      const row = {route:asset ? '/brand/*' : route, state:'pending', reference:null};
      (asset ? assets : requests).push(row);
      request._viewObservation = row;
    });
    page.on('response', response => {
      const row = response.request()._viewObservation;
      if (!row) return;
      row.status = response.status();
      const reference = response.headers()['x-metis-request-id'];
      if (/^[0-9a-f]{32}$/.test(reference || '')) row.reference = reference;
      row.state = 'response_started';
    });
    page.on('requestfinished', request => {if(request._viewObservation) request._viewObservation.state='completed';});
    page.on('requestfailed', request => {if(request._viewObservation) request._viewObservation.state='failed';});
    page.setDefaultTimeout(10000);
    let pageErrors = 0;
    page.on('pageerror', () => pageErrors++);
    const query = new URLSearchParams({document:input.document});
    step='source_selection'; expectedState='selected_document_and_controls';
    const selection = await page.goto(origin+'/source-selection?'+query);
    if (selection.status() !== 200) throw Error('selection_unavailable');
    // The export intentionally has Content-Disposition: attachment. Navigation
    // would start a download, which this context forbids. Fetch its JSON from
    // the scoped same-origin page; browser routing and capability checks apply.
    step='stored_inventory'; expectedState='same_document_revision_and_bounded_export';
    const exported = await page.evaluate(async url => {
      const response = await fetch(url, {credentials:'same-origin', redirect:'error'});
      if (response.status !== 200) throw Error('export_unavailable');
      return response.json();
    }, origin+'/inzicht/document/passages?'+query+'&format=json');
    if (exported.snapshot_id !== input.document || exported.objects_revision !== input.revision || exported.rows.length>1000) throw Error('context_changed');
    const selected = await page.locator('[data-source-document][data-selected="true"]').getAttribute('data-source-document');
    const selectedValue = await page.locator('select[name=document]').inputValue();
    step='formation_problems'; expectedState='problem_room_and_existing_actions';
    // Problem details now share the selected source page. Observe the same
    // captured page instead of repeating its potentially deep document read.
    await page.getByRole('heading', {name:'Vormingsproblemen', exact:true}).waitFor();
    coverage.formation_problems='first_page_read_only';
    step='review_inventory'; expectedState='visible_inventory_with_stored_text';
    const review = await page.goto(origin+'/review?'+query+'&task=inventory');
    if (review.status() !== 200 || new URL(page.url()).pathname !== '/review') throw Error('review_unavailable');
    await page.locator('.review-passage-inventory').first().waitFor();
    // Disclosures contain source rows too. Open them before observing/capturing.
    await page.locator('details').evaluateAll(nodes => nodes.forEach(node => {node.open=true;}));
    step='rendered_content'; expectedState='visible_stored_fields';
    const observed = await page.locator('[data-passage-id], [data-source-record]').evaluateAll((nodes, documentId) => {
      const renderedText = node => node && node.getClientRects().length && !node.closest('[hidden]') &&
        getComputedStyle(node).visibility !== 'hidden' ? node.innerText : null;
      return nodes.map(node => ({id:node.dataset.passageId || node.dataset.sourceRecord,
        source:!!node.dataset.sourceRecord,
        sourceLabel:renderedText(node.querySelector('[data-source-label-hint]')),
        text:renderedText(node.dataset.sourceRecord ? node.querySelector('p') : node.querySelector('.review-row-title')),
        linked:[...node.querySelectorAll('a[href]')].some(a => {
          const url = new URL(a.href); return url.searchParams.get('document')===documentId &&
            url.searchParams.get('object')===(node.dataset.passageId || node.dataset.sourceRecord);
        })}));
    }, input.document);
    const checks = [...compareInventory(exported.rows, observed, input.source_ids), ...compareContent(exported.rows, observed, input.source_ids)];
    coverage = {...coverage, objects_checked:exported.rows.filter(row => typeof row.content?.clean_text === 'string' && row.content.clean_text.length > 0).map(row => row.object_id),
      objects_unchecked:exported.rows.filter(row => typeof row.content?.clean_text !== 'string' || !row.content.clean_text.length).map(row => row.object_id),
      object_order:'knowledge_rows_only_source_groups_not_checked', inventory:'all_rows'};
    checks.push({id:'source_selection', verdict:selected===input.document && selectedValue===input.document?'pass':'fail',
      expected:1, observed:Number(selected===input.document && selectedValue===input.document)});
    checks.push({id:'browser_errors',verdict:pageErrors?'fail':'pass',expected:0,observed:pageErrors});
    step='screen_evidence'; expectedState='bounded_screenshot';
    const screenshot = await page.screenshot({type:'png',fullPage:false});
    return {checks,browser_version:browser.version(),screenshot:screenshot.toString('base64'),
      // Limits are explicit: these checks do not certify clinical correctness.
      coverage, diagnosis:diagnose(checks.some(row => row.verdict === 'fail') ? 'difference' : checks.some(row => row.verdict === 'not_established') ? 'not_established' : 'matched'),
      scenario_sha256:hash(require('node:fs').readFileSync(__filename))};
  } catch (error) {
    // No exception text, URL queries, headers, cookies, or DOM in diagnostics.
    return {incomplete:true, checks:['inventory_identity','source_partition','review_links','rendered_text','rendered_order','rendered_context','source_selection','browser_errors']
      .map(id => ({id,verdict:'not_established',expected:0,observed:0})),
      coverage, diagnosis:diagnose(error.name === 'TimeoutError' ? 'timeout' : 'not_established'), browser_version:browser.version()};
  } finally { await browser.close(); }
}

module.exports = {compareInventory, compareContent};
if (require.main === module) {
  let raw='';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => {raw+=chunk; if(raw.length>1024*1024) process.exit(2);});
  process.stdin.on('end', () => run(JSON.parse(raw)).then(result => process.stdout.write(JSON.stringify(result)))
    .catch(() => process.exit(1)));
}
