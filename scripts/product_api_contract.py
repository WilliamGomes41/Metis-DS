#!/usr/bin/env python3
"""Generate and protect the stable Metis Product API v1 OpenAPI contract.

The running FastAPI application is the contract authority. CI materializes that
contract as an artifact and compares it with the contract generated from the
base revision. No hand-authored duplicate OpenAPI document is maintained.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantRegistry
from src.usage_ledger_v1 import UsageLedger

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "runtime" / "product_api_v1.openapi.json"
HISTORICAL_BASELINE_PATH = "output/v2/product_api/openapi-v1.json"
PUBLIC_METHODS = {"get", "post", "put", "patch", "delete"}


class ContractCompatibilityError(RuntimeError):
    pass


def _paths(tmp: Path) -> ProductPaths:
    defaults = ProductPaths.defaults(ROOT)
    return ProductPaths(
        real_records=defaults.real_records,
        fixture_records=defaults.fixture_records,
        real_published=defaults.real_published,
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp / "unused-tenants.json",
        usage_db=tmp / "usage.sqlite",
    )


def generate_contract() -> dict[str, Any]:
    """Generate OpenAPI from the same application factory used at runtime."""
    with tempfile.TemporaryDirectory(prefix="metis-product-contract-") as raw:
        tmp = Path(raw)
        paths = _paths(tmp)
        app = create_product_app(
            "fixture",
            paths=paths,
            tenant_registry=TenantRegistry([]),
            usage_ledger=UsageLedger(paths.usage_db),
            allow_fixture=True,
        )
        spec = app.openapi()
    return _canonical_contract(spec)


def _canonical_contract(spec: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(spec))
    out.pop("servers", None)
    return out


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _git_show(ref: str, path: str) -> dict[str, Any] | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def _git_has_path(ref: str, path: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{path}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _generate_from_ref(ref: str) -> dict[str, Any] | None:
    """Generate the base contract from base code, not from a copied spec.

    PR3 bootstraps against the historical OpenAPI artifact because main before
    PR3 has no generator yet. Once PR3 is merged, later changes compare two
    independently generated runtime contracts.
    """
    if not _git_has_path(ref, "scripts/product_api_contract.py"):
        baseline = _git_show(ref, HISTORICAL_BASELINE_PATH)
        return _canonical_contract(baseline) if baseline is not None else None

    with tempfile.TemporaryDirectory(prefix="metis-contract-base-") as raw:
        worktree = Path(raw) / "base"
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), ref],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if add.returncode != 0:
            raise SystemExit("Unable to materialize base revision for Product API contract check")
        try:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(worktree)
            code = (
                "import json; "
                "from scripts.product_api_contract import generate_contract; "
                "print(json.dumps(generate_contract(), ensure_ascii=False, sort_keys=True))"
            )
            run = subprocess.run(
                [sys.executable, "-c", code],
                cwd=worktree,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if run.returncode != 0:
                raise SystemExit(
                    "Unable to generate Product API contract from base revision:\n"
                    + run.stderr
                )
            return _canonical_contract(json.loads(run.stdout))
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )


def _schema_type(schema: dict[str, Any]) -> Any:
    if "type" in schema:
        return schema["type"]
    if "anyOf" in schema:
        members = []
        for item in schema.get("anyOf") or []:
            if "$ref" in item:
                members.append(("ref", item["$ref"]))
            elif "type" in item:
                members.append(item["type"])
            else:
                members.append(("schema", json.dumps(item, sort_keys=True)))
        return ("anyOf", tuple(sorted(members, key=repr)))
    if "$ref" in schema:
        return ("ref", schema["$ref"])
    return None


def _resolve(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    prefix = "#/components/schemas/"
    if not str(ref).startswith(prefix):
        return schema
    return spec.get("components", {}).get("schemas", {}).get(str(ref)[len(prefix):], {})


def _compare_schema(
    old_spec: dict[str, Any],
    new_spec: dict[str, Any],
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
    *,
    path: str,
    request: bool,
    errors: list[str],
) -> None:
    old = _resolve(old_spec, old_schema)
    new = _resolve(new_spec, new_schema)
    old_type = _schema_type(old)
    new_type = _schema_type(new)
    if old_type is not None and new_type is not None and old_type != new_type:
        errors.append(f"{path}: type changed from {old_type!r} to {new_type!r}")
        return

    old_props = old.get("properties") or {}
    new_props = new.get("properties") or {}
    old_required = set(old.get("required") or [])
    new_required = set(new.get("required") or [])

    if request:
        newly_required = new_required - old_required
        if newly_required:
            errors.append(f"{path}: new required request fields {sorted(newly_required)}")
    else:
        missing_required = old_required - set(new_props)
        if missing_required:
            errors.append(f"{path}: required response fields removed {sorted(missing_required)}")
        no_longer_required = old_required - new_required
        if no_longer_required:
            errors.append(f"{path}: required response fields became optional {sorted(no_longer_required)}")

    for name, old_child in old_props.items():
        if name not in new_props:
            if name in old_required or not request:
                errors.append(f"{path}.{name}: field removed")
            continue
        _compare_schema(
            old_spec,
            new_spec,
            old_child,
            new_props[name],
            path=f"{path}.{name}",
            request=request,
            errors=errors,
        )

    old_items = old.get("items")
    new_items = new.get("items")
    if old_items and new_items:
        _compare_schema(
            old_spec,
            new_spec,
            old_items,
            new_items,
            path=f"{path}[]",
            request=request,
            errors=errors,
        )

    if request:
        for key, direction in (
            ("minLength", "increase"),
            ("minimum", "increase"),
            ("minItems", "increase"),
            ("maxLength", "decrease"),
            ("maximum", "decrease"),
            ("maxItems", "decrease"),
        ):
            if key not in old or key not in new:
                continue
            if direction == "increase" and new[key] > old[key]:
                errors.append(f"{path}: {key} tightened from {old[key]} to {new[key]}")
            if direction == "decrease" and new[key] < old[key]:
                errors.append(f"{path}: {key} tightened from {old[key]} to {new[key]}")
        if "enum" in old and "enum" in new and not set(old["enum"]).issubset(set(new["enum"])):
            errors.append(f"{path}: enum narrowed")


def assert_contract_complete(spec: dict[str, Any]) -> None:
    errors: list[str] = []
    paths = spec.get("paths") or {}
    for path, path_item in paths.items():
        if not str(path).startswith("/v1/"):
            continue
        for method, operation in path_item.items():
            if method.lower() not in PUBLIC_METHODS:
                continue
            response = (
                operation.get("responses", {})
                .get("200", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            if "$ref" not in response:
                errors.append(f"{method.upper()} {path}: 200 response lacks explicit schema ref")
            if operation.get("security") and not operation.get("x-metis-required-scope"):
                errors.append(f"{method.upper()} {path}: secured endpoint lacks x-metis-required-scope")
    scheme = (
        spec.get("components", {})
        .get("securitySchemes", {})
        .get("VVNApiKeyBearer")
    )
    if not scheme or scheme.get("type") != "http" or scheme.get("scheme") != "bearer":
        errors.append("VVNApiKeyBearer security scheme missing or changed")
    if errors:
        raise ContractCompatibilityError("\n".join(errors))


def assert_backward_compatible(old: dict[str, Any], new: dict[str, Any]) -> None:
    errors: list[str] = []
    old_paths = old.get("paths") or {}
    new_paths = new.get("paths") or {}
    for path, old_path_item in old_paths.items():
        if not str(path).startswith("/v1/"):
            continue
        if path not in new_paths:
            errors.append(f"{path}: path removed")
            continue
        new_path_item = new_paths[path]
        for method, old_operation in old_path_item.items():
            if method.lower() not in PUBLIC_METHODS:
                continue
            if method not in new_path_item:
                errors.append(f"{method.upper()} {path}: operation removed")
                continue
            new_operation = new_path_item[method]
            old_security = old_operation.get("security")
            if old_security and new_operation.get("security") != old_security:
                errors.append(f"{method.upper()} {path}: security requirement changed")

            old_parameters = {
                (p.get("in"), p.get("name")): p
                for p in old_operation.get("parameters") or []
            }
            new_parameters = {
                (p.get("in"), p.get("name")): p
                for p in new_operation.get("parameters") or []
            }
            for key, old_parameter in old_parameters.items():
                new_parameter = new_parameters.get(key)
                if new_parameter is None:
                    errors.append(f"{method.upper()} {path}: parameter {key} removed")
                    continue
                if bool(old_parameter.get("required")) and not bool(new_parameter.get("required")):
                    errors.append(f"{method.upper()} {path}: required parameter {key} became optional")
                _compare_schema(
                    old,
                    new,
                    old_parameter.get("schema") or {},
                    new_parameter.get("schema") or {},
                    path=f"{method.upper()} {path} parameter {key}",
                    request=True,
                    errors=errors,
                )

            old_body = old_operation.get("requestBody")
            if old_body:
                new_body = new_operation.get("requestBody")
                if not new_body:
                    errors.append(f"{method.upper()} {path}: request body removed")
                else:
                    old_schema = (
                        old_body.get("content", {})
                        .get("application/json", {})
                        .get("schema", {})
                    )
                    new_schema = (
                        new_body.get("content", {})
                        .get("application/json", {})
                        .get("schema", {})
                    )
                    _compare_schema(
                        old,
                        new,
                        old_schema,
                        new_schema,
                        path=f"{method.upper()} {path} request",
                        request=True,
                        errors=errors,
                    )

            old_responses = old_operation.get("responses") or {}
            new_responses = new_operation.get("responses") or {}
            for status, old_response in old_responses.items():
                if status not in new_responses:
                    errors.append(f"{method.upper()} {path}: response {status} removed")
                    continue
                old_schema = (
                    old_response.get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                new_schema = (
                    new_responses[status].get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                if old_schema and new_schema:
                    _compare_schema(
                        old,
                        new,
                        old_schema,
                        new_schema,
                        path=f"{method.upper()} {path} response {status}",
                        request=False,
                        errors=errors,
                    )

    if errors:
        raise ContractCompatibilityError("\n".join(errors))


def check_contract(*, base_ref: str | None = None) -> None:
    generated = generate_contract()
    assert_contract_complete(generated)
    if base_ref:
        baseline = _generate_from_ref(base_ref)
        if baseline is None:
            raise SystemExit(f"Unable to resolve Product API contract baseline from {base_ref}")
        assert_backward_compatible(baseline, generated)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--base-ref")
    args = parser.parse_args()

    generated: dict[str, Any] | None = None
    if args.write:
        generated = generate_contract()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(_json_text(generated), encoding="utf-8")
    if args.check:
        check_contract(base_ref=args.base_ref)
    if not args.write and not args.check:
        print(_json_text(generate_contract()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
