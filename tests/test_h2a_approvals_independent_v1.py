"""Herstelstap 2a (H2, deel onafhankelijk van H2-4): aanvallen van Lex en D-DEL-1.

Regels:
- D-DEL-1: een ongepubliceerd document MOET verwijderbaar zijn door de rol
  publisher en door de uploader; elk ander account MAG NIET verwijderen.
- D-SEC-1: ``record_authorization`` MOET de identiteit van de goedkeurder
  verifiëren; een agent of een onbekend account telt NOOIT.
- D-SEC-2: de herstelroute MOET het agentfilter, onafhankelijkheid en four-eyes
  afdwingen; de CLI MOET buiten pilot/dev fail-closed weigeren en op account-id
  vergelijken.
- D-SEC-3: de publicatiepoort zit in het contract; alleen de locatorblocker
  valt onder de G2-controle van de console.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.operations_console_v1 import ConsoleError
from tests import test_v220_unpublished_document_delete as delete_fixture
from tests import test_legacy_canonical_recovery_v1 as recovery_fixture
from tests import test_storage_publication_v2 as cli_fixture

pytestmark = [pytest.mark.release_control_opslag, pytest.mark.release_control_toegang,
              pytest.mark.release_control_scope_belofte, pytest.mark.release_control_slop,
              pytest.mark.release_control_releasebewijs]
ROOT = Path(__file__).resolve().parents[1]


# --- D-DEL-1 ---------------------------------------------------------------------

def _delete_setup(tmp_path, title):
    console = delete_fixture._console(tmp_path)
    accounts = delete_fixture._accounts(console)
    accounts["other_researcher"] = console.create_account(
        username="researcher.dirk", password="dirk-secret", roles=("researcher", "reviewer"),
        display_name="Dirk Onderzoeker")
    receipt = delete_fixture._ingest(console, accounts, title=title)
    return console, accounts, receipt


def _delete(console, actor, receipt, title):
    return console.delete_unpublished_snapshot(actor_id=actor["account_id"], snapshot_id=receipt["snapshot_id"],
                                               confirmed=True, confirm_title=title)


def _listed(console, receipt):
    return receipt["snapshot_id"] in {row["snapshot_id"] for row in console.list_envelopes()}


def test_publisher_role_deletes_unpublished_document(tmp_path):
    console, accounts, receipt = _delete_setup(tmp_path, "Publisher verwijdert")
    _delete(console, accounts["publisher"], receipt, "Publisher verwijdert")
    assert not _listed(console, receipt)


def test_uploader_deletes_unpublished_document(tmp_path):
    console, accounts, receipt = _delete_setup(tmp_path, "Uploader verwijdert")
    _delete(console, accounts["researcher"], receipt, "Uploader verwijdert")
    assert not _listed(console, receipt)


@pytest.mark.parametrize("actor", ["other_researcher", "reviewer"])
def test_non_uploader_non_publisher_delete_is_refused(tmp_path, actor):
    console, accounts, receipt = _delete_setup(tmp_path, "Niet van jou")
    with pytest.raises(ConsoleError, match="unpublished_delete_not_permitted"):
        _delete(console, accounts[actor], receipt, "Niet van jou")
    assert _listed(console, receipt)


def test_delete_control_follows_the_same_rule():
    from src.operations_console_app import _can_delete_unpublished
    row = {"uploader_account_id": "acct-up"}
    assert _can_delete_unpublished({"account_id": "acct-pub", "roles": ["publisher"]}, row)
    assert _can_delete_unpublished({"account_id": "acct-up", "roles": ["researcher"]}, row)
    assert not _can_delete_unpublished({"account_id": "acct-x", "roles": ["researcher", "reviewer"]}, row)


# --- D-SEC-1 ---------------------------------------------------------------------

def _binding(**overrides):
    from src.publish_authorization_v1 import tuple_record
    values = dict(object_id="o-1", object_version="1.0", canonical_object_hash="h" * 64,
                  confirmed_object_type="recommendation", reviewer="reviewer.bert",
                  reviewer_id="acct-bert", decision="approve")
    values.update(overrides)
    return tuple_record(**values)


HUMAN = {"account_id": "acct-bert", "username": "reviewer.bert", "display_name": "Bert", "roles": ["reviewer"]}


def test_record_authorization_accepts_verified_human_reviewer():
    from src.publish_authorization_v1 import record_authorization
    rows = record_authorization([], _binding(), account=HUMAN)
    assert rows[0]["valid"] is True


@pytest.mark.parametrize("account,binding", [
    ({**HUMAN, "username": "grok bot", "display_name": "Grok Bot"}, {"reviewer": "grok bot"}),
    ({**HUMAN, "account_id": "acct-other"}, {}),
    ({**HUMAN, "roles": ["researcher"]}, {}),
    ({**HUMAN, "retirement": {"at": "2026-01-01"}}, {}),
    (None, {}),
    (HUMAN, {"reviewer": "metis"}),
])
def test_record_authorization_refuses_unverified_or_agent_identity(account, binding):
    from src.publish_authorization_v1 import ApproverIdentityError, record_authorization
    with pytest.raises(ApproverIdentityError):
        record_authorization([], _binding(**binding), account=account)


# --- D-SEC-2: herstelroute (RT1/RT2) -------------------------------------------------

def _recovery(tmp_path, *, approvers, uploader="uploader-1", high_risk=False):
    from src.legacy_canonical_recovery_v1 import prepare_legacy_canonical_candidate
    path, documents, reviews, blobs, _manifest = recovery_fixture._fixture(tmp_path)
    documents.envelope["uploader_account_id"] = uploader
    obj = documents.objects[0]
    if high_risk:
        from src.integrity_kernel import compute_canonical_object_hash
        obj["risk"] = {"risk_level": "high", "risk_fields": ["dosage"]}
        digest = compute_canonical_object_hash(obj)
        obj["provenance"].update({"canonical_object_hash": digest, "content_hash": digest})
        manifest = json.loads(path.read_text())
        manifest["objects"][0].update(canonical_object_hash=digest, content_hash=digest)
        path.write_text(json.dumps(manifest))
    template = reviews.read_bindings()[reviews.snapshot_id][0]
    rows = [{**template, "canonical_object_hash": obj["provenance"]["canonical_object_hash"],
             "reviewer": name, "reviewer_id": rid} for name, rid in approvers]
    reviews.read_bindings = lambda: {reviews.snapshot_id: rows}
    return lambda: prepare_legacy_canonical_candidate(path, documents=documents, reviews=reviews, source_store=blobs)


def test_recovery_refuses_release_whose_only_approver_is_an_agent(tmp_path):
    from src.legacy_canonical_recovery_v1 import LegacyCanonicalRecoveryError
    prepare = _recovery(tmp_path, approvers=[("Grok Bot", "grok bot")])
    with pytest.raises(LegacyCanonicalRecoveryError, match="legacy_release_object_authorization_missing"):
        prepare()


def test_recovery_refuses_release_approved_only_by_uploader(tmp_path):
    from src.legacy_canonical_recovery_v1 import LegacyCanonicalRecoveryError
    prepare = _recovery(tmp_path, approvers=[("Uploader", "uploader-1")])
    with pytest.raises(LegacyCanonicalRecoveryError, match="legacy_release_object_authorization_missing"):
        prepare()


def test_recovery_refuses_high_risk_without_four_eyes(tmp_path):
    from src.legacy_canonical_recovery_v1 import LegacyCanonicalRecoveryError
    prepare = _recovery(tmp_path, approvers=[("Reviewer", "reviewer-1"), ("Grok Bot", "grok bot")], high_risk=True)
    with pytest.raises(LegacyCanonicalRecoveryError, match="legacy_release_object_four_eyes_missing"):
        prepare()


def test_recovery_refuses_stale_human_approval(tmp_path):
    """Opslag stale: een goedkeuring op een oudere objecthash telt NOOIT."""
    from src.legacy_canonical_recovery_v1 import LegacyCanonicalRecoveryError
    from src.legacy_canonical_recovery_v1 import prepare_legacy_canonical_candidate
    path, documents, reviews, blobs, _manifest = recovery_fixture._fixture(tmp_path)
    documents.envelope["uploader_account_id"] = "uploader-1"
    template = reviews.read_bindings()[reviews.snapshot_id][0]
    reviews.read_bindings = lambda: {reviews.snapshot_id: [{**template, "canonical_object_hash": "0" * 64}]}
    with pytest.raises(LegacyCanonicalRecoveryError, match="legacy_release_object_authorization_missing"):
        prepare_legacy_canonical_candidate(path, documents=documents, reviews=reviews, source_store=blobs)


def test_recovery_accepts_independent_human_approval(tmp_path):
    prepare = _recovery(tmp_path, approvers=[("Reviewer", "reviewer-1")])
    assert prepare().objects


def test_recovery_refuses_missing_uploader_identity(tmp_path):
    from src.legacy_canonical_recovery_v1 import LegacyCanonicalRecoveryError
    prepare = _recovery(tmp_path, approvers=[("Reviewer", "reviewer-1")], uploader="")
    with pytest.raises(LegacyCanonicalRecoveryError, match="legacy_release_uploader_missing"):
        prepare()


# --- D-SEC-2: CLI ------------------------------------------------------------------

def _cli(args, env_mode):
    import os
    env = {k: v for k, v in os.environ.items() if k != "METIS_RUNTIME_MODE"}
    if env_mode:
        env["METIS_RUNTIME_MODE"] = env_mode
    return subprocess.run([sys.executable, "-m", "src.canonical_store", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True)


@pytest.mark.parametrize("mode", [None, "production", "azure"])
def test_cli_fails_closed_outside_pilot_or_dev(tmp_path, mode):
    result = _cli(["init", "--db", str(tmp_path / "s.db")], mode)
    assert result.returncode == 2
    assert "canonical_store_cli_disabled_outside_pilot" in result.stdout + result.stderr
    assert not (tmp_path / "s.db").exists()


@pytest.mark.parametrize("mode", ["pilot", "dev"])
def test_cli_runs_in_pilot_or_dev(tmp_path, mode):
    assert _cli(["init", "--db", str(tmp_path / "s.db")], mode).returncode == 0


def _accounts_file(tmp_path, rows):
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps(rows))
    return path


def _import(tmp_path, obj, accounts):
    from src.canonical_store import import_approved
    inp = tmp_path / "in.jsonl"
    cli_fixture.write_jsonl(inp, [obj])
    return import_approved(tmp_path / "s.db", inp, cli_fixture.SCHEMA_PATH, "technical-test",
                           accounts=_accounts_file(tmp_path, accounts))


ACCOUNTS = [
    {"account_id": "acct-a", "username": "Reviewer A", "roles": ["reviewer"]},
    {"account_id": "acct-b", "username": "Reviewer B", "roles": ["reviewer"]},
]


def _approved(**governance):
    obj = cli_fixture.make_approved()
    obj["governance"]["validated_by"] = "acct-a"
    obj["governance"].update(governance)
    return obj


def test_cli_import_accepts_known_account_id(tmp_path):
    assert _import(tmp_path, _approved(), ACCOUNTS)["imported_objects"] == 1


def test_cli_import_refuses_name_instead_of_account_id(tmp_path):
    report = _import(tmp_path, _approved(validated_by="Reviewer A"), ACCOUNTS)
    assert report["imported_objects"] == 0
    assert "reviewer_account_id_unknown" in report["blocked"][0]["errors"]


def test_cli_import_refuses_agent_account(tmp_path):
    accounts = [{"account_id": "acct-a", "username": "Grok Bot", "roles": ["reviewer"]}]
    report = _import(tmp_path, _approved(), accounts)
    assert "forbidden_reviewer_identity" in report["blocked"][0]["errors"]


def test_cli_import_compares_creator_and_reviewer_on_account_id(tmp_path):
    obj = _approved()
    obj["provenance"]["created_by"] = "acct-a"
    report = _import(tmp_path, obj, ACCOUNTS)
    assert "reviewer_must_differ_from_creator" in report["blocked"][0]["errors"]


# --- D-SEC-3: publicatiepoort in het contract (RT3) ---------------------------------

def test_contract_owns_the_only_locator_exception():
    from src.four_eyes_v1 import CONSOLE_VERIFIED_BLOCKERS
    assert CONSOLE_VERIFIED_BLOCKERS == frozenset({"blocked_pending_immutable_locator"})


def test_contract_reports_authorization_blockers_without_locator():
    from src.four_eyes_v1 import publish_authorization_contract
    contract = publish_authorization_contract(obj={"object_id": "o-1", "object_type": "recommendation"},
                                              bindings=[], uploader_id="u", immutable_locator=None)
    assert "blocked_pending_immutable_locator" not in contract["authorization_blockers"]
    assert contract["authorization_blockers"]
    assert contract["authorization_ok"] is False


def test_extra_contract_blocker_with_valid_locator_blocks_publication(tmp_path, monkeypatch):
    from tests import test_vsa_publish_readiness_ui_v1 as ready
    import src.four_eyes_v1 as four_eyes
    import src.operations_console_v1 as kernel
    console, accounts, receipt, _source = ready._console_with_document(tmp_path)
    ready._complete_review(console, accounts, receipt)
    sid = receipt["snapshot_id"]
    assert console.publication_readiness(sid)["publish_allowed"] is True
    original = four_eyes.publish_authorization_contract

    def with_extra(**kwargs):
        result = original(**kwargs)
        result["blockers"] = [*result["blockers"], "rt3_injected_contract_blocker"]
        result["authorization_blockers"] = [*result["authorization_blockers"], "rt3_injected_contract_blocker"]
        result["authorization_ok"] = False
        return result

    monkeypatch.setattr(four_eyes, "publish_authorization_contract", with_extra)
    monkeypatch.setattr(kernel, "publish_authorization_contract", with_extra, raising=False)
    readiness = console.publication_readiness(sid)
    assert readiness["publish_allowed"] is False
    assert "rt3_injected_contract_blocker" in readiness["blockers"]
