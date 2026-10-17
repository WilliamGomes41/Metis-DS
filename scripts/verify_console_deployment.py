#!/usr/bin/env python3
"""Verify the running console's identity and exact packaged commit after deploy.

Read-only HTTP checks; no Azure, database, or application mutation. Curl bounds
each response by time and size. Output contains fixed codes and the expected
commit only, never response bodies, URLs, or transport exception messages.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from urllib.parse import urlsplit


def health_url(value: str) -> str:
    """Normalize the health path when an app origin ends with a slash."""
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                 and parsed.port != 0 and parsed.username is None and parsed.password is None
                 and not parsed.query and not parsed.fragment and parsed.path.strip("/") == "health")
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("deployment_health_url_invalid")
    return f"{parsed.scheme}://{parsed.netloc}/health"


def expected_commit(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("deployment_expected_commit_invalid")
    return value


def attempts(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if not 1 <= number <= 60:
        raise argparse.ArgumentTypeError("deployment_attempts_invalid")
    return number


def retry_delay(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError:
        seconds = -1
    if not 0 <= seconds <= 60:
        raise argparse.ArgumentTypeError("deployment_retry_delay_invalid")
    return seconds


def check_once(url: str, commit: str) -> str | None:
    try:
        response = subprocess.run(
            ["curl", "--disable", "--fail", "--silent", "--proto", "=http,https",
             "--connect-timeout", "5", "--max-time", "10", "--max-filesize", "65536",
             "--write-out", "\n%{http_code}", url],
            capture_output=True, timeout=11, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "deployment_health_unavailable"
    if response.returncode != 0:
        return "deployment_health_unavailable"
    body, _, status = response.stdout.rpartition(b"\n")
    if status != b"200":
        return "deployment_health_unavailable"
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        return "deployment_health_invalid_json"
    if not isinstance(payload, dict):
        return "deployment_health_invalid_json"
    if payload.get("status") != "ok":
        return "deployment_health_status_mismatch"
    if payload.get("service") != "operations-console":
        return "deployment_health_service_mismatch"
    if payload.get("deployed_commit") != commit:
        return "deployment_health_commit_mismatch"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health-url", type=health_url, required=True)
    parser.add_argument("--expected-commit", type=expected_commit, required=True)
    parser.add_argument("--attempts", type=attempts, default=13)
    parser.add_argument("--retry-delay", type=retry_delay, default=5)
    args = parser.parse_args()
    for attempt in range(1, args.attempts + 1):
        failure = check_once(args.health_url, args.expected_commit)
        if failure is None:
            print(f"deployment_verified commit={args.expected_commit}")
            return 0
        print(f"deployment_verification_failed attempt={attempt} code={failure}")
        if attempt < args.attempts:
            time.sleep(args.retry_delay)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
