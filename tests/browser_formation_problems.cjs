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
    await page.getByRole('button',{name:'Open werk opnieuw verwerken',exact:true}).waitFor();
    const contrast = () => page.evaluate(() => {
      const luminance = color => {
        const c=color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{
          v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;
        });
        return .2126*c[0]+.7152*c[1]+.0722*c[2];
      };
      return [...document.querySelectorAll('.formation-quote p,.formation-reason,.formation-technical summary,.formation-header .muted')].map(node=>{
        let background=node;
        while(background.parentElement && getComputedStyle(background).backgroundColor==='rgba(0, 0, 0, 0)') background=background.parentElement;
        const a=luminance(getComputedStyle(node).color),b=luminance(getComputedStyle(background).backgroundColor);
        return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
      });
    });
    const lightContrast=await contrast();
    if (Math.min(...lightContrast)<4.5) throw Error('light text contrast below AA');
    const problemIds = await page.locator('[id^="problem-"]').evaluateAll(nodes=>nodes.map(n=>n.id));
    if (problemIds.length !== 2) throw Error('missing original findings');
    if (await page.locator('.formation-item').count() !== 1) throw Error('same source range not grouped');
    if ((await page.locator('.formation-quote').innerText()).trim() !== 'Controleer dagelijks de huid.') throw Error('literal source missing');
    if (await page.locator('.formation-technical code').first().isVisible()) throw Error('technical code visible before disclosure');
    const technical=page.getByText('Technische details',{exact:true});
    await technical.focus(); await page.keyboard.press('Enter');
    if (!await page.locator('.formation-technical code').first().isVisible()) throw Error('keyboard disclosure inaccessible');
    await page.keyboard.press('Enter');
    await page.screenshot({path:process.env.METIS_PROBLEM_SCREENSHOT.replace('.png','-desktop.png'),fullPage:true});
    await page.reload();
    const reloaded = await page.locator('[id^="problem-"]').evaluateAll(nodes=>nodes.map(n=>n.id));
    if (JSON.stringify(problemIds)!==JSON.stringify(reloaded)) throw Error('unstable problem identity');
    await page.setViewportSize({width:390,height:844});
    if (await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)) throw Error('mobile overflow');
    const targets=await page.locator('.formation-next a,.formation-technical summary,.formation-related summary').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().height));
    if (Math.min(...targets)<44) throw Error('small treatment/disclosure touch target');
    await page.screenshot({path:process.env.METIS_PROBLEM_SCREENSHOT, fullPage:true});
    for (const width of [320,768]) {
      await page.setViewportSize({width,height:844});
      if (await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)) throw Error('overflow at '+width);
    }
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>document.documentElement.dataset.theme='dark');
    const darkContrast=await contrast();
    if (Math.min(...darkContrast)<4.5) throw Error('dark text contrast below AA');
    await page.screenshot({path:process.env.METIS_PROBLEM_SCREENSHOT.replace('.png','-dark.png'),fullPage:true});
    await page.evaluate(()=>document.documentElement.style.fontSize='200%');
    if (await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)) throw Error('text zoom overflow');
    await page.screenshot({path:process.env.METIS_PROBLEM_SCREENSHOT.replace('.png','-zoom.png'),fullPage:true});
    await page.evaluate(()=>{document.documentElement.style.fontSize='';document.documentElement.dataset.theme='light';});
    fs.writeFileSync(process.env.METIS_PROBLEM_SCREENSHOT.replace('.png','.json'),JSON.stringify({
      knownSourceGroups:1,originalFindings:2,technicalDetailsInitiallyHidden:true,
      keyboardDisclosure:true,viewports:[320,390,768,1440],textZoomPercent:200,
      minLightTextContrast:Math.min(...lightContrast),minDarkTextContrast:Math.min(...darkContrast),
      minTreatmentTargetHeight:Math.min(...targets),physicalDevice:false},null,2));
    await page.getByRole('button',{name:'Uitloggen',exact:true}).click();
    await login('reviewer');
    await page.goto(base+'/review?document='+sid+'&task=inventory');
    await page.getByRole('link',{name:'Vormingsproblemen behandelen',exact:true}).waitFor();
    if (errors.length) throw Error('browser errors: '+errors.join(','));
    console.log(JSON.stringify({navigatedWhileProcessing:true, reviewAndProblemsVisible:true,
      stableProblemIdentity:true, mobileOverflow:false, pageErrors:errors}));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
