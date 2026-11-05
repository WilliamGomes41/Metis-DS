"""Suitability and final-judgement choices of the review form.

What may be chosen comes only from ``allowed_eindoordelen`` (the kernel's
disposition rule). The server-rendered form already hides judgements that do
not fit the checked suitability through CSS ``:has()``; JavaScript only adds
``disabled`` and clears a judgement that stopped fitting. The kernel stays the
authority and refuses a conflict with ``ReviewDispositionConflict``.
"""
from __future__ import annotations

from html import escape

from src.review.closed_review_loop_v1 import ReviewDispositionConflict, allowed_eindoordelen
from src.review.review_cockpit_v1 import EINDOORDEEL_TO_DECISION, EINDOORDEEL_VALUES, SUITABILITY_VALUES

SUITABILITY_QUESTION = "Is deze passage op zichzelf bruikbaar?"
DECISION_QUESTION = "Wat is je besluit?"
SUITABILITY_LABELS = {
    "ja": "Ja, als zelfstandig stukje kennis",
    "mist_context": "Nee, ik mis uitleg eromheen",
    "samenvoegen": "Nee, deze hoort samen met een andere passage",
    "alleen_onderbouwing": "Alleen als onderbouwing van een andere passage",
    "geen_kenniseenheid": "Geen zelfstandig stukje kennis",
}
# (name, consequence); the name alone is used when Metis refers to the choice.
EINDOORDEEL_LABELS = {
    "goedkeuren": ("Goedkeuren", "inhoud en indeling kloppen"),
    "goedkeuren_na_correctie": ("Correctie specificeren", "maak een nieuw voorstel voor beoordeling"),
    "afwijzen": ("Afwijzen", "niet gebruiken als kennisobject"),
    "later_beoordelen": ("Later beoordelen", "nog geen besluit"),
}
_EINDOORDEEL_FOR_DECISION = {decision: value for value, decision in EINDOORDEEL_TO_DECISION.items()}


def _quoted(text: str) -> str:
    return f"‘{text}’"


def _either(items: list[str]) -> str:
    quoted = [_quoted(item) for item in items]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " of " + quoted[-1]


def scope_sentence(suitability: str) -> str:
    names = [EINDOORDEEL_LABELS[value][0] for value in allowed_eindoordelen(suitability)]
    return f"Bij {_quoted(SUITABILITY_LABELS[suitability])} kun je kiezen uit {_either(names)}."


def conflict_message(error: Exception) -> str:
    """Plain-Dutch explanation of a refused combination; empty when unknown."""
    if not isinstance(error, ReviewDispositionConflict):
        return ""
    eindoordeel = _EINDOORDEEL_FOR_DECISION.get(error.decision)
    if error.suitability not in SUITABILITY_LABELS or eindoordeel not in EINDOORDEEL_LABELS:
        return ""
    return (
        f"Je koos {_quoted(SUITABILITY_LABELS[error.suitability])} met het besluit "
        f"{_quoted(EINDOORDEEL_LABELS[eindoordeel][0])}. Die combinatie kan niet. "
        f"{scope_sentence(error.suitability)} Je beoordeling is niet opgeslagen. "
        "Ga terug naar de passage en kies een besluit dat past."
    )


def _checked(selected: str, value: str) -> str:
    return " checked" if selected == value else ""


def suitability_choices_html(selected: str) -> str:
    options = "".join(
        f'<label class="check"><input type="radio" name="suitability" value="{value}"'
        f'{_checked(selected, value)}> {escape(SUITABILITY_LABELS[value])}</label>'
        for value in SUITABILITY_VALUES
    )
    return f"<fieldset><legend><h4>{SUITABILITY_QUESTION}</h4></legend>{options}</fieldset>"


def _fits_for(eindoordeel: str) -> str:
    return " ".join(s for s in SUITABILITY_VALUES if eindoordeel in allowed_eindoordelen(s))


def _scope_css() -> str:
    # One rule set per suitability value; which option fits lives only in
    # data-allowed-for, written from the kernel rule.
    form = ".review-decision-form"
    rules = [
        f"{form} [data-decision-scope]{{display:none}}",
        f'{form}:not(:has([name="suitability"]:checked)) [data-decision-scope=""]{{display:block}}',
    ]
    for value in SUITABILITY_VALUES:
        chosen = f'{form}:has([name="suitability"][value="{value}"]:checked)'
        misfit = f'[data-allowed-for]:not([data-allowed-for~="{value}"])'
        rules += [
            f'{chosen} [data-decision-scope="{value}"]{{display:block}}',
            f"{chosen} {misfit}:not(:has(:checked)){{display:none}}",
            f"{chosen} {misfit} [data-decision-mismatch]{{display:block}}",
        ]
    return "@supports selector(:has(*)){" + "".join(rules) + "}"


def decision_choices_html(object_id: str, selected: str, *, approval: str | None) -> str:
    """Final-judgement fieldset; ``approval`` is None when approving is not offered here."""
    scope_id = f"decision-scope-{object_id}"
    notes = [f'<span data-decision-scope="">Kies eerst hierboven of de passage op zichzelf bruikbaar is. '
             "Daarna zie je welke besluiten daarbij passen.</span>"]
    notes += [f'<span data-decision-scope="{value}">{escape(scope_sentence(value))}</span>'
              for value in SUITABILITY_VALUES]
    options = []
    for value in EINDOORDEEL_VALUES:
        if value == "goedkeuren" and approval is None:
            continue
        name, consequence = EINDOORDEEL_LABELS[value]
        extra = approval if value == "goedkeuren" else ""
        options.append(
            f'<label class="check" data-allowed-for="{_fits_for(value)}"><input type="radio" '
            f'name="eindoordeel" value="{value}"{extra}{_checked(selected, value)}> '
            f"<span>{escape(name)} — {escape(consequence)}"
            '<span class="decision-mismatch" data-decision-mismatch>Past niet bij je keuze hierboven. '
            "Kies een ander besluit.</span></span></label>"
        )
    return (
        f'<style>{_scope_css()}</style>'
        f'<fieldset id="decision-{escape(object_id)}" aria-describedby="{escape(scope_id)}">'
        f"<legend><h4>{DECISION_QUESTION}</h4></legend>"
        f'<p class="field-help decision-scope" id="{escape(scope_id)}">{"".join(notes)}</p>'
        + "".join(options) + "</fieldset>"
    )
