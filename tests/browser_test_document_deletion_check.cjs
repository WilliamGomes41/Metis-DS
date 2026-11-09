const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const base=process.env.METIS_BROWSER_BASE, output=process.env.METIS_BROWSER_OUTPUT;
  const m=await (await fetch(base+'/browser-manifest')).json();
  const browser=await chromium.launch({headless:true,executablePath:process.env.METIS_BROWSER_EXECUTABLE});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  async function api(oid) {return page.evaluate(async ({oid,key}) =>
    (await fetch('/public/v1/knowledge/'+oid,{headers:{Authorization:'Bearer '+key}})).status,{oid,key:m.key});}
  await page.goto(base+'/login');
  await page.locator('[name=username]').fill(m.username);
  await page.locator('[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(u=>u.pathname==='/'),page.locator('button[type=submit]').click()]);
  assert.equal(await api(m.old_object),200);
  await page.goto(base+'/tree');
  const row=page.locator('details.document-row').filter({has:page.locator(`a[href="/documents/test-delete?document=${m.document}"]`)});
  await row.locator('summary').first().click();
  await row.getByRole('link',{name:'Hele testdocument verwijderen',exact:true}).click();
  assert.match(await page.locator('body').innerText(),/Publicaties die verdwijnen: 1/);
  assert.match(await page.locator('body').innerText(),/Bronversie 1.0/);
  assert.match(await page.locator('body').innerText(),/Bronversie 2.0/);
  assert.match(await page.locator('body').innerText(),/Annotaties: 1/);
  assert.match(await page.locator('body').innerText(),/De controlehistorie blijft bewaard/);
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:`${output}/test-delete-${width}.png`,fullPage:true});
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:output+'/test-delete-zoom.png',fullPage:true});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  const posts=[];page.on('request',r=>{if(r.method()==='POST' && new URL(r.url()).pathname==='/documents/test-delete')posts.push(r);});
  const submit=page.getByRole('button',{name:'Hele testdocument permanent verwijderen',exact:true});
  await page.locator('[name=confirm_title]').fill(m.title);
  await page.locator('[name=reason]').fill('Testgegevens opruimen voor annotatie.');
  await submit.click();
  assert.equal(posts.length,0,'unchecked test confirmation must not submit');
  await page.locator('[name=confirmed_test]').check();
  await page.locator('[name=confirm_title]').fill('Verkeerd document');
  await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/documents/test-delete' && r.status()===400),submit.click()]);
  await page.getByRole('alert').filter({hasText:'Typ de documenttitel exact over.'}).waitFor();
  assert.equal(await page.locator('[name=reason]').inputValue(),'Testgegevens opruimen voor annotatie.');
  assert.equal(await api(m.old_object),200);
  await page.screenshot({path:output+'/test-delete-error.png',fullPage:true});
  await page.locator('[name=confirm_title]').fill(m.title);
  await page.locator('[name=confirmed_test]').check();
  await Promise.all([page.waitForURL(u=>u.pathname==='/documents/test-delete/receipt'),submit.click()]);
  assert.match(await page.getByRole('status').innerText(),/Versies: 2. Publicaties: 1/);
  await page.reload();
  assert.equal(await api(m.old_object),404);
  assert.equal(await api(m.other_object),200);
  await page.screenshot({path:output+'/test-delete-receipt.png',fullPage:true});
  await page.getByRole('link',{name:'Terug naar Documenten',exact:true}).click();
  assert.equal(await page.getByText(m.title,{exact:true}).count(),0);
  assert.match(await page.locator('body').innerText(),/Ander document/);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/result.json',JSON.stringify({wholeLineage:true,confirmation:true,inputPreserved:true,
    receiptReload:true,apiRemoved:true,otherDocumentPreserved:true,zoom:200,widths:[1440,390]},null,2));
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
