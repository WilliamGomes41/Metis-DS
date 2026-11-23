"""Minimal local lesson reconciliation. Metis receives only the reference list."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Lesson:
    revision: int
    reference_indices: tuple[int, ...]
    causes: dict[int, str] = field(default_factory=dict)
    last_check: datetime | None = None


def apply_check(lessons: dict[str, Lesson], requested_revisions: dict[str, int],
                reference_count: int, response: dict) -> set[str]:
    """Call only after a successful HTTP response, in one local transaction.

    Indices refer to this request's saved reference list. Persist that list,
    revisions and the results together in a real application.
    """
    observed = datetime.fromisoformat(response["observed_at"])
    results = response["results"]
    if (observed.tzinfo is None or len(results) != reference_count
            or any(item["index"] != i or item["state"] not in
                   {"active", "withdrawn", "superseded", "unconfirmed"}
                   for i, item in enumerate(results))):
        raise ValueError("invalid reference batch")
    affected = set()
    for name, revision in requested_revisions.items():
        lesson = lessons.get(name)
        if (lesson is None or lesson.revision != revision
                or (lesson.last_check is not None and observed <= lesson.last_check)):
            continue
        lesson.causes = {i: results[i]["state"] for i in lesson.reference_indices
                         if results[i]["state"] != "active"}
        lesson.last_check = observed
        if lesson.causes:
            affected.add(name)
    return affected
