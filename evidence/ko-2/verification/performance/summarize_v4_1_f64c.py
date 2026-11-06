from pathlib import Path
import json,math,statistics
root=Path('/workspace/ko2-perf-evidence/v4.1-f64c476b')
def p95(values):return sorted(values)[math.ceil(len(values)*.95)-1]
def describe(rows):
 result={'samples':len(rows),'statuses':sorted({r['status']for r in rows})}
 for metric in ['server_ms','wall_ms','db_json_bytes','db_queries']:
  values=[r[metric]for r in rows]
  result[metric]={'p95':p95(values),'median':statistics.median(values),'min':min(values),'max':max(values)}
 connections=[sum(r.get('db',{}).get('db_connections',0)for r in m['requests'])for m in rows]
 result['physical_connections']={'p95':p95(connections),'median':statistics.median(connections),'min':min(connections),'max':max(connections)}
 return result
summary={'probe_version':4,'log_finalize_version':'v4-after-server-stop','method':'Frozen fresh-process production HTTPS server per execution; parent seeds and parses client/logJSON, child ordinary production restart and HTTP only, default GC. All direct proof verification after all3timed flows, exact events reverified after stop. Five alternating baseline/head rounds per fixture; nearest-rank p95 over15distinct approval samples per side/fixture. All real redirects and head bon plus continuation included. Unchanged10% p95 server-time and PostgreSQL JSON-byte thresholds for both initial card and whole save flow.', 'baseline_sha':'595fe8f233fdee98dfb67609bd5c7206136ee956','head_sha':'f64c476b9cde822af650397c1c938a98c83dcb09','environment':'Local synthetic production-composed app, Python3.13/PostgreSQL17, Uvicorn HTTPS; not Azure SLO. Root authorized quiet window.','fixtures':{},'checks':{},'verdict':'PASS'}
all_runs=[]
breakdown={}
for fixture in ['legacy','native']:
 runs={side:[json.loads((root/f'{fixture}-{side}-{n}.json').read_text())for n in range(1,6)]for side in ['base','head']}
 all_runs += [r for side in runs.values()for r in side]
 result={'paragraphs':runs['base'][0]['paragraphs'],'candidate_count':runs['base'][0]['candidate_count'],'paths':{}}
 for path in ['card','save']:
  item={side:describe([s for run in runs[side]for s in run[path]])for side in ['base','head']}
  item['budget_10_percent']={}
  for metric in ['server_ms','db_json_bytes']:
   baseline=item['base'][metric]['p95'];head=item['head'][metric]['p95']
   passed=head<=baseline*1.1
   item['budget_10_percent'][metric]={'ratio':head/baseline,'percent_change':(head/baseline-1)*100,'pass':passed}
   if not passed:summary['verdict']='FAIL'
  result['paths'][path]=item
 result['head_save_to_receipt']=describe([s for run in runs['head']for s in run['save_to_receipt']])
 result['head_continue_to_next']=describe([s for run in runs['head']for s in run['continue']if s is not None])
 result['head_context_expand']=describe([run['context_expand']for run in runs['head']])
 summary['fixtures'][fixture]=result
 breakdown[fixture]={}
 for side in ['base','head']:
  rows=[run for run in runs[side]]
  breakdown[fixture][side]={}
  for key in ['card','save_to_receipt','continue']:
   metrics=[m for run in rows for m in run[key]if m]
   if not metrics:continue
   segments=[]
   for index in range(len(metrics[0]['requests'])):
    entries=[m['requests'][index]for m in metrics]
    segment={'method':entries[0]['method'],'route':entries[0]['route'],'server_ms':{'median':statistics.median(r['elapsed_ms']for r in entries),'p95':p95([r['elapsed_ms']for r in entries]),'values':[r['elapsed_ms']for r in entries]},'physical_connections':sorted({r.get('db',{}).get('db_connections')for r in entries}),'db_queries':sorted({r.get('db',{}).get('db_queries')for r in entries}),'phases_median_ms':{}}
    for phase in sorted({phase for r in entries for phase in r.get('phases',{})}):
     segment['phases_median_ms'][phase]=statistics.median(r.get('phases',{}).get(phase,{}).get('inclusive_ms',0)for r in entries)
    segments.append(segment)
   breakdown[fixture][side][key]=segments
for run in all_runs:
 assert run['probe_version']==4 and run['log_finalize_version']=='v4-after-server-stop' and len(run['save'])==3
 assert run['sha']==summary['head_sha'if run['label']=='head'else'baseline_sha']
 assert run['restart_immutability_verified'] and run['durable_events_reverified_after_server_stop']
 assert run['server_process']['gc_enabled'] and run['server_process']['gc_threshold']==[2000,10,10]
 assert run['server_process']['pid']!=run['parent_pid']
 for approval in run['save']:
  assert approval['durable_binding_verified'] and approval['durable_event_verified']
  if run['label']=='head':assert approval['durable_assessment_verified']
summary['checks']={'executions':len(all_runs),'durable_approvals':sum(len(r['save'])for r in all_runs),'head_assessments':sum(len(r['save'])for r in all_runs if r['label']=='head'),'startup_immutability_verified':len(all_runs),'after_stop_committed_events_verified':len(all_runs),'head_full_section_expansions':sum('context_expand'in r for r in all_runs),'forced_reaps':sum(r['server_reaped_after_grace']for r in all_runs),'child_exit_codes':sorted({r['server_exit_code']for r in all_runs})}
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(root/'request-breakdown.json').write_text(json.dumps(breakdown,indent=2)+'\n')
print(json.dumps(summary,indent=2))
