const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE);
const fs = require('node:fs');
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
      await Promise.all([page.waitForURL(base+'/'), page.locator('button[type=submit]').click()]);
    }
    await login('author');
    await page.goto(base+'/source-selection?document='+sid);
    await page.getByRole('button',{name:'Starten',exact:true}).click();
    await page.waitForURL('**/source-selection?**');
    await page.goto(base+'/formation-problems?document='+sid);
    await page.getByRole('heading',{name:'Vormingsproblemen',exact:true}).waitFor();
    fs.writeFileSync(process.env.METIS_PROBLEM_NAVIGATED, 'yes');
    for (let i=0;i<50;i++) {
      await page.goto(base+'/source-selection?document='+sid);
      if (await page.getByRole('link',{name:'Naar Review',exact:true}).count()) break;
      await new Promise(resolve => setTimeout(resolve,200));
    }
    await page.getByRole('link',{name:'Naar Review',exact:true}).waitFor();
    await page.goto(base+'/formation-problems?document='+sid);
    await page.getByRole('button',{name:'Open bronwerk hervatten',exact:true}).waitFor();
    const problemIds = await page.locator('article[id^="problem-"]').evaluateAll(nodes=>nodes.map(n=>n.id));
    if (!problemIds.length) throw Error('missing problems');
    await page.reload();
    const reloaded = await page.locator('article[id^="problem-"]').evaluateAll(nodes=>nodes.map(n=>n.id));
    if (JSON.stringify(problemIds)!==JSON.stringify(reloaded)) throw Error('unstable problem identity');
    await page.setViewportSize({width:390,height:844});
    if (await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)) throw Error('mobile overflow');
    await page.screenshot({path:process.env.METIS_PROBLEM_SCREENSHOT, fullPage:true});
    await page.getByRole('button',{name:'Uitloggen',exact:true}).click();
    await login('reviewer');
    await page.goto(base+'/review?document='+sid+'&task=inventory');
    await page.getByRole('link',{name:'Vormingsproblemen behandelen',exact:true}).waitFor();
    if (errors.length) throw Error('browser errors: '+errors.join(','));
    console.log(JSON.stringify({navigatedWhileProcessing:true, reviewAndProblemsVisible:true,
      stableProblemIdentity:true, mobileOverflow:false, pageErrors:errors}));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
