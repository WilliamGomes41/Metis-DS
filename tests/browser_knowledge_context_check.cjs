const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
(async()=>{
 const base=process.env.METIS_BROWSER_BASE, m=await (await fetch(base+'/browser-manifest')).json();
 const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,args:['--no-sandbox']});
 const page=await browser.newPage();
 async function login(user){await page.goto(base+'/login');await page.locator('input[name=username]').fill(user);await page.locator('input[name=password]').fill(m.password);await Promise.all([page.waitForURL(url=>!url.pathname.endsWith('/login')),page.locator('button[type=submit]').click()]);}
 await login(m.first_user);
 for(const key of ['first','second','paths']){
   let approval;
   if(key==='second'){approval=await page.evaluate(()=>fetch('/browser-approve-first',{method:'POST'}).then(r=>r.json()));await page.goto(base+'/logout');await login(m.second_user);}
   for(const [width,height] of [[1440,1000],[390,844]]){
     await page.setViewportSize({width,height});
     await page.goto(base+m[key]);
     const proof=await page.evaluate(()=>({stylesheetLoaded:[...document.styleSheets].some(s=>s.href?.includes('/brand/console.css')&&s.cssRules.length>0),core:document.querySelector('[data-full-knowledge-passage]')?.textContent,context:document.querySelector('[data-essential-context]')?.textContent,revision:document.querySelector('[data-reviewed-version]')?.getAttribute('data-reviewed-version'),paths:[...document.querySelectorAll('[data-path-alternative]')].map(x=>x.innerText),overflow:document.documentElement.scrollWidth>innerWidth,backgroundClosed:[...document.querySelectorAll('[data-review-background]')].every(x=>!x.open),technicalClosed:[...document.querySelectorAll('[data-review-diagnostics]')].every(x=>!x.open)}));
     fs.writeFileSync(`${process.env.METIS_BROWSER_OUTPUT}/${key}-${width}.json`,JSON.stringify(proof,null,2));
     await page.screenshot({path:`${process.env.METIS_BROWSER_OUTPUT}/${key}-${width}.png`,fullPage:true});
     if(!proof.stylesheetLoaded||!proof.core||proof.overflow||!proof.backgroundClosed||!proof.technicalClosed)throw Error('Incomplete/overflowing card '+JSON.stringify(proof));
     if((key==='first'||key==='second')&&(proof.core!==m.core||!proof.context.includes(m.condition)||!proof.context.includes(m.exception)))throw Error('Lost literal meaning');
     if(key==='paths'&&(proof.paths.length!==2||!proof.paths[0].includes('Vaak')||!proof.paths[1].includes('Soms')))throw Error('Paths conflated');
     console.log(key,width,proof.revision,'PASSED');
     if(key==='second' && proof.revision!==approval.object_version)throw Error('Wrong reviewed revision');
   }
   if(key==='second'){await page.goto(base+'/logout');await login(m.first_user);}
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
