#!/usr/bin/env python3
"""INERT prepared G2 synthetic SHA-256 smoke.

THIS SCRIPT MUST NOT RUN in this PR.
THIS SCRIPT MUST NOT RUN without later explicit owner consent.

It is a prepared placeholder only. Default execution is refuse-closed.
It never uploads, never deletes blobs, never stores keys, and never
calls publish().
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Hard inert. Do not flip in this PR. A later owner-authorized change
# would still also require METIS_G2_SYNTHETIC_SMOKE_OWNER_CONSENT.
SMOKE_INERT = True
OWNER_CONSENT_ENV = "METIS_G2_SYNTHETIC_SMOKE_OWNER_CONSENT"
OWNER_CONSENT_VALUE = "I_HAVE_EXPLICIT_OWNER_CONSENT"
PREPARED_SYNTHETIC_BYTES = b"metis-g2-synthetic-smoke-v1\nnot-a-canonical-source\n"
PREPARED_SHA256 = hashlib.sha256(PREPARED_SYNTHETIC_BYTES).hexdigest()
PREPARED_FILENAME = "g2-synthetic-smoke-v1.txt"


def prepared_synthetic_digest() -> dict[str, str]:
    """Local digest of the prepared payload. Does not talk to Azure."""
    return {
        "filename": PREPARED_FILENAME,
        "sha256": PREPARED_SHA256,
        "bytes": str(len(PREPARED_SYNTHETIC_BYTES)),
        "inert": str(SMOKE_INERT),
    }


def execute_smoke() -> None:
    """Armed path. Remains unreachable while SMOKE_INERT is True."""
    raise RuntimeError("smoke_not_armed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="INERT G2 synthetic SHA-256 smoke. Must not run without later owner consent."
    )
    parser.add_argument(
        "--i-have-explicit-owner-consent",
        action="store_true",
        help="Later owner-consent flag. Insufficient while SMOKE_INERT is True.",
    )
    parser.parse_args(argv)
    report = {
        "status": "INERT",
        "ran": False,
        "smoke_inert": SMOKE_INERT,
        "reason": "g2_synthetic_smoke_inert_requires_explicit_owner_consent_later",
        "prepared": prepared_synthetic_digest(),
        "mutations": [],
        "publish_called": False,
        "azure_called": False,
        "docs": "docs/G2_BLOB_ACTIVATION_RUNBOOK.md",
    }
    print(json.dumps(report, indent=2))
    if SMOKE_INERT:
        return 2
    if os.environ.get(OWNER_CONSENT_ENV) != OWNER_CONSENT_VALUE:
        return 2
    execute_smoke()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
