# PR-D3: source-derived import boundary (#779)

This experiment tests whether Bend adds useful evidence to retiring the unused
provider vector route. It does not implement retrieval or prove Python semantics.
The existing root `LAWS.bend` and its meaning are unchanged.

## Run

From the repository root, with Bend 2.0.37 on PATH:

```sh
bend guide
python experiments/bend/pr-d3/audit.py --python-only
python experiments/bend/pr-d3/audit.py
python tests/test_bend_experiment.py
```

`audit.py` parses the current `src/` and `scripts/` without importing product
code. It reuses the architecture checker's ordinary/relative and literal dynamic
import extraction, resolves project modules (including legacy bare fallbacks),
and traverses the four runtime roots plus all scripts. The report records source
SHA-256, graph size, paths to either retired module and external importers.

For Bend, it emits **raw edges and root IDs**, not Python-computed verdicts, as
`Facts.bend` in a temporary directory beside copies of these three Bend files.
It runs `bend PROOF.bend` there. The laws require that roots are retained and no
edge enters the removed pair from outside it. Independent edge/list checks use
parallel lets. No speedup claim or GPU/native compilation is made.

Set `METIS_BEND_VERDICT=1` to run `bend PROOF.bend --verdict` instead, requiring
Lean 4.34.0 or a built kernel via `BENDTT`. The existing Bend Actions job installs
checksum-pinned Lean and sets this flag. Without it, local tests check with
Bend's standard checker; they do not claim the independent kernel ran.
The existing experiment path filters remain scoped; this is not a new mandatory
product-runtime gate for every source change.

## Observed value and limits

On base `929ce510f6c361781284530f86bdfbb44b69bb44`, ordinary import analysis
found 238 modules and 41 roots, with no path or external importer into the pair.
After deletion: 236 modules, 1,205 project import edges, the same 41 roots, and
no path or external importer. The standard Bend proof passed.

The negative test appends a relative import of the removed provider-vector
module to **a temporary copy** of `service_app.py`. Both Python-only analysis
and Bend reject the same violation; Bend fails because its law computes
`False`, not because it imports Python or encounters a syntax error. The
repository source is never mutated by the test.

**Incremental defect detection demonstrated: none.** No previously unknown
product defect was found. The same AST extraction feeds both checks, so Bend
cannot discover an import that extraction missed. It adds a separate typed
checker over the emitted edges, plus toolchain/code/CI maintenance. This case
does not establish that those costs improve Metis code quality.

Nonliteral reflection, arbitrary external plugins/operators, Python execution,
retrieval ranking/abstention, publication and lifecycle behavior are outside
these laws. Existing retrieval and Product API tests remain the behavioral
evidence. Local independent kernel execution was unavailable (Lean could not
start in this environment); the Actions result is reported in the PR.
