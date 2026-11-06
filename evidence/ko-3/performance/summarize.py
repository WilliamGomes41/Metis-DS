from pathlib import Path
import hashlib,json,math,statistics,sys
root=Path(sys.argv[1]);manifest=json.loads((root/'manifest.json').read_text())
assert manifest['rounds']==6 and manifest['samples_per_path_side']==18
assert manifest['baseline_sha']=='c6fa679b7c0cc630d24e32e4578e21398cb796c4'
assert manifest['budgets']=={'consider_wall_p95_ratio':1.1,'selected_publish_server_p95_ratio':1.1}
for name,sha in manifest['sources'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha
order=[json.loads(l)for l in(root/'execution-order.jsonl').read_text().splitlines()];assert len(order)==24
for item,a,b in zip(manifest['planned_order'],order[::2],order[1::2]):
 assert a['event']=='started'and b['event']=='completed'and b['exit_code']==0
 assert all(a[k]==v and b[k]==v for k,v in item.items())
runs={side:[json.loads((root/f'{side}-{n}.json').read_text())for n in range(1,7)]for side in ['base','head']}
for side,rows in runs.items():
 assert len(rows)==6
 for row in rows:
  assert row['sha']==manifest['baseline_sha'if side=='base'else'head_sha']
  assert row['fixture']['raw_source_fragments']==900 and row['fixture']['definition_candidates']==92
  assert len(row['consider'])==len(row['http'])==3
  assert row['proofs']['database_unchanged']and row['proofs']['source_files_unchanged']and row['proofs']['existing_results_stable']
  if side=='head':assert row['proofs']['head_rows_verified']and row['head_object_rows']>=92
  assert not row['http_forced_reap']
reference=runs['base'][0]['compatibility_result']
for rows in runs.values():
 for row in rows:
  assert row['compatibility_result']==reference, 'Existing blocker/count/flag parity failed'
  assert row['existing_result_keys']==runs['base'][0]['existing_result_keys'], 'Existing fields removed or changed beyond additive object_readiness'
def describe(values):
 assert len(values)==18
 return {'median':statistics.median(values),'min':min(values),'max':max(values),'p95':sorted(values)[math.ceil(.95*len(values))-1],'values':values}
summary={'method_version':1,'baseline_sha':manifest['baseline_sha'],'head_sha':manifest['head_sha'],
 'method':'KO3:6counterbalanced pairs(3AB/3BA),18samples/path/side,nearest-rankp95=max;fresh production child;startup excluded;standardGC/auth;proofs afterallpaths;no publishes.',
 'metrics':{},'verdict':'PASS','existing_field_parity':True,'sources':manifest['sources']}
for path,key in [('consider','wall_ms'),('http','server_ms')]:
 d={side:describe([m[key]for r in rows for m in r[path]])for side,rows in runs.items()};ratio=d['head']['p95']/d['base']['p95'];d['ratio']=ratio;d['percent_change']=(ratio-1)*100;d['pass']=ratio<=1.1
 if not d['pass']:summary['verdict']='FAIL'
 summary['metrics'][path+'_'+key]=d
summary['http_attribution']={side:{k:describe([m[k]for r in rows for m in r['http']])for k in ['db_queries','db_json_bytes','physical_connections','wall_ms']}for side,rows in runs.items()}
summary['direct_untimed_attribution']={side:{k:describe([m['attribution_only'][k]for r in rows for m in r['consider']])for k in ['queries','json_bytes','connections']}for side,rows in runs.items()}
summary['attribution_warning']='Direct counters describe a separate untimed warm call; never the measured first call. No query/byte acceptance gates.'
summary['proofs']={'executions':12,'fresh_children':48,'measured_consider_calls':36,'untimed_attribution_calls':36,'selected_http_pages':36,'database_unchanged':12,'source_files_unchanged':12,'head_object_rows_verified':6,'balanced_pairs':{'AB':3,'BA':3}}
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
