import json
from copy import deepcopy

import pytest

from src.four_eyes_v1 import requires_four_eyes
from src.operations_console_v1 import ConsoleError
from src.review_policy_v1 import CONTRACT, validate_policy
from src.review_duty_v1 import review_stage
from tests.test_v225_beslisboom_path import _accounts, _console, _ingest_boom, _confirm_applies_if, _boom_freeze_bytes


def policy(accounts, participation=None):
    return {"contract": CONTRACT, "revision": 1,
            "primary": accounts["researcher"]["account_id"],
            "assignments": ([{"reviewer_id": accounts["reviewer"]["account_id"],
                              "participation": participation}] if participation else [])}


@pytest.mark.parametrize("participation", [None, "optional", "required"])
def test_explicit_participation_survives_restart_and_drives_exact_review(tmp_path, participation):
    console = _console(tmp_path)
    accounts = _accounts(console)
    payload = json.loads(_boom_freeze_bytes())
    payload["nodes"][1]["score_points"] = 2
    receipt = _ingest_boom(console, accounts, data=json.dumps(payload).encode(), named_reviewers=[], review_policy=policy(accounts, participation))
    sid = receipt["snapshot_id"]
    primary = accounts["researcher"]["account_id"]
    secondary = accounts["reviewer"]["account_id"]
    # A score risk is retained, without silently requiring another reviewer.
    obj = next(o for o in console.snapshot_objects(sid) if o.get("scorelist"))
    assert obj["risk"]["risk_fields"]
    assert requires_four_eyes(obj) == (participation == "required")
    console.review_object(actor_id=primary, snapshot_id=sid, object_id=obj["object_id"],
                          decision="approve", confirmed_object_type="node")
    console = _console(tmp_path)
    obj = next(o for o in console.snapshot_objects(sid) if o.get("scorelist"))
    assert console._envelope(sid)["review_policy"] == policy(accounts, participation)
    bindings = console.object_review_bindings(sid)
    assert review_stage(obj, review_path="boom", bindings=bindings) == ("second_review" if participation == "required" else None)
    considered = console.consider_publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    assert "second_named_reviewer_required" not in considered["blockers"]
    assert ("required_policy_review_missing" in considered["blockers"]) == (participation == "required")
    if participation:
        console.approve_second_review(actor_id=secondary, snapshot_id=sid, object_id=obj["object_id"])
        # Repeating a review is idempotent; optional participants can contribute.
        console.approve_second_review(actor_id=secondary, snapshot_id=sid, object_id=obj["object_id"])
        obj = next(o for o in console.snapshot_objects(sid) if o.get("scorelist"))
        assert review_stage(obj, review_path="boom", bindings=console.object_review_bindings(sid)) is None


def test_policy_rejects_duplicate_and_unprivileged_reviewers(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    p = policy(accounts, "required")
    p["assignments"][0]["reviewer_id"] = p["primary"]
    with pytest.raises(ValueError, match="invalid_review_assignment"):
        validate_policy(p)
    p = policy(accounts)
    p["primary"] = accounts["publisher"]["account_id"]
    with pytest.raises(ConsoleError, match="reviewer_role_required"):
        _ingest_boom(console, accounts, named_reviewers=[], review_policy=p)


def test_every_required_reviewer_is_needed_optional_cannot_substitute(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    extra = console.create_account(username="reviewer.extra", password="extra-secret", roles=("reviewer",))
    optional = console.create_account(username="reviewer.optional", password="optional-secret", roles=("reviewer",))
    p = policy(accounts, "required")
    p["assignments"] += [{"reviewer_id": extra["account_id"], "participation": "required"},
                         {"reviewer_id": optional["account_id"], "participation": "optional"}]
    sid = _ingest_boom(console, accounts, named_reviewers=[], review_policy=p)["snapshot_id"]
    obj = next(o for o in console.snapshot_objects(sid) if o.get("scorelist"))
    oid = obj["object_id"]
    console.review_object(actor_id=p["primary"], snapshot_id=sid, object_id=oid,
                          decision="approve", confirmed_object_type="node")
    for actor in [p["primary"], accounts["reviewer"]["account_id"], optional["account_id"]]:
        console.approve_second_review(actor_id=actor, snapshot_id=sid, object_id=oid)
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == oid)
    assert review_stage(current, review_path="boom", bindings=console.object_review_bindings(sid)) == "second_review"
    console.approve_second_review(actor_id=extra["account_id"], snapshot_id=sid, object_id=oid)
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == oid)
    assert review_stage(current, review_path="boom", bindings=console.object_review_bindings(sid)) is None
