"""One-off PR-D3 audit; AST only, never imports product code."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import argparse
import os
import shutil
import subprocess
import tempfile
import time

EXPERIMENT = Path(__file__).resolve().parent
REPOSITORY = EXPERIMENT.parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=REPOSITORY)
parser.add_argument("--python-only", action="store_true")
args = parser.parse_args()
root = args.root.resolve()
spec = importlib.util.spec_from_file_location("boundaries", REPOSITORY / "scripts/check_architecture_boundaries.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
targets = {"src.retrieval.embedding_provider_v1", "src.retrieval.provider_vector_retrieval_v1"}
paths = sorted([*root.joinpath("src").rglob("*.py"), *root.joinpath("scripts").rglob("*.py")])
def module(path):
    return path.relative_to(root).with_suffix("").as_posix().replace("/", ".").removesuffix(".__init__")
modules = {module(p): p for p in paths}
known = set(modules) | targets
def resolve(raw):
    # Direct package-qualified imports, parent package execution, and legacy
    # bare-module fallbacks. Ambiguous bare names are conservatively included.
    result = {m for m in known if raw == m or raw.startswith(m + ".")}
    if not raw.startswith(("src.", "scripts.")):
        result |= {m for m in known if m.endswith("." + raw)}
    return result
graph = {}
digest = hashlib.sha256()
for name, path in modules.items():
    relative = path.relative_to(root).as_posix()
    content = path.read_bytes()
    digest.update(relative.encode() + b"\0" + content + b"\0")
    tree = ast.parse(content, filename=relative)
    graph[name] = set()
    for _, imported in checker._imports(tree, relative):
        graph[name] |= resolve(imported)
roots = ["src.console_asgi", "src.cli", "src.service_app", "src.product_api_v1"]
roots += sorted(name for name in modules if name.startswith("scripts."))
if any(name not in modules for name in roots):
    raise ValueError("A runtime root is missing")
results = {}
for start in roots:
    parents = {start: None}
    queue = [start]
    for node in queue:
        for child in sorted(graph.get(node, set())):
            if child not in parents:
                parents[child] = node
                queue.append(child)
    hits = {}
    for target in sorted(targets & parents.keys()):
        chain = [target]
        while parents[chain[-1]] is not None:
            chain.append(parents[chain[-1]])
        hits[target] = chain[::-1]
    results[start] = {"reachable_count": len(parents), "target_paths": hits}
external = {t: sorted(n for n, children in graph.items() if t in children and n not in targets) for t in sorted(targets)}
report = {"source_digest": digest.hexdigest(), "module_count": len(modules), "root_count": len(roots), "roots": results, "external_importers": external,
          "limitations": "Static ordinary/relative and literal dynamic imports, including common aliases. Nonliteral reflection, sys.path-dependent external plugins and external operators are not proved absent."}
report["python_boundary_pass"] = not any(external.values())
report["edge_count"] = sum(map(len, graph.values()))
if args.python_only:
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["python_boundary_pass"] else 1)
# Emit raw edges, not Python-computed pass/fail flags, to the independent checker.
ids = {name: index for index, name in enumerate([*sorted(targets), *sorted(set(modules) - targets)])}
edges = [f"Boundary.Import{{{ids[source]}, {ids[target]}}}"
         for source, children in sorted(graph.items()) for target in sorted(children)]
facts = "import Base\nimport ./Boundary.bend as Boundary\n\n"
facts += "def edges() -> List<Boundary.Edge>:\n  [" + ", ".join(edges) + "]\n\n"
facts += "def roots() -> List<U32>:\n  [" + ", ".join(str(ids[name]) for name in roots) + "]\n"
with tempfile.TemporaryDirectory(prefix="metis-d3-bend-") as directory:
    target = Path(directory)
    for name in ("Boundary.bend", "LAWS.bend", "PROOF.bend"):
        shutil.copyfile(EXPERIMENT / name, target / name)
    (target / "Facts.bend").write_text(facts)
    started = time.perf_counter()
    kernel = os.environ.get("METIS_BEND_VERDICT") == "1"
    report["checker"] = "bend2-and-bendtt" if kernel else "bend2"
    command = ["bend", "PROOF.bend", *(["--verdict"] if kernel else [])]
    result = subprocess.run(command, cwd=target, capture_output=True, text=True,
                            env={**os.environ, "BEND_NO_TELEMETRY": "1"}, timeout=60)
    report["bend_seconds"] = round(time.perf_counter() - started, 3)
    report["bend_exit_code"] = result.returncode
    report["bend_output"] = result.stdout + result.stderr
print(json.dumps(report, indent=2))
sys.exit(result.returncode)
