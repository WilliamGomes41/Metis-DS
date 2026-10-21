"""Separate test vs production deploy identities (Protocol v2.22 wave C).

Test cannot production. Production cannot test. Deploy jobs stay
fail-closed until Azure App Service ``vvn-metis-console-test`` exists.
An app-setting MUST NOT open G2 or ``publish()``.
"""
from __future__ import annotations

import argparse
import os
from typing import Any

TEST_APP = "vvn-metis-console-test"
PRODUCTION_APP = "vvn-metis-console"
TEST_IDENTITY = "metis-deploy-test"
PRODUCTION_IDENTITY = "metis-deploy-production"


class DeployIdentityError(RuntimeError):
    """Fail-closed deploy identity or activation error."""


def assert_deploy_allowed(*, environment: str, identity: str, target_app: str) -> None:
    env = environment.strip().lower()
    ident = identity.strip()
    target = target_app.strip()
    if env == "test":
        if ident != TEST_IDENTITY:
            raise DeployIdentityError("identity_environment_mismatch")
        if target == PRODUCTION_APP:
            raise DeployIdentityError("test_cannot_production")
        if target != TEST_APP:
            raise DeployIdentityError("test_target_invalid")
        return
    if env == "production":
        if ident != PRODUCTION_IDENTITY:
            raise DeployIdentityError("identity_environment_mismatch")
        if target == TEST_APP:
            raise DeployIdentityError("production_cannot_test")
        if target != PRODUCTION_APP:
            raise DeployIdentityError("production_target_invalid")
        return
    raise DeployIdentityError("unknown_deploy_environment")


def require_deploy_activation(*, ready_flag: str, declared_app: str) -> None:
    """Keep deploy-test/deploy-production inactive until the named test app exists."""
    if ready_flag != "true":
        raise DeployIdentityError("test_app_missing")
    if declared_app.strip() != TEST_APP:
        raise DeployIdentityError("unexpected_test_app")


def storage_app_settings(environment: str) -> dict[str, str]:
    """Per-environment storage coordinates. Values are app settings, not secrets."""
    env = environment.strip().lower()
    if env == "test":
        return {
            "G2_STORAGE_ACCOUNT": "aidataservice",
            "G2_BLOB_CONTAINER": "canonical-sources-test",
            "CONSOLE_DATA_ROOT": "/home/data/metis-console-test",
        }
    if env == "production":
        return {
            "G2_STORAGE_ACCOUNT": "aidataservice",
            "G2_BLOB_CONTAINER": "canonical-sources",
            "CONSOLE_DATA_ROOT": "/home/data/metis-console",
        }
    raise DeployIdentityError("unknown_deploy_environment")


def require_activation_from_env() -> dict[str, Any]:
    require_deploy_activation(
        ready_flag=os.environ.get("METIS_TEST_APP_READY", ""),
        declared_app=os.environ.get("AZURE_TEST_WEBAPP_NAME", TEST_APP),
    )
    environment = os.environ.get("METIS_DEPLOY_ENVIRONMENT", "").strip().lower()
    identity = os.environ.get("METIS_DEPLOY_IDENTITY", "").strip()
    if environment == "test":
        target = os.environ.get("AZURE_TEST_WEBAPP_NAME", TEST_APP)
    elif environment == "production":
        target = os.environ.get("AZURE_PRODUCTION_WEBAPP_NAME", PRODUCTION_APP)
    else:
        raise DeployIdentityError("unknown_deploy_environment")
    assert_deploy_allowed(environment=environment, identity=identity, target_app=target)
    return {"status": "allowed", "environment": environment, "target_app": target}


def main() -> int:
    parser = argparse.ArgumentParser(prog="deploy-identity")
    parser.add_argument("--environment", required=True, choices=("test", "production"))
    args = parser.parse_args()
    os.environ["METIS_DEPLOY_ENVIRONMENT"] = args.environment
    if args.environment == "test":
        os.environ.setdefault("METIS_DEPLOY_IDENTITY", TEST_IDENTITY)
    else:
        os.environ.setdefault("METIS_DEPLOY_IDENTITY", PRODUCTION_IDENTITY)
    require_activation_from_env()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
