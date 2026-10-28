"""Timeline semantics for every existing persisted formation phase.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
import re

import pytest

from src.settings.insight_v1 import _diagnosis_steps_html
from src.vorming.processing_trace_v1 import PHASES


# Domain expectations from the actual producers: extraction/reconstruction,
# task planning/model proposals, and validation/accounting. There is no
# persisted phase for human publication or a separate candidate-creation step.
PHASE_GROUPS = {
    1: {"reserved", "extraction_started", "extraction_finished", "extraction_checkpoint",
        "extraction_reused", "source_reconstructed", "source_views_pinned"},
    2: {"task_plan_pinned", "worker_claimed", "worker_handover", "model_request",
        "response_received", "model_response", "proposal_parsed", "proposal_received",
        "task_rejected", "budget_exhausted"},
    4: {"validation_started", "validation_rejected", "proposal_gate_rejected",
        "evidence_resolved", "formation_accounted", "joint_validation_rejected"},
}


def test_canonical_trace_phases_have_a_timeline_expectation():
    # A newly introduced persisted phase must get an explicit UI meaning.
    assert PHASES <= set().union(*PHASE_GROUPS.values())


@pytest.mark.parametrize("phase,step", [(phase, step) for step, phases in PHASE_GROUPS.items()
                                       for phase in sorted(phases)])
@pytest.mark.parametrize("state", ["running", "failed"])
def test_timeline_shows_recorded_stage_instead_of_falling_back_to_model_work(phase, step, state):
    html = _diagnosis_steps_html({"state": state}, "recorded_attempt_failure" if state == "failed" else "",
        {}, None, {"phase": phase, "checkpoints": [{"phase": "proposal_received"}]})
    rows = re.findall(r'<li([^>]*)><h3>(\d)\..*?</h3><p class="diagnosis-status">(.*?)</p>', html, flags=re.S)
    selected = [int(number) for attrs, number, label in rows
                if (label == "Bezig" if state == "running" else 'class="blocked"' in attrs)]
    assert selected == [step]
