"""From signal to next step: guidance for error groups and ranked insights.

Rules map what telemetry can prove (codes, exception types, in-repo frames,
phases, commits) onto where to look and what to try. Guidance is advice for an
engineer, never an automatic action. Processing codes reuse the existing
classification in ``attempt_diagnostics_v1``.
"""
from __future__ import annotations

from typing import Any

PHASE_ADVICE = {
    "db_execute": ("Database-queries", "Veel of trage queries. Zoek N+1-patronen: hetzelfde type query per document of object. Bundel ze in één query (zie #724–#727)."),
    "db_fetch": ("Database-resultaten lezen", "Grote resultaatsets. Lees alleen de benodigde kolommen en rijen."),
    "db_connect": ("Databaseverbinding", "Verbinding opbouwen kost tijd. Controleer de PostgreSQL-bereikbaarheid en overweeg verbindingen te hergebruiken."),
    "store_lock_wait": ("Wachten op de store-lock", "Opdrachten wachten op elkaar. Kijk welke opdracht de lock lang vasthoudt (store_lock_hold) en of zware stappen buiten de lock kunnen."),
    "store_lock_hold": ("Store-lock vastgehouden", "De lock wordt lang vastgehouden. Verplaats lezen en rekenwerk naar vóór de Storeopdracht."),
    "store_transaction": ("Storeopdracht-transactie", "De transactie duurt lang. Controleer het aantal schrijfacties en write_bundle (#729)."),
    "source_reconstruction": ("Bron reconstrueren", "Bronreconstructie is duur. Controleer of hergebruik binnen het verzoek werkt (source_reconstruction_reused)."),
    "review_render": ("Reviewpagina renderen", "Het opbouwen van de pagina is traag. Kijk naar het aantal objecten en of de werkitems gecachet worden."),
    "document_list": ("Documentenlijst", "De documentenlijst schaalt met het aantal documenten (#686)."),
}

CODE_ADVICE = {
    "store_command_foreign_owner": ("Ongeoorloofde nesting", "Een tweede console probeerde mee te doen met een open Storeopdracht. Zoek in de frames de aanroeper die een andere console gebruikt (#678)."),
    "store_command_participant_refresh_failed": ("Storeopdracht teruggedraaid", "Na een opgevangen fout kon de staat niet uit PostgreSQL worden ververst. Controleer de PostgreSQL-gezondheid op dat moment."),
    "snapshot_object_write_conflict": ("Gelijktijdige wijziging", "Iemand anders wijzigde hetzelfde document. Bij lage aantallen is dit verwacht. Bij veel conflicten: controleer de wachttijd op de lock en dubbele submits."),
    "workflow_review_write_failed": ("Review-opslag mislukt", "Schrijven naar PostgreSQL (review) faalde. Kijk naar database-fouten rond dit tijdstip."),
    "workflow_document_write_failed": ("Document-opslag mislukt", "Schrijven naar PostgreSQL (documenten) faalde. Kijk naar database-fouten rond dit tijdstip."),
    "workflow_review_unavailable": ("Review-opslag niet bereikbaar", "PostgreSQL voor reviews was niet bereikbaar. Controleer de netwerkverbinding en de credentials."),
    "workflow_document_unavailable": ("Document-opslag niet bereikbaar", "PostgreSQL voor documenten was niet bereikbaar. Controleer de netwerkverbinding en de credentials."),
    "not_authenticated": ("Niet aangemeld", "Gebruiker niet (meer) aangemeld. Geen defect, tenzij het plotseling vaak voorkomt (sessieproblemen)."),
}


