"""KO3 six counterbalanced pairs; no execution without exact immutable head env."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,shutil,subprocess,sys
ROOT=Path('/tmp/ko3-perf');BASE='c6fa679b7c0cc630d24e32e4578e21398cb796c4';PY='/workspace/.venvs/metis-ds/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def plan():
 return [dict(sequence=(n-1)*2+i+1,round=n,side=side,pair_order='AB'if n%2 else'BA')for n in range(1,7)for i,side in enumerate(('base','head')if n%2 else('head','base'))]
def main():
 head=os.environ.get('KO3_HEAD_SHA','');assert re.fullmatch('[0-9a-f]{40}',head),'Explicit KO3_HEAD_SHA required'
 pinned={side:subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/side,text=True).strip()for side in ['base','head']};assert pinned=={'base':BASE,'head':head}
 protocol=json.loads((ROOT/'protocol.json').read_text())
 for name,expected in protocol['source_hashes'].items():assert sha(ROOT/name)==expected
 out=Path('/workspace/ko3-perf-evidence')/('v1-counterbalanced-'+head[:8]);assert not out.exists(),'Never overwrite prior evidence';out.mkdir(parents=True)
 sources={name:sha(ROOT/name)for name in ['probe.py','server.py','runner.py','summarize.py']}
 for name in sources:shutil.copyfile(ROOT/name,out/name)
 manifest={'method_version':1,'baseline_sha':BASE,'head_sha':head,'actual_pinned_heads':pinned,'rounds':6,'samples_per_path_side':18,
  'planned_order':plan(),'sources':sources,'fixture':{'raw_source_fragments':900,'paragraphs':899,'definition_candidates':92},
  'budgets':{'consider_wall_p95_ratio':1.1,'selected_publish_server_p95_ratio':1.1},'children_per_execution':4,
  'direct':'3fresh children;one first-call measuredconsider each;startup excluded;warm extra call attributiononly',
  'http':'1fresh HTTPS child;publisherlogin then3selectedGETs;no proof/logJSONIO between requests;parse afterstop',
  'immutability':'Setup reference beforeanychild;one comparison afteralltimedpaths;allbusinessPGtables and sourcefiles,excluding deliberate authsessioncreation',
  'p95':'nearest-rankceil(.95*18)=18,max;retain all observations;query/bytes attributiononly'}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
 def event(name,item,**extra):
  with(out/'execution-order.jsonl').open('a')as log:log.write(json.dumps({'event':name,'timestamp':datetime.now(timezone.utc).isoformat(),**item,**extra})+'\n')
 for item in manifest['planned_order']:
  if item['sequence']%2:
   with(out/'load.txt').open('a')as log:subprocess.run(['uptime'],stdout=log,check=True)
  side=item['side'];checkout=ROOT/side
  assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()==(BASE if side=='base'else head)
  for name,expected in sources.items():assert sha(ROOT/name)==expected
  target=checkout/'tests/ko3_perf_probe_tmp.py';assert not target.exists();event('started',item);shutil.copyfile(ROOT/'probe.py',target)
  env={**os.environ,'PATH':'/workspace/.postgres/usr/lib/postgresql/17/bin:'+os.environ['PATH'],
   'METIS_TEST_POSTGRES_DSN':'postgresql://postgres@127.0.0.1:55432/postgres','KO3_OUT':str(out),'KO3_SIDE':side,'KO3_ROUND':str(item['round']),'KO3_HEAD':'1'if side=='head'else'0'}
  try:
   with(out/f"{side}-{item['round']}.log").open('w')as log:done=subprocess.run([PY,'-m','pytest','-q','tests/ko3_perf_probe_tmp.py'],cwd=checkout,env=env,stdout=log,stderr=subprocess.STDOUT)
  finally:target.unlink(missing_ok=True)
  event('completed'if done.returncode==0 else'failed',item,exit_code=done.returncode)
  if done.returncode:raise SystemExit(done.returncode)
  print(f"Round{item['round']} {side} {item['pair_order']} completed",flush=True)
if __name__=='__main__':main()
