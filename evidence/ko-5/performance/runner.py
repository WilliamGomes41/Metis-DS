"""Execute the fixed five AB/BA pairs after root supplies immutable head + quiet GO."""
import hashlib, json, os, platform, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg import sql

OUT=Path('/workspace/ko5-perf-final-evidence')
PYTHON='/workspace/.venvs/metis-ds/bin/python'
BASE='07db5080666f0428a454f5a705e50825a4fc5506'
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    assert os.environ.get('KO5_QUIET_GO')=='1','Root quiet measurement slot required'
    head=os.environ['KO5_HEAD_SHA']
    checkouts={'base':'/workspace/Metis-ko5-base','head':os.environ['KO5_HEAD_CHECKOUT']}
    pins={'base':BASE,'head':head}
    assert len(head)==40
    frozen=json.loads((OUT/'frozen-sources.json').read_text())
    for name,value in frozen.items():
        assert digest(OUT/name)==value,name
    for side,path in checkouts.items():
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()==pins[side]
        assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=path,text=True).strip(),side
    for side in pins:
        assert not (OUT/f'{side}-1.json').exists(),'Archive calibration before decisive run'
    fixture=json.loads((OUT/'fixture.json').read_text())
    # Only owned clones are reset. Seed fixture itself stays unchanged.
    with psycopg.connect('postgresql://postgres@127.0.0.1:55440/postgres',autocommit=True) as con:
        for side in pins:
            name=f'ko5_perf_final_{side}_v1'
            con.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            con.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(name),sql.Identifier(fixture['database'])))
            shutil.rmtree(OUT/f'runtime-{side}')
            shutil.copytree(OUT/'fixture',OUT/f'runtime-{side}')
    order=[{'round':r,'side':s,'pair_order':'AB' if r%2 else 'BA'}
           for r in range(1,6) for s in (['base','head'] if r%2 else ['head','base'])]
    manifest={'baseline_sha':BASE,'head_sha':head,'checkouts':checkouts,'planned_order':order,
              'frozen_hashes':frozen,'python':sys.version,'platform':platform.platform(),
              'started':datetime.now(timezone.utc).isoformat(),'fixture':fixture}
    assert not (OUT/'manifest.json').exists(),'Never overwrite final evidence'
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    for i,item in enumerate(order,1):
        side=item['side'];r=item['round']
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkouts[side],text=True).strip()==pins[side]
        for name,value in frozen.items():
            assert digest(OUT/name)==value,name
        load=subprocess.check_output(['uptime'],text=True).strip()
        event={'sequence':i,**item,'started':datetime.now(timezone.utc).isoformat(),'load':load}
        with (OUT/'execution-order.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
        with (OUT/f'{side}-{r}.log').open('w') as f:
            result=subprocess.run([PYTHON,str(OUT/'probe.py'),checkouts[side],side,str(r),pins[side]],
                                  cwd=checkouts[side],stdout=f,stderr=subprocess.STDOUT)
        if result.returncode: raise SystemExit(result.returncode)
        print(f'Completed {i}/10 round{r} {side}',flush=True)
    metrics={}
    for side in pins:
        receipts=[json.loads((OUT/f'{side}-{r}.json').read_text()) for r in range(1,6)]
        cold=sorted(row['cold_ms'] for row in receipts)
        card=sorted(sample['server_ms'] for row in receipts for sample in row['card'])
        assert len(card)==100
        metrics[side]={'cold_ms':cold,'cold_mean_ms':sum(cold)/5,'cold_median_ms':cold[2],
            'card_server_ms':card,'card_server_p95_ms':card[94],
            'round_card_p95_ms':[sorted(x['server_ms'] for x in row['card'])[18] for row in receipts]}
    ratios={key:metrics['head'][key]/metrics['base'][key] for key in ['cold_mean_ms','card_server_p95_ms']}
    summary={'metrics':metrics,'head_base_ratios':ratios,'budget':1.05,
             'gate':'PASS' if all(x<=1.05 for x in ratios.values()) else 'FAIL',
             'baseline_sha':BASE,'head_sha':head,'protocol_sha256':digest(OUT/'protocol.json')}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({'ratios':ratios,'gate':summary['gate']}))
if __name__=='__main__':main()