def _nl(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _frames_hint(frames: list[str]) -> str | None:
    if not frames:
        return None
    return frames[-1]


def guidance_for_group(group: dict[str, Any] | None) -> dict[str, Any] | None:
    if not group:
        return None
    kind = group.get("kind")
    code = group.get("code") or ""
    frames = list(group.get("frames") or [])
    where = _frames_hint(frames)
    steps: list[str] = []
    if kind == "aborted":
        title, category = "Afronding van verzoek ontbreekt", "missing_completion"
        explanation = ("Er is geen afronding vastgelegd. De oorzaak is niet vastgesteld: "
                       "telemetrie kan ontbreken, of de verwerking kan zijn onderbroken door een crash, time-out of herstart.")
        steps = ["Controleer eerst de meetdekking, leesfouten en ontbrekende events; logs alleen bewijzen geen afbreking.",
                 "Zoek in de App Service-logs (stderr) rond dit tijdstip naar een faulthandler-stackdump "
                 "('Fatal Python error' of 'Current thread').",
                 "Bekijk de laatst vastgelegde heartbeat en fase; latere meetgegevens kunnen ontbreken.",
                 "Controleer of er rond hetzelfde moment een process_started was (herstart)."]
    elif code in CODE_ADVICE:
        title, explanation = CODE_ADVICE[code]
        category = "afgehandeld" if group.get("handled") else "fout"
    elif code:
        from src.attempt_diagnostics_v1 import classification
        category, action = classification(code)
        title = f"Foutcode {code}"
        explanation = f"Categorie: {category}. Aanbevolen eerste stap: {action.replace('_', ' ')}."
    elif kind in ("exception", "unhandled"):
        title, category = f"Onverwachte fout: {group.get('error_type') or 'Exception'}", "defect"
        explanation = "Een exceptie die niet als ConsoleError is afgehandeld: een defect in de code."
        steps = ["Begin bij het diepste Metis-frame hieronder: daar ging het mis."]
    elif kind == "log":
        title, category = "Waarschuwing of fout in de logs", "log"
        explanation = "Een logregel op WARNING of hoger. Vaak een teken van degradatie, zoals een remirror die mislukte."
    else:
        title, category = "Serverfout zonder exceptie", "status"
        explanation = "Een 5xx-status zonder vastgelegde exceptie. Controleer de route-handler."
    commits = group.get("commits") or []
    if len(commits) == 1 and group.get("count", 0) >= 3:
        steps.append(f"Komt alleen voor in commit {str(commits[0])[:12]}. Vergelijk met de vorige deploy (mogelijke regressie).")
    routes = group.get("routes") or []
    if routes:
        steps.append("Betrokken route(s): " + ", ".join(routes[:3]) + ".")
    return {"title": title, "category": category, "explanation": explanation, "where": where,
            "frames": frames, "steps": steps}


def insights(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Ranked, plain-language findings with evidence and a drill-down filter."""
    found: list[dict[str, Any]] = []
    kpis = summary.get("kpis") or {}
    if kpis.get("aborted"):
        found.append({"severity": "warning", "title": f"Bij {kpis['aborted']} verzoek(en) ontbreekt de afronding",
                      "detail": "Controleer de meetdekking: ontbrekende telemetrie en onderbroken verwerking zijn beide mogelijk. De oorzaak is niet vastgesteld.",
                      "filter": {"state": "aborted"}})
    for group in (summary.get("errors") or [])[:3]:
        if group["kind"] in ("exception", "unhandled", "status") and group["count"]:
            found.append({"severity": "serious", "title": f"{group['label']}: {group['count']}×",
                          "detail": (group.get("guidance") or {}).get("explanation", ""),
                          "filter": {"error": group["key"]}})
    for commit in summary.get("commits") or []:
        if commit.get("delta_error_rate", 0) >= 0.02 and commit["requests"] >= 10:
            found.append({"severity": "serious",
                          "title": f"Foutpercentage steeg na deploy {commit['commit'][:12]}",
                          "detail": f"+{_nl(round(commit['delta_error_rate'] * 100, 1))} procentpunt ten opzichte van de vorige commit.",
                          "filter": {"commit": commit["commit"]}})
        if commit.get("delta_p95_ratio", 0) >= 1.5 and commit["requests"] >= 10:
            found.append({"severity": "warning",
                          "title": f"Trager na deploy {commit['commit'][:12]}",
                          "detail": f"p95 is {_nl(commit['delta_p95_ratio'])}× die van de vorige commit.",
                          "filter": {"commit": commit["commit"]}})
    phases = summary.get("phases") or []
    if phases and phases[0]["share"] >= 0.4:
        name = phases[0]["phase"]
        label, advice = PHASE_ADVICE.get(name, (name, "Deze fase domineert de tijd."))
        found.append({"severity": "warning", "title": f"{label} kost {phases[0]['share'] * 100:.0f}% van de tijd",
                      "detail": advice, "filter": {}})
    if (kpis.get("lock_wait_p95_ms") or 0) >= 500:
        found.append({"severity": "warning", "title": f"Wachten op de store-lock: p95 {kpis['lock_wait_p95_ms']:.0f} ms",
                      "detail": PHASE_ADVICE["store_lock_wait"][1], "filter": {}})
    for row in (summary.get("correlations") or [])[:4]:
        if row["dimension"] == "meting":
            text = f"{row['outcome'].capitalize()} verzoeken hebben {_nl(row['lift'])}× zoveel {row['value']}"
            detail = f"Gemiddeld {_nl(row['mean_in'])} tegenover {_nl(row['mean_out'])}."
            flt: dict[str, str] = {}
        else:
            text = f"{row['outcome'].capitalize()} hangt samen met {row['dimension']} {row['value']}"
            detail = f"{row['rate'] * 100:.0f}% tegenover {row['base_rate'] * 100:.0f}% gemiddeld (lift {_nl(row['lift'])}×, {row['support']} verzoeken)."
            flt = {"route": row["value"]} if row["dimension"] == "route" else (
                {"commit": row["value"]} if row["dimension"] == "commit" else {})
        found.append({"severity": "info", "title": text, "detail": detail, "filter": flt})
    if not kpis.get("requests"):
        found.append({"severity": "info", "title": "Nog geen verzoeken in dit venster",
                      "detail": "Kies een groter tijdvenster of controleer of telemetrie is geïnstalleerd.", "filter": {}})
    order = {"critical": 0, "serious": 1, "warning": 2, "info": 3}
    return sorted(found, key=lambda item: order[item["severity"]])[:10]
