const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE);
const fs=require('node:fs');
(async()=>{
  const base=process.env.METIS_BROWSER_BASE;
  const directory=process.env.METIS_BROWSER_OUTPUT;
  const browser=await chromium.launch({headless:true,executablePath:process.env.METIS_BROWSER_EXECUTABLE});
  try {
    const manifest=await (await fetch(base+'/browser-manifest')).json();
    const cases=[{document:manifest.document, username:'reviewer', password:'fixture-only'},
      {document:manifest.source_document, username:manifest.source_reviewer, password:'bert-secret'}];
    const before=await (await fetch(base+'/browser-domain-state')).json();
    const results=[];
    for(const testCase of cases){
      const {document,username,password}=testCase;
      const page=await browser.newPage();
      await page.goto(base+'/login');
      await page.locator('[name=username]').fill(username);
      await page.locator('[name=password]').fill(password);
      await Promise.all([page.waitForURL(base+'/'),page.locator('button[type=submit]').click()]);
      await page.goto(base+'/inzicht/document?'+new URLSearchParams({document}));
      await Promise.all([page.waitForURL('**/*view_check=**'),page.getByRole('button',{name:'Controleer weergave',exact:true}).click()]);
      const id=new URL(page.url()).searchParams.get('view_check');
      if(!id)throw Error('missing investigation id');
      let result;
      for(let i=0;i<50;i++){
        result=await page.evaluate(async id => {
          const response=await fetch('/inzicht/weergavecontrole/'+id);
          if(!response.ok)throw Error('result unavailable');
          return response.json();
        },id);
        if(['completed','failed'].includes(result.state))break;
        await new Promise(resolve=>setTimeout(resolve,1000));
      }
      if(result.state!=='completed'||result.result.checks.length!==5||result.result.checks.some(c=>c.verdict!=='pass'))
        throw Error('view check did not establish the inventory contract: '+JSON.stringify(result.result));
      await page.reload();
      await page.getByRole('heading',{name:'Uitkomst weergavecontrole',exact:true}).waitFor();
      const evidence=await page.evaluate(async id=>{
        const response=await fetch('/inzicht/weergavecontrole/'+id+'/bewijs');
        return {status:response.status,type:response.headers.get('content-type'),size:(await response.arrayBuffer()).byteLength};
      },id);
      if(evidence.status!==200||evidence.type!=='image/png'||evidence.size===0)throw Error('missing private evidence');
      results.push({id,state:result.state,checks:result.result.checks,evidence});
      await page.close();
    }
    if(!results[1].checks.some(c=>c.id==='source_partition'&&c.expected>0))throw Error('source partition was empty');
    const after=await (await fetch(base+'/browser-domain-state')).json();
    if(before.sha256!==after.sha256)throw Error('browser investigation changed domain authority');
    fs.writeFileSync(directory+'/view-check-result.json',JSON.stringify({...results[0],sourceCase:results[1],domainUnchanged:true},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
