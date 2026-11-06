"""Actual recommendation controls follow the existing suitability contract.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import os
from pathlib import Path
import subprocess

import pytest

from tests.test_ko_receipt_ui import prepared


@pytest.mark.skipif(not os.environ.get('METIS_BROWSER_EXECUTABLE'), reason='Chromium verification is opt-in')
@pytest.mark.parametrize('javascript', [True, False])
def test_closed_recommendation_discrepancy_controls(tmp_path, production_console, monkeypatch, javascript):
    console, sid, reviewer, obj, client, page, data = prepared(tmp_path, production_console, monkeypatch)
    assert page.status_code == 200
    source = tmp_path / 'review.html'
    source.write_text(page.text)
    script = tmp_path / 'review.cjs'
    script.write_text('''
const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const http=require('node:http');
const assert=require('node:assert/strict');
(async()=>{
  const server=http.createServer((req,res)=>{
    if(req.url.startsWith('/brand/console.css')){res.setHeader('Content-Type','text/css');res.end(fs.readFileSync(process.argv[3]));}
    else if(req.url==='/review'){res.setHeader('Content-Type','text/html');res.end(fs.readFileSync(process.argv[2]));}
    else {res.statusCode=404;res.end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,args:['--no-sandbox']});
  try {
    const page=await browser.newPage({javaScriptEnabled:JSON.parse(process.argv[4])});
    page.setDefaultTimeout(7000);
    await page.goto(`http://127.0.0.1:${server.address().port}/review`,{waitUntil:'domcontentloaded'});
    await page.locator('[name=suitability][value=ja]').check();
    const control=page.locator('[name=source_discrepancy][value=context_ontbreekt]');
    await control.check();
    await page.locator('[name=suitability][value=geen_kenniseenheid]').check();
    assert.equal(await page.locator('[data-review-question=completeness]').isVisible(),true);
    assert.equal(await page.locator('[data-review-step=discrepancy]').isVisible(),false);
    if(JSON.parse(process.argv[4])) {
      assert.equal(await control.isDisabled(),true);
      assert.deepEqual(await page.locator('[data-review-form]').evaluate(form=>new FormData(form).getAll('source_discrepancy')),[]);
    }
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exit(1);});
''')
    stylesheet = Path(__file__).resolve().parents[1] / 'assets/brand/console.css'
    subprocess.run(['node', str(script), str(source), str(stylesheet), json.dumps(javascript)],
                   check=True, timeout=45)
