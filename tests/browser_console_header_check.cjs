// Keyboard, responsive layout and navigation in the actual console header.
const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE);
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {withBrowserEvidence}=require('./browser_evidence.cjs');

async function checkConsoleHeader(page, base, directory, isReviewer) {
  const routes = isReviewer ? [['/publish', 403, 'Actie niet uitgevoerd']] : [
    ['/', 200, 'Vorming'], ['/ingest', 200, 'Document inleveren'],
    ['/source-selection', 200, 'Vorming'], ['/review', 200, 'Review'],
    ['/publish', 200, 'Publiceren'], ['/tree', 200, 'Documenten'],
    ['/settings', 200, 'Instellingen'], ['/over-console', 200, 'Metis uitgelegd'],
  ];
  for (const [width, height] of isReviewer ? [[320, 844]] : [[390, 844], [1360, 900], [1440, 900]]) {
    await page.setViewportSize({width, height});
    for (const [path, status, heading] of width <= 390 ? routes : [routes[1]]) {
      const response = await page.goto(base + path);
      assert.equal(response.status(), status, path);
      await page.getByRole('heading', {name:heading, exact:true}).first().waitFor();
      const header = page.locator('header.topbar');
      const menu = header.getByRole('button', {name:/Menu/});
      if (path === '/ingest' || isReviewer)
        await page.screenshot({path:directory + '/console-header-' + width + '-start.png'});
      await page.keyboard.press('Tab');
      const skip = page.getByRole('link', {name:'Naar hoofdinhoud', exact:true});
      assert.equal(await skip.count(), 1, path + ' exposes one skip link');
      assert.ok(await skip.evaluate(link => link === document.activeElement), path + ' first Tab');
      if (path === '/ingest' && width === 390)
        await page.screenshot({path:directory + '/console-header-390-skip-link.png'});
      await page.keyboard.press('Enter');
      const main = page.getByRole('main');
      assert.equal(await main.count(), 1, path);
      assert.ok(await main.evaluate(node => node === document.activeElement), path + ' skip target');
      assert.equal(await header.evaluate(node => node.closest('main') !== null), false, path);
      if (path === '/over-console') assert.equal(await main.getAttribute('id'), 'uitleg-inhoud');
      if (isReviewer) assert.equal(await main.locator('[data-error-code]').count(), 1);

      if (width <= 390) {
        assert.equal(await menu.getAttribute('aria-expanded'), 'false', path);
        assert.equal(await header.getByRole('button', {name:'Uitloggen'}).count(), 0, path);
        if (path === '/ingest' || isReviewer) {
          if (!isReviewer) {
            assert.match(await menu.innerText(), /Inleveren/);
            const height = (await header.boundingBox()).height;
            assert.ok(height <= 160, '390 px compact header');
            fs.writeFileSync(directory + '/console-header-geometry.json',
              JSON.stringify({viewport:width, closedHeaderHeight:height, maxHeight:160}));
          }
          await menu.focus();
          await page.keyboard.press(isReviewer ? 'Space' : 'Enter');
          assert.equal(await menu.getAttribute('aria-expanded'), 'true');
          await page.keyboard.press('Tab');
          assert.ok(await header.locator('nav.rooms a').first()
            .evaluate(link => link === document.activeElement), 'keyboard reaches first menu link');
          await header.getByRole('button', {name:'Uitloggen'}).waitFor();
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no horizontal overflow');
          await page.screenshot({path:directory + '/console-header-' + width + '-open.png'});
          await page.keyboard.press('Escape');
          assert.equal(await menu.getAttribute('aria-expanded'), 'false');
          assert.ok(await menu.evaluate(button => button === document.activeElement), 'Escape restores focus');
          if (!isReviewer) {
            await menu.click();
            const theme = header.getByRole('button', {name:'Wissel tussen lichte en donkere modus'});
            const previous = await theme.getAttribute('aria-pressed');
            await theme.click();
            assert.notEqual(await theme.getAttribute('aria-pressed'), previous);
            await theme.click();
            await header.getByRole('link', {name:'Vorming', exact:true}).click();
            assert.equal(new URL(page.url()).pathname, '/source-selection');
          }
        }
      } else {
        assert.equal(await menu.count(), 0);
        const centers = await header.locator('.brand, .rooms, .theme-toggle, .who')
          .evaluateAll(nodes => nodes.map(node => {
            const rect = node.getBoundingClientRect();
            return rect.top + rect.height / 2;
          }));
        assert.equal(centers.length, 4);
        assert.ok(Math.max(...centers) - Math.min(...centers) < 1, 'desktop header stays on one row');
      }
    }
  }
}

(async()=>{
  const base=process.env.METIS_BROWSER_BASE;
  const directory=process.env.METIS_BROWSER_OUTPUT;
  await withBrowserEvidence(chromium, {base, output:directory, label:'console-header',
    launchOptions:{headless:true,executablePath:process.env.METIS_BROWSER_EXECUTABLE}}, async ({newContext})=>{
    const manifest=await (await fetch(base+'/browser-manifest')).json();
    for(const username of [manifest.author, manifest.reviewer]){
      const context=await newContext();
      const page=await context.newPage();
      await page.goto(base+'/login');
      await page.locator('[name=username]').fill(username);
      await page.locator('[name=password]').fill(manifest.password);
      await Promise.all([page.waitForURL(base+(username===manifest.reviewer?'/review':'/source-selection')),page.locator('button[type=submit]').click()]);
      await checkConsoleHeader(page, base, directory, username===manifest.reviewer);
      if (username===manifest.author) {
        const fallback = await newContext({javaScriptEnabled:false, viewport:{width:390,height:844},
          storageState:await context.storageState()});
        try {
          const noScript = await fallback.newPage();
          await noScript.goto(base + '/ingest');
          await noScript.getByRole('link', {name:'Vorming', exact:true}).waitFor();
          await noScript.keyboard.press('Tab');
          await noScript.keyboard.press('Enter');
          assert.ok(await noScript.getByRole('main').evaluate(node => node === document.activeElement));
        } finally {
          await fallback.close();
        }
      }
      await context.close();
    }
  });
})().catch(error => { console.error(error); process.exitCode=1; });
