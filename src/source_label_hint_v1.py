"""Read-only hints about label-shaped text; never a review or meaning decision."""
from __future__ import annotations

import re
from typing import Any


def source_label_hint(obj: dict[str, Any]) -> dict[str, str]:
    from src.source_context_review_v1 import role_of
    if role_of(obj):
        return {}
    content = obj.get("content") or {}
    text = str(content.get("clean_text") or content.get("raw_text") or "")
    normalized = " ".join(text.split()).casefold()
    if normalized not in {"doen", "niet doen"} and not re.fullmatch(r"niveau [1-4]", normalized):
        return {}
    return {
        "status": "possible_source_label",
        "basis": "derived_from_current_text_not_a_review_decision",
        "label": "Mogelijk bronlabel — context controleren",
        "guidance": (
            "Deze korte tekst kan een label in de bron zijn. "
            "Controleer in de volledige bron bij welke passage(s) het hoort. "
            "Het is op zichzelf geen volledige aanbeveling. "
            "DOEN of NIET DOEN bewijst geen sterke of zwakke aanbeveling; "
            "een niveaunummer heeft alleen betekenis volgens de uitleg in de bron. "
            "De koppeling en betekenis zijn hiermee niet bevestigd."
        ),
    }
