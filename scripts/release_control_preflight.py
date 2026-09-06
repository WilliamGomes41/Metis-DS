#!/usr/bin/env python3
"""Map changed paths to Metis ontwikkel- en releasecontrole skill categories.

Fail-closed: a `required` category without a matching test marker or
evidence path (and any extra tokens that category demands) BLOCKS CI.
Product categories opslag–metrics stay n.v.t. until a product path is
in the diff. Stdlib only; does not replace repository_preflight.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]

SKILL_CATEGORIES = (
    "scope/belofte",
    "opslag",
    "beschikbaarheid",
    "toegang",
    "kwaliteit",
    "metrics",
    "slop",
    "releasebewijs",
)
PRODUCT_CATEGORIES = (
    "opslag",
    "beschikbaarheid",
    "toegang",
    "kwaliteit",
    "metrics",
)
PROCESS_CATEGORIES = (
    "scope/belofte",
    "slop",
    "releasebewijs",
)
PR_REPORT_FIELDS = (
    "belofte",
    "wijziging",
    "bewijs",
    "onzekerheid",
    "advies",
)

# Path triggers sharpened on real src/ modules. Matching is src/-only so
# tests/, scripts/, docs/ and PROTOCOL files never force product categories.
PATH_RULES: dict[str, tuple[str, ...]] = {
    "opslag": (
        "src/operations_console_v1.py",
        "src/review_ledger.py",
        "src/canonical_store.py",
        "src/g2_source_store.py",
        "src/published_projection_v1.py",
        "src/runtime_data_inventory_v1.py",
        "src/storage_prepare.py",
        "src/*_store.py",
    ),
    "toegang": (
        "src/operations_console_app.py",
        "src/console_asgi.py",
        "src/service_app.py",
        "src/product_security_v1.py",
        "src/product_api_v1.py",
        "src/eligibility_policy.py",
        "src/publish_authorization_v1.py",
        "src/*security*.py",
        "src/*authorization*.py",
    ),
    "beschikbaarheid": (
        "src/ingest_limits_v1.py",
        "src/ingest*.py",
        "src/extract_html_v1.py",
        "src/extract_pdf_v2.py",
        "src/semantic_transform_v2.py",
        "src/semantic_transform_v21.py",
        "src/semantic_transform_generic_v1.py",
        "src/atomic_split_v1.py",
        "src/context_aware_split_v1.py",
        "src/context_scan_v1.py",
        "src/embedding_provider_v1.py",
        "src/semantic_vector_retrieval_v1.py",
        "src/hybrid_retrieval_v1.py",
        "src/lexical_retrieval_v1.py",
        "src/provider_vector_retrieval_v1.py",
        "src/register_source_binary.py",
        "src/extract_html*.py",
        "src/extract_pdf*.py",
        "src/semantic_transform*.py",
        "src/*_split_v1.py",
        "src/*embedding*.py",
    ),
    "kwaliteit": (
        "src/admission_gate_v1.py",
        "src/prepublication_gate_v2.py",
        "src/prepublication_gate_v3.py",
        "src/validation_workflow_v2.py",
        "src/integrity_kernel.py",
        "src/answerability_gate_v1.py",
        "src/validate_golden_set.py",
        "src/extract_coverage_v1.py",
        "src/audit_pdf_text_completeness.py",
        "src/four_eyes_v1.py",
        "src/*_gate_v1.py",
        "src/*_gate_v2.py",
        "src/*_gate_v3.py",
        "src/*validation*.py",
        "src/integrity_*.py",
    ),
    "metrics": (
        "src/extract_metrics_v1.py",
        "src/evaluate_retrieval_baseline.py",
        "src/evaluate_vector_retrieval.py",
        "src/evaluate_hybrid_retrieval.py",
        "src/usage_ledger_v1.py",
        "src/*metrics*.py",
        "src/evaluate_*retrieval*.py",
    ),
}

REQUIRED_EVIDENCE_TOKENS: dict[str, tuple[str, ...]] = {
    "opslag": ("concurrent", "stale"),
    "metrics": ("teller", "noemer", "score-must-drop"),
}

REASON_REQUIRED: dict[str, str] = {
    "scope/belofte": "iedere wijziging heeft een belofte; noem die in tests/PR-rapport",
    "opslag": "review-/objectpersistitie geraakt; concurrent/stale-controles MUST bestaan",
    "beschikbaarheid": "ingest/zware verwerking geraakt",
    "toegang": "routes/auth/URL-ingest geraakt",
    "kwaliteit": "kwaliteits-/gatepaden geraakt",
    "metrics": "metrics-module geraakt; teller/noemer + score-must-drop verplicht",
    "slop": "iedere wijziging MUST slop (PROTOCOL-paste, HANDOFF, extra stuurlaag) vermijden",
    "releasebewijs": "iedere wijziging MUST releasebewijs (testmarker/evidence path) dragen",
}
REASON_NVT: dict[str, str] = {
    "scope/belofte": "geen gewijzigde paden",
    "opslag": "geen opslag-/review-persistitiepaden in de wijziging",
    "beschikbaarheid": "geen ingest-/zware-verwerkingspaden in de wijziging",
    "toegang": "geen routes-/auth-/URL-ingestpaden in de wijziging",
    "kwaliteit": "geen kwaliteits-/gatepaden in de wijziging",
    "metrics": "geen metrics-modules in de wijziging",
    "slop": "geen gewijzigde paden",
    "releasebewijs": "geen gewijzigde paden",
}

MARKER_LINE_RE = re.compile(
    r"^\s*(?:@)?pytest\.mark\.release_control_([a-z0-9_]+)\b",
    re.MULTILINE,
)
EVIDENCE_RE = re.compile(r"^\s*#\s*release-control-evidence:\s*(\S+)(.*)$", re.IGNORECASE | re.MULTILINE)
TOKEN_SPLIT_RE = re.compile(r"[\s,;/]+")
DIFF_FILTER = "ACMRD"


def _posix(path: str) -> str:
    norm = path.replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _slug(category: str) -> str:
    return category.replace("/", "_").replace("-", "_")


def _normalize_token(token: str) -> str:
    return token.strip().lower().replace("_", "-")


def _path_matches(path: str, patterns: Sequence[str]) -> bool:
    norm = _posix(path)
    for pattern in patterns:
        if fnmatch(norm, pattern):
            return True
        if norm.endswith("/" + pattern):
            return True
    return False


def _reason(category: str, status: str, paths: Sequence[str]) -> str:
    if status == "required":
        why = REASON_REQUIRED[category]
        if paths:
            why = f"{why} ({', '.join(paths)})"
    else:
        why = REASON_NVT[category]
    return f"{category}: {status} — {why}"


def classify_paths(paths: Sequence[str]) -> dict[str, dict[str, Any]]:
    normalized = [_posix(path) for path in paths if str(path).strip()]
    hits: dict[str, list[str]] = {category: [] for category in SKILL_CATEGORIES}
    for path in normalized:
        for category, patterns in PATH_RULES.items():
            if _path_matches(path, patterns) and path not in hits[category]:
                hits[category].append(path)

    report: dict[str, dict[str, Any]] = {}
    any_change = bool(normalized)
    for category in SKILL_CATEGORIES:
        if category in PROCESS_CATEGORIES:
            status = "required" if any_change else "n.v.t."
            triggered = list(normalized) if status == "required" else []
        else:
            triggered = hits[category]
            status = "required" if triggered else "n.v.t."
        report[category] = {
            "status": status,
            "reason": _reason(category, status, triggered if category in PRODUCT_CATEGORIES else []),
            "paths": triggered if category in PRODUCT_CATEGORIES else list(triggered),
            "required_evidence": list(REQUIRED_EVIDENCE_TOKENS.get(category, ())),
        }
    return report


def _path_in_changed(evidence_path: str, changed: Sequence[str]) -> bool:
    ev = _posix(evidence_path)
    ev_name = Path(ev).name
    for raw in changed:
        ch = _posix(raw)
        if not ch:
            continue
        if ev == ch or ev.endswith("/" + ch) or ch.endswith("/" + ev):
            return True
        if ev_name == Path(ch).name and (ev.startswith("tests/") or ch.startswith("tests/")):
            return True
    return False


def collect_evidence(
    tests_root: Path | str,
    changed_paths: Sequence[str] | None = None,
) -> dict[str, dict[str, Any]]:
    root = Path(tests_root)
    collected: dict[str, dict[str, Any]] = {
        category: {"paths": [], "tokens": set()} for category in SKILL_CATEGORIES
    }
    if not root.exists():
        return collected

    for path in sorted(root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            rel = _posix(str(path.relative_to(root)))
            if root.name:
                rel = f"{root.name}/{rel}"
        except ValueError:
            rel = path.name
        if changed_paths is not None and not _path_in_changed(rel, changed_paths):
            continue
        slugs_in_file = set(MARKER_LINE_RE.findall(text))
        for match in EVIDENCE_RE.finditer(text):
            category = match.group(1).strip()
            extra = TOKEN_SPLIT_RE.split(match.group(2).strip()) if match.group(2) else []
            if category in collected:
                slugs_in_file.add(_slug(category))
                collected[category]["tokens"].update(_normalize_token(tok) for tok in extra if tok)
        lowered = text.lower()
        file_tokens = {_normalize_token(tok) for tok in TOKEN_SPLIT_RE.split(lowered) if tok}
        for category in SKILL_CATEGORIES:
            if _slug(category) not in slugs_in_file:
                continue
            if rel not in collected[category]["paths"]:
                collected[category]["paths"].append(rel)
            collected[category]["tokens"].update(file_tokens)
    return collected


def _missing_tokens(required: Sequence[str], seen: Iterable[str]) -> list[str]:
    have = {_normalize_token(tok) for tok in seen}
    return [tok for tok in required if _normalize_token(tok) not in have]


def evaluate_release_control(
    *,
    paths: Sequence[str],
    tests_root: Path | str,
) -> dict[str, Any]:
    categories = classify_paths(paths)
    evidence = collect_evidence(tests_root, changed_paths=paths)
    errors: list[str] = []
    for category, item in categories.items():
        found_paths = list(evidence[category]["paths"])
        item["evidence"] = found_paths
        if item["status"] != "required":
            continue
        if not found_paths:
            errors.append(
                f"{category}: required but no matching test marker/evidence path"
            )
            continue
        missing = _missing_tokens(item["required_evidence"], evidence[category]["tokens"])
        if missing:
            errors.append(
                f"{category}: required evidence tokens missing: {', '.join(missing)}"
            )

    status = "BLOCKED" if errors else "PASS"
    changed = [_posix(path) for path in paths if str(path).strip()]
    required = [name for name, item in categories.items() if item["status"] == "required"]
    nvt = [name for name, item in categories.items() if item["status"] == "n.v.t."]
    report = {
        "belofte": (
            "Automate Metis ontwikkel- en releasecontrole: changed paths mark "
            "skill categories required|n.v.t.; CI fails when required lacks evidence."
        ),
        "wijziging": (
            f"paths={', '.join(changed) or '(none)'}; required={', '.join(required) or '(none)'}; "
            f"n.v.t.={', '.join(nvt) or '(none)'}"
        ),
        "bewijs": (
            f"{status}: "
            + (
                "; ".join(errors)
                if errors
                else "every required category has a test marker/evidence path"
            )
        ),
        "onzekerheid": (
            "Path mapping is src/-prefix tooling, not a semantic diff of _save_objects. "
            "Product categories 2–6 stay n.v.t. until a product PR hits those paths. "
            "Evidence counts only when the marked test file is in the evaluated diff. "
            "Auditor verdict is not in this job."
        ),
        "advies": (
            "Keep repository_preflight.py and this mapping in .github/workflows/ci.yml. "
            "A product PR that touches opslag/toegang/ingest/metrics MUST add the matching "
            "test marker plus concurrent/stale or teller/noemer/score-must-drop evidence."
        ),
    }
    return {
        "status": status,
        "categories": categories,
        "report": report,
        "errors": errors,
        "checked_paths": changed,
    }


def _git(repo_root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _ref_is_commit(repo_root: Path, ref: str) -> bool:
    proc = _git(repo_root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    return proc.returncode == 0


def discover_changed_paths(
    repo_root: Path,
    base: str | None,
    *,
    allow_working_tree: bool = False,
) -> list[str]:
    env_paths = os.environ.get("RELEASE_CONTROL_PATHS")
    if env_paths:
        return [line.strip() for line in env_paths.splitlines() if line.strip()]

    resolved_base = base or os.environ.get("RELEASE_CONTROL_BASE")
    if not resolved_base:
        github_base = os.environ.get("GITHUB_BASE_REF")
        resolved_base = f"origin/{github_base}" if github_base else "origin/main"

    if not _ref_is_commit(repo_root, resolved_base):
        raise RuntimeError(f"unresolved release-control base: {resolved_base}")

    last_error = ""
    for spec in (f"{resolved_base}...HEAD", f"{resolved_base}..HEAD"):
        try:
            proc = _git(repo_root, ["diff", "--name-only", f"--diff-filter={DIFF_FILTER}", spec])
        except OSError as exc:
            last_error = str(exc)
            continue
        if proc.returncode == 0:
            return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        last_error = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"

    if allow_working_tree:
        proc = _git(repo_root, ["diff", "--name-only", f"--diff-filter={DIFF_FILTER}", "HEAD"])
        if proc.returncode == 0:
            return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        last_error = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"

    raise RuntimeError(f"unable to discover changed paths against {resolved_base}: {last_error}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", nargs="*", default=None, help="Changed paths (skip git discovery)")
    parser.add_argument("--base", default=None, help="Git merge-base ref (default origin/main)")
    parser.add_argument("--tests-root", default=None, help="Root scanned for evidence markers")
    parser.add_argument("--repo-root", default=None, help="Repository root")
    parser.add_argument(
        "--allow-working-tree",
        action="store_true",
        help="Only if explicitly requested: fall back to uncommitted HEAD diff",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else ROOT
    tests_root = Path(args.tests_root) if args.tests_root else repo_root / "tests"
    try:
        paths = (
            list(args.paths)
            if args.paths
            else discover_changed_paths(
                repo_root,
                args.base,
                allow_working_tree=args.allow_working_tree,
            )
        )
    except RuntimeError as exc:
        print(json.dumps({"status": "BLOCKED", "errors": [str(exc)]}, indent=2))
        return 2

    result = evaluate_release_control(paths=paths, tests_root=tests_root)
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
