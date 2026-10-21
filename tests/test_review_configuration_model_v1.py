"""H2 slice 2b-1: `review_configuration` model, legacy-default projection, migration 017.

Geen gedragswijziging: niets in de review- of publicatiepoort leest dit model
in deze slice. De poort blijft op main-gedrag tot slice 2b-3.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

pytestmark = [pytest.mark.release_control_opslag, pytest.mark.release_control_scope_belofte,
              pytest.mark.release_control_slop, pytest.mark.release_control_releasebewijs]
ROOT = Path(__file__).resolve().parents[1]
UP = "acct-uploader"


def _model():
    import src.review_configuration_v1 as model
    return model


def _cfg(**overrides):
    value = {"contract": "review-configuration-v1", "option": "one_other", "four_eyes_required": False,
             "reviewers": ["acct-b"], "readers": [], "revision": 1, "locked_at": None, "source": "chosen"}
    value.update(overrides)
    return value


# --- validatie -------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    _cfg(),
    _cfg(four_eyes_required=True),
    _cfg(option="two_others", reviewers=["acct-b", "acct-c"]),
    _cfg(option="uploader_sole", reviewers=[]),
    _cfg(readers=["acct-r"]),
])
def test_valid_configuration_is_accepted(value):
    assert _model().validate_configuration(value, uploader_id=UP) == value


def test_four_eyes_with_uploader_sole_is_refused():
    """OPENVRAAG-B10-1: four-eyes + uploader als enige reviewer MOET geweigerd worden."""
    with pytest.raises(ValueError, match="review_configuration_four_eyes_uploader_sole_refused"):
        _model().validate_configuration(_cfg(option="uploader_sole", reviewers=[], four_eyes_required=True),
                                        uploader_id=UP)


@pytest.mark.parametrize("value,code", [
    (_cfg(option="everyone"), "invalid_review_configuration"),
    (_cfg(reviewers=[]), "review_configuration_reviewers_missing"),
    (_cfg(option="two_others", reviewers=["acct-b"]), "review_configuration_reviewers_missing"),
    (_cfg(reviewers=[UP]), "review_configuration_uploader_not_other_reviewer"),
    (_cfg(reviewers=["acct-b", "acct-b"]), "review_configuration_duplicate_reviewer"),
    (_cfg(readers=["acct-b"]), "review_configuration_reader_is_reviewer"),
    (_cfg(readers=[UP]), "review_configuration_reader_is_reviewer"),
    (_cfg(option="uploader_sole", reviewers=["acct-b"]), "review_configuration_uploader_sole_has_reviewers"),
    (_cfg(four_eyes_required="ja"), "invalid_review_configuration"),
    (_cfg(source="raden"), "invalid_review_configuration"),
    ({"option": "one_other"}, "invalid_review_configuration"),
])
def test_invalid_configuration_is_refused(value, code):
    with pytest.raises(ValueError, match=code):
        _model().validate_configuration(value, uploader_id=UP)


@pytest.mark.parametrize("uploader", ["ai", "metis"])
def test_uploader_sole_refuses_forbidden_uploader_identity(uploader):
    """Codex P2: bij uploader_sole is de uploader de reviewer; die MOET door is_forbidden_reviewer."""
    with pytest.raises(ValueError, match="forbidden_reviewer_identity"):
        _model().validate_configuration(_cfg(option="uploader_sole", reviewers=[]), uploader_id=uploader)


def test_migration_017_constraint_check_is_scoped_to_table():
    """Codex P2: de pg_constraint-check MOET op conrelid zijn gescoped, net als de andere migraties."""
    sql = (ROOT / "db/migrations/017_publication_review_provenance.sql").read_text(encoding="utf-8")
    assert "AND conrelid = 'publication_releases'::regclass" in sql


# --- legacy default (H2-7 a) -----------------------------------------------------

def test_envelope_without_choice_projects_legacy_default_matching_main():
    envelope = {"uploader_account_id": UP, "named_reviewers": [UP, "acct-b", "acct-c"]}
    before = deepcopy(envelope)
    effective = _model().effective_configuration(envelope)
    assert envelope == before, "projectie MAG NIET schrijven"
    assert effective["option"] == "one_other"
    assert effective["four_eyes_required"] is False
    assert effective["reviewers"] == ["acct-b", "acct-c"]
    assert effective["readers"] == []
    assert effective["source"] == "legacy_default"
    assert effective["needs_choice"] is False


def test_legacy_document_without_other_reviewer_needs_choice():
    effective = _model().effective_configuration({"uploader_account_id": UP, "named_reviewers": [UP]})
    assert effective["needs_choice"] is True


def test_stored_configuration_wins_and_is_validated():
    stored = _cfg(option="two_others", reviewers=["acct-b", "acct-c"])
    effective = _model().effective_configuration({"uploader_account_id": UP, "named_reviewers": [UP, "acct-b", "acct-c"],
                                                  "review_configuration": stored})
    assert effective["option"] == "two_others" and effective["source"] == "chosen"
    assert effective["needs_choice"] is False


def test_invalid_stored_configuration_fails_closed_as_needs_choice():
    effective = _model().effective_configuration({"uploader_account_id": UP, "named_reviewers": [UP],
                                                  "review_configuration": _cfg(reviewers=[])})
    assert effective["needs_choice"] is True
    assert effective["invalid_reason"] == "review_configuration_reviewers_missing"


# --- H2-1: eenmalige mapping van review_policy -----------------------------------

def _policy(primary, required=(), optional=(), contract="explicit-review-v1"):
    rows = [{"reviewer_id": r, "participation": "required"} for r in required]
    rows += [{"reviewer_id": r, "participation": "optional"} for r in optional]
    return {"contract": contract, "revision": 1, "primary": primary, "assignments": rows}


@pytest.mark.parametrize("policy,option,four_eyes,reviewers", [
    (_policy(UP), "uploader_sole", False, []),
    (_policy(UP, ["acct-b"]), "one_other", True, ["acct-b"]),
    (_policy("acct-b"), "one_other", False, ["acct-b"]),
    (_policy("acct-b", ["acct-c"]), "two_others", False, ["acct-b", "acct-c"]),
])
def test_review_policy_maps_to_best_fitting_option(policy, option, four_eyes, reviewers):
    effective = _model().effective_configuration({"uploader_account_id": UP, "named_reviewers": [], "review_policy": policy})
    assert (effective["option"], effective["four_eyes_required"], effective["reviewers"]) == (option, four_eyes, reviewers)
    assert effective["source"] == "migrated_policy"
    assert effective["needs_choice"] is False


def test_optional_participants_map_to_readers():
    effective = _model().effective_configuration(
        {"uploader_account_id": UP, "named_reviewers": [], "review_policy": _policy("acct-b", optional=["acct-r"])})
    assert effective["readers"] == ["acct-r"]
    assert "acct-r" not in effective["reviewers"]


@pytest.mark.parametrize("policy", [
    _policy(UP, ["acct-b", "acct-c"]),           # drie verplichte goedkeuringen: geen optie past
    _policy("acct-b", ["acct-c", "acct-d"]),     # drie anderen
    {"contract": "explicit-review-v1", "revision": 1, "primary": "", "assignments": []},  # ongeldig
    {"contract": "managed-review-v2", "revision": 2, "primary": "acct-b",
     "assignments": [{"reviewer_id": "acct-c", "participation": "required", "status": "archived"}],
     "review_basis": None, "minimum_required": 1},  # archived-required
])
def test_ambiguous_policy_needs_a_new_choice(policy):
    effective = _model().effective_configuration({"uploader_account_id": UP, "named_reviewers": [], "review_policy": policy})
    assert effective["needs_choice"] is True
    assert effective["source"] == "migrated_policy"


# --- migratie 017 ------------------------------------------------------------------

def test_migration_017_adds_provenance_columns_non_destructively():
    sql = (ROOT / "db/migrations/017_publication_review_provenance.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE publication_releases" in sql
    assert "ADD COLUMN IF NOT EXISTS review_provenance TEXT NOT NULL DEFAULT 'pending_verification'" in sql
    assert "ADD COLUMN IF NOT EXISTS review_provenance_changed_at TIMESTAMPTZ" in sql
    assert "'recovered_unverified'" in sql
    for forbidden in ("DROP ", "DELETE ", "UPDATE ", "TRUNCATE"):
        assert forbidden not in sql.upper()


def test_migration_017_defaults_to_pending_verification():
    """OPENVRAAG-624-P1 optie A (William): NOOIT verified_review voor een controle; 2b-6 promoveert."""
    sql = (ROOT / "db/migrations/017_publication_review_provenance.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS review_provenance TEXT NOT NULL DEFAULT 'pending_verification'" in sql
    assert "DEFAULT 'verified_review'" not in sql
    assert ("CHECK (review_provenance IN ('pending_verification', 'verified_review', 'recovered_unverified'))"
            in sql)


def test_only_ingest_and_publish_gate_read_the_configuration():
    """Vanaf 2b-3 leest alleen de ingest en de publicatiepoort (console + contract) de keuze."""
    users = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "src").rglob("*.py")
                   if "review_configuration_v1" in path.read_text(encoding="utf-8"))
    assert (ROOT / "src/review_configuration_v1.py").exists()
    assert users == ["src/four_eyes_v1.py", "src/operations_console_v1.py"]
