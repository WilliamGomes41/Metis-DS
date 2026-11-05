"""#981: context size and scope of bounded formation tasks, counts only.

usage: python evidence/981/measure_context.py <blocks.json>
blocks.json: a list of semantic source blocks (block_id, text, section_path,
heading, position). The script prints aggregates only, never source text.
"""
import json, sys, subprocess
sys.path.insert(0, '.')
from src.vorming.bounded_formation_v1 import tasks_for, MAX_CONTEXT_CHARS, module_depth
from src.vorming.recommendation_coverage_v1 import inventory
blocks = json.load(open(sys.argv[1]))
tasks = tasks_for(blocks, blocks)
# Module key at the same depth the production code detects (below a title, if any).
DEPTH = module_depth(blocks, blocks, {r['span']['block_id'] for r in inventory(blocks, recommendation_sections_only=False)})
def module(path):
    return tuple(path[:DEPTH])
sizes = [sum(len(b['text']) for b in t['evidence_blocks']) for t in tasks]
rec = [t for t in tasks if 'Aanbevelingen' in t['section_path']]
def has(t, name):
    return any(module(b['section_path']) == module(t['section_path']) and name in b['section_path'] for b in t['evidence_blocks'])
foreign = sum(any(b.get('heading') and module(b['section_path']) != module(t['section_path']) for b in t['evidence_blocks']) for t in tasks)
s = sorted(sizes)
print(json.dumps({"tasks": len(tasks), "context_chars_total": sum(sizes), "context_chars_median": s[len(s)//2],
  "context_chars_max": max(sizes), "over_limit": sum(x > MAX_CONTEXT_CHARS for x in sizes),
  "tasks_with_foreign_module_heading": foreign, "recommendation_section_tasks": len(rec),
  "with_rationale": sum(has(t, 'Rationale') for t in rec),
  "with_considerations": sum(has(t, 'Van bewijs naar aanbeveling (overwegingen)') for t in rec),
  "module_depth": DEPTH, "module_context_tasks": sum(x > 0 and len(t['evidence_blocks']) > 0 and any(b['section_path'] != t['section_path'] and not b.get('heading') for b in t['evidence_blocks']) for t, x in zip(tasks, sizes))}))
