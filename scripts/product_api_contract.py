#!/usr/bin/env python3
"""Generate and protect the stable Metis Product API v1 OpenAPI contract."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantRegistry
from src.usage_ledger_v1 import UsageLedger

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "schemas" / "product_api_v1.openapi.json"
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
    """Keep deterministic public-contract content only."""
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


def _schema_type(schema: dict[str, Any]) -> Any:
    if "$ref" in schema:
        return ("ref", schema["$ref"])
    return schema.get("type")


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
    if old_type and new_type and old_type != new_type:
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
    if not CONTRACT_PATH.exists():
        raise SystemExit(f"Committed contract missing: {CONTRACT_PATH.relative_to(ROOT)}")
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if committed != generated:
        raise SystemExit(
            "Product API OpenAPI drift detected. Run "
            "'python scripts/product_api_contract.py --write' and review compatibility."
        )

    if base_ref:
        baseline = _git_show(base_ref, str(CONTRACT_PATH.relative_to(ROOT)))
        if baseline is None:
            baseline = _git_show(base_ref, HISTORICAL_BASELINE_PATH)
        if baseline is not None:
            assert_backward_compatible(_canonical_contract(baseline), generated)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--base-ref")
    args = parser.parse_args()

    if args.write:
        CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT_PATH.write_text(_json_text(generate_contract()), encoding="utf-8")
    if args.check:
        check_contract(base_ref=args.base_ref)
    if not args.write and not args.check:
        print(_json_text(generate_contract()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
