"""Golden current ingest, including persisted state after refusal/failure.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from .support import choice, command, _file_console_at as console_at, observe, policy

# These goldens assert the complete retiring JSON file tree, including writers.
pytestmark = pytest.mark.file_topology

CASES = {
    "html": {},
    "receive_only": {"_receive_only": True},
    "command": {"command_id": "characterization-command"},
    "receive_command": {"_receive_only": True, "command_id": "characterization-command"},
    "bad_source_status": {"source_status": "invalid"},
    "bad_ingest_kind": {"ingest_kind": "invalid"},
    "bad_class": {"class_": "invalid"},
    "blank_title": {"title": " "},
    "blank_family": {"family": " "},
    "bad_version": {"version": "../invalid"},
    "bad_date": {"date": "invalid"},
    "missing_data": {"data": None},
    "missing_reviewers": {"named_reviewers": []},
    "sole_uploader": {"named_reviewers": [], "review_choice": choice("uploader_sole", [])},
    "sole_uploader_conflicting_named": {"review_choice": choice("uploader_sole", [])},
    "chosen_reviewers": {"named_reviewers": [], "review_choice": choice()},
    "configuration_mismatch": {"named_reviewers": ["other"], "review_choice": choice()},
    "policy": {"review_policy": policy()},
    "policy_unnamed": {"review_policy": policy(), "named_reviewers": []},
    "policy_membership_conflict": {"review_policy": policy(), "named_reviewers": ["other"]},
    "policy_and_choice": {"review_policy": policy(), "review_choice": choice()},
    "policy_choice_conflict": {"review_policy": policy(), "review_choice": choice(reviewers=["other"])},
    "policy_four_eyes_conflict": {"review_policy": policy(), "review_choice": choice(four_eyes=True)},
    "reader_is_optional_reviewer": {"review_policy": policy(optional=["other"]), "named_reviewers": [],
                                    "review_choice": choice(readers=["other"])},
    "blank_command": {"command_id": " "},
    "long_command": {"command_id": "x" * 129},
    "new_version_missing_predecessor": {"ingest_kind": "new_version"},
    "tree_html_refusal": {"class_": "beslisboom"},
    "tree_invalid_freeze": {"class_": "beslisboom", "data": b"{}", "filename": "tree.json"},
    "tree_live_without_file": {"class_": "beslisboom", "data": None,
                               "live_url": "https://example.test/api/live"},
}


@pytest.mark.parametrize("case", CASES)
def test_ingest_golden(case, tmp_path, golden):
    console = console_at(tmp_path)
    golden("ingest", case, observe(console, lambda: console.ingest(**command(**CASES[case]))))
