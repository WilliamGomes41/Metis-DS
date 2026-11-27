const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE);
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.METIS_BROWSER_EXECUTABLE});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const base = process.env.METIS_BROWSER_BASE;
    const sid = process.env.METIS_PROBLEM_DOCUMENT;
    async function login(username) {
      await page.goto(base+'/login');
      await page.locator('[name=username]').fill(username);
      await page.locator('[name=password]').fill('fixture-only');
      await Promise.all([page.waitForURL(base+(username==='author'?'/source-selection':'/review')), page.locator('button[type=submit]').click()]);
    }
    await login('author');
    await page.goto(base+'/source-selection?document='+sid);
    const card = page.locator('[data-source-document="'+sid+'"]');
    await card.getByRole('link',{name:'Nieuwe bronversie inleveren'}).waitFor();
    if (await card.locator('#formation-problems, form[action="/source-selection/start"]').count()) {
      throw Error('Historical guideline still offers automatic processing');
    }
    const status = await page.evaluate(async ({sid,revision}) => (await fetch('/source-selection/start',
      {method:'POST',body:new URLSearchParams({document:sid,expected_revision:revision,command_id:'old-start'})})).status,
      {sid,revision:process.env.METIS_PROBLEM_REVISION});
    if (status!==404) throw Error('Historical start returned '+status);
    await login('reviewer');
    await page.goto(base+'/review?document='+sid+'&task=inventory');
    await page.getByRole('link',{name:'Bekijk documentdiagnose',exact:true}).waitFor();
    if (errors.length) throw Error('browser errors: '+errors.join(','));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
