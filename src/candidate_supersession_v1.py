"""A3-3: candidates superseded by a fresh attempt after a contract change.

Rules (B18):
- Een verse poging na een contractwijziging MOET alle huidige kandidaten van die
  revisie als `superseded` markeren. Ze blijven zichtbaar en worden NOOIT verwijderd
  (append-only opvolger via `revision_workflow.revise_object`).
- Goedkeuringen MOGEN NIET meegaan: de opvolger heeft een nieuwe objectversie,
  dus bestaande bindingen matchen niet meer.
- De publicatiepoort MOET een goedgekeurde kandidaat die `superseded` is weigeren
  met precies één reden: `superseded_candidate_refused`.
"""
from copy import deepcopy

REASON = "contract change supersession"
REASON_CODE = "superseded_candidate_refused"


def _status(row):
    return (row.get("governance") or {}).get("validation_status")


def supersede_for_contract_change(rows, *, snapshot_id, actor):
    """Return the full history plus one superseded successor per current candidate."""
    from src.revision_workflow import current_revisions, knowledge_revision, revise_object
    history = [deepcopy(row) for row in rows]
    for row in current_revisions(rows, snapshot_id=snapshot_id):
        if not knowledge_revision(row) or _status(row) == "superseded":
            continue
        retired = revise_object(row, row, snapshot_id=snapshot_id, actor=actor, reason=REASON, force=True)
        retired["governance"]["validation_status"] = "superseded"
        history.append(retired)
    return history


def refuses_superseded(objects, approved_ids):
    """True when any approved candidate is superseded. Read-only."""
    return any(_status(obj) == "superseded" and str(obj.get("object_id") or "") in approved_ids
               for obj in objects)


def contract_changed(envelope, active_contract):
    """True only when a stored and an active full contract identifier exist and differ."""
    components = ((envelope.get("semantic_replay") or {}).get("identity") or {}).get("components") or {}
    stored = components.get("semantic_contract_version")
    if not isinstance(stored, str) or not stored or not isinstance(active_contract, str) or not active_contract:
        return False  # legacy/no replay or non-semantic mode: NOOIT supersede without evidence
    return stored != active_contract


def supersede_if_contract_changed(rows, envelope, *, active_contract, snapshot_id, actor):
    """Trigger: a fresh attempt after a full-contract change supersedes the revision's candidates."""
    if not contract_changed(envelope, active_contract):
        return rows
    return supersede_for_contract_change(rows, snapshot_id=snapshot_id, actor=actor)
