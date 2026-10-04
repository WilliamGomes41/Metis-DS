"""FastAPI HTML surface for the internal operations console.

Task-oriented researcher door over the knowledge kernel (Protocol v2.9).
Not the Product API, not a care-app frontend, and not a public website.
Chat is not a room.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import re
import uuid
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.document_status_v1 import DOCUMENT_STATUS_LABELS
from src.four_eyes_v1 import requires_four_eyes
from src.api_access_v1 import ApiAccessConflict, ApiAccessError, ApiAccessStoreError, PostgresApiAccessStore, VALID_SCOPES
from src.beslisboom_path_v1 import CLOSED_BOOM_TYPES, review_path_for_klasse
from src.klasse_wijzigen_v1 import is_cross_model_class_change
from src.heading_parent_list_v1 import (
    heading_visible_text,
    is_heading_object,
    parent_choice_list,
    parent_proposal_may_bind,
    parse_outline_number,
)
from src.object_taxonomy_v1 import (
    CLOSED_OBJECT_TYPES,
    CLOSED_RECOMMENDATION_STRENGTHS,
    STRENGTH_STAMP_LABELS,
    recommendation_strength_sentence,
    recommendation_strength_ui_applies,
    review_priority_rank,
)
from src.admission_gate_v1 import admission_of, is_admission_blocked
from src.recommendation_semantics_v1 import (
    confirmed_recommendation_semantics_of,
    proposed_recommendation_semantics_of,
)
from src.knowledge_relations_v1 import (
    confirmed_knowledge_relations_of,
    proposed_knowledge_relations_of,
)
from src.knowledge_relation_review_v1 import (
    has_semantic_relation_review,
    relation_choice_value,
)
from src.review_duty_v1 import authoritative_review_type, review_duty_for, review_duty_lane, reviewer_route_for
from src.review_interaction_v1 import (
    build_review_interaction_evidence,
    new_review_interaction_id,
    review_burden_projection,
)
from src.review_ledger import read_events
from src.review_context_v1 import (
    AUTHORITY_CONFIRMED,
    DIRECTION_INCOMING,
    DIRECTION_OUTGOING,
    RESOLUTION_CURRENT,
    RESOLUTION_MISSING,
    RESOLUTION_VERSION_MISMATCH,
    review_context,
)
from src.domain_dimensions_v1 import processing_issue_objects
from src.processing_diagnostics_v1 import (
    passage_export_rows,
    passage_export_csv,
    processing_diagnostic_rows,
    processing_diagnostics,
)
from src.processing_evidence_export_v1 import processing_evidence_zip
from src.source_label_hint_v1 import source_label_hint
from src.source_context_review_v1 import projection as source_context_projection, role_of
from src.extract_coverage_v1 import coverage_panel_rows
from src.review_cockpit_v1 import (
    SUITABILITY_VALUES,
    broncontext_parts,
    confirmable_proposed_type,
    found_under_path,
    map_eindoordeel,
    proposed_type_of,
    why_selected,
)
from src.ingest_limits_v1 import (
    INGEST_PAYLOAD_TOO_LARGE,
    URL_DESTINATION_NOT_ALLOWED,
    install_ingest_limits,
    read_upload_limited,
)
from src.llm_provider_v1 import load_llm_provider_config
from src.passage_formation_policy_v1 import DETERMINISTIC_MODE, SEMANTIC_MODE, SEMANTIC_V2_MODE, SEMANTIC_V3_MODE
from src.operations_console_v1 import (
    ALLOWED_CLASSES,
    ALLOWED_DELETE_NEXT,
    CONSOLE_VERSION,
    PRE_REVIEW_BLOCKED,
    ConsoleError,
    OperationsConsole,
    REPO_ROOT,
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    review_card_sentence,
    review_row_status,
    review_row_title,
    review_stacks,
    slow_review_duty,
)
from src.open_original_v1 import OpenOriginalError, full_document_segments, parse_page_bbox, researcher_visible_prose
from src.review_disposition_v1 import definitive_review_disposition
from src.publication_readiness_v1 import review_followup_queues
from src.product_security_v1 import SlidingWindowRateLimiter
from src.proportionate_review_v1 import (
    ProportionateReviewConsole,
    normal_risk_batch_counts,
    regular_individual_review_queue,
    render_normal_risk_batch_panel,
)
from src.serving_relations_v1 import CLOSED_RELATION_TYPES, proposed_relations
from src.metis_dictionary_ui import render as render_metis_dictionary

SERVICE_VERSION = CONSOLE_VERSION
COOKIE = "console_session"
FILENAME_HINT = (
    "Bestandsnaam: letters, cijfers, punt, streepje of underscore. "
    "Spaties en accenten worden automatisch aangepast. "
    "De titel hieronder mag wél spaties bevatten."
)
BRAND_DIR = REPO_ROOT / "assets" / "brand"
CANONICAL_REVIEW_TASKS = frozenset({
    "structure",
    "contextual",
    "batch",
    "second_review",
    "repair",
    "history",
    "disposition",
    "inventory",
    "waiting",
})
LEGACY_REVIEW_TASK_ALIASES = {
    "headings": "structure",
    "individual": "contextual",
    "together": "batch",
    "control": "repair",
    "decisions": "history",
    "closure": "disposition",
}
REVIEW_TASKS = frozenset({
    *CANONICAL_REVIEW_TASKS,
    *LEGACY_REVIEW_TASK_ALIASES,
})


def normalize_review_task(value: str) -> str:
    task = str(value or "").strip()
    return LEGACY_REVIEW_TASK_ALIASES.get(task, task if task in CANONICAL_REVIEW_TASKS else "")


def _passage_formation_status_html(state: OperationsConsole) -> str:
    reader = getattr(state, "_passage_formation_mode_reader", None)
    mode = reader() if callable(reader) else DETERMINISTIC_MODE
    if mode in {SEMANTIC_MODE, SEMANTIC_V2_MODE, SEMANTIC_V3_MODE}:
        label = "Semantisch met bronbewijs" if mode in {SEMANTIC_V2_MODE, SEMANTIC_V3_MODE} else "Semantisch"
        detail = (
            "Nieuwe en opnieuw verwerkte passages worden momenteel brongebonden "
            "semantisch gevormd. Review blijft verplicht."
        )
    elif mode == DETERMINISTIC_MODE:
        label = "Deterministisch"
        detail = (
            "Nieuwe en opnieuw verwerkte passages worden momenteel zonder taalmodel "
            "gevormd. Review blijft verplicht."
        )
    else:
        label = "Configuratiefout"
        detail = (
            "De passage-formation configuratie is ongeldig. Nieuwe verwerking wordt "
            "fail-closed geblokkeerd."
        )
    return (
        '<div class="banner formation-mode-status" role="status">' 
        f'<strong>Actieve verwerkingsmodus: {_esc(label)}</strong>'
        f'<p class="field-help">{_esc(detail)}</p>'
        "</div>"
    )
STATUS_LABELS = {
    "captured_not_published": "ingevoerd, niet gepubliceerd",
    "needs_review": "wacht op beoordeling",
    "approved": "goedgekeurd",
    "rejected": "afgewezen",
    "published": "gepubliceerd",
}
STATUS_LABELS.update(DOCUMENT_STATUS_LABELS)
OBJECT_TYPE_LABELS = {
    "unclassified": "Nog niet geclassificeerd",
    "factual_finding": "Feitelijke constatering",
    "heading": "Kop",
    "definition": "Definitie",
    "explanation": "Toelichting",
    "condition": "Voorwaarde",
    "exception": "Uitzondering",
    "recommendation": "Aanbeveling",
    "path": "Pad — route of resultaatbundel",
    "node": "Knoop — vraag of beslispunt",
    "outcome": "Uitkomst — afsluitend advies",
}
BLOCKER_LABELS = {
    "second_named_reviewer_required": "Nog een andere benoemde reviewer moet goedkeuren.",
    "blocked_pending_immutable_locator": "Duurzame opslag ontbreekt; publicatie blijft geblokkeerd.",
    "object_tuple_required": "Nog niet alle vereiste passagebeoordelingen zijn afgerond. Ga naar Review en rond de open beoordelingen af.",
    "pre_review_processing_incomplete": "Pre-review is nog niet afgerond; verwerk het document eerst opnieuw vanuit Documenten.",
    "four_eyes_required": "High-risk objecten vereisen four-eyes: een tweede benoemde reviewer op hetzelfde objecttupel.",
    "already_published": "Dit document is al gepubliceerd.",
    "g2_source_store_unavailable": "De bronopslag is niet bereikbaar. Publiceren is daarom geblokkeerd. Probeer later opnieuw; meld het bij de beheerder als dit blijft gebeuren.",
    "g2_source_checksum_mismatch": "Het opgeslagen bronbestand wijkt af van de gecontroleerde versie. Publiceren is geblokkeerd. Laat de beheerder dit onderzoeken.",
    "g2_source_verification_failed": "Metis kan het opgeslagen bronbestand niet betrouwbaar controleren. Publiceren is geblokkeerd. Meld dit bij de beheerder.",
    "prepublication_schema_invalid": "Een goedgekeurde passage mist gegevens die nodig zijn voor publicatie. Laat de beheerder controleren welke passage moet worden hersteld.",
    "prepublication_projection_failed": "Metis kon de publicatie niet voorbereiden. Controleer de publicatiestatus en meld dit bij de beheerder voordat je opnieuw probeert.",
}
ERROR_COPY = {
    "docling_no_source_text": "Er is geen bruikbare brontekst vastgelegd. De verwerking is geblokkeerd. Controleer het bronbestand; lege en gescande pagina’s worden in deze route nog niet automatisch onderscheiden.",
    "docling_page_text_unverified": "Voor één of meer pagina’s is geen bruikbare brontekst vastgelegd. De verwerking is geblokkeerd. Controleer het bronbestand; lege en gescande pagina’s worden in deze route nog niet automatisch onderscheiden.",
    "processing_diagnostic_write_failed": "Het foutbewijs kon niet duurzaam worden opgeslagen. Laat de beheerder de opslag controleren voordat je opnieuw probeert.",
    "processing_recovery_reason_required": "Geef een reden op voor deze eenmalige herstelpoging.",
    "processing_recovery_not_required": "Eenmalig herstel is alleen beschikbaar voor een geblokkeerd document na het maximumaantal pogingen.",
    "processing_recovery_already_authorized": "Voor dit document is al een eenmalige herstelpoging toegestaan of gebruikt.",
    "pre_review_llm_proposal_rejected": "De voorcontrole heeft het modelvoorstel afgewezen omdat het niet aan de brongebonden controles voldoet. Er zijn geen nieuwe passages voor Review vrijgegeven. Meld de technische informatie hieronder bij de beheerder.",
    "pre_review_llm_provider_unavailable": "De modeldienst kon de voorcontrole niet afronden. Meld de technische informatie bij de beheerder om de verbindingsfout te onderzoeken.",
    "pre_review_llm_api_key_required": "De modeldienst is niet geconfigureerd. Laat de beheerder de configuratie van de voorcontrole controleren.",
    "pre_review_llm_model_required": "Het model voor de voorcontrole is niet ingesteld. Laat de beheerder de configuratie controleren.",
    "pre_review_llm_response_invalid": "De modeldienst gaf geen bruikbaar antwoord voor de voorcontrole. Meld dit bij de beheerder.",
    "pre_review_llm_response_not_completed": "Het antwoord van de modeldienst was niet volledig. De voorcontrole kon daardoor niet worden afgerond.",
    "pre_review_llm_response_empty": "De modeldienst gaf geen voorstel terug. De voorcontrole kon daardoor niet worden afgerond.",
    "pre_review_llm_refused": "De modeldienst heeft het verzoek geweigerd. Meld dit bij de beheerder.",
    "pre_review_llm_abstained": "De modeldienst kon geen veilig voorstel op basis van de bron maken. Meld dit bij de beheerder.",
    "account_fields_required": "Vul alle verplichte accountgegevens in en probeer opnieuw.",
    "cannot_silently_mutate": "Deze wijziging vereist een nieuwe versie met vastgelegde reden. Gebruik de correctieactie bij de passage.",
    "class_unchanged": "Het gekozen documenttype is al ingesteld. Kies een ander type als je het wilt wijzigen.",
    "correction_role_required": "Je account heeft geen rechten om een correctie uit te voeren. Vraag de beheerder om de juiste rol.",
    "curator_role_required": "Je account heeft geen rechten voor deze beheeractie. Vraag de beheerder om hulp.",
    "document_not_unique": "Meerdere documenten passen bij deze keuze. Open het bedoelde document via Documenten en voer de actie daar uit.",
    "immutable_source_recovery_failed": "Metis kan het oorspronkelijke bronbestand niet herstellen. Meld dit bij de beheerder voordat je verdergaat.",
    "immutable_source_storage_failed": "Het bronbestand kon niet veilig worden opgeslagen. Controleer of het document bij Documenten staat en meld dit bij de beheerder voordat je opnieuw inlevert.",
    "ingest_fields_required": "Vul de verplichte documentgegevens in: titel, versie, datum en onderwerp.",
    "invalid_class": "Dit documenttype wordt niet herkend. Kies een type uit de keuzelijst Klasse.",
    "invalid_ingest_kind": "Kies bij inleveren Nieuw document of Nieuwe versie van een bestaand document.",
    "multiple_parents_not_allowed": "Een passage kan maar één bovenliggende kop hebben. Kies de kop waaronder deze passage hoort.",
    "named_reviewer_must_have_reviewer_role": "Een gekozen beoordelaar heeft geen beoordelaarsrechten. Kies een andere beoordelaar of vraag de beheerder de rol te controleren.",
    "pre_review_reprocess_not_required": "Dit document komt niet in aanmerking voor deze herstelactie. Controleer de huidige status bij Documenten.",
    "pre_review_retry_requires_postgres": "Veilige herverwerking vereist de duurzame workflowopslag. Laat de beheerder de configuratie controleren.",
    "pre_review_retry_existing_work": "Dit document bevat al passages of beoordelingen. Deze herstelactie vervangt die niet.",
    "processing_attempt_in_progress": "Er loopt al een verwerkingspoging voor dit document. Bekijk de technische diagnose voor de voortgang.",
    "processing_attempt_expired": "De vorige verwerkingspoging is onderbroken of verlopen. Start een nieuwe poging vanuit Documenten.",
    "processing_attempt_not_active": "Deze verwerkingspoging is niet meer actief. Het resultaat is niet toegepast.",
    "processing_command_id_invalid": "De verwerkingsopdracht is ongeldig. Open Documenten opnieuw en probeer het nogmaals.",
    "processing_command_conflict": "Deze opdracht hoort bij een andere verwerkingspoging. Open Documenten opnieuw.",
    "processing_dependency_failed": "De verwerking kon niet worden afgerond door een technische fout. Het bestaande werk is behouden.",
    "pre_review_llm_connection_timeout": "De verbinding met de modeldienst kwam niet binnen de ingestelde tijd tot stand. Het document is bewaard.",
    "pre_review_llm_connection_failed": "De verbinding met de modeldienst is mislukt. Het document is bewaard.",
    "pre_review_llm_inactivity_timeout": "De modeldienst gaf binnen de ingestelde wachttijd geen transportantwoord meer. Dit zegt niets over de juistheid van het document.",
    "pre_review_llm_processing_timeout": "De maximale duur van de modelaanroep is bereikt. Het document en bestaand reviewwerk zijn bewaard.",
    "pre_review_llm_processing_in_progress": "Er loopt een verwerkingspoging. De kernel bewaakt de eindtijd; transportactiviteit is geen inhoudelijke voortgang.",
    "pre_review_llm_limits_invalid": "De ingestelde verwerkingsgrenzen zijn ongeldig. Laat de beheerder de configuratie controleren.",
    "pre_review_llm_transport_unsupported": "Deze verwerkingsroute vereist de ondersteunde Linux-runtime.",
    "processing_retry_cooldown": "Een nieuwe poging is nog niet mogelijk vóór de vermelde herprobeertijd. Externe annulering van het eerdere verzoek is onbekend.",
    "processing_attempt_limit_reached": "Het ingestelde maximumaantal pogingen is bereikt. Laat de beheerder de oorzaak onderzoeken.",
    "processing_structural_limit": "Deze opdracht overschrijdt een invoer- of uitvoergrens. Herhalen zonder de oorzaak te wijzigen is geen herstel.",
    "processing_timeout": "De verwerking is niet op tijd afgerond. Het bestaande werk is behouden; start zo nodig een nieuwe poging.",
    "pre_review_no_reviewable_candidates": "De voorcontrole heeft geen passages vrijgegeven die de toelatingscontroles doorstaan. Bekijk de technische diagnose.",
    "public_signup_forbidden": "Je kunt zelf geen account aanmaken. Vraag de beheerder om toegang tot Metis.",
    "replaces_snapshot_id_required": "Kies welk bestaand document deze nieuwe versie vervangt.",
    "review_failed": "De beoordeling kon niet worden afgerond. Controleer de huidige passagestatus en meld dit bij de beheerder als de oorzaak niet zichtbaar is.",
    "reviewer_not_named_on_snapshot": "Je bent niet aangewezen als beoordelaar voor dit document. Vraag de verantwoordelijke voor het document om je toe te wijzen.",
    "primary_replacement_required": "Je kunt de primaire reviewer niet archiveren. Kies ‘Reviewer vervangen’ en wijs in dezelfde handeling een vervanger aan.",
    "reviewer_already_assigned": "Deze reviewer neemt al deel aan dit traject. Kies een andere reviewer.",
    "independent_replacement_required": "Kies een andere, beschikbare reviewer die nog geen actieve of verplichte plek in dit traject heeft.",
    "required_participation_cannot_be_downgraded": "Deze reviewer heeft nog een verplichte plek. Heractiveer die als verplicht of wijs een vervanger aan.",
    "active_participation_required": "Deze deelname is niet meer actief. Open het deelnemersbeheer opnieuw om de actuele mogelijkheden te zien.",
    "participation_not_found": "Deze deelname is niet gevonden. Open het deelnemersbeheer opnieuw.",
    "reviewer_unavailable": "Dit account is niet beschikbaar als reviewer. Kies een actieve menselijke reviewer.",
    "participation_publisher_required": "Voor deze wijziging is een publisher nodig. Een toegewezen reviewer mag alleen een andere optionele reviewer toevoegen.",
    "legacy_participation_activation_requires_publisher": "Een publisher moet het deelnemersbeheer voor dit bestaande traject eerst activeren.",
    "snapshot_object_write_conflict": "Dit traject is intussen gewijzigd. Open de pagina opnieuw en controleer de actuele situatie voordat je de handeling herhaalt.",
    "revision_schema_invalid": "De correctie levert een ongeldige passage op. Controleer je wijziging en meld dit bij de beheerder als opslaan blijft mislukken.",
    "source_continuation_changed": "De bronaanvulling is tussentijds gewijzigd. Open de passage opnieuw en controleer de actuele aanvulling.",
    "source_continuation_not_available": "Er is geen bronaanvulling beschikbaar voor deze passage. Open de passage opnieuw om de actuele mogelijkheden te zien.",
    "source_continuation_not_literal": "De aanvulling komt niet letterlijk overeen met de bron. Controleer de oorspronkelijke tekst voordat je verdergaat.",
    "unknown_account": "Dit account is niet gevonden. Open de accountlijst opnieuw en controleer je keuze.",
    "unknown_document": "Dit document is niet gevonden. Kies het opnieuw via Documenten.",
    "unknown_rereview_scope": "De gekozen omvang van de herbeoordeling wordt niet herkend. Kies een optie uit de keuzelijst.",
    "unsupported_official_file": "Dit bestandstype wordt niet ondersteund. Lever een PDF, HTML-bestand of ondersteunde beslisboomexport in.",
    "username_already_exists": "Deze gebruikersnaam bestaat al. Kies een andere naam of gebruik het bestaande account.",

    "invalid_store_path": "De bestandsnaam kan niet veilig worden verwerkt. Hernoem het bestand, bijvoorbeeld naar eenzaamheid.pdf, en kies het opnieuw.",
    "not_authenticated": "Je sessie is verlopen of je bent nog niet aangemeld. Meld je aan om verder te gaan.",
    "invalid_credentials": "De gebruikersnaam en het wachtwoord komen niet overeen. Controleer beide en probeer opnieuw.",
    "uploader_cannot_be_sole_required_reviewer": "Bij de expliciete policy kan een bevoegde uploader zelf afronden. Iedere verplicht gekozen reviewer moet onafhankelijk deelnemen. PDF-beslisbomen gebruiken de expliciete policy.",
    "word_not_first_wave": "Dit Word-bestand kan niet worden verwerkt. Sla het op als PDF en lever die PDF in.",
    "story_html_boom_player_out_of_first_wave": "Deze interactieve beslisboom kan niet als HTML-pagina worden ingeleverd. Vraag de beheerder om een ondersteunde export.",
    "story_html_alone_insufficient": "Dit HTML-bestand bevat niet de volledige beslisboom. Vraag de beheerder om een volledige beslisboomexport.",
    "live_rest_not_sole_source": "Deze koppeling levert geen vaste bronversie op. Vraag de beheerder om een volledige beslisboomexport.",
    "live_rest_sole_source": "Deze koppeling levert geen vaste bronversie op. Vraag de beheerder om een volledige beslisboomexport.",
    "outcome_review_failed": "De beslisboomuitkomst is nog niet compleet. Controleer de tekst, afzonderlijke adviezen en de koppeling met de bijbehorende voorwaarde.",
    "outcome_relation_unconfirmed": "Koppel deze uitkomst eerst aan de bijbehorende voorwaarde met de relatie ‘geldt indien’.",
    "outcome_strength_required": "Kies DOEN, OVERWEEG of NIET DOEN voor een handelingsuitkomst.",
    "empty_boom_freeze": "De beslisboomexport bevat geen stappen en uitkomsten. Controleer de export of vraag een nieuwe aan.",
    "invalid_boom_freeze": "Metis herkent dit bestand niet als beslisboomexport. Controleer of je het juiste bestand hebt gekozen.",
    "condition_fused_into_outcome": "Leg de voorwaarde ook vast met de relatie ‘geldt indien’, zodat duidelijk is wanneer deze uitkomst geldt.",
    "official_file_or_url_required": "Kies een HTML-, PDF- of boom-freezebestand, of een URL.",
    "named_reviewers_required": "Kies minstens één andere reviewer dan jezelf.",
    "publisher_role_required": "Je account heeft geen rechten om te publiceren. Vraag een bevoegde publiceerder om deze stap uit te voeren.",
    "reviewer_role_required": "Je account heeft geen rechten om te beoordelen. Vraag de beheerder om de juiste rol.",
    "researcher_role_required": "Je account heeft geen rechten om documenten in te leveren. Vraag de beheerder om de juiste rol.",
    "live_url_html_not_allowed": "Een live HTML-URL kan niet worden ingeleverd. Lever een HTML-bestand of een PDF-URL in.",
    "unknown_object_type": "Het gekozen passagetype is niet beschikbaar. Kies een type uit de keuzelijst.",
    "blocked_candidate_not_reviewable": "Deze passage voldoet nog niet aan de voorwaarden voor beoordeling. Bekijk de reden bij de passage en kies revisie of afwijzen.",
    "object_type_not_confirmed": "Bevestig eerst het passagetype met een keuze uit de keuzelijst.",
    "unknown_role": "Alleen researcher, reviewer of publisher zijn toegestaan.",
    "forbidden_reviewer_identity": "Deze identiteit kan niet als beoordelaar worden gebruikt. Kies een persoonlijk account van de beoordelaar.",
    "unknown_relation_type": "Deze relatie is niet beschikbaar. Kies een relatie uit de keuzelijst.",
    "knowledge_relation_review_required": "Controleer en bevestig eerst de voorgestelde relaties.",
    "knowledge_relation_target_stale": "Een gekoppeld kennisobject is gewijzigd. Controleer de relaties opnieuw.",
    "knowledge_relation_target_missing": "Een gekoppelde passage bestaat niet meer in deze werkversie. Open de beoordeling opnieuw en controleer de koppelingen.",
    "knowledge_relation_choice_not_available": "De gekozen koppeling is niet meer beschikbaar. Open de beoordeling opnieuw en controleer de huidige koppelingen.",
    "knowledge_relation_source_version_stale": "Het bronobject is gewijzigd. Open de review opnieuw.",
    "knowledge_relation_endpoint_type_invalid": "De koppeling past niet bij de typen van de twee passages. Controleer de passagetypen en kies daarna een passende relatie.",
    "second_review_not_required": "Voor deze passage is geen tweede beoordeling nodig. Ga terug naar Mijn werk voor je open beoordelingen.",
    "second_review_not_available": "Deze tweede beoordeling is niet meer actueel. Open Mijn werk opnieuw voor de huidige taken.",
    "first_review_required": "De eerste beoordeling is nog niet afgerond. Laat die afronden voordat je de tweede beoordeling uitvoert.",
    "independent_second_reviewer_required": "De tweede beoordeling moet door iemand anders dan de eerste beoordelaar worden uitgevoerd. Vraag een andere beoordelaar deze taak op te pakken.",
    "second_review_command_required": "Open deze passage via de taak voor tweede beoordeling in Mijn werk.",
    "open_original_required": "Open eerst de bronpassage. Type bevestigen zonder het origineel is niet toegestaan.",
    "source_locator_missing": "De verwijzing naar de oorspronkelijke passage ontbreekt. Laat de beoordeling open en vraag de beheerder om de bronverwijzing te controleren.",
    "freeze_bytes_missing": "Het oorspronkelijke bronbestand is niet beschikbaar. Laat de beoordeling open en meld dit bij de beheerder.",
    "locator_kind_mismatch": "De bronverwijzing past niet bij het opgeslagen bestand. Meld dit bij de beheerder zodat de juiste passage kan worden geopend.",
    "unsupported_locator": "Metis kan deze bronverwijzing niet openen. Laat de beoordeling open en meld dit bij de beheerder.",
    "invalid_review_decision": "Kies een eindoordeel: goedkeuren, goedkeuren na correctie, afwijzen of later beoordelen.",
    "suitability_required": "Kies of de passage geschikt is.",
    "review_comment_required": "Geef een toelichting bij goedkeuren na correctie of afwijzen.",
    "source_date_required": "Vul de publicatiedatum uit het colofon in.",
    "invalid_source_date": "Gebruik een geldige kalenderdatum.",
    "source_version_required": "Vul het versienummer van het brondocument in, bijvoorbeeld 1.0.",
    "invalid_source_version": "Versie is alleen getallen met punten, bijvoorbeeld 1.0. Geen jaartal en geen v-voorvoegsel.",
    "fast_lane_heading_required": "Je kunt alleen koppen in één keer bevestigen. Beoordeel andere passages afzonderlijk.",
    "recommendation_strength_requires_recommendation": "Sterkte hoort alleen bij een aanbeveling.",
    "source_context_role_invalid": "Kies bronlabel, context, niet opnemen of de bronrol opheffen.",
    "source_context_reason_required": "Licht toe waarom deze bronrol en koppeling juist zijn.",
    "source_context_command_required": "Het formulier is niet volledig. Open de passage opnieuw en vul de koppeling in.",
    "source_context_command_conflict": "Deze opdracht is al opgeslagen met andere keuzes. Open de passage opnieuw voor een nieuwe opdracht.",
    "source_context_target_required": "Kies minstens één passage voor een label of context. Kies bij niet opnemen geen doelpassages.",
    "source_context_target_invalid": "Kies een inhoudelijke passage uit dit document. Een kop, het label zelf of een ander contextfragment kan hier geen doel zijn.",
    "source_context_evidence_required": "Het exacte bronbewijs ontbreekt. Laat de koppeling open en vraag de beheerder de bronverwijzing te controleren.",
    "source_context_not_knowledge": "Dit fragment is bevestigd als bronlabel of context. Het is geen zelfstandige kennispassage; beoordeel de gekoppelde passages.",
    "source_context_review_incomplete": "Een broncontextkoppeling verwijst naar gewijzigde of ontbrekende tekst. Controleer de koppeling en beoordeel de betrokken passages opnieuw.",
    "source_context_check_required": "Controleer de bron en bevestig dit voordat je de koppeling opslaat.",
    "source_context_independent_transaction_required": "De broncontext kon niet als zelfstandige opdracht worden opgeslagen. Er is niets bevestigd; laat de beheerder de workflowopslag controleren.",
    "invalid_parent_structure": "Deze kop kan niet boven deze passage worden geplaatst. Kies een kop die hoger in de documentstructuur staat.",
    "unknown_recommendation_strength": "Kies DOEN, OVERWEEG of NIET DOEN.",
    "recommendation_direction_required": "Kies of de aanbeveling iets aanraadt of afraadt.",
    "recommendation_strength_confirmation_required": "Kies sterk, zwak of niet vermeld in de bron.",
    "recommendation_direction_evidence_missing": "Metis vindt geen bronbewijs voor de gekozen richting. Controleer de oorspronkelijke passage. Laat de beoordeling open als de bron onvoldoende duidelijk is.",
    "recommendation_strength_evidence_required": "Metis herkent in de bron geen expliciete aanduiding die je keuze Sterk of Zwak ondersteunt. Controleer de oorspronkelijke passage en de context. Vermeldt de bron geen sterkte? Kies Niet vermeld in de bron. Staat de sterkte er wel expliciet? Laat de beoordeling open en meld dit bij de beheerder.",
    "recommendation_strength_not_stated_conflict": "De bron bevat wel een expliciete sterkteaanduiding; kies sterk of zwak, of laat de beoordeling open als de herkende bronverwijzing niet klopt.",
    "recommendation_semantics_confirmation_invalid": "De richting en sterkte konden niet samen worden bevestigd. Controleer beide keuzes aan de hand van de oorspronkelijke passage.",
    "legacy_recommendation_strength_not_allowed": "DOEN, OVERWEEG en NIET DOEN zijn voor nieuwe richtlijnaanbevelingen vervangen door aparte richting en sterkte.",
    "published_objects_must_not_be_rewritten": "Deze passage is al gepubliceerd. Lever een nieuwe documentversie in om een wijziging te laten beoordelen.",
    "unknown_object": "Deze passage is niet meer beschikbaar. Open het document opnieuw via Review.",
    "entra_access_denied": "Je account heeft geen toegang tot Metis. Vraag de beheerder om toegang.",
    "entra_local_auth_disabled": "Aanmelden met een lokaal wachtwoord is uitgeschakeld. Gebruik de organisatieaanmelding.",
    "unknown_snapshot": "Dit document is niet meer beschikbaar. Ga naar Documenten en kies het document opnieuw.",
    "delete_confirmation_required": "Bevestig eerst dat je dit nog niet gepubliceerde document wilt verwijderen.",
    "delete_title_confirmation_required": "Typ de exacte documenttitel om te bevestigen.",
    "published_projection_must_not_be_deleted": "Dit document is gepubliceerd en kan hier niet worden verwijderd. Vraag de beheerder naar de procedure voor intrekken.",
    "publish_confirmation_required": "Bevestig eerst dat je de gereviewde kennisobjecten wilt publiceren.",
    "already_published": "Dit document is al gepubliceerd. Controleer de publicatiestatus; opnieuw publiceren is niet nodig.",
    "g2_source_store_unavailable": "De bronopslag is niet bereikbaar. Publiceren is daarom geblokkeerd. Probeer later opnieuw; meld het bij de beheerder als dit blijft gebeuren.",
    "g2_source_checksum_mismatch": "Het opgeslagen bronbestand wijkt af van de gecontroleerde versie. Publiceren is geblokkeerd. Laat de beheerder dit onderzoeken.",
    "g2_source_verification_failed": "Metis kan het opgeslagen bronbestand niet betrouwbaar controleren. Publiceren is geblokkeerd. Meld dit bij de beheerder.",
    "prepublication_schema_invalid": "Een goedgekeurde passage mist gegevens die nodig zijn voor publicatie. Laat de beheerder controleren welke passage moet worden hersteld.",
    "prepublication_projection_failed": "Metis kon de publicatie niet voorbereiden. Controleer de publicatiestatus en meld dit bij de beheerder voordat je opnieuw probeert.",
    "object_tuple_required": "Nog niet alle vereiste passagebeoordelingen zijn afgerond. Ga naar Review en rond de open beoordelingen af.",
    "unpublished_delete_role_required": "Je account heeft geen rechten om dit document te verwijderen. Vraag een onderzoeker of beoordelaar om deze stap uit te voeren.",
    "hide_selected_objects_forbidden": "Losse passages kunnen niet worden verborgen terwijl dit document in beoordeling blijft. Rond de beoordeling van deze passages af.",
    "cross_model_direct_change_blocked": "Omzetten tussen een beslisboom en een ander documenttype vereist opnieuw verwerken. Gebruik de actie voor opnieuw verwerken van dit document.",
    "class_change_confirmation_required": "Bevestig eerst de consequentie van Klasse wijzigen.",
    "published_class_change_blocked": "Van een gepubliceerd document kun je het documenttype niet wijzigen. Lever een nieuwe versie in.",
    "cross_model_reextract_required": "Dit document moet opnieuw worden verwerkt om het naar het gekozen documenttype om te zetten.",
    "source_identity_must_not_change": "Deze actie mag de oorspronkelijke brongegevens niet wijzigen. Lever een nieuw document of een nieuwe versie in.",
    INGEST_PAYLOAD_TOO_LARGE: "Het bestand of de download is te groot. Lever een kleiner HTML- of PDF-bestand in.",
    URL_DESTINATION_NOT_ALLOWED: "Deze URL wijst naar een interne bestemming en kan niet worden ingeleverd.",
    SNAPSHOT_OBJECT_WRITE_CONFLICT: (
        "Deze beoordeling is niet opgeslagen. Het document is tussentijds gewijzigd. "
        "Je invoer staat nog in het formulier; sla opnieuw op."
    ),
    "pre_review_llm_response_not_completed": "De semantische verwerking is niet afgerond. Het onvolledige antwoord is niet toegepast. Probeer de verwerking opnieuw; blijft dit gebeuren, laat de beheerder de verwerkingsgegevens controleren.",
    "unpublished_delete_requires_independent_transaction": "Het document is niet verwijderd. Rond de andere bewerking eerst af en probeer daarna opnieuw te verwijderen.",
}
RELATION_LABELS = {
    "applies_if": "geldt indien",
    "except_if": "geldt niet indien",
    "defines": "definieert",
    "explains": "licht toe",
    "supported_by": "onderbouwd door",
    "supersedes": "vervangt",
    "parent": "bovenliggend",
    "child": "onderliggend",
}


def _checked(selected: str, value: str) -> str:
    return " checked" if selected == value else ""


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _status_label(state: str) -> str:
    return STATUS_LABELS.get(state, state.replace("_", " "))


def _object_type_label(value: str | None) -> str:
    return OBJECT_TYPE_LABELS.get(value or "", (value or "").replace("_", " "))


def _beeldmerk() -> str:
    return (
        '<img class="beeldmerk" src="/brand/venvn-beeldmerk.png" '
        'width="94" height="32" alt="v&amp;vn">'
    )


def _metis_wordmark() -> str:
    return (
        '<img class="metis-wordmark" src="/brand/metis-wordmark.jpg" '
        'width="1000" height="363" alt="Metis — V&amp;VN Data Services">'
    )


def _metis_mark() -> str:
    return (
        '<img class="metis-mark" src="/brand/metis-mark.jpg" '
        'width="96" height="72" alt="">'
    )


def _login_brand() -> str:
    return f"""
    <div class="login-brand">
      <a class="login-wordmark" href="/login" aria-label="Metis — V&amp;VN Data Services">
        {_metis_wordmark()}
      </a>
      <div class="venvn-endorsement">
        <span>Een dienst van</span>
        {_beeldmerk()}
      </div>
    </div>
    """


def _page(body: str, *, title: str | None = None) -> str:
    page_title = title or "V&amp;VN Data Services — Interne operations console"
    stylesheet = BRAND_DIR / "console.css"
    stylesheet_url = "/brand/console.css"
    if stylesheet.is_file():
        # ZIP entries have fixed mtimes; version by content, not Last-Modified.
        version = hashlib.sha256(stylesheet.read_bytes()).hexdigest()[:16]
        stylesheet_url += f"?v={version}"
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
<script>
try {{
  const saved = location.pathname === '/login' ? 'light' : localStorage.getItem('metis-theme');
  document.documentElement.dataset.theme = saved === 'light' || saved === 'dark'
    ? saved : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
}} catch (_) {{ document.documentElement.dataset.theme = 'light'; }}
</script>
<link rel="stylesheet" href="{stylesheet_url}">
</head>
<body>
<div class="shell">
<div class="canvas">
{body}
</div>
</div>
<script>
document.querySelectorAll('[data-theme-toggle]').forEach((button) => {{
  const sync = () => {{
    const dark = document.documentElement.dataset.theme === 'dark';
    button.textContent = dark ? 'Lichte modus' : 'Donkere modus';
    button.setAttribute('aria-pressed', String(dark));
  }};
  button.addEventListener('click', () => {{
    const dark = document.documentElement.dataset.theme === 'dark';
    document.documentElement.dataset.theme = dark ? 'light' : 'dark';
    try {{ localStorage.setItem('metis-theme', document.documentElement.dataset.theme); }} catch (_) {{}}
    sync();
  }});
  sync();
}});
document.querySelectorAll('[data-select-review-batch]').forEach((button) => {{
  button.addEventListener('click', () => {{
    button.closest('form').querySelectorAll('[name="object_ids"]').forEach((input) => {{
      input.checked = true;
    }});
  }});
}});
document.querySelectorAll('[data-clear-review-batch]').forEach((button) => {{
  button.addEventListener('click', () => {{
    button.closest('form').querySelectorAll('[name="object_ids"]').forEach((input) => {{
      input.checked = false;
    }});
  }});
}});
document.querySelectorAll('[data-review-form]').forEach((form) => {{
  const decision = form.querySelector('[name="decision"]');
  const eindoordeel = form.querySelectorAll('[name="eindoordeel"]');
  const type = form.querySelector('[name="confirmed_object_type"]');
  const typeAction = form.querySelectorAll('[name="type_action"]');
  const typeChooser = form.querySelector('[data-type-chooser]');
  const proposed = form.querySelector('[name="proposed_object_type"]');
  const comment = form.querySelector('[name="comment"]');
  const commentField = form.querySelector('[data-comment-field]');
  const correctionField = form.querySelector('[data-correction-field]');
  const hint = form.querySelector('[data-decision-hint]');
  const submit = form.querySelector('[data-submit-review]');
  const stamp = form.querySelector('[data-stamp-block]');
  const strength = stamp ? stamp.querySelector('[name="recommendation_strength"]') : null;
  const semantics = form.querySelector('[data-recommendation-semantics-block]');
  const direction = form.querySelectorAll('[name="recommendation_direction"]');
  const strengthLevel = form.querySelectorAll('[name="recommendation_strength_level"]');
  const chooser = form.querySelector('[data-heading-chooser]');
  const search = form.querySelector('[data-heading-search]');
  const posAction = form.querySelectorAll('[name="documentpositie_action"]');
  const suitability = form.querySelectorAll('[name="suitability"]');
  const relationAck = form.querySelector('[name="relation_review_ack"]');
  const strengthTypes = new Set(['recommendation', 'outcome']);
  const selected = (nodes) => {{
    const hit = Array.from(nodes || []).find((node) => node.checked);
    return hit ? hit.value : '';
  }};
  const liveType = () => {{
    const action = selected(typeAction);
    if (action === 'dit_klopt' && proposed && proposed.value) return proposed.value;
    return type ? type.value : '';
  }};
  const updateStamp = () => {{
    const card = form.closest('[data-confirmed-type]');
    const confirmedType = card ? (card.getAttribute('data-confirmed-type') || '') : '';
    const changingType = selected(typeAction) === 'type_wijzigen';
    const confirmingProposal = selected(typeAction) === 'dit_klopt';
    const live = liveType();
    const showLegacy = Boolean(stamp) && live === 'outcome' && (
      confirmedType === 'outcome' || changingType || confirmingProposal
    );
    const showSemantics = Boolean(semantics) && live === 'recommendation' && (
      confirmedType === 'recommendation' || changingType || confirmingProposal
    );
    if (stamp) stamp.hidden = !showLegacy;
    if (strength) {{
      strength.disabled = !showLegacy;
      if (!showLegacy) strength.value = '';
    }}
    if (semantics) semantics.hidden = !showSemantics;
    direction.forEach((node) => {{
      node.disabled = !showSemantics;
      if (!showSemantics) node.checked = false;
    }});
    strengthLevel.forEach((node) => {{
      node.disabled = !showSemantics;
      if (!showSemantics) node.checked = false;
    }});
  }};
  const updateChooser = () => {{
    if (chooser) chooser.hidden = selected(posAction) !== 'andere_kop';
    if (typeChooser) typeChooser.hidden = selected(typeAction) !== 'type_wijzigen';
    if (type) {{
      if (selected(typeAction) === 'dit_klopt' && proposed && proposed.value) {{
        type.value = proposed.value;
      }}
      type.hidden = selected(typeAction) !== 'type_wijzigen';
    }}
  }};
  const update = () => {{
    const value = selected(eindoordeel) || (decision ? decision.value : '');
    if (decision && selected(eindoordeel)) {{
      if (value === 'goedkeuren') decision.value = 'approve';
      else if (value === 'goedkeuren_na_correctie') decision.value = 'revise';
      else if (value === 'afwijzen') decision.value = 'reject';
      else if (value === 'later_beoordelen') decision.value = 'later';
    }}
    const mapped = decision ? decision.value : value;
    const needsComment = mapped === 'reject' || mapped === 'revise' || value === 'afwijzen' || value === 'goedkeuren_na_correctie';
    const needsCorrection = mapped === 'revise' || value === 'goedkeuren_na_correctie';
    const needsType = mapped === 'approve' || value === 'goedkeuren';
    if (commentField) commentField.hidden = !needsComment;
    if (correctionField) correctionField.hidden = !needsCorrection;
    if (comment) comment.required = needsComment;
    if (type) type.required = needsType && selected(typeAction) === 'type_wijzigen';
    const hasType = !needsType || liveType();
    const hasComment = !needsComment || (comment && comment.value.trim());
    const hasSuitability = Boolean(selected(suitability));
    const needsRecommendationSemantics = needsType && liveType() === 'recommendation' && Boolean(semantics);
    const hasRecommendationSemantics = (
      !needsRecommendationSemantics
      || (Boolean(selected(direction)) && Boolean(selected(strengthLevel)))
    );
    const needsRelationReview = needsType && Boolean(relationAck);
    const hasRelationReview = !needsRelationReview || Boolean(relationAck && relationAck.checked);
    if (submit) {{
      submit.disabled = !value || !hasType || !hasComment || !hasSuitability || !hasRecommendationSemantics || !hasRelationReview;
      submit.textContent = mapped === 'revise' ? 'Correctie specificeren' : 'Review opslaan en volgende';
    }}
    if (hint) {{
      if (!value) hint.textContent = 'Kies een eindoordeel.';
      else if (!hasSuitability) hint.textContent = 'Kies of de passage geschikt is.';
      else if (needsType && !liveType()) hint.textContent = 'Bevestig eerst het type.';
      else if (needsRecommendationSemantics && !hasRecommendationSemantics) hint.textContent = 'Bevestig richting en sterkte van de aanbeveling.';
      else if (needsRelationReview && !hasRelationReview) hint.textContent = 'Controleer en bevestig de voorgestelde relaties.';
      else hint.textContent = '';
    }}
    updateChooser();
    updateStamp();
  }};
  eindoordeel.forEach((node) => node.addEventListener('change', update));
  typeAction.forEach((node) => node.addEventListener('change', update));
  posAction.forEach((node) => node.addEventListener('change', update));
  suitability.forEach((node) => node.addEventListener('change', update));
  if (relationAck) relationAck.addEventListener('change', update);
  if (type) type.addEventListener('change', update);
  direction.forEach((node) => node.addEventListener('change', update));
  strengthLevel.forEach((node) => node.addEventListener('change', update));
  if (comment) comment.addEventListener('input', update);
  if (decision) decision.addEventListener('change', update);
  if (search && chooser) {{
    search.addEventListener('input', () => {{
      const query = search.value.trim().toLowerCase();
      chooser.querySelectorAll('[data-parent-choice-list] li').forEach((item) => {{
        item.hidden = Boolean(query) && !item.textContent.toLowerCase().includes(query);
      }});
    }});
  }}
  updateChooser();
  updateStamp();
  update();
}});
</script>
</body>
</html>
"""


def _nav(account: dict[str, Any] | None, current: str = "", counts: dict[str, int] | None = None) -> str:
    who = (
        f'{_esc(account.get("display_name"))} · rollen: {", ".join(_esc(r) for r in account.get("roles") or [])}'
        if account
        else "niet aangemeld"
    )
    counts = counts or {}
    rooms = [
        ("home", "/", "Mijn werk", 0),
        ("ingest", "/ingest", "Inleveren", counts.get("ingest", 0)),
        ("review", "/review", "Review", counts.get("review", 0)),
        ("publish", "/publish", "Publiceren", counts.get("publish", 0)),
        ("tree", "/tree", "Documenten", counts.get("tree", 0)),
        ("settings", "/settings", "Instellingen", 0),
    ]
    links = []
    for key, href, label, count in rooms:
        current_key = "settings" if current in {"settings", "accounts", "llm-settings", "about", "audit"} else current
        current_attr = ' aria-current="page"' if current_key == key else ""
        badge = f'<span class="badge">{count}</span>' if count else ""
        links.append(f'<a href="{href}"{current_attr}>{label}{badge}</a>')
    links.append('<form method="post" action="/logout"><button class="quiet" type="submit">Uitloggen</button></form>')
    return f"""
    <header class="topbar">
      <a class="brand metis-brand" href="/" aria-label="Metis — V&amp;VN Data Services">
        <span class="metis-mark-frame">{_metis_mark()}</span>
        <span class="brand-copy">
          <strong>Metis</strong>
          <span>V&amp;VN Data Services</span>
        </span>
      </a>
      <nav class="rooms">{"".join(links)}</nav>
      <button class="theme-toggle" type="button" data-theme-toggle aria-label="Wissel tussen lichte en donkere modus">Donkere modus</button>
      <div class="who">{who}</div>
    </header>
    """


def _task_links(topic: str) -> str:
    """Separate destinations, never embedded instructional or diagnostic UI."""
    return (
        '<nav class="task-secondary-nav" aria-label="Hulp en beheer">'
        f'<a href="/help/{_esc(topic)}">Uitleg bij deze taak</a> · '
        '<a href="/settings/technical">Technisch beheer</a></nav>'
    )


def _review_validation_script() -> str:
    """Task-local validation; no changes to the home page's shared script."""
    return """<script>
    document.addEventListener('DOMContentLoaded', () => {
      document.querySelectorAll('[data-review-form]').forEach((form) => {
        const button = form.querySelector('[data-submit-review]');
        if (!button) return;
        form.noValidate = true;
        const selected = (name) => form.querySelector('[name="' + name + '"]:checked');
        const errors = () => {
          const missing = [];
          const add = (name, message) => missing.push({name, message});
          const decision = selected('eindoordeel');
          if (!decision) add('eindoordeel', 'Kies een besluit.');
          if (!selected('suitability')) add('suitability', 'Kies of de passage zelfstandig bruikbaar is.');
          if (decision && decision.value === 'goedkeuren') {
            const position = selected('documentpositie_action');
            const type = selected('type_action');
            if (!position) add('documentpositie_action', 'Bevestig de kop of kies een andere kop.');
            if (position && position.value === 'andere_kop' && !selected('parent_choice'))
              add('parent_choice', 'Kies een kop.');
            if (!type) add('type_action', 'Bevestig het type of kies een ander type.');
            const typeField = form.querySelector('[name="confirmed_object_type"]');
            const proposal = form.querySelector('[name="proposed_object_type"]');
            const kind = type && type.value === 'dit_klopt' ? proposal.value : typeField.value;
            if (type && type.value === 'type_wijzigen' && !kind) add('confirmed_object_type', 'Kies een type.');
            if (kind === 'recommendation' && form.querySelector('[data-recommendation-semantics-block]')) {
              if (!selected('recommendation_direction')) add('recommendation_direction', 'Kies de richting van de aanbeveling.');
              if (!selected('recommendation_strength_level')) add('recommendation_strength_level', 'Kies de sterkte die de bron vermeldt.');
            }
            const relation = form.querySelector('[name="relation_review_ack"]');
            if (relation && !relation.checked) add('relation_review_ack', 'Bevestig de relaties.');
          }
          Array.from(form.elements).filter((field) => field.willValidate && !field.validity.valid)
            .forEach((field) => { if (!missing.some((item) => item.name === field.name))
              add(field.name, field.name === 'comment' ? 'Vul een toelichting in.' : 'Controleer dit veld.'); });
          return missing;
        };
        const showErrors = (missing) => {
          let summary = form.querySelector('[data-review-error-summary]');
          if (!summary) {
            summary = document.createElement('div');
            summary.className = 'banner err'; summary.dataset.reviewErrorSummary = '';
            summary.setAttribute('role', 'alert'); summary.tabIndex = -1;
            form.prepend(summary);
          }
          form.querySelectorAll('[aria-invalid="true"]').forEach((field) => field.removeAttribute('aria-invalid'));
          form.querySelectorAll('[data-review-field-error]').forEach((note) => note.remove());
          form.querySelectorAll('[data-review-error-describedby]').forEach((field) => {
            field.removeAttribute('aria-describedby'); delete field.dataset.reviewErrorDescribedby;
          });
          summary.replaceChildren(); summary.hidden = !missing.length;
          if (!missing.length) return;
          const title = document.createElement('p'); title.textContent = 'Er ontbreekt nog iets'; summary.append(title);
          const list = document.createElement('ul'); summary.append(list);
          missing.forEach((item, index) => {
            const field = form.querySelector('[name="' + item.name + '"]');
            const row = document.createElement('li'); const link = document.createElement('a');
            link.textContent = item.message;
            if (field) {
              if (!field.id) field.id = 'review-required-' + form.querySelector('[name="object_id"]').value + '-' + index;
              field.setAttribute('aria-invalid', 'true'); link.href = '#' + field.id;
              const note = document.createElement('p'); note.className = 'field-error';
              note.dataset.reviewFieldError = ''; note.id = field.id + '-error'; note.textContent = item.message;
              field.closest('section, fieldset, label').append(note);
              if (!field.hasAttribute('aria-describedby')) {
                field.setAttribute('aria-describedby', note.id); field.dataset.reviewErrorDescribedby = '';
              }
              link.addEventListener('click', () => field.focus());
            }
            row.append(link); list.append(row);
          });
          summary.focus();
        };
        const enable = () => { button.disabled = false; };
        form.addEventListener('input', enable); form.addEventListener('change', enable);
        form.addEventListener('submit', (event) => {
          // Source continuation is a separate existing command, not a review decision.
          if (event.submitter && event.submitter.hasAttribute('formaction')) return;
          const missing = errors();
          if (missing.length) { event.preventDefault(); showErrors(missing); }
        });
        enable();
      });
    });
    </script>"""


def _home_tile(
    *,
    href: str,
    icon: str,
    title: str,
    description: str,
    badge: str,
    priority: bool = False,
) -> str:
    priority_class = " home-tile-priority" if priority else ""
    priority_label = '<span class="home-tile-now">Nu doen</span>' if priority else ""
    return f"""
    <a class="home-tile{priority_class}" href="{href}">
      <span class="home-tile-icon" aria-hidden="true">{icon}</span>
      <span class="home-tile-title">{title}</span>
      <span class="home-tile-description">{description}</span>
      <span class="home-tile-footer"><span class="home-tile-badge">{badge}</span>{priority_label}</span>
    </a>
    """


def _class_options(selected: str = "richtlijn") -> str:
    return "".join(
        f'<option value="{_esc(name)}"{" selected" if name == selected else ""}>{_esc(name)}</option>'
        for name in ALLOWED_CLASSES
    )


def _document_options(rows: list[dict[str, Any]], selected: str = "") -> str:
    options = ['<option value="">Kies een document</option>']
    for row in rows:
        label = f'{row["title"]} · {row["version"]} · {row["family"]}'
        snap = row["snapshot_id"]
        options.append(
            f'<option value="{_esc(snap)}"{" selected" if snap == selected else ""}>{_esc(label)}</option>'
        )
    return "".join(options)


def _type_options(confirmed: str, *, review_path: str = "richtlijn", proposed: str = "") -> str:
    shown = confirmed or proposed
    placeholder_selected = " selected" if not shown else ""
    options = [
        f'<option value="" disabled{placeholder_selected}>nog niet bevestigd</option>'
    ]
    names = CLOSED_BOOM_TYPES if review_path == "boom" else CLOSED_OBJECT_TYPES
    for name in names:
        selected = " selected" if name == shown else ""
        options.append(f'<option value="{name}"{selected}>{_esc(_object_type_label(name))}</option>')
    return "".join(options)


def _relation_checkboxes(obj: dict[str, Any], objects: list[dict[str, Any]]) -> str:
    by_id = {row.get("object_id"): row for row in objects}
    confirmed = {
        (row.get("relation_type"), row.get("target_object_id"))
        for row in (obj.get("confirmed_relations") or [])
        if row.get("relation_type") in CLOSED_RELATION_TYPES
    }
    proposed = [
        row
        for row in proposed_relations(obj)
        if row.get("relation_type") in CLOSED_RELATION_TYPES
    ]
    if not proposed:
        return ""
    boxes = []
    for row in proposed:
        rel = row["relation_type"]
        target_id = row["target_object_id"]
        target = by_id.get(target_id) or {}
        target_text = (
            (target.get("content") or {}).get("heading")
            or (target.get("content") or {}).get("clean_text")
            or target_id
        )
        checked = " checked" if (rel, target_id) in confirmed else ""
        if rel in {"child", "parent"} and is_heading_object(obj) and is_heading_object(target):
            child, parent = (obj, target) if rel == "child" else (target, obj)
            if not parent_proposal_may_bind(child, parent, objects):
                checked = ""
        label = RELATION_LABELS.get(rel, rel)
        boxes.append(
            f'<div class="relation-choice"><p class="relation-copy">Dit kennisobject is '
            f'<b>{_esc(label)}</b> aan:</p><label class="check">'
            f'<input type="checkbox" name="relation" value="{_esc(rel)}:{_esc(target_id)}"{checked}>'
            f'<span>{_esc(target_text)}</span></label></div>'
        )
    return (
        '<fieldset class="relations">'
        "<legend>Voorgestelde relatie</legend>"
        '<p class="field-help">Klopt deze voorgestelde relatie? Vink hem aan om deze te bevestigen.</p>'
        f"{''.join(boxes)}"
        '<button class="btn-secondary" type="submit" form="relations-'
        f'{_esc(obj["object_id"])}">Relatie bevestigen</button>'
        "</fieldset>"
    )


def _context_resolution_copy(endpoint: dict[str, Any]) -> str:
    resolution = str(endpoint.get("resolution") or "")
    expected = str(endpoint.get("expected_version") or "")
    current = str(endpoint.get("current_version") or "")
    if resolution == RESOLUTION_CURRENT:
        return f"versie {expected}"
    if resolution == RESOLUTION_VERSION_MISMATCH:
        return (
            f"verwacht versie {expected}; actuele versie {current}. "
            "Deze relatie is niet automatisch aangepast."
        )
    if resolution == RESOLUTION_MISSING:
        return f"verwacht versie {expected}; passage ontbreekt in deze werkversie"
    return f"versie {expected}"


def _review_context_block(
    obj: dict[str, Any],
    objects: list[dict[str, Any]],
    *,
    snapshot_id: str,
    review_path: str,
    task: str = "",
) -> str:
    context = review_context(
        obj,
        objects=objects,
        review_path=review_path,
    )
    links = context.get("links") or []
    if not links:
        return ""

    snap = quote(str(snapshot_id), safe="")
    normalized_task = normalize_review_task(task)
    task_query = f"&task={quote(normalized_task, safe='')}" if normalized_task else ""
    rows: list[str] = []
    for link in links:
        outgoing = link.get("direction") == DIRECTION_OUTGOING
        related = link.get("target") if outgoing else link.get("source")
        related = related if isinstance(related, dict) else {}
        relation_type = str(link.get("relation_type") or "")
        label = RELATION_LABELS.get(relation_type, relation_type)
        authority = str(link.get("authority") or "")
        authority_label = (
            "Bevestigde relatie"
            if authority == AUTHORITY_CONFIRMED
            else "Voorstel van Metis"
        )
        direction_label = "uitgaand" if outgoing else "inkomend"
        text = str(related.get("text") or related.get("object_id") or "")
        object_id = str(related.get("object_id") or "")
        object_type = _object_type_label(str(related.get("object_type") or ""))
        resolution = str(link.get("resolution") or RESOLUTION_CURRENT)
        stale_endpoint = (
            link.get("stale_endpoint")
            if isinstance(link.get("stale_endpoint"), dict)
            else None
        )
        resolution_copy = _context_resolution_copy(
            stale_endpoint if stale_endpoint is not None else related
        )
        stale_class = " relation-context-stale" if resolution != RESOLUTION_CURRENT else ""
        warning = ""
        if resolution != RESOLUTION_CURRENT:
            warning = (
                '<p class="banner warn relation-context-warning">'
                f'{_esc(resolution_copy)}</p>'
            )
        duty = related.get("review_duty")
        duty_copy = ""
        if isinstance(duty, dict):
            stage = str(duty.get("stage") or "")
            duty_copy = (
                "Tweede beoordeling open"
                if stage == "second_review"
                else "Nog te beoordelen"
            )
        else:
            duty_copy = "Geen open reviewplicht"

        open_link = ""
        if object_id and resolution != RESOLUTION_MISSING:
            open_link = (
                f'<a class="btn-secondary relation-context-open" '
                f'href="/review?document={snap}&object={quote(object_id, safe="")}{task_query}">'
                "Open passage</a>"
            )

        rows.append(
            f'<article class="relation-context-item{stale_class}" '
            f'data-relation-authority="{_esc(authority)}" '
            f'data-relation-direction="{_esc(direction_label)}" '
            f'data-relation-resolution="{_esc(resolution)}">'
            f'<p class="eyebrow">{_esc(authority_label)}</p>'
            f'<p><b>{_esc(label)}</b> · {_esc(direction_label)}</p>'
            f'<p>{_esc(text)}</p>'
            f'<p class="meta"><span>type <b>{_esc(object_type)}</b></span> '
            f'<span>{_esc(resolution_copy)}</span> '
            f'<span>{_esc(duty_copy)}</span></p>'
            f'{warning}{open_link}'
            "</article>"
        )

    return f"""
      <section class="review-card-context review-step" data-review-step="context" aria-label="Samenhang met andere kennisobjecten">
        <h4>Samenhang met andere kennisobjecten</h4>
        <div class="relation-context-list">{"".join(rows)}</div>
      </section>
    """


def _knowledge_relation_review_block(
    obj: dict[str, Any],
    objects: list[dict[str, Any]],
    *,
    review_path: str,
    draft: dict[str, Any] | None = None,
) -> str:
    if not has_semantic_relation_review(obj):
        return ""

    context = review_context(
        obj,
        objects=objects,
        review_path=review_path,
        stage="first_review",
    )
    outgoing_by_key = {}
    for link in context.get("links") or []:
        if link.get("direction") != DIRECTION_OUTGOING:
            continue
        target = link.get("target") if isinstance(link.get("target"), dict) else {}
        key = (
            str(link.get("relation_type") or ""),
            str(target.get("object_id") or ""),
            str(target.get("expected_version") or ""),
        )
        outgoing_by_key[key] = link

    proposed = proposed_knowledge_relations_of(obj)
    confirmed = confirmed_knowledge_relations_of(obj)
    basis = proposed if proposed else confirmed
    confirmed_keys = {
        (
            str(row.get("relation_type") or ""),
            str(row.get("target_object_id") or ""),
            str(row.get("target_object_version") or ""),
        )
        for row in confirmed
    }

    submitted_choices = (draft or {}).get("relation_choice")
    selected_choices = set(submitted_choices) if isinstance(submitted_choices, list) else None
    rows: list[str] = []
    for relation in basis:
        relation_type = str(relation.get("relation_type") or "")
        target_id = str(relation.get("target_object_id") or "")
        target_version = str(relation.get("target_object_version") or "")
        key = (relation_type, target_id, target_version)
        link = outgoing_by_key.get(key) or {}
        target = link.get("target") if isinstance(link.get("target"), dict) else {}
        target_text = str(target.get("text") or target_id)
        resolution = str(target.get("resolution") or RESOLUTION_MISSING)
        resolution_copy = _context_resolution_copy(
            target
            if target
            else {
                "resolution": RESOLUTION_MISSING,
                "expected_version": target_version,
                "current_version": "",
            }
        )
        selected = (
            relation_choice_value(relation) in selected_choices
            if selected_choices is not None else key in confirmed_keys
        )
        checked = " checked" if selected else ""
        label = RELATION_LABELS.get(relation_type, relation_type)
        stale_note = (
            f' <span class="relation-review-stale">({_esc(resolution_copy)})</span>'
            if resolution != RESOLUTION_CURRENT
            else f' <span class="muted">(versie {_esc(target_version)})</span>'
        )
        rows.append(
            '<label class="check relation-review-choice" '
            f'data-relation-resolution="{_esc(resolution)}">'
            f'<input type="checkbox" name="relation_choice" '
            f'value="{_esc(relation_choice_value(relation))}"{checked}>'
            f'<span><b>{_esc(label)}</b> → {_esc(target_text)}{stale_note}</span>'
            "</label>"
        )

    return f"""
      <section class="review-step review-knowledge-relations" data-review-step="relations">
        <h4>Welke relaties kloppen?</h4>
        <div class="relation-review-list">{"".join(rows)}</div>
        <label class="check relation-review-ack">
          <input type="checkbox" name="relation_review_ack" value="1"{_checked((draft or {}).get("relation_review_ack", ""), "1")}>
          <span>Ik heb de voorgestelde relaties gecontroleerd.</span>
        </label>
      </section>
    """


def _review_location(
    console: OperationsConsole,
    snapshot_id: str,
    object_id: str | None = None,
    *,
    task: str = "",
) -> str:
    """Redirect only to a stored snapshot (and optional object), never raw form bytes."""
    envelope = console._envelope(snapshot_id)
    snap = quote(str(envelope["snapshot_id"]), safe="")
    task_query = f"&task={quote(task, safe='')}" if task in REVIEW_TASKS else ""
    if not object_id:
        return f"/review?document={snap}{task_query}"
    known = next(
        (
            row["object_id"]
            for row in console.snapshot_objects(envelope["snapshot_id"])
            if row["object_id"] == object_id
        ),
        None,
    )
    if known is None:
        raise ConsoleError("unknown_object")
    return f"/review?document={snap}&object={quote(str(known), safe='')}{task_query}"


def _coverage_panel(objects: list[dict[str, Any]]) -> str:
    rows = coverage_panel_rows(objects)
    if not rows:
        return ""
    items = []
    for row in rows:
        parts = [
            f"{_esc(label)} {count}"
            for label, count in (row.get("labels") or {}).items()
            if count
        ]
        detail = ", ".join(parts) if parts else "geen passages"
        items.append(
            f"<li><b>{_esc(row['section'])}</b> — {detail}</li>"
        )
    return f"""
      <details class="review-coverage" aria-label="Controleoverzicht per kop">
        <summary>Controleoverzicht per kop <span class="info-tip" tabindex="0" aria-label="Dit overzicht laat zien wat al is afgehandeld en wat nog aandacht vraagt.">ⓘ<span class="info-tip-text">Dit overzicht laat zien wat al is afgehandeld en wat nog aandacht vraagt.</span></span></summary>
        <p class="lead">Dit overzicht is bedoeld om de voortgang te controleren. Je hoeft hier geen extra stap uit te voeren.</p>
        <ul>{"".join(items)}</ul>
      </details>
    """


def _document_list_page(rows: list[dict[str, Any]], *, q: str, page: int, path: str) -> tuple[list[dict[str, Any]], str]:
    """Bound rendered document lists; search the complete authorized collection."""
    query = q.strip()
    terms = query.casefold().split()
    matches = [row for row in rows if all(term in (
        str(row.get("title") or "") + " " + str(row.get("family") or "")
    ).casefold() for term in terms)]
    size = 25
    pages = max(1, (len(matches) + size - 1) // size)
    page = max(1, min(page, pages))
    links = []
    for number, label in ((page - 1, "Vorige"), (page + 1, "Volgende")):
        if 1 <= number <= pages:
            links.append(f'<a href="{path}?{_esc(urlencode({"q": query, "page": number}))}">{label}</a>')
    controls = f'''<form method="get" action="{path}" class="document-search">
      <label>Zoek documenten<input type="search" name="q" value="{_esc(query)}" placeholder="Titel of onderwerp"></label>
      <button class="btn-secondary" type="submit">Zoeken</button>
    </form><nav class="document-pagination" aria-label="Documentpagina’s">
      <span>{len(matches)} documenten · pagina {page} van {pages}</span> {" · ".join(links)}</nav>'''
    return matches[(page - 1) * size:page * size], controls


def _document_summary(row: dict[str, Any]) -> str:
    from src.document_status_ui_v1 import current_document_lifecycle_status
    lifecycle = current_document_lifecycle_status(str(row.get("snapshot_id") or "")) or {}
    status = row.get("meaningful_status") or lifecycle.get("presentation_status") or row.get("status") or row.get("state") or ""
    return (f'<span class="doc-title">{_esc(row["title"])}</span>'
            f'<span class="meta">Versie {_esc(row["version"])} · {_esc(row.get("family"))} · '
            f'{_esc(row.get("class"))} · status <b>{_esc(_status_label(status))}</b></span>')


def _document_card_heading(row: dict[str, Any]) -> str:
    return f"""
      <header>
        <p class="doc-title">{_esc(row["title"])}</p>
      </header>
      <p class="meta">
        <span>versie <b>{_esc(row["version"])}</b></span>
        <span>onderwerp <b>{_esc(row["family"])}</b></span>
        <span>klasse <b>{_esc(row["class"])}</b></span>
        <span>status <b>{_esc(_status_label(row.get("status") or row.get("state") or ""))}</b></span>
      </p>
    """


def _can_delete_unpublished(account: dict[str, Any] | None) -> bool:
    roles = set((account or {}).get("roles") or [])
    return bool(roles & {"researcher", "reviewer"})


def _unpublished_delete_control(
    row: dict[str, Any],
    *,
    account: dict[str, Any] | None,
    console: OperationsConsole,
    next_path: str,
    mutable: bool | None = None,
) -> str:
    """Researcher Dutch delete control. Documenten room (/tree) only. Type-to-confirm title."""
    if next_path != "/tree":
        return ""
    if not _can_delete_unpublished(account):
        return ""
    snap = str(row.get("snapshot_id") or "")
    if not snap:
        return ""
    if mutable is False:
        return ""
    if mutable is None:
        try:
            if console.snapshot_is_published(snap):
                return ""
        except ConsoleError:
            return ""
    title = str(row.get("title") or "")
    target = next_path if next_path in ALLOWED_DELETE_NEXT else "/tree"
    return f"""
      <form class="delete-unpublished" method="post" action="/documents/delete">
        <input type="hidden" name="snapshot_id" value="{_esc(snap)}">
        <input type="hidden" name="next" value="{_esc(target)}">
        <p class="delete-title-confirm">
          <span>Documenttitel</span>
          <strong class="delete-title-shown">{_esc(title)}</strong>
        </p>
        <label>Typ de exacte documenttitel
          <input name="confirm_title" autocomplete="off" required>
        </label>
        <label class="check">
          <input type="checkbox" name="confirm" value="1">
          <span>Ik bevestig dat ik dit unpublished document wil verwijderen</span>
        </label>
        <button class="btn-secondary" type="submit">Verwijder unpublished document</button>
      </form>
    """


def _strength_options(selected: str | None) -> str:
    options = ['<option value="">Nog niet vastgelegd</option>']
    for name in CLOSED_RECOMMENDATION_STRENGTHS:
        mark = " selected" if name == selected else ""
        options.append(
            f'<option value="{name}"{mark}>{_esc(STRENGTH_STAMP_LABELS[name])}</option>'
        )
    return "".join(options)


def _stamp_block(obj: dict[str, Any], *, hidden: bool = False) -> str:
    proposed = obj.get("proposed_recommendation_strength") or ""
    confirmed = obj.get("confirmed_recommendation_strength") or ""
    shown = confirmed or proposed
    sentence = recommendation_strength_sentence(shown) if shown else (
        "Sterkte van de aanbeveling: kies DOEN, OVERWEEG of NIET DOEN."
    )
    hidden_attr = " hidden" if hidden else ""
    disabled_attr = " disabled" if hidden else ""
    return f"""
                    <section class="review-step review-stamp" data-stamp-block{hidden_attr}>
                      <h4>Sterkte van de aanbeveling</h4>
                      <p class="stamp-sentence">{_esc(sentence)}</p>
                      <label for="strength-{_esc(obj["object_id"])}">Sterkte</label>
                      <select id="strength-{_esc(obj["object_id"])}" name="recommendation_strength"{disabled_attr}>
                        {_strength_options(shown or None)}
                      </select>
                    </section>
    """


def _recommendation_semantics_block(
    obj: dict[str, Any],
    draft: dict[str, Any],
    *,
    hidden: bool = False,
) -> str:
    proposed = proposed_recommendation_semantics_of(obj)
    confirmed = confirmed_recommendation_semantics_of(obj)
    direction = str(draft.get("recommendation_direction") or confirmed.get("direction") or "")
    strength_level = str(draft.get("recommendation_strength_level") or "")
    if not strength_level and confirmed:
        strength_level = (
            "not_stated"
            if confirmed.get("strength_status") == "not_stated"
            else str(confirmed.get("strength") or "")
        )

    proposed_direction = str(proposed.get("direction") or "")
    if proposed.get("strength_status") == "not_stated":
        proposed_strength = "niet vermeld in de bron"
    elif proposed.get("strength_status") == "unmapped":
        proposed_strength = "expliciete bronterm nog niet gemapt"
    else:
        proposed_strength = {
            "strong": "sterk",
            "weak": "zwak",
        }.get(str(proposed.get("strength") or ""), "niet voorgesteld")
    direction_label = {"for": "aanraden", "against": "afraden"}.get(
        proposed_direction,
        "niet voorgesteld",
    )
    direction_evidence = str(proposed.get("direction_evidence_span") or "")
    strength_evidence = str(proposed.get("strength_evidence_span") or "")
    evidence_html = (
        '<div class="recommendation-semantics-evidence">'
        f'<p><b>Metis stelt voor:</b> richting {_esc(direction_label)}; sterkte {_esc(proposed_strength)}.</p>'
        + (
            f'<p><b>Richting uit de bron:</b> {_esc(direction_evidence)}</p>'
            if direction_evidence
            else ""
        )
        + (
            f'<p><b>Sterkte uit de bron:</b> {_esc(strength_evidence)}</p>'
            if strength_evidence
            else ""
        )
        + "</div>"
    )
    hidden_attr = " hidden" if hidden else ""
    disabled_attr = " disabled" if hidden else ""
    return f"""
                    <section class="review-step review-recommendation-semantics" data-recommendation-semantics-block data-stamp-block{hidden_attr}>
                      <h4>Sterkte van de aanbeveling</h4>
                      {evidence_html}
                      <fieldset>
                        <legend>Richting</legend>
                        <label class="check"><input type="radio" name="recommendation_direction" value="for"{disabled_attr}{_checked(direction, "for")}> Aanraden</label>
                        <label class="check"><input type="radio" name="recommendation_direction" value="against"{disabled_attr}{_checked(direction, "against")}> Afraden</label>
                      </fieldset>
                      <fieldset>
                        <legend>Welke sterkte vermeldt de bron?</legend>
                        {('<div class="banner err" role="alert">' + _esc(ERROR_COPY.get(draft.get("validation_error", ""), "")) + '<p>Je beoordeling is niet opgeslagen. Je invoer staat hieronder nog klaar.</p></div>') if draft.get("validation_error") else ""}
                        <label class="check"><input type="radio" name="recommendation_strength_level" value="strong"{disabled_attr}{_checked(strength_level, "strong")}> Sterk</label>
                        <label class="check"><input type="radio" name="recommendation_strength_level" value="weak"{disabled_attr}{_checked(strength_level, "weak")}> Zwak</label>
                        <label class="check"><input type="radio" name="recommendation_strength_level" value="not_stated"{disabled_attr}{_checked(strength_level, "not_stated")}> Niet vermeld in de bron</label>
                      </fieldset>
                      <select name="recommendation_strength" hidden disabled data-legacy-recommendation-strength-compat aria-hidden="true"></select>
                    </section>
    """


def _heading_chooser(
    obj: dict[str, Any],
    objects: list[dict[str, Any]],
    snapshot_id: str,
    selected_parent: str = "",
) -> str:
    choice = parent_choice_list(objects)
    snap = quote(str(snapshot_id), safe="")
    choice_items = []
    for row in choice:
        text = heading_visible_text(row)
        outline = parse_outline_number(text)
        loc = (row.get("provenance") or {}).get("source_locator") or row.get("source_locator") or {}
        page = loc.get("page") or loc.get("locator_value")
        object_id = str(row.get("object_id") or "")
        attrs = f' data-object-id="{_esc(object_id)}"' * bool(object_id)
        if outline:
            attrs = f' data-outline="{".".join(str(part) for part in outline)}"' + attrs
        locator = f' <span class="muted">({_esc(page)})</span>' * bool(page)
        blocked = (
            is_heading_object(obj)
            and is_heading_object(row)
            and not parent_proposal_may_bind(obj, row, objects)
        )
        may_select = bool(object_id) and object_id != obj.get("object_id") and not blocked
        radio = (
            f'<label class="heading-select"><input type="radio" name="parent_choice" '
            f'value="{_esc(object_id)}"{_checked(selected_parent, object_id)}> Kies</label>'
        ) * may_select
        choice_items.append(
            f'<li data-heading-role="body"{attrs}>'
            f'<a href="/review?document={snap}&object={quote(object_id, safe="")}">{_esc(text)}</a>'
            f"{locator}{radio}</li>"
        )
    return f"""
                    <div data-heading-chooser hidden>
                      <p>Koppen in de hoofdtekst</p>
                      <label>Zoek een kop
                        <input type="search" data-heading-search autocomplete="off">
                      </label>
                      <div data-parent-choice-list>
                        <ol class="parent-choice-rows">{"".join(choice_items)}</ol>
                      </div>
                    </div>
    """


def _semantic_selection_markup(source_text: str, selection_text: str) -> tuple[str, bool]:
    tokens = (selection_text or "").split()
    if not source_text or not tokens:
        return _esc(source_text), False
    pattern = re.compile(r"\s+".join(re.escape(token) for token in tokens))
    matches = list(pattern.finditer(source_text))
    if len(matches) != 1:
        return _esc(source_text), False
    match = matches[0]
    return (
        _esc(source_text[: match.start()])
        + '<mark class="broncontext-marked">'
        + _esc(source_text[match.start() : match.end()])
        + "</mark>"
        + _esc(source_text[match.end() :]),
        True,
    )


def _source_bound_fields_html(obj: dict[str, Any]) -> str:
    from src.source_bound_fields_v2 import KEY, FIELDS, bound_values
    record = (obj.get("metadata") or {}).get(KEY)
    if record is None:
        return ""
    if record.get("version") == "source-bound-fields-v3":
        from src.source_bound_fields_v3 import FIELDS
    labels = {
        "actor_span": "Uitvoerder", "target_group_span": "Doelgroep", "scope_span": "Toepassingsbereik",
        "subject_span": "Onderwerp", "predicate_span": "Gezegde",
        "type_evidence_spans": "Bewijs voor type", "actor_of_scope": "Actor of doelgroep",
        "recommended_action": "Handeling", "action_object_or_goal": "Doel of object",
        "recommendation_evidence_span": "Aanbevelingsbewijs", "defined_term": "Gedefinieerde term",
        "definiens_span": "Definitie", "condition_span": "Voorwaarde",
        "condition_target": "Waarvoor geldt de voorwaarde", "exception_span": "Uitzondering",
        "exception_target": "Waarop geldt de uitzondering", "support_span": "Onderbouwing",
        "supported_object": "Onderbouwde uitspraak", "factual_claim_span": "Bevinding",
    }
    try:
        values = bound_values(record, text=str((obj.get("content") or {}).get("clean_text") or ""),
                              proposed_type=str(obj.get("proposed_object_type") or "unclassified"),
                              context=((obj.get("metadata") or {}).get("source_bound_context") or {}).get("entries") or [])
    except ValueError:
        return '<p class="muted" data-source-bound-fields-invalid>Het veldbewijs past niet meer bij deze passage. Opnieuw controleren is nodig.</p>'
    rows = []
    reasons = {"not_stated": "Niet expliciet vermeld", "uncertain": "Onzeker", "not_applicable": "Niet van toepassing"}
    for field in FIELDS:
        entry = record["evidence"][field]
        if entry.get("missing_reason") == "not_applicable" and field not in values:
            continue
        value = values.get(field)
        text = " / ".join(value) if isinstance(value, list) else value
        rows.append(f'<tr><th>{_esc(labels[field])}</th><td>{_esc(text or reasons.get(entry.get("missing_reason"), "Ontbreekt"))}</td></tr>')
    return ('<section data-source-bound-fields><h4>Bronbewijs bij het voorstel</h4>'
            '<table><tbody>' + ''.join(rows) + '</tbody></table></section>')


def _broncontext_html(
    obj: dict[str, Any],
    snapshot_id: str,
    object_id: str,
    passage_ok: bool,
    *,
    task: str = "",
) -> str:
    parts = broncontext_parts(obj)
    lines = []
    hint = source_label_hint(obj)
    if hint:
        lines.append(f'<p data-source-label-hint><strong>{_esc(hint["label"])}</strong></p>')
    for ancestor in parts["ancestor_headings"]:
        lines.append(f'<p class="broncontext-heading">{_esc(ancestor)}</p>')
    if parts["current_heading"]:
        lines.append(f'<p class="broncontext-heading">{_esc(parts["current_heading"])}</p>')
    if parts["previous_paragraph"]:
        lines.append(f'<p class="broncontext-prev">{_esc(parts["previous_paragraph"])}</p>')

    source_exact = str(parts["source_text_exact"] or "")
    origin = str(parts.get("semantic_selection_origin") or "")
    selection_text = str(parts.get("semantic_selection_text") or "")
    spans = parts.get("semantic_spans") or []
    selection_warning = ""
    if source_exact and origin:
        selection_label = (
            "Door Metis voorgestelde bronselectie"
            if origin == "proposal_selected"
            else "Nog niet beoordeelde brontekst"
        )
        lines.append(f'<p class="eyebrow">{_esc(selection_label)}</p>')
        source_markup, found = _semantic_selection_markup(source_exact, selection_text)
        lines.append(
            f'<p class="broncontext-source" data-semantic-origin="{_esc(origin)}" '
            f'data-semantic-span-count="{len(spans)}">{source_markup}</p>'
        )
        if not found:
            selection_warning = (
                '<p class="muted" data-semantic-selection-unresolved>'
                "De opgeslagen bronselectie kon niet eenduidig in deze context worden gemarkeerd. "
                "Controleer daarom de volledige bron."
                "</p>"
            )
    elif source_exact:
        lines.append(
            f'<p class="broncontext-marked"><mark class="broncontext-marked">{_esc(source_exact)}</mark></p>'
        )
    if parts["next_paragraph"]:
        lines.append(f'<p class="broncontext-next">{_esc(parts["next_paragraph"])}</p>')
    missing = ""
    if not passage_ok:
        missing = (
            '<p class="muted">De exacte plaats in het origineel kan niet worden geopend; '
            "goedkeuren blijft uitgeschakeld.</p>"
        )
    return f"""
                  <section class="review-card-bronpassage review-broncontext" data-review-step="b" aria-label="Broncontext">
                    <h4>Bronpassage en context</h4>
                    <div class="broncontext-freeze">{"".join(lines)}</div>
                    {selection_warning}
                    {missing}
                    {_source_bound_fields_html(obj)}
                    <p><a class="btn-secondary" href="/review/bronpassage?document={_esc(snapshot_id)}&amp;object={_esc(object_id)}{f'&amp;task={_esc(task)}' if task in REVIEW_TASKS else ''}">Open oorspronkelijke bron</a></p>
                  </section>
    """


_REVIEW_DRAFT_SETS = {
    "suitability": frozenset(SUITABILITY_VALUES),
    "eindoordeel": frozenset(
        {"goedkeuren", "goedkeuren_na_correctie", "afwijzen", "later_beoordelen"}
    ),
    "documentpositie_action": frozenset({"dit_klopt", "andere_kop"}),
    "type_action": frozenset({"dit_klopt", "type_wijzigen"}),
}
_REVIEW_DRAFT_DEFAULTS: dict[str, str] = {}
_RECOMMENDATION_DIRECTION_VALUES = frozenset({"for", "against"})
_RECOMMENDATION_STRENGTH_LEVEL_VALUES = frozenset({"strong", "weak", "not_stated"})
def _sanitize_review_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    sanitized = {
        key: str(value or "")
        for key, value in (draft or {}).items()
        if key != "relation_choice"
    }
    if draft is not None and "relation_choice" in draft:
        choices = draft["relation_choice"]
        sanitized["relation_choice"] = (
            [str(value) for value in choices] if isinstance(choices, list) else []
        )
    closed_types = frozenset(CLOSED_OBJECT_TYPES) | frozenset(CLOSED_BOOM_TYPES)
    for key, allowed in _REVIEW_DRAFT_SETS.items():
        default = _REVIEW_DRAFT_DEFAULTS.get(key, "")
        value = sanitized.get(key, "") or default
        sanitized[key] = value if value in allowed else default
    confirmed = sanitized.get("confirmed_object_type", "")
    sanitized["confirmed_object_type"] = confirmed if confirmed in closed_types else ""
    direction = sanitized.get("recommendation_direction", "")
    sanitized["recommendation_direction"] = (
        direction if direction in _RECOMMENDATION_DIRECTION_VALUES else ""
    )
    strength_level = sanitized.get("recommendation_strength_level", "")
    sanitized["recommendation_strength_level"] = (
        strength_level if strength_level in _RECOMMENDATION_STRENGTH_LEVEL_VALUES else ""
    )
    return sanitized


def _review_conflict_html(
    conflict: bool,
    *,
    current: dict[str, Any] | None = None,
    draft: dict[str, Any] | None = None,
) -> str:
    if not conflict:
        return ""
    banner = (
        f'<div class="banner err" data-stale-write-conflict '
        f'data-error-code="{_esc(SNAPSHOT_OBJECT_WRITE_CONFLICT)}">'
        f"{_esc(ERROR_COPY[SNAPSHOT_OBJECT_WRITE_CONFLICT])}</div>"
    )
    diffs: list[str] = []
    if current is not None and draft is not None:
        passage = (current.get("metadata") or {}).get("review_passage") or {}
        current_suit = str(passage.get("suitability") or "")
        draft_suit = str(draft.get("suitability") or "").strip()
        if current_suit and current_suit != draft_suit:
            diffs.append(
                '<div data-diff-field="suitability">'
                f"<dt>Huidige geschiktheid</dt><dd>{_esc(current_suit)}</dd>"
                f"<dt>Jouw concept</dt><dd>{_esc(draft_suit)}</dd></div>"
            )
        current_eindoordeel = str(passage.get("eindoordeel") or "")
        draft_eindoordeel = str(draft.get("eindoordeel") or "").strip()
        if current_eindoordeel and current_eindoordeel != draft_eindoordeel:
            diffs.append(
                '<div data-diff-field="eindoordeel">'
                f"<dt>Huidig eindoordeel</dt><dd>{_esc(current_eindoordeel)}</dd>"
                f"<dt>Jouw concept</dt><dd>{_esc(draft_eindoordeel)}</dd></div>"
            )
    extra = ""
    if diffs:
        extra = (
            '<aside data-stale-write-differences>'
            "<p>Huidige verschillen ten opzichte van jouw concept:</p>"
            f"<dl>{''.join(diffs)}</dl></aside>"
        )
    return banner + extra


def _snapshot_revision_input(revision: str) -> str:
    return f'<input type="hidden" name="snapshot_revision" value="{_esc(revision)}">'


def _review_index_item(
    obj: dict[str, Any],
    snapshot_id: str,
    *,
    checkbox: bool = False,
    reason: str = "",
    task: str = "",
) -> str:
    title = review_row_title(obj)
    status = review_row_status(obj)
    task_query = f"&amp;task={_esc(task)}" if task in REVIEW_TASKS else ""
    link = (
        f'<a class="review-row-title" href="/review?document={_esc(snapshot_id)}&amp;object={_esc(obj["object_id"])}{task_query}">'
        f"{_esc(title)}</a>"
    )
    status_html = f'<span class="review-row-status">{_esc(status)}</span>'
    if checkbox:
        return (
            '<li class="review-row">'
            f'<label class="review-select-target"><input type="checkbox" name="object_ids" '
            f'value="{_esc(obj["object_id"])}"><span class="visually-hidden">Selecteer {_esc(title)}</span></label>'
            f'{link}{status_html}'
            "</li>"
        )
    return f'<li class="review-row">{link}{status_html}</li>'


def _review_section_groups(
    objects: list[dict[str, Any]],
    snapshot_id: str,
    *,
    priority_ids: set[str] | None = None,
    task: str = "contextual",
    context_objects: list[dict[str, Any]] | None = None,
    review_path: str = "richtlijn",
) -> str:
    """Presentation only: preserve exact source paths and existing object links."""
    priority_ids = priority_ids or set()
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for obj in objects:
        raw_path = admission_of(obj).get("section_path") or (obj.get("structure") or {}).get("section_path") or []
        key = tuple(str(part).strip() for part in raw_path if str(part).strip())
        groups.setdefault(key, []).append(obj)
    context_objects = objects if context_objects is None else context_objects

    def passage_row(obj: dict[str, Any]) -> str:
        item = _review_index_item(
            obj, snapshot_id,
            reason=_individual_review_reason(obj, priority=str(obj.get("object_id")) in priority_ids),
            task=task,
        )
        context = _review_context_block(
            obj, context_objects, snapshot_id=snapshot_id, review_path=review_path, task=task,
        )
        if context:
            item = item.removesuffix("</li>") + (
                '<details class="review-queue-context"><summary>Bekijk verbonden passages</summary>'
                + context + "</details></li>"
            )
        return item

    panels = []
    for index, (key, rows) in enumerate(groups.items()):
        path = " › ".join(key)
        title = key[-1] if key else "Brononderdeel nog te controleren"
        panels.append(
            f'<details class="review-section"{" open" if index == 0 else ""}>'
            f'<summary>{_esc(title)} <span class="review-section-count">{len(rows)} passages</span></summary>'
            f'<p class="review-source-path">{_esc(path or "Geen bronpad beschikbaar")}</p>'
            '<ol class="object-index">'
            + "".join(
                passage_row(obj)
                for obj in rows
            )
            + '</ol></details>'
        )
    return "".join(panels)


def _individual_review_reason(obj: dict[str, Any], *, priority: bool = False) -> str:
    if priority:
        return "Deze passage vraagt een eigen oordeel, omdat zij advies, een voorwaarde, een uitzondering of mogelijk risico bevat."
    uncertainty = obj.get("uncertainty") if isinstance(obj.get("uncertainty"), dict) else {}
    if uncertainty.get("has_uncertainty"):
        return "Deze passage vraagt een eigen beoordeling, omdat de betekenis of context nog niet zeker genoeg is."
    return "Deze passage kan niet veilig samen met andere passages worden bevestigd. Beoordeel haar daarom afzonderlijk."


def _review_lane_copy(review_path: str, koppen: list[dict[str, Any]]) -> dict[str, str]:
    if review_path == "boom":
        return {
            "fast_title": f"Paden controleren ({len(koppen)})",
            "fast_lead": "Paden helpen bij het plaatsen van onderdelen. Zij veranderen de inhoud niet.",
            "fast_button": "Bevestig geselecteerde paden als structuur",
        }
    return {
        "fast_title": f"Koppen controleren ({len(koppen)})",
        "fast_lead": "Koppen helpen passages op de juiste plek te plaatsen. Zij veranderen de inhoud niet.",
        "fast_button": "Bevestig geselecteerde koppen als structuur",
    }


def _review_is_final(obj: dict[str, Any]) -> bool:
    return (obj.get("governance") or {}).get("validation_status") in {"approved", "rejected", "superseded"}


def _review_was_revised(obj: dict[str, Any]) -> bool:
    governance = obj.get("governance") if isinstance(obj.get("governance"), dict) else {}
    provenance = obj.get("provenance") if isinstance(obj.get("provenance"), dict) else {}
    return (
        governance.get("validation_status") == "needs_review"
        and bool(provenance.get("previous_object_version"))
    )


def _review_progress_summary(objects: list[dict[str, Any]]) -> dict[str, int]:
    """Read-only projection over the existing definitive review disposition."""
    rows = [obj for obj in objects if obj.get("object_type") != "document"]
    counts = {
        "total": len(rows),
        "done": 0,
        "approved": 0,
        "rejected": 0,
        "not_included": 0,
        "context": 0,
        "support": 0,
        "superseded": 0,
        "revised": 0,
    }
    for obj in rows:
        disposition = definitive_review_disposition(obj)
        if disposition["final"]:
            counts["done"] += 1
            review_status = str(disposition.get("review_status") or "")
            outcome = str(disposition.get("outcome") or "")
            if review_status == "rejected":
                counts["rejected"] += 1
            elif outcome == "approved":
                counts["approved"] += 1
            elif outcome == "excluded_with_reason":
                counts["not_included"] += 1
            elif outcome == "used_as_context":
                counts["context"] += 1
            elif outcome == "linked_as_support":
                counts["support"] += 1
            elif outcome == "superseded":
                counts["superseded"] += 1
        if _review_was_revised(obj):
            counts["revised"] += 1
    counts["open"] = counts["total"] - counts["done"]
    return counts


def _review_decision_label(obj: dict[str, Any]) -> str:
    if _review_was_revised(obj):
        return "Herzien na correctie"
    disposition = definitive_review_disposition(obj)
    review_status = str(disposition.get("review_status") or "")
    outcome = str(disposition.get("outcome") or "")
    if review_status == "rejected":
        return "Afgewezen"
    labels = {
        "approved": "Goedgekeurd",
        "linked_as_support": "Alleen onderbouwing",
        "used_as_context": "Context",
        "excluded_with_reason": "Niet opgenomen",
        "superseded": "Vervangen",
    }
    return labels.get(outcome, review_row_status(obj))


def _review_signals_for_object(
    audit_signals: list[dict[str, Any]],
    *,
    snapshot_id: str,
    object_id: str,
) -> list[dict[str, Any]]:
    return [
        event
        for event in audit_signals
        if str(event.get("object_id") or "") == object_id
        and str(
            (event.get("details") if isinstance(event.get("details"), dict) else {}).get(
                "snapshot_id"
            )
            or ""
        )
        == snapshot_id
    ]


def _review_signal_for_object(
    audit_signals: list[dict[str, Any]],
    *,
    snapshot_id: str,
    object_id: str,
) -> dict[str, Any] | None:
    signals = _review_signals_for_object(
        audit_signals,
        snapshot_id=snapshot_id,
        object_id=object_id,
    )
    return signals[0] if signals else None


def _current_review_objects(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    for row in rows:
        object_id = str(row.get("object_id") or "")
        if object_id:
            current[object_id] = row
    return list(current.values())


def _review_object_versions(
    rows: list[dict[str, Any]],
    object_id: str,
) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("object_id") or "") == object_id]


def _review_history_status(obj: dict[str, Any]) -> str:
    status = str((obj.get("governance") or {}).get("validation_status") or "")
    return {
        "needs_review": "Te beoordelen",
        "approved": "Goedgekeurd",
        "rejected": "Afgewezen",
        "revise": "Correctie gevraagd",
        "superseded": "Vervangen",
        "draft": "Concept",
    }.get(status, status.replace("_", " ") or "Onbekend")


def _review_version_changes(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> list[tuple[str, str, str]]:
    def text(obj: dict[str, Any]) -> str:
        content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
        return str(content.get("clean_text") or content.get("raw_text") or "").strip()

    def object_type(obj: dict[str, Any]) -> str:
        return str(obj.get("confirmed_object_type") or obj.get("object_type") or "").strip()

    def status(obj: dict[str, Any]) -> str:
        return _review_history_status(obj)

    def section(obj: dict[str, Any]) -> str:
        structure = obj.get("structure") if isinstance(obj.get("structure"), dict) else {}
        return " › ".join(str(part) for part in structure.get("section_path") or [])

    fields = (
        ("Passagetekst", text),
        ("Type", object_type),
        ("Reviewstatus", status),
        ("Bronpositie", section),
    )
    return [
        (label, before, after)
        for label, getter in fields
        if (before := getter(previous)) != (after := getter(current))
    ]


def _review_object_history(
    snapshot_id: str,
    obj: dict[str, Any],
    all_rows: list[dict[str, Any]],
    audit_signals: list[dict[str, Any]],
) -> str:
    object_id = str(obj.get("object_id") or "")
    versions = _review_object_versions(all_rows, object_id)
    by_version = {
        str(row.get("object_version") or ""): row
        for row in versions
        if str(row.get("object_version") or "")
    }
    provenance = obj.get("provenance") if isinstance(obj.get("provenance"), dict) else {}
    previous_version = str(provenance.get("previous_object_version") or "")
    previous = by_version.get(previous_version)
    if previous is None and len(versions) > 1:
        previous = versions[-2]

    changes = _review_version_changes(previous, obj) if previous is not None else []
    if changes:
        change_html = "".join(
            f'<div class="review-version-change"><dt>{_esc(label)}</dt>'
            f'<dd><span class="review-version-before">{_esc(before or "—")}</span>'
            f'<span aria-hidden="true">→</span>'
            f'<span class="review-version-after">{_esc(after or "—")}</span></dd></div>'
            for label, before, after in changes
        )
        diff_html = f"""
          <section class="review-version-diff" aria-labelledby="review-version-diff-title">
            <h3 id="review-version-diff-title">Verschil met vorige versie</h3>
            <p class="muted">Alleen velden die aantoonbaar tussen de opgeslagen versies verschillen worden getoond.</p>
            <dl>{change_html}</dl>
          </section>
        """
    else:
        diff_html = """
          <section class="review-version-diff">
            <h3>Verschil met vorige versie</h3>
            <p class="muted">Voor deze versie is geen eerdere opgeslagen objectversie met aantoonbare verschillen beschikbaar.</p>
          </section>
        """

    signals = _review_signals_for_object(
        audit_signals,
        snapshot_id=snapshot_id,
        object_id=object_id,
    )
    signals_by_version: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        signals_by_version.setdefault(str(signal.get("object_version") or ""), []).append(signal)

    timeline = []
    current_version = str(obj.get("object_version") or "")
    for version in versions:
        version_id = str(version.get("object_version") or "")
        governance = version.get("governance") if isinstance(version.get("governance"), dict) else {}
        version_provenance = (
            version.get("provenance") if isinstance(version.get("provenance"), dict) else {}
        )
        version_signals = signals_by_version.get(version_id) or []
        signal = version_signals[0] if version_signals else None
        details = (
            (signal or {}).get("details")
            if isinstance((signal or {}).get("details"), dict)
            else {}
        )
        actor = str(
            (signal or {}).get("actor") or governance.get("validated_by") or ""
        ).strip()
        occurred_at = str(
            (signal or {}).get("occurred_at") or governance.get("validation_date") or ""
        ).strip()
        reason = str(
            details.get("comment") or version_provenance.get("revision_reason") or ""
        ).strip()
        metadata = []
        if actor:
            metadata.append(actor)
        if occurred_at:
            metadata.append(occurred_at)
        meta_html = (
            f'<p class="muted">{" · ".join(_esc(item) for item in metadata)}</p>'
            if metadata
            else ""
        )
        reason_html = f'<p>{_esc(reason)}</p>' if reason else ""
        current_badge = (
            '<span class="review-history-current">huidige versie</span>'
            if version_id == current_version
            else ""
        )
        timeline.append(
            f"""
            <li class="review-history-event">
              <div class="review-history-event-heading">
                <strong>Versie {_esc(version_id)}</strong>
                <span class="review-row-status">{_esc(_review_history_status(version))}</span>
                {current_badge}
              </div>
              {reason_html}
              {meta_html}
            </li>
            """
        )

    return f"""
      {_review_task_header(snapshot_id, "Objecthistorie", "Bekijk opgeslagen versies en reviewbesluiten zonder de reviewstatus te wijzigen")}
      <section class="review-object-history" data-review-object-history="{_esc(object_id)}">
        <h3>{_esc(review_row_title(obj))}</h3>
        <p class="muted">Object {_esc(object_id)} · huidige versie {_esc(current_version)}</p>
        {diff_html}
        <section aria-labelledby="review-history-timeline-title">
          <h3 id="review-history-timeline-title">Versiehistorie</h3>
          <ol class="review-history-timeline">{"".join(timeline)}</ol>
        </section>
      </section>
    """


def _review_decision_row(
    obj: dict[str, Any],
    snapshot_id: str,
    audit_signals: list[dict[str, Any]],
) -> str:
    signal = _review_signal_for_object(
        audit_signals,
        snapshot_id=snapshot_id,
        object_id=str(obj.get("object_id") or ""),
    )
    details = (signal or {}).get("details") if isinstance((signal or {}).get("details"), dict) else {}
    provenance = obj.get("provenance") if isinstance(obj.get("provenance"), dict) else {}
    governance = obj.get("governance") if isinstance(obj.get("governance"), dict) else {}
    comment = str(
        details.get("comment")
        or provenance.get("revision_reason")
        or ""
    ).strip()
    actor = str((signal or {}).get("actor") or governance.get("validated_by") or "").strip()
    occurred_at = str((signal or {}).get("occurred_at") or governance.get("validation_date") or "").strip()
    previous = str(provenance.get("previous_object_version") or "").strip()
    current_version = str(obj.get("object_version") or "").strip()
    meta = []
    if actor:
        meta.append(actor)
    if occurred_at:
        meta.append(occurred_at)
    if previous:
        meta.append(f"vorige versie {previous}")
    if current_version:
        meta.append(f"versie {current_version}")
    meta_html = f'<span class="muted">{" · ".join(_esc(item) for item in meta)}</span>' if meta else ""
    comment_html = f'<p class="muted">{_esc(comment)}</p>' if comment else ""
    object_id = str(obj.get("object_id") or "")
    source_href = (
        f"/review/bronpassage?document={quote(snapshot_id, safe='')}"
        f"&amp;object={quote(object_id, safe='')}"
        "&amp;task=history"
    )
    history_href = (
        f"/review?document={quote(snapshot_id, safe='')}"
        f"&amp;object={quote(object_id, safe='')}"
        "&amp;task=history"
    )
    return f"""
      <li class="review-row review-decision-row">
        <div>
          <span class="review-row-title">{_esc(review_row_title(obj))}</span>
          {comment_html}
          {meta_html}
        </div>
        <div>
          <span class="review-row-status">{_esc(_review_decision_label(obj))}</span>
          <a class="btn-secondary" href="{history_href}">Bekijk historie</a>
          <a class="btn-secondary" href="{source_href}">Bekijk bron</a>
        </div>
      </li>
    """


def _review_progress_overview(
    snapshot_id: str,
    progress: dict[str, int],
) -> str:
    total = int(progress["total"])
    done = int(progress["done"])
    percent = round((done / total) * 100) if total else 100
    extras = []
    if progress["context"]:
        extras.append(f'<strong>{progress["context"]}</strong> context')
    if progress["support"]:
        extras.append(f'<strong>{progress["support"]}</strong> onderbouwing')
    if progress["superseded"]:
        extras.append(f'<strong>{progress["superseded"]}</strong> vervangen')
    if progress["revised"]:
        extras.append(f'<strong>{progress["revised"]}</strong> herzien na correctie')
    extras_html = '<p class="review-progress-extra">' + " · ".join(extras) + '</p>' if extras else ""
    return f"""
      <section class="review-progress-overview" aria-labelledby="review-progress-title">
        <div class="review-task-heading">
          <h2 id="review-progress-title">Reviewvoortgang</h2>
          <p class="review-progress-number">{percent}<span>%</span></p>
          <p>{done} van {total} bronpassages afgehandeld</p>
        </div>
        <progress aria-label="Afgehandelde bronpassages" value="{done}" max="{max(total, 1)}">{percent}%</progress>
        <dl class="review-progress-counts">
          <div><dt>Nog te beoordelen</dt><dd>{progress["open"]}</dd></div>
          <div><dt>Goedgekeurd</dt><dd>{progress["approved"]}</dd></div>
          <div><dt>Afgewezen</dt><dd>{progress["rejected"]}</dd></div>
          <div><dt>Niet opgenomen</dt><dd>{progress["not_included"]}</dd></div>
        </dl>
        {extras_html}
        <a class="review-history-link" href="/review?document={_esc(snapshot_id)}&amp;task=history">Besluiten en historie <span aria-hidden="true">→</span></a>
      </section>
    """


def _review_task_card(
    snapshot_id: str,
    *,
    task: str,
    title: str,
    description: str,
    status: str,
    recommended: bool = False,
) -> str:
    action = "Ga verder" if recommended else "Open taak"
    return f'''
      <a class="review-task-card" href="/review?document={_esc(snapshot_id)}&amp;task={_esc(task)}">
        <span class="review-task-card-title">{_esc(title)}</span>
        <span class="review-task-card-status">{_esc(status)}</span>
        <span class="review-task-card-action">{action} <span aria-hidden="true">→</span></span>
      </a>
    '''


def _review_task_dashboard(
    snapshot_id: str,
    *,
    koppen: list[dict[str, Any]],
    individual: list[dict[str, Any]],
    normal_passages: int,
    normal_batches: int,
    blocked_count: int,
    progress: dict[str, int],
    heading_pending_override: int | None = None,
    heading_total_override: int | None = None,
    individual_pending_override: int | None = None,
    individual_total_override: int | None = None,
    second_review_pending: int = 0,
    disposition_pending: int = 0,
    waiting_pending: int = 0,
    heading_done_override: int | None = None,
    individual_done_override: int | None = None,
) -> str:
    heading_pending = (
        int(heading_pending_override)
        if heading_pending_override is not None
        else sum(not _review_is_final(obj) for obj in koppen)
    )
    heading_total = (
        int(heading_total_override)
        if heading_total_override is not None
        else len(koppen)
    )
    heading_done = max(heading_total - heading_pending, 0) if heading_done_override is None else heading_done_override
    individual_pending = (
        int(individual_pending_override)
        if individual_pending_override is not None
        else sum(not _review_is_final(obj) for obj in individual)
    )
    individual_total = (
        int(individual_total_override)
        if individual_total_override is not None
        else len(individual)
    )
    individual_done = max(individual_total - individual_pending, 0) if individual_done_override is None else individual_done_override
    # Navigation is a projection of existing duties, never a second review policy.
    tasks = [
        ("structure", "Documentindeling controleren", "Controleer koppen en hun plaats in de bron", heading_pending),
        ("contextual", "Passages afzonderlijk beoordelen", "Controleer inhoud, type en benodigde broncontext", individual_pending),
        ("batch", "Passages selecteren en bevestigen", "Bekijk iedere passage; bevestig alleen geschikte selecties samen", normal_passages),
        ("second_review", "Een onafhankelijke tweede beoordeling geven", "Beoordeel dezelfde versie zonder het eerdere besluit over te nemen", second_review_pending),
        ("disposition", "Gebruik van bronpassages bepalen", "Bekijk per passage wat ontbreekt en welke afhandeling mogelijk is", disposition_pending),
    ]
    available = [row for row in tasks if row[3]]
    recommended = available[0] if available else None
    statuses = {
        "structure": f"{heading_pending} te controleren · {heading_done} afgerond",
        "contextual": f"{individual_pending} te beoordelen · {individual_done} afgerond",
        "batch": f"{normal_passages} passages",
        "second_review": f"{second_review_pending} te beoordelen",
        "disposition": f"{disposition_pending} af te handelen",
    }
    if recommended:
        next_step = f'''
          <section class="review-next-step" aria-labelledby="review-next-title">
            <p class="eyebrow">Volgende stap</p>
            <h2 id="review-next-title">{_esc(recommended[1])}</h2>
            <p>{_esc(statuses[recommended[0]])}</p>
            <a class="btn-primary" href="/review?document={_esc(snapshot_id)}&amp;task={recommended[0]}">Ga verder met beoordelen</a>
          </section>
        '''
    else:
        next_step = '<p class="review-task-empty">Geen inhoudelijke beoordeling voor jou beschikbaar.</p>'
    rows = "".join(
        _review_task_card(
            snapshot_id, task=task, title=title,
            description="", status=statuses[task],
            recommended=bool(recommended and task == recommended[0]),
        )
        for task, title, description, count in available
        if recommended is None or task != recommended[0]
    )
    waiting = (
        f'<p><a href="/review?document={_esc(snapshot_id)}&amp;task=waiting">'
        f'{waiting_pending} wachten op een andere beoordelaar</a>. Jij kunt deze tweede beoordeling niet overnemen.</p>'
        if waiting_pending else ''
    )
    repair_notice = (
        f'<p class="review-blocked-notice">{blocked_count} '
        f'{"passage is" if blocked_count == 1 else "passages zijn"} nog niet beschikbaar voor goedkeuring. '
        f'<a href="/review?document={_esc(snapshot_id)}&amp;task=repair">Passages corrigeren</a></p>'
        if blocked_count else ''
    )
    return f'''
      <section class="review-task-dashboard" aria-labelledby="review-task-title">
        <div class="review-workspace-layout">
        <div class="review-work-main">
        {next_step}
        <div class="review-work-header">
          <div>
            <h2 id="review-task-title">Jouw open werk</h2>
          </div>
          <a class="btn-secondary" href="/review?document={_esc(snapshot_id)}&amp;task=inventory">Alle passages bekijken</a>
        </div>
        <div class="review-task-grid">{rows}</div>
        {waiting}
        </div>
        <aside class="review-sidebar" aria-label="Reviewvoortgang">
        {_review_progress_overview(snapshot_id, progress)}
        {repair_notice}
        </aside>
        </div>
      </section>
    '''


def _review_task_header(snapshot_id: str, title: str, description: str) -> str:
    return f'''
      <header class="review-task-workspace">
        <a class="btn-secondary review-task-back" href="/review?document={_esc(snapshot_id)}">← Terug naar taken</a>
        <h2>{_esc(title)}</h2>
        {_task_links("review")}
      </header>
    '''


_PROCESSING_FAMILY_LABELS = {
    "source_binding": "Bronkoppeling",
    "unit_completeness": "Zelfstandigheid van passage",
    "semantic_contract": "Semantisch contract",
    "dependency_resolution": "Ontbrekende afhankelijkheid of context",
    "processing_completeness": "Verwerking niet volledig",
    "unclassified": "Nog niet ingedeeld",
}


def _diagnostic_count_list(rows: dict[str, int]) -> str:
    if not rows:
        return '<p class="muted">Geen gegevens.</p>'
    return (
        '<ul class="processing-diagnostic-list">'
        + "".join(
            f'<li><code>{_esc(name)}</code>: <b>{int(count)}</b></li>'
            for name, count in rows.items()
        )
        + "</ul>"
    )


def _processing_diagnostics_html(
    snapshot_objects: list[dict[str, Any]],
) -> str:
    diagnostics = processing_diagnostics(snapshot_objects)
    blocked_count = int(diagnostics["blocked_candidate_count"])
    if not blocked_count:
        return ""

    issue_count = int(diagnostics["issue_occurrence_count"])
    without_reason = int(diagnostics["blocked_without_reason_count"])
    families = diagnostics["by_family"]
    family_rows = "".join(
        (
            "<tr>"
            f"<td>{_esc(_PROCESSING_FAMILY_LABELS.get(family, family))}</td>"
            f"<td>{int(values['candidate_count'])}</td>"
            f"<td>{int(values['issue_occurrence_count'])}</td>"
            "</tr>"
        )
        for family, values in families.items()
    )
    reason_rows = "".join(
        (
            "<tr>"
            f"<td><code>{_esc(code)}</code></td>"
            f"<td>{int(values['candidate_count'])}</td>"
            f"<td>{int(values['issue_occurrence_count'])}</td>"
            "</tr>"
        )
        for code, values in diagnostics["by_reason_code"].items()
    )
    anomaly = (
        f'<p class="banner-error"><b>{without_reason}</b> geblokkeerde '
        "passage(s) hebben geen reason code. Dit is een diagnostische anomalie.</p>"
        if without_reason
        else ""
    )
    unknown = diagnostics["unknown_reason_codes"]
    unknown_html = (
        '<p class="field-help">Niet ingedeelde reason codes: '
        + ", ".join(f"<code>{_esc(code)}</code>" for code in unknown)
        + ".</p>"
        if unknown
        else ""
    )
    return f"""
      <section class="processing-diagnostics" aria-labelledby="processing-diagnostics-title">
        <h3 id="processing-diagnostics-title">Waarom passages technisch geblokkeerd zijn</h3>
        <p class="lead">
          <b>{blocked_count}</b> passages hebben samen <b>{issue_count}</b> technische signalen.
          Een passage kan meerdere signalen hebben. Deze signalen tonen welk admission-contract niet is gehaald; ze bewijzen niet automatisch de onderliggende root cause en zijn geen inhoudelijke afwijzing door een reviewer.
        </p>
        {anomaly}
        <h4>Signalen per diagnostische familie</h4>
        <table>
          <thead><tr><th>Familie</th><th>Passages</th><th>Signalen</th></tr></thead>
          <tbody>{family_rows}</tbody>
        </table>
        {unknown_html}
        <details>
          <summary>Bekijk exacte reason codes</summary>
          <table>
            <thead><tr><th>Reason code</th><th>Passages</th><th>Voorkomens</th></tr></thead>
            <tbody>{reason_rows}</tbody>
          </table>
        </details>
        <details>
          <summary>Bekijk diagnostische uitsplitsing</summary>
          <div class="review-diagnostic-breakdowns">
            <h4>Voorgesteld type</h4>
            {_diagnostic_count_list(diagnostics["by_proposed_type"])}
            <h4>Brononderdeel</h4>
            {_diagnostic_count_list(diagnostics["by_section_role"])}
            <h4>Passagevorming</h4>
            {_diagnostic_count_list(diagnostics["by_formation_strategy"])}
            <h4>Selectie-oorsprong</h4>
            {_diagnostic_count_list(diagnostics["by_selection_origin"])}
          </div>
        </details>
      </section>
    """


def _review_route_objects(
    objects: list[dict[str, Any]],
    *,
    review_path: str,
    bindings: list[dict[str, Any]] | None,
    reviewer_id: str,
    canonical_task: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in objects:
        if bindings is None:
            duty = review_duty_for(
                obj,
                review_path=review_path,
                bindings=None,
            )
            if not duty:
                continue
            task = (
                "second_review"
                if duty.get("stage") == "second_review"
                else str(duty.get("lane") or "")
            )
            if task == canonical_task:
                rows.append(obj)
            continue

        route = reviewer_route_for(
            obj,
            review_path=review_path,
            reviewer_id=reviewer_id,
            bindings=bindings,
        )
        if not route or not route.get("actionable"):
            continue
        if str(route.get("canonical_task") or "") != canonical_task:
            continue
        rows.append(obj)
    return sorted(rows, key=review_priority_rank)


def _decision_paths_html(console: OperationsConsole, snapshot_id: str, obj: dict[str, Any], objects: list[dict[str, Any]]) -> str:
    from src.decision_graph_v1 import ordered_paths, publication_issues
    envelope = console._envelope(snapshot_id)
    if "decision_graph" not in envelope:
        return ""
    result = ordered_paths(envelope["decision_graph"], objects, envelope["decision_graph_evidence"], str(obj["object_id"]))
    if result["issues"]:
        return '<section data-decision-paths><h4>Beslispad</h4><p class="banner warn">Pad nog niet vastgesteld. Controleer de beslisroutes.</p></section>'
    by_id = {row["object_id"]: row for row in objects}
    paths = []
    for index, path in enumerate(result["paths"], 1):
        steps = ''.join('<li>' + _esc((by_id[step["object_id"]].get("content") or {}).get("clean_text"))
                        + ('<p><b>Antwoord: ' + _esc(step["label"]) + '</b></p>' if step["label"] else '<p>Onvoorwaardelijke vervolgstap</p>')
                        + '<p>Vervolg: ' + _esc((by_id[step["next_object_id"]].get("content") or {}).get("clean_text")) + '</p></li>'
                        for step in path["steps"])
        paths.append(f'<article data-path-alternative><h5>Pad {index}</h5><ol>{steps}</ol></article>')
    unresolved = publication_issues(envelope, objects)
    notice = '<p class="banner warn">Deze routes zijn nog niet door alle vereiste reviewers bevestigd.</p>' if unresolved else ''
    return '<section data-decision-paths><h4>Afzonderlijke paden naar deze uitkomst</h4>' + notice + ''.join(paths) + '</section>'


def _knowledge_review_html(obj: dict[str, Any], objects: list[dict[str, Any]]) -> str:
    from src.review_cockpit_v1 import knowledge_review_projection
    projected = knowledge_review_projection(obj, objects)
    essential = "".join(
        f'<li data-context-status="{_esc(row["status"])}"><b>{_esc({"condition": "Voorwaarde", "exception": "Uitzondering", "scope": "Toepassingsgebied", "support": "Onderbouwing"}.get(row["role"], _object_type_label(row["role"])))}</b>: '
        f'{_esc(row["text"])} '
        + ('<strong> — nog niet geldig verbonden</strong>' if row["status"] in {"unresolved", "stale"} else '')
        + '</li>' for row in projected["essential_context"])
    issues = ('<p class="banner warn" data-unresolved-meaning>Er staan nog controles open: '
              + _esc("Betekeniscontext, bronbinding of verplichte velden vragen nog controle.") + '</p>'
              if projected["unresolved_reasons"] else '')
    proposal = ('<aside class="object-expand-merge" data-context-proposal><h4>Voorgestelde wijziging — nog niet opgeslagen</h4>'
                f'<p>{_esc(projected["proposal"])}</p></aside>' if projected["proposal"] else '')
    return f'''<section class="review-card-object review-step" data-review-step="a" aria-label="Geselecteerde passage"
        data-reviewed-version="{_esc(projected['object_version'])}">
      <p class="meta">type <b>{_esc(_object_type_label(str(projected['object_type'] or '')))}</b> ·
        status <b>{_esc(review_row_status(obj))}</b> · versie <b>{_esc(projected['object_version'])}</b></p>
      <p class="eyebrow">Te beoordelen passage</p><h3 data-full-knowledge-passage>{_esc(projected['text'])}</h3>
      <section data-essential-context><h4>Voorwaarden, uitzonderingen en scope</h4>
        {f'<ul>{essential}</ul>' if essential else '<p>Geen afzonderlijke betekeniscontext vastgelegd.</p>'}</section>
      {issues}{proposal}
    </section>'''


def _render_second_review_card(
    console: OperationsConsole,
    snapshot_id: str,
    obj: dict[str, Any],
    snapshot_objects: list[dict[str, Any]],
    review_path: str,
    *,
    reviewer_id: str,
    snapshot_revision: str,
) -> str:
    bindings = console.object_review_bindings(snapshot_id)
    route = reviewer_route_for(
        obj,
        review_path=review_path,
        reviewer_id=reviewer_id,
        bindings=bindings,
    )
    if not route or route.get("canonical_task") != "second_review":
        raise ConsoleError("second_review_not_available")
    if not route.get("actionable"):
        raise ConsoleError("independent_second_reviewer_required")

    semantics = confirmed_recommendation_semantics_of(obj)
    semantics_html = ""
    if semantics:
        semantics_html = (
            '<section class="review-step">'
            '<h4>Bevestigde aanbevelingssemantiek</h4>'
            f'<p>Richting: <b>{_esc(semantics.get("direction") or "")}</b> · '
            f'Sterkte: <b>{_esc(semantics.get("strength") or semantics.get("strength_status") or "")}</b></p>'
            '</section>'
        )
    relations = confirmed_knowledge_relations_of(obj)
    relations_html = ""
    if relations:
        items = "".join(
            f'<li><b>{_esc(RELATION_LABELS.get(str(row.get("relation_type") or ""), str(row.get("relation_type") or "")))}</b> '
            f'→ {_esc(row.get("target_object_id") or "")} '
            f'(versie {_esc(row.get("target_object_version") or "")})</li>'
            for row in relations
        )
        relations_html = (
            '<section class="review-step"><h4>Bevestigde relaties</h4>'
            f'<ul>{items}</ul></section>'
        )

    first_reviewers = [
        str(row.get("reviewer") or row.get("reviewer_id") or "")
        for row in bindings
        if row.get("valid")
        and row.get("decision") == "approve"
        and row.get("object_id") == obj.get("object_id")
        and row.get("object_version") == obj.get("object_version")
        and row.get("canonical_object_hash") == (obj.get("provenance") or {}).get("canonical_object_hash")
        and row.get("confirmed_object_type") == obj.get("confirmed_object_type")
    ]
    first_copy = ", ".join(dict.fromkeys(first_reviewers)) or "eerste reviewer"
    text = str((obj.get("content") or {}).get("clean_text") or "")
    return f"""
      <p><a class="btn-secondary" href="/review?document={_esc(snapshot_id)}&amp;task=second_review">← Terug naar tweede beoordelingen</a></p>
      <article class="object review-card-two-column second-review-card" data-object-id="{_esc(obj.get("object_id"))}">
        {_knowledge_review_html(obj, snapshot_objects)}
        <div class="review-cockpit-copy">
          <p class="eyebrow">Onafhankelijke tweede beoordeling</p>
          <p>Versie {_esc(obj.get("object_version"))}</p>
        </div>
        {_decision_paths_html(console, snapshot_id, obj, snapshot_objects)}
        {_broncontext_html(obj, snapshot_id, str(obj.get("object_id") or ""), True, task="second_review")}
        {_review_context_block(
            obj,
            snapshot_objects,
            snapshot_id=snapshot_id,
            review_path=review_path,
            task="second_review",
        )}
        {semantics_html}
        {relations_html}
        <form method="post" action="/review/second-review" class="review-decision-form">
          <input type="hidden" name="snapshot_id" value="{_esc(snapshot_id)}">
          <input type="hidden" name="object_id" value="{_esc(obj.get("object_id") or "")}">
          <input type="hidden" name="interaction_id" value="{_esc(new_review_interaction_id())}">
          {_snapshot_revision_input(snapshot_revision)}
          <section class="review-step">
            <h4>Tweede beoordeling</h4>
            <button class="btn-primary" type="submit" name="action" value="approve">Tweede beoordeling goedkeuren</button>
            <label for="second-review-comment-{_esc(obj.get("object_id") or "")}">Correctie nodig</label>
            <textarea id="second-review-comment-{_esc(obj.get("object_id") or "")}" name="comment"></textarea>
            <button class="btn-secondary" type="submit" name="action" value="revise">Correctie nodig</button>
          </section>
        </form>
      </article>
    """


def _review_bindings(console: OperationsConsole, snapshot_id: str) -> list[dict[str, Any]] | None:
    """Actor routes when bindings exist; governance fallback for projection consoles."""
    try:
        return console.object_review_bindings(snapshot_id)
    except AttributeError:
        return None
    except ConsoleError as exc:
        if exc.code == "unknown_snapshot":
            return None
        raise


def _lane_total(
    objects: list[dict[str, Any]],
    *,
    review_path: str,
    lane: str,
    open_rows: list[dict[str, Any]],
) -> int:
    """Open duties plus already finished objects of the same lane.

    The task list only contains open work. The dashboard still reports how
    many objects of that lane are already afgerond.
    """
    open_ids = {str(obj.get("object_id") or "") for obj in open_rows}
    finished = 0
    for obj in objects:
        object_id = str(obj.get("object_id") or "")
        if not object_id or object_id in open_ids:
            continue
        if str(obj.get("object_type") or "") == "document":
            continue
        if not _review_is_final(obj):
            continue
        if review_duty_lane(obj, review_path=review_path, stage="first_review") != lane:
            continue
        finished += 1
    return len(open_rows) + finished


def _review_inventory(
    snapshot_id: str,
    objects: list[dict[str, Any]],
    *,
    review_path: str,
    bindings: list[dict[str, Any]] | None,
    reviewer_id: str,
    task: str,
) -> str:
    """Every current passage remains reachable; no admission or finality writes."""
    followups = review_followup_queues(objects, review_path=review_path, bindings=bindings)
    followup_tasks = {
        str(obj["object_id"]): name
        for name, rows in followups.items() for obj in rows
    }
    labels = {
        "structure": "Documentindeling controleren", "contextual": "Passage afzonderlijk beoordelen",
        "batch": "Passages selecteren en bevestigen", "second_review": "Tweede beoordeling",
        "waiting": "Wacht op andere reviewer", "repair": "Passages corrigeren",
        "disposition": "Gebruik van bronpassage bepalen", "history": "Status en historie",
    }
    outcomes = {
        "not_yet_assessed": "Nog niet afgehandeld", "candidate_review_open": "Kandidaat nog te beoordelen",
        "review_open": "Afhandeling nog niet definitief", "approved": "Goedgekeurd",
        "rejected": "Afgewezen", "superseded": "Vervangen door opvolger",
        "used_as_context": "Als context gebruikt", "linked_as_support": "Als onderbouwing gebruikt",
        "excluded_with_reason": "Gemotiveerd uitgesloten",
        "invalid_register_status": "Afhandelingsstatus ontbreekt of is ongeldig",
        "invalid_disposition_state": "Afhandeling moet worden uitgezocht",
    }
    items = []
    for obj in objects:
        if obj.get("object_type") == "document":
            continue
        if bindings is None:
            duty = review_duty_for(obj, review_path=review_path, bindings=None)
            route_task = ""
            if duty:
                route_task = "second_review" if duty["stage"] == "second_review" else str(duty["lane"])
        else:
            route = reviewer_route_for(obj, review_path=review_path, bindings=bindings, reviewer_id=reviewer_id)
            route_task = ""
            if route:
                route_task = str(route["canonical_task"]) if route["actionable"] else "waiting"
        object_id = str(obj.get("object_id") or "")
        disposition = definitive_review_disposition(obj)
        category = route_task or followup_tasks.get(object_id) or "history"
        if task != "inventory" and category != task:
            continue
        gate = str(admission_of(obj).get("gate_result") or "")
        outcome = outcomes.get(str(disposition.get("outcome") or ""), "Afhandeling controleren")
        register = (obj.get("metadata") or {}).get("passage_register") or {}
        origin = "Vastgelegd door een beoordelaar" if register.get("source") == "review" else "Voorstel uit de bron"
        target_task = "second_review" if category == "waiting" else category
        next_action = "Open de passage en controleer het voorstel met de bron."
        if category == "waiting":
            next_action = "Een andere bevoegde reviewer moet deze versie onafhankelijk beoordelen."
        elif category == "repair":
            next_action = "Controleer de bron en herstel het verwerkingsprobleem voordat je goedkeurt."
        elif category == "history":
            next_action = "Bekijk het vastgelegde besluit; dit is geen nieuwe beoordelingsopdracht."
        elif category == "disposition":
            if not disposition.get("valid"):
                next_action = "De opgeslagen afhandeling is ongeldig. Open de passage om het conflict te onderzoeken; keur niet automatisch goed."
            elif gate != "allowed":
                next_action = "Metis heeft nog niet vastgesteld of deze passage inhoudelijk beoordeelbaar is. Open de bron en bepaal het gebruik of herstel de verwerking."
            else:
                next_action = "Er ontbreekt een definitieve afhandeling. Open de passage en bepaal of zij kennis, context, onderbouwing of niet op te nemen tekst is."
        hint = source_label_hint(obj)
        hint_html = f'<p data-source-label-hint>{_esc(hint["label"])}</p>' if hint else ''
        source_role = role_of(obj)
        if source_role:
            role_label = {"label": "Bevestigd bronlabel", "context": "Bevestigd contextfragment", "excluded": "Niet opgenomen met reden"}.get(source_role.get("role"), "Bronrol controleren")
            hint_html += f'<p data-confirmed-source-role>{_esc(role_label)} · {_esc(source_role.get("reason"))}</p>'
        items.append(
            f'<li data-passage-id="{_esc(object_id)}" data-passage-category="{_esc(category)}">'
            f'<a class="review-row-title" href="/review?document={_esc(snapshot_id)}&amp;object={_esc(object_id)}&amp;task={_esc(target_task)}">{_esc(review_card_sentence(obj))}</a>'
            f'{hint_html}'
            f'<p>{_esc(labels[category])} · {_esc(outcome)}</p>'
            f'<p class="review-next-action">{_esc(next_action)}</p>'
            f'<a href="/review/bronpassage?document={_esc(snapshot_id)}&amp;object={_esc(object_id)}&amp;task={_esc(target_task)}">Bekijk bronpassage</a>'
            f'<p class="muted">{_esc(origin)}</p></li>'
        )
    title = "Alle passages en hun afhandeling" if task == "inventory" else labels[task]
    if task == "repair":
        title += f" ({len(items)})"
    panel_class = "review-blocked-audit" if task == "repair" else "review-passage-inventory"
    return (
        f'<section class="{panel_class}">'
        + _review_task_header(snapshot_id, title, "Beoordelingswerk en bronafhandeling zijn afzonderlijke controles; de aantallen mogen overlappen")
        + f'<p>{len(items)} passages in dit overzicht.</p>'
        + f'<p><a href="/review?document={_esc(snapshot_id)}&amp;task=inventory">Alle passages bekijken</a></p>'
        + '<ol class="object-index review-passage-inventory">' + "".join(items) + '</ol>'
        + ('<p class="review-task-empty">Deze lijst is leeg. Controleer het volledige passage-overzicht voor ander werk.</p>' if not items else '')
        + '</section>'
    )


def _source_context_panel(obj: dict[str, Any], objects: list[dict[str, Any]], snapshot_id: str,
                          snapshot_revision: str) -> str:
    evidence = source_context_projection(obj, objects)
    parts: list[str] = []
    if evidence["links"]:
        items = ''.join(f'<li><b>{_esc(link.get("text"))}</b> · '
                        f'<a href="/review?document={_esc(snapshot_id)}&amp;object={_esc(link.get("source_object_id"))}">Bekijk contextbron</a>'
                        f'<p>{_esc(link.get("reason"))}</p></li>' for link in evidence["links"])
        parts.append('<section data-confirmed-source-context><h4>Bevestigde broncontext</h4>'
                     f'<ul>{items}</ul></section>')
    if evidence["issues"]:
        parts.append('<p class="banner warn">Deze contextkoppeling moet opnieuw worden gecontroleerd; tekst of bronverwijzing is gewijzigd.</p>')
    if obj.get('object_type') == 'document' or evidence['links']:
        return ''.join(parts)
    role = evidence['role']
    role_options = ''.join(f'<option value="{value}"' + (' selected' if value == role.get('role', 'label') else '') + f'>{label}</option>'
                           for value, label in [('label', 'Bronlabel'), ('context', 'Contextfragment'), ('excluded', 'Niet opnemen'), ('reset', 'Bronrol opheffen; opnieuw beoordelen')])
    if role:
        labels = {'label': 'Bronlabel', 'context': 'Contextfragment', 'excluded': 'Niet opgenomen, met reden'}
        parts.append(f'<p data-confirmed-source-role><strong>{_esc(labels.get(role.get("role"), "Bronrol"))}</strong> · '
                     f'{_esc(role.get("reviewer"))}<br>{_esc(role.get("reason"))}</p>')
    options = []
    selected = set(evidence['target_object_ids'])
    for row in objects:
        if row.get('object_id') == obj.get('object_id') or row.get('object_type') in {'document', 'heading', 'path'} or role_of(row):
            continue
        text = str((row.get('content') or {}).get('clean_text') or row.get('object_id'))
        checked = ' checked' if row.get('object_id') in selected else ''
        options.append(f'<label><input type="checkbox" name="target_object_ids" value="{_esc(row.get("object_id"))}"{checked}> '
                       f'{_esc(text[:180])} (versie {_esc(row.get("object_version"))})</label>')
    parts.append(f'''<section class="review-step" data-source-context-form><h3>Bronrol en contextkoppeling</h3>
      <form method="post" action="/review/source-context">
        <input type="hidden" name="snapshot_id" value="{_esc(snapshot_id)}">
        <input type="hidden" name="source_object_id" value="{_esc(obj.get('object_id'))}">
        <input type="hidden" name="snapshot_revision" value="{_esc(snapshot_revision)}">
        <input type="hidden" name="command_id" value="{uuid.uuid4().hex}">
        <label>Bronrol <select name="role">{role_options}</select></label>
        <h4>Geldt voor passages</h4>
        <div class="source-context-targets">{''.join(options)}</div>
        <label>Toelichting <textarea name="reason" required maxlength="4000">{_esc(role.get('reason'))}</textarea></label>
        <label><input type="checkbox" name="source_checked" value="1" required> Ik heb de bron en de gekozen passage(s) gecontroleerd.</label>
        <p>Gewijzigde context vraagt opnieuw beoordelen van de betrokken passages. Dit besluit wijzigt geen type, richting of sterkte.</p>
        <button type="submit">Bronrol en koppeling opslaan</button>
      </form></section>''')
    return ''.join(parts)


def _render_review_index(
    snapshot_id: str,
    snapshot_objects: list[dict[str, Any]],
    review_path: str,
    snapshot_revision: str = "",
    normal_content_html: str = "",
    task: str = "",
    normal_review_enabled: bool = True,
    audit_signals: list[dict[str, Any]] | None = None,
    bindings: list[dict[str, Any]] | None = None,
    reviewer_id: str = "",
) -> str:
    task = normalize_review_task(task)
    bindings = list(bindings) if bindings is not None else None
    if task in {"inventory", "disposition", "waiting"}:
        return _review_inventory(snapshot_id, snapshot_objects, review_path=review_path,
                                 bindings=bindings, reviewer_id=reviewer_id, task=task)
    followups = review_followup_queues(snapshot_objects, review_path=review_path, bindings=bindings)
    koppen = _review_route_objects(
        snapshot_objects,
        review_path=review_path,
        bindings=bindings,
        reviewer_id=reviewer_id,
        canonical_task="structure",
    )
    individual = _review_route_objects(
        snapshot_objects,
        review_path=review_path,
        bindings=bindings,
        reviewer_id=reviewer_id,
        canonical_task="contextual",
    )
    second_review = _review_route_objects(
        snapshot_objects,
        review_path=review_path,
        bindings=bindings,
        reviewer_id=reviewer_id,
        canonical_task="second_review",
    )
    blocked = followups["repair"]
    normal_passages, normal_batches = (0, 0)
    if normal_review_enabled:
        normal_passages, normal_batches = normal_risk_batch_counts(
            snapshot_objects,
            review_path=review_path,
            bindings=bindings,
        )
    copy = _review_lane_copy(review_path, koppen)
    progress = _review_progress_summary(snapshot_objects)
    if task == "history":
        decision_rows = [
            obj
            for obj in snapshot_objects
            if obj.get("object_type") != "document"
            and (_review_is_final(obj) or _review_was_revised(obj))
        ]
        return f'''
          {_review_task_header(snapshot_id, "Besluiten en historie", "Bekijk read-only welke passages zijn afgehandeld en welke na correctie opnieuw ter beoordeling staan")}
          {_review_progress_overview(snapshot_id, progress)}
          <section class="review-decision-history">
            <ol class="object-index">
              {"".join(_review_decision_row(obj, snapshot_id, audit_signals or []) for obj in decision_rows) if decision_rows else '<li class="review-task-empty">Nog geen besluiten of correcties vastgelegd.</li>'}
            </ol>
          </section>
        '''
    if task == "contextual":
        return f'''
          {_review_task_header(snapshot_id, "Passages afzonderlijk beoordelen", "Controleer iedere passage met de bron; passages staan hieronder per brononderdeel, niet per inhoudelijke relatie")}
          <section class="review-lane-slow">
            {_review_section_groups(
                individual,
                snapshot_id,
                priority_ids={str(obj.get("object_id")) for obj in individual},
                task="contextual",
                context_objects=snapshot_objects,
                review_path=review_path,
            ) if individual else '<p class="review-task-empty">Deze beoordelingslijst is leeg. Bekijk alle passages voor resterend werk.</p>'}
            <p><a href="/review?document={_esc(snapshot_id)}&amp;task=inventory">Alle passages bekijken</a></p>
          </section>
        '''
    if task == "batch":
        return f'''
          {_review_task_header(snapshot_id, "Passages selecteren en bevestigen", "Selecteer alleen passages die je hebt gecontroleerd; hetzelfde brononderdeel en type betekenen niet dezelfde inhoud")}
          {normal_content_html or '<p class="review-task-empty">Deze taak is afgerond.</p>'}
        '''
    if task == "structure":
        return f'''
          {_review_task_header(snapshot_id, copy["fast_title"], copy["fast_lead"])}
          <section class="review-lane-fast">
            <form method="post" action="/review/headings/batch-confirm">
              <input type="hidden" name="snapshot_id" value="{_esc(snapshot_id)}">
              <input type="hidden" name="interaction_id" value="{_esc(new_review_interaction_id())}">
              {_snapshot_revision_input(snapshot_revision)}
              <div class="review-batch-tools">
                <span>Selecteer alleen koppen die je hebt gecontroleerd.</span>
                <button class="btn-secondary" type="button" data-select-review-batch>Selecteer alles</button>
                <button class="btn-secondary" type="button" data-clear-review-batch>Selectie wissen</button>
              </div>
              <ol class="object-index review-heading-list">{"".join(_review_index_item(obj, snapshot_id, checkbox=True, task="structure") for obj in koppen)}</ol>
              <button class="btn-primary" type="submit">{copy["fast_button"]}</button>
            </form>
          </section>
        '''
    if task == "second_review":
        return f'''
          {_review_task_header(snapshot_id, "Tweede beoordelingen", "Beoordeel onafhankelijk exact dezelfde goedgekeurde objectversie")}
          <section class="review-lane-second">
            {_review_section_groups(
                second_review,
                snapshot_id,
                priority_ids=set(),
                task="second_review",
                context_objects=snapshot_objects,
                review_path=review_path,
            ) if second_review else '<p class="review-task-empty">Deze taak is afgerond of wacht op een andere reviewer.</p>'}
          </section>
        '''
    if task == "repair":
        return f'''
          {_review_task_header(snapshot_id, "Geblokkeerde passages herstellen", "Controleer de bron en handel verwerkingsproblemen af voordat je inhoudelijk beoordeelt")}
          {_review_inventory(snapshot_id, snapshot_objects, review_path=review_path, bindings=bindings, reviewer_id=reviewer_id, task="repair")}

        '''
    return _review_task_dashboard(
        snapshot_id,
        koppen=koppen,
        individual=individual,
        normal_passages=normal_passages,
        normal_batches=normal_batches,
        blocked_count=len(blocked),
        progress=progress,
        heading_pending_override=len(koppen),
        heading_total_override=_lane_total(
            snapshot_objects,
            review_path=review_path,
            lane="structure",
            open_rows=koppen,
        ),
        individual_pending_override=len(individual),
        individual_total_override=_lane_total(
            snapshot_objects,
            review_path=review_path,
            lane="contextual",
            open_rows=individual,
        ),
        second_review_pending=len(second_review),
        disposition_pending=len(followups["disposition"]),
        waiting_pending=sum(
            bool(route and route.get("waiting_for_other_reviewer"))
            for obj in snapshot_objects
            for route in [reviewer_route_for(obj, review_path=review_path, reviewer_id=reviewer_id, bindings=bindings)]
        ) if bindings is not None else 0,
    )


def _render_review_card(
    console: OperationsConsole,
    snapshot_id: str,
    obj: dict[str, Any],
    snapshot_objects: list[dict[str, Any]],
    review_path: str,
    draft: dict[str, Any],
    conflict_html: str,
    snapshot_revision: str = "",
    task: str = "",
) -> str:
    heading = review_card_sentence(obj)
    obj_text = (obj.get("content") or {}).get("clean_text") or ""
    heading_norm = " ".join(heading.split())
    body_norm = " ".join(str(obj_text).split())
    object_text_html = ""
    expand_merge = admission_of(obj).get("expand_merge") or {}
    merged_text = str(expand_merge.get("merged_text") or "").strip()
    merged_norm = " ".join(merged_text.split())
    merge_adds_text = bool(
        merged_norm
        and merged_norm != heading_norm
        and merged_norm != body_norm
    )
    if (
        expand_merge.get("kind") == "sentence_continuation"
        and merge_adds_text
    ):
        parts = list(expand_merge.get("parts") or [])
        missing = str(parts[1] if len(parts) > 1 else "").strip()
        object_text_html += f'''
          <aside class="source-continuation-proposal" aria-label="Voorstel om afgebroken zin te herstellen">
            <h4>Voorstel: afgebroken zin aanvullen</h4>
            <p><b>Ontbrekende brontekst:</b> {_esc(missing)}</p>
            <p><b>Herstelde passage:</b> {_esc(merged_text)}</p>
            <p class="field-help">Na aanvullen ontstaat een nieuwe versie. Die versie is nog niet goedgekeurd en moet opnieuw worden beoordeeld.</p>
            <button class="btn-secondary" type="submit" formaction="/review/context/accept" formmethod="post">Passage aanvullen met brontekst</button>
          </aside>
        '''
    proposed = proposed_type_of(obj)
    confirmable = confirmable_proposed_type(obj)
    confirmed = obj.get("confirmed_object_type") or ""
    type_options = _type_options(
        draft.get("confirmed_object_type") or confirmed,
        review_path=review_path,
        proposed=confirmable,
    )
    try:
        console.open_source_passage(snapshot_id=snapshot_id, object_id=obj["object_id"])
        passage_ok = True
    except ConsoleError:
        passage_ok = False
    disabled = "" if passage_ok else " disabled"
    gate = str(admission_of(obj).get("gate_result") or "")
    admission_notice = ""
    if is_admission_blocked(obj, review_path=review_path) or (review_path != "boom" and gate != "allowed" and authoritative_review_type(obj) != "heading"):
        admission_notice = (
            "Deze passage kan nog niet worden goedgekeurd. Een correctie of gemotiveerde afhandeling is nodig."
            if gate == "blocked" else
            "Deze passage is nog niet beschikbaar voor goedkeuring."
        )
    approval_disabled = disabled or (
        " disabled" if is_admission_blocked(obj, review_path=review_path) else ""
    )
    repair_guidance = (
        '<aside class="banner warn"><b>Eerst de passage herstellen.</b> '
        'Kies hieronder wat ontbreekt en vervolgens <b>Correctie specificeren</b>. '
        'Je kiest daarna de oorspronkelijke bronfragmenten of de passende structurele correctie. '
        'De herstelde passage wordt een nieuw voorstel dat opnieuw beoordeeld moet worden.</aside>'
        if is_admission_blocked(obj, review_path=review_path) else ""
    )
    if review_path == "boom" and "decision_unit_graph_unresolved" in admission_of(obj).get("reason_codes", []):
        repair_guidance = (
            '<aside class="banner warn"><b>Eerst de beslisstructuur controleren.</b> '
            'Controleer vragen, antwoordlabels en verbindingen tegen de bron. '
            f'<a href="/review/decision-graph?document={_esc(snapshot_id)}">Open beslisroutes</a>. '
            'Onvolledige bronpassages blijven daarna afzonderlijk herstelwerk.</aside>'
        )
    four_eyes_html = ""
    if requires_four_eyes(obj, confirmed_type=confirmed or None):
        four_eyes_html = (
            '<div class="banner warn">Voor deze passage is een '
            "<b>onafhankelijke tweede beoordeling nodig</b>.</div>"
        )
    path_text = found_under_path(obj)
    proposed_label = _object_type_label(proposed or confirmable)
    classification_note = (
        f'Eerder bevestigd type: <b>{_esc(_object_type_label(str(confirmed)))}</b>. '
        f'Oorspronkelijk voorstel van Metis: {_esc(proposed_label)}.'
        if confirmed else
        f'Metis stelt voor: <b>{_esc(proposed_label)}</b>. Dit type is nog niet door jou bevestigd.'
    )
    if review_path == "boom":
        classification_note = (
            f'Eerder bevestigd type: <b>{_esc(_object_type_label(str(confirmed)))}</b>.'
            if confirmed else
            f'Huidige indeling: <b>{_esc(proposed_label)}</b>. Dit type is nog niet door jou bevestigd.'
        )
    return f"""
                <p><a class="btn-secondary" href="{_review_location(console, snapshot_id, task=task)}">← Terug naar taken</a></p>
                <article class="object review-card-two-column" data-object-id="{_esc(obj["object_id"])}" data-object-type="{_esc(proposed or confirmable)}" data-confirmed-type="{_esc(str(confirmed or ""))}">
                  <form class="review-decision-form" method="post" action="/review" data-review-form>
                    <input type="hidden" name="snapshot_id" value="{_esc(snapshot_id)}">
                    <input type="hidden" name="object_id" value="{_esc(obj["object_id"])}">
                    <input type="hidden" name="return_task" value="{_esc(task if task in REVIEW_TASKS else '')}">
                    <input type="hidden" name="interaction_id" value="{_esc(new_review_interaction_id())}">
                    {_snapshot_revision_input(snapshot_revision)}
                    <input type="hidden" name="proposed_object_type" value="{_esc(confirmable)}">
                    <input type="hidden" name="found_under" value="{_esc(path_text)}">
                    <input type="hidden" name="decision" value="">
                    {four_eyes_html}
                    {conflict_html}
                    <div class="review-decision-layout">
                    <div class="review-source-column">
                    {_knowledge_review_html(obj, snapshot_objects)}
                    {_decision_paths_html(console, snapshot_id, obj, snapshot_objects)}
                    {object_text_html}
                    {_broncontext_html(obj, snapshot_id, obj["object_id"], passage_ok, task=task)}
                    {_review_context_block(
                        obj,
                        snapshot_objects,
                        snapshot_id=snapshot_id,
                        review_path=review_path,
                        task=task,
                    )}
                    </div>
                    <div class="review-choices-column">
                    {f'<p>{_esc(admission_notice)}</p>' if admission_notice else ''}{repair_guidance}
                    <section class="review-step" data-review-step="c">
                      <h4>Is deze passage op zichzelf bruikbaar?</h4>
                      <label class="check"><input type="radio" name="suitability" value="ja"{_checked(draft.get("suitability", ""), "ja")}> Ja, als zelfstandig stukje kennis</label>
                      <label class="check"><input type="radio" name="suitability" value="mist_context"{_checked(draft.get("suitability", ""), "mist_context")}> Nee, ik mis uitleg eromheen</label>
                      <label class="check"><input type="radio" name="suitability" value="samenvoegen"{_checked(draft.get("suitability", ""), "samenvoegen")}> Nee, deze hoort samen met een andere passage</label>
                      <label class="check"><input type="radio" name="suitability" value="alleen_onderbouwing"{_checked(draft.get("suitability", ""), "alleen_onderbouwing")}> Alleen als onderbouwing van een andere passage</label>
                      <label class="check"><input type="radio" name="suitability" value="geen_kenniseenheid"{_checked(draft.get("suitability", ""), "geen_kenniseenheid")}> Geen zelfstandig stukje kennis</label>
                    </section>
                    <section class="review-step" data-review-step="d">
                      <h4>Staat de passage onder de juiste kop?</h4>
                      <p>Gevonden onder: <b>{_esc(path_text or "het document")}</b></p>
                      <label class="check"><input type="radio" name="documentpositie_action" value="dit_klopt"{_checked(draft.get("documentpositie_action", ""), "dit_klopt")}> Dit klopt</label>
                      <label class="check"><input type="radio" name="documentpositie_action" value="andere_kop"{_checked(draft.get("documentpositie_action", ""), "andere_kop")}> Andere kop kiezen</label>
                      {_heading_chooser(obj, snapshot_objects, snapshot_id, draft.get("parent_choice", ""))}
                    </section>
                    <section class="review-step" data-review-step="e" id="classification-{_esc(obj["object_id"])}">
                      <h4>Wat voor informatie is dit?</h4>
                      <p>{classification_note}</p>
                      <label class="check"><input type="radio" name="type_action" value="dit_klopt"{_checked(draft.get("type_action", ""), "dit_klopt")}> Dit klopt</label>
                      <label class="check"><input type="radio" name="type_action" value="type_wijzigen"{_checked(draft.get("type_action", ""), "type_wijzigen")}> Type wijzigen</label>
                      <div data-type-chooser hidden>
                        <label for="type-{_esc(obj["object_id"])}">Ander type</label>
                        <select id="type-{_esc(obj["object_id"])}" name="confirmed_object_type" hidden{disabled}>{type_options}</select>
                      </div>
                    </section>
                    {(
                        _stamp_block(obj, hidden=not recommendation_strength_ui_applies(obj))
                        if review_path == "boom"
                        else _recommendation_semantics_block(
                            obj,
                            draft,
                            hidden=not (
                                draft.get("validation_error")
                                or (obj.get("confirmed_object_type") or obj.get("object_type"))
                                == "recommendation"
                            ),
                        )
                    )}
                    {_knowledge_relation_review_block(
                        obj,
                        snapshot_objects,
                        review_path=review_path,
                        draft=draft,
                    )}
                    <section class="review-step" data-review-step="f">
                      <h4>Wat is je besluit?</h4>
                      <fieldset id="decision-{_esc(obj["object_id"])}">
                      <label class="check"><input type="radio" name="eindoordeel" value="goedkeuren"{approval_disabled}{_checked(draft.get("eindoordeel", ""), "goedkeuren")}> Goedkeuren — inhoud en indeling kloppen</label>
                      <label class="check"><input type="radio" name="eindoordeel" value="goedkeuren_na_correctie"{_checked(draft.get("eindoordeel", ""), "goedkeuren_na_correctie")}> Correctie specificeren — maak een nieuw voorstel voor beoordeling</label>
                      <label class="check"><input type="radio" name="eindoordeel" value="afwijzen"{_checked(draft.get("eindoordeel", ""), "afwijzen")}> Afwijzen — niet gebruiken als kennisobject</label>
                      <label class="check"><input type="radio" name="eindoordeel" value="later_beoordelen"{_checked(draft.get("eindoordeel", ""), "later_beoordelen")}> Later beoordelen — nog geen besluit</label>
                      </fieldset>
                      <p class="field-help" data-decision-hint>Kies een eindoordeel.</p>
                      <div class="decision-comment" data-comment-field hidden>
                        <label for="comment-{_esc(obj["object_id"])}">Toelichting (verplicht)</label>
                        <textarea id="comment-{_esc(obj["object_id"])}" name="comment">{html.escape(draft.get("comment", ""), quote=True)}</textarea>
                      </div>
                      <div class="decision-correction" data-correction-field hidden>
                        <label for="correction-{_esc(obj["object_id"])}">Voorgestelde correctie</label>
                        <textarea id="correction-{_esc(obj["object_id"])}" name="proposed_correction">{html.escape(draft.get("proposed_correction", ""), quote=True)}</textarea>
                      </div>
                      <button class="btn-primary" type="submit" data-submit-review>Review opslaan en volgende</button>
                    </section>
                    </div></div>
                  </form>
                </article>
                {_review_validation_script()}
                """


def _render_review_room(
    console: OperationsConsole,
    account: dict[str, Any],
    document: str = "",
    object: str = "",
    *,
    task: str = "",
    counts: dict[str, int] | None = None,
    draft: dict[str, Any] | None = None,
    conflict: bool = False,
    batch_selection: list[str] | None = None,
    batch_completed: int = 0,
    snapshot: tuple[list[dict[str, Any]], str] | None = None,
) -> str:
    chosen = document.strip()
    chosen_object_id = object.strip()
    chosen_task = normalize_review_task(task)
    draft = _sanitize_review_draft(draft)
    conflict_html = _review_conflict_html(conflict)
    if conflict and batch_completed:
        conflict_html = (
            f'<div class="banner warn" data-partial-batch-conflict>'
            f'{batch_completed} geselecteerde passage'
            f'{" is" if batch_completed == 1 else "s zijn"} al opgeslagen. '
            'Het document is tussentijds gewijzigd; controleer de resterende selectie en probeer die opnieuw.'
            '</div>'
        )
    snapshot_revision = ""
    envelopes = console.list_envelopes()
    chosen_row = next((row for row in envelopes if row["snapshot_id"] == chosen), None)
    cards = []
    if not chosen:
        for row in envelopes:
            cards.append(
                f"""
                    <article class="doc-card review-document-card">
                      {_document_card_heading({**row, "status": row["state"]})}
                      <p class="lead">Beoordeel passages stap voor stap, met de oorspronkelijke bron als uitgangspunt.</p>
                      <p><a class="btn-primary" href="/review?document={_esc(row["snapshot_id"])}">Beoordeel</a></p>
                    </article>
                    """
            )
    objects_html = ""
    if chosen_row:
        objects_html = (
            f'<div class="doc-card review-document-card">'
            '<div class="review-document-card-top"><span class="review-document-kicker">Document in review</span>'
            '<a class="btn-secondary" href="/review">Ander document kiezen</a></div>'
            f'{_document_card_heading({**chosen_row, "status": chosen_row["state"]})}'
            "</div>"
        )
        history_enabled = chosen_task == "history"
        if history_enabled:
            loaded_objects, snapshot_revision = console.snapshot_objects_and_revision(
                chosen,
                include_blocked=True,
            )
            all_object_versions = loaded_objects
            snapshot_objects = _current_review_objects(loaded_objects)
        else:
            snapshot_objects, snapshot_revision = (
                snapshot if snapshot is not None else console.snapshot_objects_and_revision(chosen)
            )
            all_object_versions = []
        review_path = review_path_for_klasse(chosen_row["class"])
        audit_signals: list[dict[str, Any]] = []
        if history_enabled:
            audit_reader = getattr(console, "audit_review_signals", None)
            if callable(audit_reader):
                audit_signals = list(audit_reader())
        if not chosen_object_id:
            normal_content_html = ""
            if isinstance(console, ProportionateReviewConsole) and chosen_task == "batch":
                normal_content_html = render_normal_risk_batch_panel(
                    console, chosen,
                    snapshot=(snapshot_objects, snapshot_revision),
                    selected_ids=batch_selection or (),
                    include_individual=False,
                )
            try:
                bindings = _review_bindings(console, chosen)
            except AttributeError:
                bindings = None
            objects_html += _render_review_index(
                chosen,
                snapshot_objects,
                review_path,
                snapshot_revision,
                normal_content_html=normal_content_html,
                task=chosen_task,
                normal_review_enabled=isinstance(console, ProportionateReviewConsole),
                audit_signals=audit_signals,
                bindings=bindings,
                reviewer_id=str(account.get("account_id") or ""),
            )
        else:
            obj = next((row for row in snapshot_objects if row["object_id"] == chosen_object_id), None)
            if obj is None:
                raise ConsoleError("unknown_object")
            if history_enabled:
                objects_html += _review_object_history(
                    chosen,
                    obj,
                    all_object_versions,
                    audit_signals,
                )
            else:
                conflict_html = _review_conflict_html(conflict, current=obj, draft=draft)
                try:
                    current_bindings = _review_bindings(console, chosen)
                except AttributeError:
                    current_bindings = None
                route = (
                    reviewer_route_for(
                        obj,
                        review_path=review_path,
                        reviewer_id=str(account.get("account_id") or ""),
                        bindings=current_bindings,
                    )
                    if current_bindings is not None
                    else None
                )
                if route and route.get("canonical_task") == "second_review":
                    if route.get("actionable"):
                        objects_html += _render_second_review_card(
                            console,
                            chosen,
                            obj,
                            snapshot_objects,
                            review_path,
                            reviewer_id=str(account.get("account_id") or ""),
                            snapshot_revision=snapshot_revision,
                        )
                    else:
                        objects_html += f"""
                          <p><a class="btn-secondary" href="/review?document={_esc(chosen)}">← Terug naar taken</a></p>
                          <div class="banner warn">Deze tweede beoordeling moet door een andere onafhankelijke reviewer worden uitgevoerd.</div>
                        """
                elif chosen_task == "second_review":
                    objects_html += _render_second_review_card(
                        console,
                        chosen,
                        obj,
                        snapshot_objects,
                        review_path,
                        reviewer_id=str(account.get("account_id") or ""),
                        snapshot_revision=snapshot_revision,
                    )
                elif role_of(obj):
                    objects_html += f'<section data-source-role-card><h3>Bronfragment</h3><p>{_esc((obj.get("content") or {}).get("clean_text"))}</p><p>Deze bronrol is expliciet beoordeeld. Gebruik hieronder Bronrol en contextkoppeling om het besluit te wijzigen. Beoordeel de gekoppelde inhoudelijke passages afzonderlijk.</p></section>'
                else:
                    objects_html += _render_review_card(
                        console,
                        chosen,
                        obj,
                        snapshot_objects,
                        review_path,
                        draft,
                        conflict_html,
                        snapshot_revision,
                        chosen_task,
                    )
                if 'reviewer' in (account.get('roles') or []) and str(account.get('account_id') or '') in chosen_row.get('named_reviewers', []) and not console.snapshot_is_published(chosen):
                    objects_html += _source_context_panel(obj, snapshot_objects, chosen, snapshot_revision)
    empty = '<p class="muted">Nog geen documenten om te reviewen.</p>' if not envelopes else ""
    return _page(
        f"""
            {_nav(account, "review", counts)}
            <section class="room review-room">
              <h1>Review</h1>
              {_task_links("review")}
              {conflict_html if not chosen_object_id else ""}
              {"".join(cards) if not chosen else ""}
              {objects_html or empty}
            </section>
            """
    )


def create_console_app(
    console: OperationsConsole | None = None,
    *,
    trusted_origin: str | None = None,
    api_access_store: Any | None = None,
) -> FastAPI:
    state = console or OperationsConsole(root=REPO_ROOT)
    install_ingest_limits(state)
    from src.console_entra_v1 import install_entra
    entra = install_entra(state, trusted_origin)
    access_store = api_access_store
    access_store_error = ""
    selected_access_mode = str(os.getenv("METIS_API_ACCESS_STORE", "legacy") or "legacy").strip().lower()
    if access_store is None and selected_access_mode == "postgres":
        try:
            access_store = PostgresApiAccessStore()
            access_store.verify_schema()
        except ApiAccessStoreError as exc:
            access_store_error = str(exc)
    app = FastAPI(
        title="V&VN Data Services Internal Operations Console",
        version=SERVICE_VERSION,
        description="Internal researcher/reviewer console. Not the Product API. Chat is not a room.",
    )
    if BRAND_DIR.is_dir():
        app.mount("/brand", StaticFiles(directory=str(BRAND_DIR)), name="brand")

    expected_origin = ""
    if trusted_origin is not None:
        parsed = urlsplit(str(trusted_origin).strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("console_trusted_origin_invalid")
        expected_origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    @app.middleware("http")
    async def require_same_origin(request: Request, call_next):
        if expected_origin and request.url.path != "/mcp" and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = str(request.headers.get("origin") or "").strip().lower().rstrip("/")
            if supplied != expected_origin:
                return HTMLResponse(
                    "Cross-origin request blocked.",
                    status_code=403,
                )
        return await call_next(request)

    if entra is not None:
        from src.console_entra_routes_v1 import install_entra_routes
        install_entra_routes(app, state, entra, render_page=_page)

    login_limiter = SlidingWindowRateLimiter()
    login_attempts_per_minute = 10

    def _current(request: Request) -> dict[str, Any] | None:
        token = request.cookies.get(COOKIE)
        try:
            return state.session_account(token)
        except ConsoleError:
            return None

    def _require(request: Request) -> dict[str, Any]:
        account = _current(request)
        if not account:
            raise ConsoleError("not_authenticated")
        return account

    def _counts(account: dict[str, Any] | None) -> dict[str, int]:
        if not account:
            return {}
        return state.waiting_task_counts(account["account_id"])

    from src.metis_mcp_v1 import install_mcp
    install_mcp(app, state, entra, expected_origin, require_account=_require, render_page=_page, nav=_nav)

    @app.exception_handler(ConsoleError)
    async def console_errors(_request: Request, exc: ConsoleError) -> HTMLResponse:
        status = 401 if exc.code in {"not_authenticated", "invalid_credentials"} else 403 if "role_required" in exc.code or exc.code in {"entra_access_denied", "entra_local_auth_disabled"} else 400
        message = ERROR_COPY.get(exc.code, "Metis kon deze actie niet afronden. Controleer de huidige status voordat je opnieuw probeert. Blijft dit gebeuren? Meld het bij de beheerder.")
        account = _current(_request)
        filename_error = exc.code == "invalid_store_path" and _request.url.path == "/ingest"
        hint = f'<p class="field-help">{_esc(FILENAME_HINT)}</p>' if filename_error else ""
        processing_details = ""
        if account and exc.code.startswith("pre_review_llm_"):
            diagnostic = getattr(exc, "pre_review_diagnostics", {})
            reason = str(diagnostic.get("reason_code") or "")
            reference = str(diagnostic.get("reference") or "")
            if re.fullmatch(r"(?:semantic|recommendation|source_bound)_[a-z_]{1,100}", reason):
                processing_details += f'<p>Validatiereden: <code>{_esc(reason)}</code></p>'
            if re.fullmatch(r"[a-f0-9]{32}", reference):
                processing_details += f'<p>Verwerkingsreferentie: <code>{reference}</code></p>'
        back = (
            '<p><a href="/ingest">Terug naar Inleveren</a></p>'
            if _request.url.path == "/ingest" and account
            else '<p><a href="/">Naar Mijn werk</a></p>' if account
            else '<p><a href="/login">Naar aanmelden</a></p>'
        )
        if account and _request.url.path == "/review/participants":
            document = _request.query_params.get("document") or getattr(_request.state, "review_participation_document", "")
            back = '<p><a href="/review?work=all">Terug naar reviewoverzicht</a></p>'
            if document:
                back += f'<p><a href="/review/participants?{_esc(urlencode({"document": document}))}">Terug naar deelnemersbeheer</a></p>'
        technical_details = (
            f'<details><summary>Technische informatie voor de beheerder</summary><code>{_esc(exc.code)}</code>{processing_details}</details>'
            if _request.url.path.startswith(("/settings", "/audit")) else ""
        )
        if not technical_details and (exc.code.startswith(("pre_review_", "processing_"))):
            message = "De verwerking is niet beschikbaar. Deze taak kan nu niet worden uitgevoerd."
        body = _page(
            f"""
            {_nav(account)}
            <section class="room">
              <h1>Actie niet uitgevoerd</h1>
              <div class="banner err" data-error-code="{_esc(exc.code)}">{_esc(message)}</div>
              {hint}
              {technical_details}
              {back}
            </section>
            """
        )
        return HTMLResponse(body, status_code=status)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request) -> str:
        account = _current(request)
        if not account:
            return _page(
                f"""
                <section class="room login-card">
                  {_login_brand()}
                  <h1>Interne operations console</h1>
                  <p class="lead">Meld je aan om documenten in te leveren, te reviewen of te publiceren.</p>
                  <p><a class="btn-primary" href="/login" style="display:inline-block;text-decoration:none;">Aanmelden</a></p>
                </section>
                """
            )
        counts = _counts(account)
        review_waiting = counts.get("review", 0)
        documents = state.list_envelopes()
        tiles = "".join(
            (
                _home_tile(
                    href="/ingest",
                    icon="⇧",
                    title="Inleveren",
                    description="Nieuwe bron toevoegen",
                    badge=(f"{counts['ingest']} terug voor revisie" if counts["ingest"] else "Nieuwe bron"),
                ),
                _home_tile(
                    href="/review",
                    icon="✓",
                    title="Review",
                    description="Beoordeel aangeleverde bronnen",
                    badge=(f"{review_waiting} wachten op jou" if review_waiting else "Geen open taken"),
                    priority=bool(review_waiting),
                ),
                _home_tile(
                    href="/publish",
                    icon="⇧",
                    title="Publiceren",
                    description="Goedgekeurde stukken publiceren",
                    badge=(f"{counts['publish']} gereed" if counts["publish"] else "Geen open taken"),
                ),
                _home_tile(
                    href="/tree",
                    icon="▰",
                    title="Documenten",
                    description="Zoeken, openen of beheren",
                    badge=f"{len(documents)} documenten",
                ),
            )
        )
        return _page(
            f"""
            {_nav(account, "home", counts)}
            <section class="room home-room">
              <h1>Mijn werk</h1>
              <p class="lead">Kies de volgende stap in het proces.</p>
              <div class="home-tiles">{tiles}</div>
            </section>
            """
        )

    @app.get("/help/{topic}", response_class=HTMLResponse)
    def task_instructions(request: Request, topic: str) -> str:
        account = _require(request)
        topics = {
            "ingest": ("Document inleveren", "/ingest", """
              <h2>Documentgegevens</h2><p>Lever HTML, PDF of een vastgelegde beslisboom aan.
              Gebruik het versienummer van het brondocument en de publicatiedatum uit het colofon.
              Kies bij een opvolgende bronversie het bestaande document.</p>
              <h2>Beoordelaars</h2><p>De verantwoordelijke beoordelaar kan de uploader zijn als die bevoegd is.
              De gekozen reviewvorm bepaalt de aanvullende deelname; bestaande onafhankelijke
              controles blijven gelden. Bij bestaande reviewregels mag de uploader niet de enige reviewer zijn.</p>
              <h2>Verwerking</h2><p>Metis maakt voorstellen; een voorstel is geen inhoudelijk besluit.
              De verwerking kan worden geblokkeerd. Diagnose en nieuwe verwerkingspogingen staan bij technisch beheer.</p>"""),
            "review": ("Beoordelen", "/review", """
              <h2>Bron en betekenis</h2><p>Controleer de passage met de oorspronkelijke bron en de relevante context.
              Metis doet een voorstel; jij bepaalt wat met de passage gebeurt.
              Een zelfstandige passage is begrijpelijk zonder de rest van het document.
              Een definitie legt een begrip uit; een toelichting beschrijft of verklaart iets;
              een advies zegt wat iemand zou moeten doen. Kop en type zijn voorstellen totdat ze zijn bevestigd.</p>
              <h2>Richting en sterkte</h2><p>Neem de sterkte over uit de oorspronkelijke richtlijn.
              Kies Sterk of Zwak alleen als de bron dit expliciet vermeldt.
              ‘De werkgroep adviseert’ is geen sterkteaanduiding. Een klinische voorwaarde maakt een advies
              niet automatisch zwak. Kies Niet vermeld in de bron wanneer geen sterkte wordt genoemd.</p>
              <h2>Beslisboom</h2><p>Een pad beschrijft de route of resultaatbundel. Een pad is zelf geen advies. Een knoop is een vraag, beslispunt of scorelijstitem;
              een uitkomst is het afsluitende advies. Een route bestaat uit opeenvolgende stappen: een verbinding legt één stap van een onderdeel naar het volgende vast. Controleer de voorwaarden en verbindingen met de bron.</p>
              <h2>Voortgang en selecties</h2><p>Afwijzen, context, onderbouwing en gemotiveerd niet opnemen
              tellen als afhandeling. Passageaantallen en aantallen handelingen kunnen overlappen.
              Controleer iedere passage voordat je een selectie bevestigt; dezelfde kop of hetzelfde type
              betekent niet dat passages hetzelfde zeggen. Geen beschikbaar werk betekent niet dat publicatie mogelijk is.</p>
              <h2>Voorstellen uit verwerking</h2><p>PDF-fragmenten kunnen standaard het type Knoop hebben gekregen bij het inlezen. Dit is geen inhoudelijke classificatie. Opsommingen kunnen automatisch gegroepeerd zijn als resultaatbundel, met afzonderlijk afgesplitste uitkomsten. Bepaal het juiste type aan de hand van de bron.</p>
              <h2>Broncontrole</h2><p>Bronbinding bewijst niet dat alle noodzakelijke context is herkend. Controleer ook de oorspronkelijke bron.</p>
              <h2>Reviewdeelname</h2><p>Archiveren bewaart historie. Een verplichte plek blijft open tot vervanging. De vervanger beoordeelt zelf; geldig werk van anderen blijft behouden. Vervang de primaire reviewer in één handeling.</p>
              <h2>Correctie en bronrol</h2><p>Een correctie maakt een nieuw voorstel voor beoordeling.
              Kies aaneengesloten bronzinnen; samengevoegde passages worden vervangen door het nieuwe voorstel.
              Alleen de geselecteerde passage wordt met het beoordelingsformulier beoordeeld. Metis doet relationele voorstellen; bevestig alleen relaties die volgens de bron bij deze passage horen. Een voorwaarde verandert de sterkte van een aanbeveling niet.
              Koppel een bronlabel of context alleen aan passages waarvoor het aantoonbaar geldt.
              Controleer daarbij ook tabellen en kolommen. Nabijheid alleen is onvoldoende.</p>"""),
            "publish": ("Publiceren", "/publish", """
              <h2>Publicatiebesluit</h2><p>De review, bronafhandeling en publicatiecontroles moeten gereed zijn.
              Metis controleert deze voorwaarden opnieuw bij het besluit. Afgeronde review betekent
              niet automatisch dat het document gepubliceerd kan worden.</p>
              <h2>Beschikbaarheid</h2><p>Een historische publicatie kan vervangen, ingetrokken of niet actief zijn.
              Na intrekking wordt een oudere versie niet automatisch opnieuw actief.</p>"""),
            "documents": ("Documenten", "/tree", """
              <h2>Documentbeheer</h2><p>Zoek een document en open de beschikbare taak.
              Gepubliceerde versies blijven ongewijzigd. Een wijziging van documenttype kan een nieuwe
              beoordeling of verwerking vereisen. Verwerking en technische herstelpogingen staan in technisch beheer.</p>"""),
        }
        if topic not in topics:
            raise ConsoleError("unknown_document")
        title, back, content = topics[topic]
        return _page(f'{_nav(account, "settings", _counts(account))}<section class="room">'
                     f'<h1>Uitleg: {_esc(title)}</h1>{content}'
                     f'<p><a href="{back}">Terug naar {_esc(title)}</a></p></section>',
                     title=f'Uitleg: {_esc(title)} — Metis')

    @app.get("/settings/technical/processing", response_class=HTMLResponse)
    def processing_management(request: Request, document: str) -> str:
        account = _require(request)
        envelope = state._envelope(document)
        roles = set(account.get("roles") or [])
        # Same authorization as processing_status/retry: researchers or assigned reviewers.
        processing = state.processing_status(document, actor_id=account["account_id"])
        controls = []
        if processing["retry_allowed"]:
            controls.append(f'''<form method="post" action="/tree/reprocess">
              <input type="hidden" name="snapshot_id" value="{_esc(document)}">
              <input type="hidden" name="command_id" value="{uuid.uuid4().hex}">
              <button class="btn-primary" type="submit">Verwerking opnieuw proberen</button></form>''')
        if ("publisher" in roles
                and (account["account_id"] in envelope.get("named_reviewers", [])
                     or account["account_id"] == envelope.get("uploader_account_id"))
                and processing.get("reason_code") == "processing_attempt_limit_reached"
                and not envelope.get("processing_recovery")):
            controls.append(f'''<form method="post" action="/tree/processing-recovery">
              <input type="hidden" name="snapshot_id" value="{_esc(document)}">
              <label>Reden voor eenmalig herstel<input name="reason" required maxlength="1000"></label>
              <button type="submit">Een herstelpoging autoriseren</button></form>''')
        code = processing.get("error_code") or processing.get("reason_code") or ""
        diagnostic = ((envelope.get("processing_attempts") or [{}])[-1].get("diagnostic") or {})
        detail = _esc(json.dumps(diagnostic, ensure_ascii=False, indent=2))
        reviewer_links = (f'<p><a href="/settings/technical?document={_esc(document)}">Passagediagnostiek en exports</a></p>'
                          if "reviewer" in roles and account["account_id"] in envelope.get("named_reviewers", []) else "")
        return _page(f'''{_nav(account, "settings", _counts(account))}<section class="room">
          <p><a href="/settings/technical">Terug naar technisch beheer</a></p>
          <h1>Verwerkingsbeheer: {_esc(envelope.get("title"))}</h1>
          <p>{_esc(ERROR_COPY.get(code, "Controleer de actuele verwerking."))}</p>
          <p>Code: <code>{_esc(code)}</code></p>
          <p>Nieuwe poging vanaf: {_esc(processing.get("retry_not_before") or "niet van toepassing")}</p>
          {"".join(controls)}<pre>{detail}</pre>{reviewer_links}
          <p><a href="/review?document={_esc(document)}">Naar beoordeling</a> · <a href="/tree">Naar Documenten</a></p>
          </section>''', title="Verwerkingsbeheer — Metis")

    @app.get("/settings", response_class=HTMLResponse)
    def settings_home(request: Request) -> str:
        account = _require(request)
        cards = """
          <div class="doc-list">
            <a class="doc-card" href="/settings/quality"><p class="doc-title">Kwaliteit &amp; werkproces</p><p>Bekijk bruikbaarheid, herstelwerk en open werk op basis van bestaande handelingen.</p></a>
            <a class="doc-card" href="/accounts" style="text-decoration:none;">
              <p class="doc-title">Accounts</p>
              <p>Beheer interne gebruikers en rollen.</p>
            </a>
            <a class="doc-card" href="/settings/technical">
              <p class="doc-title">Technisch beheer</p>
              <p>Modelconfiguratie, API-toegang, veiligheidstests, experimenten en documentdiagnostiek.</p>
            </a>
            <a class="doc-card" href="/settings/chatgpt"><p class="doc-title">ChatGPT-koppeling</p><p>Verbindingsstatus en toegang tot alleen-lezen onderzoek vanuit ChatGPT.</p></a>
            <a class="doc-card" href="/over-console" style="text-decoration:none;">
              <p class="doc-title">Over Metis</p>
              <p>Lees hoe Metis werkt, welke begrippen het gebruikt en waar de grenzen liggen.</p>
            </a>
          </div>
        """
        return _page(
            f"""
            {_nav(account, "settings", _counts(account))}
            <section class="room">
              <p class="eyebrow">Beheer</p>
              <h1>Instellingen</h1>
              <p class="lead">Accounts, werkproces, technisch beheer en informatie over Metis.</p>
              {cards}
            </section>
            """,
            title="Instellingen — Metis",
        )

    @app.get("/settings/technical", response_class=HTMLResponse)
    def technical_management(request: Request, document: str = "", q: str = "", page: int = 1) -> str:
        account = _require(request)
        document_panel = ""
        if document:
            if "reviewer" not in set(account.get("roles") or []):
                raise ConsoleError("reviewer_role_required")
            envelope = state._envelope(document)
            if account["account_id"] not in (envelope.get("named_reviewers") or []):
                raise ConsoleError("reviewer_not_named_on_snapshot")
            objects = state.snapshot_objects(document)
            burden = review_burden_projection(read_events(state._ledger_path), snapshot_id=document)
            document_panel = f'''
              <h2>Verwerkingsproblemen herstellen: {_esc(envelope.get("title"))}</h2>
              <p><a href="/review?document={_esc(document)}">Naar inhoudelijke review</a>
              · <a href="/settings/technical/exports?document={_esc(document)}">Exports</a></p>
              <p><a href="/review?document={_esc(document)}&amp;task=repair">Passages corrigeren</a></p>
              <details><summary>Diagnostiek en brondekking</summary>
                {_processing_diagnostics_html(objects)}{_coverage_panel(objects)}
              </details>
              <details class="review-burden"><summary>Reviewinteracties</summary>
                <p>{int(burden["review_interactions"])} gemeten menselijke interacties voor
                {int(burden["object_decisions"])} objectbesluiten.</p>
                <p>Historische besluiten zonder gemeten interactie: {int(burden["legacy_unmeasured_decisions"])}.</p>
              </details>
            '''
        if document:
            return _page(f'{_nav(account, "settings", _counts(account))}<section class="room">'
                         '<p><a href="/settings/technical">Terug naar technisch beheer</a></p>'
                         + document_panel + '</section>', title="Documentdiagnostiek — Metis")
        assigned = [row for row in state.list_envelopes()
                    if "researcher" in set(account.get("roles") or []) or (
                        "reviewer" in set(account.get("roles") or [])
                        and account["account_id"] in (row.get("named_reviewers") or []))]
        assigned, list_controls = _document_list_page(assigned, q=q, page=page, path="/settings/technical")
        documents = "".join(
            f'<li><a href="/settings/technical/processing?document={_esc(row["snapshot_id"])}">{_esc(row.get("title"))} · {_esc(row.get("version"))}</a></li>'
            for row in assigned
        )
        return _page(f'''
          {_nav(account, "settings", _counts(account))}
          <section class="room">
            <p><a href="/settings">← Instellingen</a></p>
            <h1>Technisch beheer</h1>
            {_passage_formation_status_html(state)}
            <p class="lead">Configuratie, technische controles en experimenten op één plek. Testresultaten zijn geen inhoudelijke beoordeling van documenten.</p>
            <h2>Configuratie en koppelingen</h2>
            <div class="doc-list">
              <a class="doc-card" href="/settings/llm"><p class="doc-title">Modelconfiguratie</p><p>Bekijk de ingestelde provider en het model.</p></a>
              <a class="doc-card" href="/settings/api-access"><p class="doc-title">API-toegang</p><p>Beheer koppelingen en toegangsgegevens.</p></a>
            </div>
            <h2>Tests en experimenten</h2>
            <div class="doc-list">
              <a class="doc-card" href="/audit/semantic-safety"><p class="doc-title">Semantische veiligheidstests</p><p>Controleer vaste testgevallen voor weglatingen, voorwaarden, uitzonderingen en ontkenningen.</p></a>
              <a class="doc-card" href="/audit"><p class="doc-title">Audit &amp; diagnostiek</p><p>Open controles, experimenten en bewaarde resultaten.</p></a>
              <a class="doc-card" href="/settings/quality/compare"><p class="doc-title">Routevergelijking</p><p>Vergelijk verwerkingsroutes op dezelfde bron.</p></a>
            </div>
            <h2>Exports</h2>
            <a class="doc-card" href="/settings/technical/exports">Alle exports</a>
            <h2>Verwerkingsproblemen herstellen</h2>
            {list_controls}
            <ul>{documents or '<li>Geen documenten gevonden.</li>'}</ul>
            {document_panel}
          </section>
        ''', title="Technisch beheer — Metis")

    @app.get("/settings/technical/exports", response_class=HTMLResponse)
    def technical_exports(request: Request, document: str = "", q: str = "", page: int = 1) -> str:
        account = _require(request)
        if "reviewer" not in set(account.get("roles") or []):
            raise ConsoleError("reviewer_role_required")
        assigned = [row for row in state.list_envelopes()
                    if account["account_id"] in (row.get("named_reviewers") or [])]
        if document and not any(row["snapshot_id"] == document for row in assigned):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        visible, controls = _document_list_page(assigned, q=q, page=page, path="/settings/technical/exports")
        if document:
            visible = [row for row in assigned if row["snapshot_id"] == document]
            controls = '<p><a href="/settings/technical/exports">Alle documenten</a></p>'
        cards = []
        for row in visible:
            snapshot = _esc(quote(row["snapshot_id"], safe=""))
            opened = " open" if document else ""
            cards.append(f'''<details class="doc-card document-disclosure"{opened}>
              <summary>{_document_summary(row)}</summary>
              <ul class="export-options">
                <li>Bronpassages:
                  <a href="/review/passages-export?document={snapshot}&amp;format=csv">CSV</a> ·
                  <a href="/review/passages-export?document={snapshot}&amp;format=json">JSON</a></li>
                <li><a href="/review/processing-diagnostics?document={snapshot}">Diagnostiek (JSON)</a></li>
                <li><a href="/review/processing-diagnostics-detail?document={snapshot}">Detaildiagnostiek (JSON)</a></li>
                <li><a href="/review/processing-evidence-export?document={snapshot}">Download verwerkingsbewijs als CSV-pakket</a></li>
              </ul>
            </details>''')
        return _page(f'''{_nav(account, "settings", _counts(account))}
          <section class="room"><p><a href="/settings/technical">← Technisch beheer</a></p>
          <h1>Exports</h1>{controls}<div class="doc-list">
          {"".join(cards) or "<p>Geen documenten gevonden.</p>"}</div></section>''', title="Exports — Metis")

    @app.get("/settings/api-access", response_class=HTMLResponse)
    def settings_api_access(request: Request) -> str:
        account = _require(request)
        if access_store is None:
            reason = access_store_error or "API Access is nog niet geactiveerd voor deze omgeving."
            return _page(
                f"""
                {_nav(account, "settings", _counts(account))}
                <section class="room">
                  <p><a href="/settings/technical">← Terug naar Technisch beheer</a></p>
                  <p class="eyebrow">Instellingen · API Access</p>
                  <h1>API Access</h1>
                  <div class="banner warn">{_esc(reason)}</div>
                </section>
                """,
                title="API Access — Metis",
            )

        try:
            consumers = access_store.list_consumers()
        except ApiAccessStoreError:
            return HTMLResponse(
                _page(
                    f"""
                    {_nav(account, "settings", _counts(account))}
                    <section class="room">
                      <p><a href="/settings/technical">← Terug naar Technisch beheer</a></p>
                      <h1>API Access</h1>
                      <div class="banner err">De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.</div>
                    </section>
                    """,
                    title="API Access — Metis",
                ),
                status_code=503,
            )

        def _scope_boxes(name: str, selected: list[str]) -> str:
            chosen = set(selected or [])
            return "".join(
                f'<label class="check"><input type="checkbox" name="{_esc(name)}" value="{_esc(scope)}"'
                + (" checked" if scope in chosen else "")
                + f'> {_esc(scope)}</label>'
                for scope in sorted(VALID_SCOPES)
            )

        def _scope_option(current: str, value: str, label: str) -> str:
            selected = " selected" if current == value else ""
            return f'<option value="{value}"{selected}>{_esc(label)}</option>'

        cards = ""
        for row in consumers:
            credentials = row.get("credentials") or []
            credential_rows = "".join(
                f"""
                <div class="meta">
                  <span><b>{_esc(item.get("credential_id"))}</b></span>
                  <span>{_esc(item.get("state"))}</span>
                  {
                    f'<form method="post" action="/settings/api-access/tenants/{_esc(row.get("tenant_id"))}/applications/{_esc(row.get("application_id"))}/credentials/{_esc(item.get("credential_id"))}/revoke" style="display:inline"><button type="submit">Revoken</button></form>'
                    if "publisher" in account["roles"] and item.get("state") == "ACTIVE"
                    else ""
                  }
                </div>
                """
                for item in credentials
            ) or '<p class="muted">Geen credentials.</p>'

            publisher_controls = ""
            if "publisher" in account["roles"]:
                tenant_docs = "\n".join(row.get("tenant_document_ids") or [])
                app_docs = "\n".join(row.get("application_document_ids") or [])
                tenant_state_button = (
                    "SUSPEND"
                    if row.get("tenant_state") == "ACTIVE"
                    else "ACTIVATE"
                )
                app_state = str(row.get("application_state") or "")
                application_buttons = ""
                if app_state != "RETIRED":
                    app_toggle = "SUSPEND" if app_state == "ACTIVE" else "ACTIVATE"
                    application_buttons = f"""
                      <form method="post" action="/settings/api-access/tenants/{_esc(row.get("tenant_id"))}/applications/{_esc(row.get("application_id"))}/state">
                        <input type="hidden" name="expected_version" value="{int(row.get("application_policy_version") or 0)}">
                        <input type="hidden" name="target_state" value="{app_toggle}">
                        <button type="submit">{"Pauzeren" if app_toggle == "SUSPEND" else "Heractiveren"}</button>
                      </form>
                      <form method="post" action="/settings/api-access/tenants/{_esc(row.get("tenant_id"))}/applications/{_esc(row.get("application_id"))}/state">
                        <input type="hidden" name="expected_version" value="{int(row.get("application_policy_version") or 0)}">
                        <input type="hidden" name="target_state" value="RETIRE">
                        <button type="submit">Definitief retireren</button>
                      </form>
                    """

                publisher_controls = f"""
                  <details>
                    <summary>Klanttoegang wijzigen</summary>
                    <form method="post" action="/settings/api-access/tenants/{_esc(row.get("tenant_id"))}/policy" class="stack">
                      <input type="hidden" name="expected_version" value="{int(row.get("tenant_policy_version") or 0)}">
                      <label>Content scope</label>
                      <select name="content_scope">
                        {_scope_option(str(row.get("tenant_content_scope")), "ALL_PUBLISHED", "Alle gepubliceerde kennis")}
                        {_scope_option(str(row.get("tenant_content_scope")), "RESOURCE_SET", "Specifieke documenten")}
                      </select>
                      <label>Document-id's</label>
                      <textarea name="document_ids">{_esc(tenant_docs)}</textarea>
                      <fieldset><legend>Capabilities</legend>{_scope_boxes("scopes", row.get("tenant_scopes") or [])}</fieldset>
                      <label>Requests per minuut</label>
                      <input type="number" name="requests_per_minute" min="1" value="{int(row.get("tenant_requests_per_minute") or 1)}" required>
                      <label>Max top_k</label>
                      <input type="number" name="max_top_k" min="1" value="{int(row.get("tenant_max_top_k") or 1)}" required>
                      <button type="submit">Klanttoegang opslaan</button>
                    </form>
                    <form method="post" action="/settings/api-access/tenants/{_esc(row.get("tenant_id"))}/state">
                      <input type="hidden" name="expected_version" value="{int(row.get("tenant_policy_version") or 0)}">
                      <input type="hidden" name="target_state" value="{tenant_state_button}">
                      <button type="submit">{"Klant pauzeren" if tenant_state_button == "SUSPEND" else "Klant heractiveren"}</button>
                    </form>
                  </details>

                  <details>
                    <summary>Applicatietoegang wijzigen</summary>
                    <form method="post" action="/settings/api-access/tenants/{_esc(row.get("tenant_id"))}/applications/{_esc(row.get("application_id"))}/grant" class="stack">
                      <input type="hidden" name="expected_version" value="{int(row.get("application_policy_version") or 0)}">
                      <label>Content scope</label>
                      <select name="content_scope">
                        {_scope_option(str(row.get("application_content_scope")), "ALL_PUBLISHED", "Volledige klanttoegang")}
                        {_scope_option(str(row.get("application_content_scope")), "RESOURCE_SET", "Specifieke documenten")}
                      </select>
                      <label>Document-id's</label>
                      <textarea name="document_ids">{_esc(app_docs)}</textarea>
                      <fieldset><legend>Capabilities</legend>{_scope_boxes("scopes", row.get("application_scopes") or [])}</fieldset>
                      <label>Requests per minuut</label>
                      <input type="number" name="requests_per_minute" min="1" value="{int(row.get("application_requests_per_minute") or 1)}" required>
                      <label>Max top_k</label>
                      <input type="number" name="max_top_k" min="1" value="{int(row.get("application_max_top_k") or 1)}" required>
                      <button type="submit">Applicatietoegang opslaan</button>
                    </form>
                    <div class="actions">{application_buttons}</div>
                  </details>

                  <form method="post" action="/settings/api-access/tenants/{_esc(row.get("tenant_id"))}/applications/{_esc(row.get("application_id"))}/credentials">
                    <button type="submit"{" disabled" if app_state != "ACTIVE" or row.get("tenant_state") != "ACTIVE" else ""}>Nieuwe credential genereren</button>
                  </form>
                """

            cards += f"""
              <article class="doc-card">
                <p class="doc-title">{_esc(row.get("tenant_name"))} · {_esc(row.get("application_name"))}</p>
                <p class="meta">
                  <span>omgeving <b>{_esc(row.get("environment"))}</b></span>
                  <span>tenant <b>{_esc(row.get("tenant_state"))}</b> · v{int(row.get("tenant_policy_version") or 0)}</span>
                  <span>app <b>{_esc(row.get("application_state"))}</b> · v{int(row.get("application_policy_version") or 0)}</span>
                  <span>actieve credentials <b>{int(row.get("active_credentials") or 0)}</b></span>
                </p>
                {publisher_controls}
                <h4>Credentials</h4>
                {credential_rows}
              </article>
            """
        cards = cards or '<p class="muted">Nog geen API-consumers.</p>'

        form = ""
        if "publisher" in account["roles"]:
            scope_boxes = "".join(
                f'<label class="check"><input type="checkbox" name="application_scopes" value="{_esc(scope)}" checked> {_esc(scope)}</label>'
                for scope in sorted(VALID_SCOPES)
            )
            tenant_scope_boxes = "".join(
                f'<label class="check"><input type="checkbox" name="tenant_scopes" value="{_esc(scope)}" checked> {_esc(scope)}</label>'
                for scope in sorted(VALID_SCOPES)
            )
            form = f"""
              <form method="post" action="/settings/api-access/provision" class="stack">
                <div class="sections">
                  <div class="section">
                    <h3>Klant en maximale toegang</h3>
                    <label>Klantnaam</label>
                    <input name="tenant_name" required>
                    <label>Content scope</label>
                    <select name="tenant_content_scope">
                      <option value="ALL_PUBLISHED">Alle gepubliceerde kennis</option>
                      <option value="RESOURCE_SET">Specifieke documenten</option>
                    </select>
                    <label>Document-id's (één per regel, alleen bij specifieke documenten)</label>
                    <textarea name="tenant_document_ids"></textarea>
                    <fieldset><legend>Maximale API-capabilities</legend>{tenant_scope_boxes}</fieldset>
                    <label>Requests per minuut</label>
                    <input type="number" name="tenant_requests_per_minute" value="600" min="1" required>
                    <label>Max top_k</label>
                    <input type="number" name="tenant_max_top_k" value="20" min="1" required>
                  </div>
                  <div class="section">
                    <h3>Consumer-applicatie</h3>
                    <label>Naam</label>
                    <input name="application_name" required>
                    <label>Omgeving</label>
                    <input name="environment" value="PRODUCTION" required>
                    <label>Content scope</label>
                    <select name="application_content_scope">
                      <option value="ALL_PUBLISHED">Binnen de volledige klanttoegang</option>
                      <option value="RESOURCE_SET">Specifieke documenten</option>
                    </select>
                    <label>Document-id's (één per regel)</label>
                    <textarea name="application_document_ids"></textarea>
                    <fieldset><legend>API-capabilities</legend>{scope_boxes}</fieldset>
                    <label>Requests per minuut</label>
                    <input type="number" name="application_requests_per_minute" value="600" min="1" required>
                    <label>Max top_k</label>
                    <input type="number" name="application_max_top_k" value="20" min="1" required>
                    <button class="btn-primary" type="submit">Consumer aanmaken en key genereren</button>
                  </div>
                </div>
              </form>
            """

        return _page(
            f"""
            {_nav(account, "settings", _counts(account))}
            <section class="room">
              <p><a href="/settings/technical">← Terug naar Technisch beheer</a></p>
              <p class="eyebrow">Instellingen · API Access</p>
              <h1>API Access</h1>
              <p class="lead">Een credential identificeert een consumer-applicatie; tenant- en applicatiebeleid bepalen de effectieve toegang.</p>
              {form}
              <div class="doc-list">{cards}</div>
            </section>
            """,
            title="API Access — Metis",
        )

    @app.post("/settings/api-access/provision", response_class=HTMLResponse)
    def settings_api_access_provision(
        request: Request,
        tenant_name: str = Form(...),
        tenant_content_scope: str = Form(...),
        tenant_document_ids: str = Form(""),
        tenant_scopes: list[str] = Form(default=[]),
        tenant_requests_per_minute: int = Form(...),
        tenant_max_top_k: int = Form(...),
        application_name: str = Form(...),
        environment: str = Form(...),
        application_content_scope: str = Form(...),
        application_document_ids: str = Form(""),
        application_scopes: list[str] = Form(default=[]),
        application_requests_per_minute: int = Form(...),
        application_max_top_k: int = Form(...),
    ) -> HTMLResponse:
        account = _require(request)
        if "publisher" not in account["roles"]:
            raise ConsoleError("publisher_role_required")
        if access_store is None:
            return HTMLResponse(
                _page(
                    f"""
                    {_nav(account, "settings", _counts(account))}
                    <section class="room">
                      <h1>API Access</h1>
                      <div class="banner err">API Access is in deze omgeving niet beschikbaar. Er is niets gewijzigd.</div>
                    </section>
                    """
                ),
                status_code=503,
            )

        parse_ids = lambda raw: [part.strip() for line in raw.splitlines() for part in line.split(",") if part.strip()]
        try:
            result = access_store.provision_consumer(
                actor_id=str(account["account_id"]),
                tenant_name=tenant_name,
                tenant_content_scope=tenant_content_scope,
                tenant_document_ids=parse_ids(tenant_document_ids),
                tenant_scopes=tenant_scopes,
                tenant_requests_per_minute=tenant_requests_per_minute,
                tenant_max_top_k=tenant_max_top_k,
                application_name=application_name,
                environment=environment,
                application_content_scope=application_content_scope,
                application_document_ids=parse_ids(application_document_ids),
                application_scopes=application_scopes,
                application_requests_per_minute=application_requests_per_minute,
                application_max_top_k=application_max_top_k,
            )
        except ApiAccessError:
            return HTMLResponse(
                _page(
                    f"""
                    {_nav(account, "settings", _counts(account))}
                    <section class="room">
                      <h1>API Access</h1>
                      <div class="banner err">De toegang kon niet worden aangemaakt. Controleer de ingevulde grenzen en probeer opnieuw.</div>
                      <p><a href="/settings/api-access">Terug</a></p>
                    </section>
                    """
                ),
                status_code=400,
            )
        except ApiAccessStoreError:
            return HTMLResponse(
                _page(
                    f"""
                    {_nav(account, "settings", _counts(account))}
                    <section class="room">
                      <h1>API Access</h1>
                      <div class="banner err">De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.</div>
                    </section>
                    """
                ),
                status_code=503,
            )

        return HTMLResponse(
            _page(
                f"""
                {_nav(account, "settings", _counts(account))}
                <section class="room">
                  <p><a href="/settings/api-access">← Terug naar API Access</a></p>
                  <p class="eyebrow">Credential uitgegeven</p>
                  <h1>Bewaar deze API-key nu</h1>
                  <div class="banner warn">Deze plaintext key wordt na deze pagina niet opnieuw getoond.</div>
                  <article class="doc-card">
                    <p>Tenant <b>{_esc(result.tenant_id)}</b></p>
                    <p>Applicatie <b>{_esc(result.application_id)}</b></p>
                    <p>Credential <b>{_esc(result.credential_id)}</b></p>
                    <label>API-key</label>
                    <input value="{_esc(result.credential)}" readonly>
                  </article>
                </section>
                """,
                title="API-key uitgegeven — Metis",
            ),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    def _api_access_parse_ids(raw: str) -> list[str]:
        return [
            part.strip()
            for line in str(raw or "").splitlines()
            for part in line.split(",")
            if part.strip()
        ]

    def _api_access_publisher(request: Request) -> dict[str, Any]:
        account = _require(request)
        if "publisher" not in account["roles"]:
            raise ConsoleError("publisher_role_required")
        return account

    def _api_access_error_response(
        account: dict[str, Any],
        message: str,
        *,
        status_code: int,
    ) -> HTMLResponse:
        return HTMLResponse(
            _page(
                f"""
                {_nav(account, "settings", _counts(account))}
                <section class="room">
                  <p><a href="/settings/api-access">← Terug naar API Access</a></p>
                  <h1>API Access</h1>
                  <div class="banner err">{_esc(message)}</div>
                </section>
                """,
                title="API Access — Metis",
            ),
            status_code=status_code,
        )

    @app.post("/settings/api-access/tenants/{tenant_id}/policy")
    def settings_api_access_tenant_policy(
        tenant_id: str,
        request: Request,
        expected_version: int = Form(...),
        content_scope: str = Form(...),
        document_ids: str = Form(""),
        scopes: list[str] = Form(default=[]),
        requests_per_minute: int = Form(...),
        max_top_k: int = Form(...),
    ):
        account = _api_access_publisher(request)
        if access_store is None:
            return _api_access_error_response(account, "API Access is niet beschikbaar.", status_code=503)
        try:
            access_store.set_tenant_entitlement(
                actor_id=str(account["account_id"]),
                tenant_id=tenant_id,
                expected_version=expected_version,
                content_scope=content_scope,
                document_ids=_api_access_parse_ids(document_ids),
                scopes=scopes,
                requests_per_minute=requests_per_minute,
                max_top_k=max_top_k,
            )
        except ApiAccessConflict:
            return _api_access_error_response(
                account,
                "De klanttoegang is intussen gewijzigd. Herlaad de pagina en probeer opnieuw.",
                status_code=409,
            )
        except ApiAccessError:
            return _api_access_error_response(
                account,
                "De klanttoegang kan niet zo worden gewijzigd. Bestaande applicatiegrants moeten binnen de nieuwe grens blijven.",
                status_code=400,
            )
        except ApiAccessStoreError:
            return _api_access_error_response(account, "De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.", status_code=503)
        return RedirectResponse("/settings/api-access", status_code=303)

    @app.post("/settings/api-access/tenants/{tenant_id}/applications/{application_id}/grant")
    def settings_api_access_application_grant(
        tenant_id: str,
        application_id: str,
        request: Request,
        expected_version: int = Form(...),
        content_scope: str = Form(...),
        document_ids: str = Form(""),
        scopes: list[str] = Form(default=[]),
        requests_per_minute: int = Form(...),
        max_top_k: int = Form(...),
    ):
        account = _api_access_publisher(request)
        if access_store is None:
            return _api_access_error_response(account, "API Access is niet beschikbaar.", status_code=503)
        try:
            access_store.set_application_grant(
                actor_id=str(account["account_id"]),
                tenant_id=tenant_id,
                application_id=application_id,
                expected_version=expected_version,
                content_scope=content_scope,
                document_ids=_api_access_parse_ids(document_ids),
                scopes=scopes,
                requests_per_minute=requests_per_minute,
                max_top_k=max_top_k,
            )
        except ApiAccessConflict:
            return _api_access_error_response(
                account,
                "De applicatietoegang is intussen gewijzigd. Herlaad de pagina en probeer opnieuw.",
                status_code=409,
            )
        except ApiAccessError:
            return _api_access_error_response(
                account,
                "De applicatietoegang moet volledig binnen de klanttoegang blijven.",
                status_code=400,
            )
        except ApiAccessStoreError:
            return _api_access_error_response(account, "De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.", status_code=503)
        return RedirectResponse("/settings/api-access", status_code=303)

    @app.post("/settings/api-access/tenants/{tenant_id}/state")
    def settings_api_access_tenant_state(
        tenant_id: str,
        request: Request,
        expected_version: int = Form(...),
        target_state: str = Form(...),
    ):
        account = _api_access_publisher(request)
        if access_store is None:
            return _api_access_error_response(account, "API Access is niet beschikbaar.", status_code=503)
        target = {"SUSPEND": "SUSPENDED", "ACTIVATE": "ACTIVE"}.get(str(target_state).upper())
        if target is None:
            return _api_access_error_response(account, "Ongeldige tenanttransitie.", status_code=400)
        try:
            access_store.set_tenant_state(
                actor_id=str(account["account_id"]),
                tenant_id=tenant_id,
                expected_version=expected_version,
                target_state=target,
            )
        except ApiAccessConflict:
            return _api_access_error_response(account, "De tenant is intussen gewijzigd. Herlaad de pagina.", status_code=409)
        except ApiAccessError:
            return _api_access_error_response(account, "Deze tenanttransitie is niet toegestaan.", status_code=400)
        except ApiAccessStoreError:
            return _api_access_error_response(account, "De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.", status_code=503)
        return RedirectResponse("/settings/api-access", status_code=303)

    @app.post("/settings/api-access/tenants/{tenant_id}/applications/{application_id}/state")
    def settings_api_access_application_state(
        tenant_id: str,
        application_id: str,
        request: Request,
        expected_version: int = Form(...),
        target_state: str = Form(...),
    ):
        account = _api_access_publisher(request)
        if access_store is None:
            return _api_access_error_response(account, "API Access is niet beschikbaar.", status_code=503)
        target = {
            "SUSPEND": "SUSPENDED",
            "ACTIVATE": "ACTIVE",
            "RETIRE": "RETIRED",
        }.get(str(target_state).upper())
        if target is None:
            return _api_access_error_response(account, "Ongeldige applicatietransitie.", status_code=400)
        try:
            access_store.set_application_state(
                actor_id=str(account["account_id"]),
                tenant_id=tenant_id,
                application_id=application_id,
                expected_version=expected_version,
                target_state=target,
            )
        except ApiAccessConflict:
            return _api_access_error_response(account, "De applicatie is intussen gewijzigd. Herlaad de pagina.", status_code=409)
        except ApiAccessError:
            return _api_access_error_response(account, "Deze applicatietransitie is niet toegestaan.", status_code=400)
        except ApiAccessStoreError:
            return _api_access_error_response(account, "De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.", status_code=503)
        return RedirectResponse("/settings/api-access", status_code=303)

    @app.post("/settings/api-access/tenants/{tenant_id}/applications/{application_id}/credentials")
    def settings_api_access_issue_credential(
        tenant_id: str,
        application_id: str,
        request: Request,
    ):
        account = _api_access_publisher(request)
        if access_store is None:
            return _api_access_error_response(account, "API Access is niet beschikbaar.", status_code=503)
        try:
            result = access_store.issue_credential(
                actor_id=str(account["account_id"]),
                tenant_id=tenant_id,
                application_id=application_id,
            )
        except ApiAccessError:
            return _api_access_error_response(
                account,
                "Een nieuwe credential kan alleen voor een actieve tenant en actieve applicatie worden uitgegeven.",
                status_code=400,
            )
        except ApiAccessStoreError:
            return _api_access_error_response(account, "De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.", status_code=503)
        return HTMLResponse(
            _page(
                f"""
                {_nav(account, "settings", _counts(account))}
                <section class="room">
                  <p><a href="/settings/api-access">← Terug naar API Access</a></p>
                  <p class="eyebrow">Credential uitgegeven</p>
                  <h1>Bewaar deze API-key nu</h1>
                  <div class="banner warn">Deze plaintext key wordt na deze pagina niet opnieuw getoond.</div>
                  <article class="doc-card">
                    <p>Tenant <b>{_esc(result.tenant_id)}</b></p>
                    <p>Applicatie <b>{_esc(result.application_id)}</b></p>
                    <p>Credential <b>{_esc(result.credential_id)}</b></p>
                    <label>API-key</label>
                    <input value="{_esc(result.credential)}" readonly>
                  </article>
                </section>
                """,
                title="API-key uitgegeven — Metis",
            ),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @app.post("/settings/api-access/tenants/{tenant_id}/applications/{application_id}/credentials/{credential_id}/revoke")
    def settings_api_access_revoke_credential(
        tenant_id: str,
        application_id: str,
        credential_id: str,
        request: Request,
    ):
        account = _api_access_publisher(request)
        if access_store is None:
            return _api_access_error_response(account, "API Access is niet beschikbaar.", status_code=503)
        try:
            access_store.revoke_credential(
                actor_id=str(account["account_id"]),
                tenant_id=tenant_id,
                application_id=application_id,
                credential_id=credential_id,
            )
        except ApiAccessError:
            return _api_access_error_response(account, "Credential niet gevonden binnen deze tenant/applicatie.", status_code=404)
        except ApiAccessStoreError:
            return _api_access_error_response(account, "De API Access-opslag is niet bereikbaar. Er is niets gewijzigd.", status_code=503)
        return RedirectResponse("/settings/api-access", status_code=303)

    @app.get("/settings/llm", response_class=HTMLResponse)
    def settings_llm(request: Request) -> str:
        account = _require(request)
        provider = load_llm_provider_config()
        key_status = "Geconfigureerd" if provider.api_key else "Niet geconfigureerd"
        model = provider.model or "Niet geconfigureerd"
        return _page(
            f"""
            {_nav(account, "llm-settings", _counts(account))}
            <section class="room">
              <p><a href="/settings/technical">← Terug naar Technisch beheer</a></p>
              <p class="eyebrow">Instellingen · LLM</p>
              <h1>LLM-instellingen</h1>
              <p class="lead">Metis gebruikt één gedeelde deploymentconfiguratie voor alle toegestane LLM-capabilities.</p>
              <div class="doc-list">
                <article class="doc-card">
                  <p class="doc-title">Model</p>
                  <p><b>{_esc(model)}</b></p>
                </article>
                <article class="doc-card">
                  <p class="doc-title">API-key</p>
                  <p><b>{key_status}</b></p>
                  <p class="muted">De sleutel wordt nooit in de console getoond.</p>
                </article>
              </div>
              <div class="banner warn">Wijzigingen aan providercredential of model worden buiten de console als deploymentconfiguratie beheerd.</div>
            </section>
            """,
            title="LLM-instellingen — Metis",
        )

    @app.get("/over-console", response_class=HTMLResponse)
    def about_console(request: Request) -> str:
        account = _require(request)
        return _page(
            f"""
            {_nav(account, "about", _counts(account))}
            {render_metis_dictionary(_esc)}
            """,
            title="Metis uitgelegd — V&amp;VN Data Services",
        )

    @app.get("/login", response_class=HTMLResponse)
    def login_form() -> str:
        if entra is not None:
            return _page(f"""
                <section class="room login-card">{_login_brand()}
                <h1>Aanmelden bij Metis</h1>
                <p>Gebruik je werkaccount. Je organisatie bepaalt of je toegang hebt.</p>
                <a class="btn-primary" href="/auth/microsoft">Inloggen met Microsoft</a>
                <p>Je hebt geen apart Metis-wachtwoord nodig. Geen toegang? Neem contact op met je Metis-beheerder.</p>
                </section>""")
        return _page(
            f"""
            <section class="room login-card">
              {_login_brand()}
              <h1>Aanmelden</h1>
              <p class="lead">Interne account. Geen open registratie.</p>
              <form method="post" action="/login">
                <label for="gebruikersnaam">Gebruikersnaam</label>
                <input id="gebruikersnaam" name="username" autocomplete="username" required>
                <label for="wachtwoord">Wachtwoord</label>
                <input id="wachtwoord" type="password" name="password" autocomplete="current-password" required>
                <button class="btn-primary" type="submit">Aanmelden</button>
              </form>
            </section>
            """
        )

    @app.post("/login")
    def login(username: str = Form(...), password: str = Form(...)):
        if entra is not None:
            raise ConsoleError("entra_local_auth_disabled")
        login_key = str(username or "").strip()
        allowed, retry_after = login_limiter.allow(login_key, login_attempts_per_minute)
        if not allowed:
            body = _page(
                """
                <section class="room login-card">
                  <h1>Aanmelden tijdelijk begrensd</h1>
                  <div class="banner err">Te veel aanmeldpogingen. Probeer het later opnieuw.</div>
                  <p><a href="/login">Terug naar aanmelden</a></p>
                </section>
                """
            )
            return HTMLResponse(
                body,
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        session = state.authenticate(username, password)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE, session["token"], httponly=True, samesite="lax", secure=True)
        return response

    @app.post("/logout")
    def logout(request: Request) -> RedirectResponse:
        state.logout(request.cookies.get(COOKIE))
        destination = "/login"
        if entra is not None:
            from urllib.parse import urlencode
            destination = entra.config.authority + "/oauth2/v2.0/logout?" + urlencode({"post_logout_redirect_uri": entra.config.origin + "/login"})
        response = RedirectResponse(destination, status_code=303)
        response.delete_cookie(COOKIE, httponly=True, samesite="lax", secure=True)
        return response

    @app.get("/ingest", response_class=HTMLResponse)
    def ingest_get(request: Request) -> str:
        account = _require(request)
        reviewers = state.list_reviewer_accounts()
        options = "".join(
            f'<option value="{_esc(row["account_id"])}">{_esc(row["display_name"])} ({_esc(row["username"])})</option>'
            for row in reviewers
        )
        documents = state.list_envelopes()
        family_options = "".join(
            f'<option value="{_esc(family)}"></option>'
            for family in sorted({str(row.get("family") or "") for row in documents if row.get("family")}, key=str.casefold)
        )
        return _page(
            f"""
            {_nav(account, "ingest", _counts(account))}
            <section class="room">
              <h1>Document inleveren</h1>
              <p class="lead">Voeg een document toe voor beoordeling.</p>
              {_task_links("ingest")}
              <form method="post" action="/ingest" enctype="multipart/form-data">
                <input type="hidden" name="command_id" value="{uuid.uuid4().hex}">
                <div class="sections">
                  <div class="section">
                    <h3>Bron</h3>
                    <label for="file">Bronbestand (HTML, PDF of beslisboom)</label>
                    <input id="file" type="file" name="file" aria-describedby="filename-help">
                    <p id="filename-help" class="field-help">{_esc(FILENAME_HINT)}</p>
                    <label for="url">Of een link naar het PDF-bestand</label>
                    <input id="url" name="url" placeholder="https://...">
                  </div>
                  <div class="section">
                    <h3>Document</h3>
                    <div class="field-row">
                      <div>
                        <label for="title">Titel</label>
                        <input id="title" name="title" required>
                      </div>
                      <div>
                        <label for="version">Versienummer van het brondocument</label>
                        <input id="version" name="version" required pattern="[0-9]+(\\.[0-9]+)*" inputmode="numeric" placeholder="bijv. 2.13" autocomplete="off">
                        <p class="field-help">Alleen getallen met punten, bijvoorbeeld 1.0 of 2.13. Geen jaartal.</p>
                      </div>
                    </div>
                    <div class="field-row">
                      <div>
                        <label for="date">Publicatiedatum (colofon)</label>
                        <div class="date-nl-wrap">
                          <input id="date" name="date" type="date" required lang="nl" autocomplete="off">
                          <p class="date-nl-display" data-date-nl aria-live="polite">dd-mm-jjjj</p>
                        </div>
                        <p class="field-help">Datum uit het colofon / publicatiedatum, weergave dd-mm-jjjj. Leeg is niet toegestaan.</p>
                      </div>
                      <div>
                        <label for="class_">Documenttype</label>
                        <select id="class_" name="class_">{_class_options()}</select>
                      </div>
                    </div>
                    <label for="family">Onderwerp</label>
                    <input id="family" name="family" required autocomplete="off" list="family-options" placeholder="Kies bestaand of typ nieuw onderwerp">
                    <datalist id="family-options">{family_options}</datalist>

                    <label for="ingest_kind">Nieuw of nieuwe versie</label>
                    <select id="ingest_kind" name="ingest_kind">
                      <option value="new">Nieuw document</option>
                      <option value="new_version">Nieuwe versie van een bestaand document</option>
                    </select>
                    <div id="replaces-row" hidden>
                      <label for="replaces_document">Bestaand document</label>
                      <select id="replaces_document" name="replaces_document">{_document_options(documents)}</select>
                    </div>
                    <label for="live_url">Link naar de online bron (optioneel)</label>
                    <input id="live_url" name="live_url">
                  </div>
                  <div class="section">
                    <h3>Reviewers</h3>
                    <label for="review_mode">Reviewdeelname</label>
                    <select id="review_mode" name="review_mode">
                      <option value="legacy">Bestaande reviewregels</option>
                      <option value="single">Eén beoordelaar</option>
                      <option value="optional">Aanvullende beoordeling mogelijk</option>
                      <option value="required">Onafhankelijke aanvullende beoordeling verplicht</option>
                    </select>
                    <label for="primary_reviewer">Verantwoordelijke beoordelaar</label>
                    <select id="primary_reviewer" name="primary_reviewer"><option value="">Uploader</option>{options}</select>
                    <label for="source_status">Vaststellingsstatus volgens de bron</label>
                    <select id="source_status" name="source_status"><option value="unknown">Niet opgegeven</option><option value="established">Vastgesteld</option><option value="draft">Concept</option></select>
                    <label for="named_reviewers">Aanvullende beoordelaars</label>
                    <select id="named_reviewers" name="named_reviewers" multiple size="6">{options}</select>

                  </div>
                </div>
                <button class="btn-primary" type="submit" id="ingest-submit">Inleveren</button>
                <p id="ingest-status" role="status" aria-live="polite" aria-atomic="true" hidden></p>
              </form>
            </section>
            <script>
            (function () {{
              var button = document.getElementById("ingest-submit");
              var form = button.form;
              var status = document.getElementById("ingest-status");
              var submitting = false;
              form.addEventListener("submit", function (event) {{
                if (submitting) {{ event.preventDefault(); return; }}
                submitting = true;
                form.setAttribute("aria-busy", "true");
                button.disabled = true;
                button.textContent = "Bezig met inleveren…";
                status.hidden = false;
                status.textContent = "Je document wordt verzonden en verwerkt. Dit kan enkele minuten duren. Houd deze pagina open en lever het document niet opnieuw in. Deze pagina toont het resultaat zodra deze aanvraag is afgerond.";
              }});
              window.addEventListener("pageshow", function () {{
                submitting = false;
                form.removeAttribute("aria-busy");
                button.disabled = false;
                button.textContent = "Inleveren";
                status.hidden = true;
                status.textContent = "";
              }});
              var kind = document.getElementById("ingest_kind");
              var row = document.getElementById("replaces-row");
              function sync() {{ row.hidden = kind.value !== "new_version"; }}
              kind.addEventListener("change", sync);
              sync();
              var date = document.getElementById("date");
              var out = document.querySelector("[data-date-nl]");
              function showNl() {{
                if (!date || !out) return;
                if (!date.value) {{ out.textContent = "dd-mm-jjjj"; return; }}
                var parts = date.value.split("-");
                if (parts.length !== 3) {{ out.textContent = "dd-mm-jjjj"; return; }}
                out.textContent = parts[2] + "-" + parts[1] + "-" + parts[0];
              }}
              if (date) {{
                date.addEventListener("input", showNl);
                date.addEventListener("change", showNl);
                showNl();
              }}
            }})();
            </script>
            """
        )

    @app.post("/ingest", response_class=HTMLResponse)
    async def ingest_post(
        request: Request,
        ingest_kind: str = Form(...),
        title: str = Form(...),
        version: str = Form(...),
        date: str = Form(...),
        live_url: str = Form(""),
        class_: str = Form(...),
        family: str = Form(...),
        url: str = Form("") ,
        replaces_document: str = Form(""),
        named_reviewers: list[str] = Form(default=[]),
        review_mode: str = Form("legacy"),
        primary_reviewer: str = Form(""),
        source_status: str = Form("unknown"),
        command_id: str = Form(""),
        file: UploadFile | None = File(None),
    ) -> str:
        account = _require(request)
        filename = None
        data = None
        content_type = None
        if file is not None and file.filename:
            filename = file.filename
            data = await read_upload_limited(file)
            content_type = file.content_type
        if isinstance(named_reviewers, str):
            named_reviewers = [named_reviewers] if named_reviewers.strip() else []
        policy = None
        if review_mode != "legacy":
            if review_mode not in {"single", "optional", "required"}:
                raise ConsoleError("invalid_review_policy")
            primary = primary_reviewer.strip() or account["account_id"]
            extras = [i for i in named_reviewers if i != primary]
            if (review_mode == "single" and extras) or (review_mode == "required" and not extras):
                raise ConsoleError("invalid_review_assignment")
            from src.review_policy_v1 import CONTRACT
            policy = {"contract": CONTRACT, "revision": 1, "primary": primary,
                      "assignments": [{"reviewer_id": i, "participation": review_mode} for i in extras]}
        receipt = await asyncio.to_thread(
            state.ingest,
            actor_id=account["account_id"],
            filename=filename,
            data=data or None,
            content_type=content_type,
            url=url.strip() or None,
            ingest_kind=ingest_kind,
            title=title,
            version=version,
            date=date,
            live_url=live_url,
            class_=class_,
            family=family,
            named_reviewers=[] if policy else named_reviewers,
            review_policy=policy,
            source_status=source_status,
            command_id=command_id or None,
            replaces_snapshot_id=replaces_document.strip() or None,
        )
        graph_link = (f'<p><a href="/review/decision-graph?document={_esc(receipt["snapshot_id"])}">Controleer beslisroutes</a></p>'
                      if "decision_graph" in receipt else "")
        pre_review_blocked = receipt.get("publication_eligibility") == PRE_REVIEW_BLOCKED
        lead = (
            "Document opgeslagen. De verwerking is niet afgerond; beoordelen is nog niet beschikbaar."
            if pre_review_blocked else "Vastgelegd en klaar voor review."
        )
        next_actions = (
            '<p><a class="btn-primary" href="/tree">Document bekijken</a></p>'
            if pre_review_blocked else '<p><a class="btn-primary" href="/review">Naar review</a></p>'
        )
        processing_notice = _task_links("ingest")
        return _page(
            f"""
            {_nav(account, "ingest", _counts(account))}
            <section class="room">
              <h1>Document ingeleverd</h1>
              <p class="lead">{_esc(lead)}</p>
              <div class="doc-card">
                {_document_card_heading({**receipt, "status": receipt["state"]})}
              </div>
              {processing_notice}{next_actions}{graph_link}
            </section>
            """
        )

    @app.get("/tree", response_class=HTMLResponse)
    def tree(request: Request, q: str = "", page: int = 1) -> str:
        account = _require(request)
        can_move = "researcher" in account["roles"] or "publisher" in account["roles"]
        can_promote = "reviewer" in account["roles"]
        payload = state.family_tree()
        move_family_options = "".join(
            f'<option value="{_esc(family)}"></option>'
            for family in sorted(payload["families"], key=str.casefold)
        )
        visible, list_controls = _document_list_page(
            [child for node in payload["families"].values() for child in node["children"]],
            q=q, page=page, path="/tree",
        )
        visible_ids = {row["snapshot_id"] for row in visible}
        blocks: list[str] = []
        for family, node in payload["families"].items():
            cards = []
            for child in node["children"]:
                if child["snapshot_id"] not in visible_ids:
                    continue
                actions = []
                pre_review_notice = ""
                try:
                    mutable = not state.snapshot_is_published(child["snapshot_id"])
                except ConsoleError:
                    mutable = False
                if not mutable:
                    actions.append('<p class="muted">Voor deze versie zijn wijzigacties niet beschikbaar. Gepubliceerde versies blijven ongewijzigd.</p>')
                    if "researcher" in account["roles"]:
                        actions.append('<a class="btn-secondary" href="/ingest">Nieuwe bronversie inleveren</a>')
                if mutable and child.get("publication_eligibility") == PRE_REVIEW_BLOCKED:
                    pre_review_notice = '<p class="banner warn">Verwerking niet afgerond. Beoordelen is nog niet beschikbaar.</p>'
                if can_move and mutable:
                    actions.append(
                        f"""
                        <form method="post" action="/tree/move">
                          <input type="hidden" name="snapshot_id" value="{_esc(child["snapshot_id"])}">
                          <input type="hidden" name="title" value="{_esc(child["title"])}">
                          <input type="hidden" name="version" value="{_esc(child["version"])}">
                          <input type="hidden" name="family" value="{_esc(child["family"])}">
                          <label>Onderwerp
                            <input name="new_family" required list="move-family-options" placeholder="Kies bestaand of typ nieuw onderwerp" autocomplete="off">
                          </label>
                          <button class="btn-secondary" type="submit">Verplaatsen</button>
                        </form>
                        """
                    )
                if can_promote and mutable:
                    actions.append(
                        f"""
                        <form method="post" action="/tree/promote">
                          <input type="hidden" name="snapshot_id" value="{_esc(child["snapshot_id"])}">
                          <input type="hidden" name="title" value="{_esc(child["title"])}">
                          <input type="hidden" name="version" value="{_esc(child["version"])}">
                          <input type="hidden" name="family" value="{_esc(child["family"])}">
                          <label>Nieuwe klasse
                            <select name="new_class">{_class_options(child["class"])}</select>
                          </label>
                          <div class="klasse-wijzigen-consequence">
                            <p>De bron blijft ongewijzigd. Deze wijziging vereist een nieuwe beoordeling.
                            Bij een overstap van of naar een beslisboom wordt de bron opnieuw verwerkt.</p>
                          </div>
                          <label class="check">
                            <input type="checkbox" name="confirm" value="1">
                            <span>Ik bevestig de consequentie van Klasse wijzigen</span>
                          </label>
                          <button class="btn-secondary" type="submit">Klasse wijzigen</button>
                        </form>
                        """
                    )
                cards.append(
                    f"""
                    <details class="doc-card document-disclosure">
                      <summary>{_document_summary(child)}</summary>
                      {pre_review_notice}
                      <div class="doc-actions">{"".join(actions)}</div>
                      {_unpublished_delete_control(child, account=account, console=state, next_path="/tree", mutable=mutable)}
                    </details>
                    """
                )
            if not cards:
                continue
            blocks.append(
                f'<h2>Onderwerp {_esc(family)}</h2><div class="doc-list">{"".join(cards)}</div>'
            )
        empty = '<p class="muted">Nog geen documenten. Lever eerst een document in.</p>'
        return _page(
            f"""
            {_nav(account, "tree", _counts(account))}
            <section class="room">
              <h1>Documenten</h1>
              {_task_links("documents")}
              <datalist id="move-family-options">{move_family_options}</datalist>
              {list_controls}
              {"".join(blocks) or ('<p>Geen documenten gevonden.</p>' if q else empty)}
            </section>
            """,
            title="Documenten — V&amp;VN Data Services",
        )

    @app.post("/tree/processing-recovery")
    def tree_processing_recovery(request: Request, snapshot_id: str = Form(...), reason: str = Form(...)):
        account = _require(request)
        state.authorize_processing_recovery(actor_id=account["account_id"], snapshot_id=snapshot_id, reason=reason)
        return RedirectResponse("/settings/technical/processing?" + urlencode({"document": snapshot_id}), status_code=303)

    @app.get("/review/processing-diagnostic-replay", response_class=JSONResponse)
    def review_processing_diagnostic_replay(request: Request, document: str, attempt_id: str):
        account = _require(request)
        if "reviewer" not in set(account.get("roles") or []):
            raise ConsoleError("reviewer_role_required")
        envelope = state._envelope(document)
        if account["account_id"] not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        attempt = next((a for a in envelope.get("processing_attempts", []) if a["attempt_id"] == attempt_id), None)
        if attempt is None:
            raise ConsoleError("processing_attempt_not_active")
        from src.attempt_diagnostics_v1 import replay_diagnostic
        return JSONResponse(replay_diagnostic(attempt), headers={"Cache-Control": "no-store"})

    @app.post("/tree/reprocess")
    def tree_reprocess(
        request: Request,
        snapshot_id: str = Form(...),
        command_id: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        state.retry_pre_review(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            command_id=command_id or uuid.uuid4().hex,
        )
        return RedirectResponse(
            "/settings/technical/processing?" + urlencode({"document": snapshot_id}),
            status_code=303,
        )

    @app.post("/tree/move")
    def tree_move(
        request: Request,
        new_family: str = Form(...),
        snapshot_id: str = Form(""),
        title: str = Form(""),
        version: str = Form(""),
        family: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        if snapshot_id.strip():
            state.move_family(actor_id=account["account_id"], snapshot_id=snapshot_id, new_family=new_family)
        else:
            state.move_family_document(
                actor_id=account["account_id"],
                title=title,
                version=version,
                family=family,
                new_family=new_family,
            )
        return RedirectResponse("/tree", status_code=303)

    @app.post("/tree/promote")
    def tree_promote(
        request: Request,
        new_class: str = Form(...),
        snapshot_id: str = Form(""),
        title: str = Form(""),
        version: str = Form(""),
        family: str = Form(""),
        confirm: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        confirmed = str(confirm or "").strip().lower() in {"1", "on", "true", "yes", "ja"}
        if not confirmed:
            raise ConsoleError("class_change_confirmation_required")
        if snapshot_id.strip():
            current = next(
                (row for row in state.list_envelopes() if row["snapshot_id"] == snapshot_id),
                None,
            )
            if current is None:
                raise ConsoleError("unknown_snapshot")
            state.promote_class(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                new_class=new_class,
                reextract=is_cross_model_class_change(current["class"], new_class),
            )
        else:
            document = state.resolve_document(title=title, version=version, family=family)
            state.promote_class_document(
                actor_id=account["account_id"],
                title=title,
                version=version,
                family=family,
                new_class=new_class,
                reextract=is_cross_model_class_change(document["class"], new_class),
            )
        return RedirectResponse("/tree", status_code=303)

    @app.post("/documents/delete")
    def documents_delete(
        request: Request,
        snapshot_id: str = Form(...),
        confirm: str = Form(""),
        confirm_title: str = Form(""),
        next_path: str = Form("/tree", alias="next"),
        object_ids: list[str] = Form(default=[]),
    ) -> RedirectResponse:
        account = _require(request)
        chosen: list[str] = []
        if isinstance(object_ids, str):
            chosen = [object_ids] if object_ids.strip() else []
        elif object_ids:
            chosen = [str(item).strip() for item in object_ids if str(item).strip()]
        if chosen:
            raise ConsoleError("hide_selected_objects_forbidden")
        confirmed = str(confirm or "").strip().lower() in {"1", "on", "true", "yes", "ja"}
        state.delete_unpublished_snapshot(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            confirmed=confirmed,
            confirm_title=confirm_title,
        )
        target = (next_path or "").strip() or "/tree"
        if target not in ALLOWED_DELETE_NEXT:
            target = "/tree"
        return RedirectResponse(target, status_code=303)

    @app.get("/review", response_class=HTMLResponse)
    def review_get(request: Request, document: str = "", object: str = "", task: str = "") -> str:
        account = _require(request)
        return _render_review_room(
            state,
            account,
            html.escape(document, quote=True),
            html.escape(object, quote=True),
            task=html.escape(task, quote=True),
            counts=_counts(account),
        )

    @app.get("/review/passages-export")
    def review_passages_export(request: Request, document: str = "", format: str = "json") -> Response:
        account = _require(request)
        if "reviewer" not in set(account.get("roles") or []):
            raise ConsoleError("reviewer_role_required")
        snapshot_id = document.strip()
        envelope = state._envelope(snapshot_id)
        if account["account_id"] not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if format not in {"json", "csv"}:
            return JSONResponse({"error": "unsupported_export_format"}, status_code=400)
        objects, revision = state.snapshot_objects_and_revision(snapshot_id)
        rows = passage_export_rows(objects)
        filename = re.sub(r"[^A-Za-z0-9_-]", "_", snapshot_id)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}-passages.{format}"',
            "Cache-Control": "no-store",
        }
        if format == "csv":
            return Response(passage_export_csv(rows), media_type="text/csv", headers=headers)
        return JSONResponse({
            "schema_version": "passage-export-v1",
            "snapshot_id": snapshot_id,
            "document_id": str(envelope.get("document_id") or ""),
            "title": str(envelope.get("title") or ""),
            "version": str(envelope.get("version") or ""),
            "objects_revision": revision,
            "passage_count": len(rows),
            "rows": rows,
        }, headers=headers)

    @app.get("/review/processing-evidence-export")
    def review_processing_evidence_export(request: Request, document: str = "") -> Response:
        account = _require(request)
        if "reviewer" not in set(account.get("roles") or []):
            raise ConsoleError("reviewer_role_required")
        snapshot_id = document.strip()
        envelope = state._envelope(snapshot_id)
        if account["account_id"] not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        objects, revision = state.snapshot_objects_and_revision(snapshot_id)
        payload = processing_evidence_zip(snapshot_id=snapshot_id, revision=revision,
                                          envelope=envelope, objects=objects)
        filename = re.sub(r"[^A-Za-z0-9_-]", "_", snapshot_id)
        return Response(payload, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{filename}-processing-evidence.zip"',
            "Cache-Control": "no-store",
        })

    @app.get("/review/processing-diagnostics", response_class=JSONResponse)
    def review_processing_diagnostics(request: Request, document: str = "") -> JSONResponse:
        account = _require(request)
        if "reviewer" not in set(account.get("roles") or []):
            raise ConsoleError("reviewer_role_required")
        snapshot_id = document.strip()
        if not snapshot_id:
            raise ConsoleError("unknown_snapshot")
        envelope = state._envelope(snapshot_id)
        if account["account_id"] not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        objects = state.snapshot_objects(snapshot_id)
        pre_review_blocked = envelope.get("publication_eligibility") == PRE_REVIEW_BLOCKED
        processing = state.processing_status(snapshot_id, actor_id=account["account_id"])
        blocker = processing.get("error_code") or processing.get("reason_code") or str(envelope.get("processing_blocker") or "")
        blocker = blocker if blocker in ERROR_COPY else None
        payload = {
            "snapshot_id": snapshot_id,
            "document_id": str(envelope.get("document_id") or ""),
            "title": str(envelope.get("title") or ""),
            "version": str(envelope.get("version") or ""),
            "objects_revision": state.objects_revision(snapshot_id),
            "processing_attempts": envelope.get("processing_attempts", []),
            "processing_recovery": envelope.get("processing_recovery"),
            "processing": processing,
            "diagnostics": processing_diagnostics(objects),
            "pre_review": {
                "blocked": pre_review_blocked,
                "reason_code": blocker if pre_review_blocked else None,
                "message": (ERROR_COPY.get(blocker, "De voorcontrole is geblokkeerd; laat de beheerder de oorzaak onderzoeken.")
                            if pre_review_blocked else "Geen opgeslagen voorcontroleblokkade. Dit is geen bewijs van geslaagde verwerking."),
                "object_count": len(objects),
                "diagnostics_scope": "stored_objects_only",
                "note": "De kandidaattellers beschrijven alleen opgeslagen objecten. Nul kandidaten betekent niet dat de voorcontrole is geslaagd. Nieuwe herstelpogingen bewaren hun uitkomst, veilige foutcode en eventuele validatiereden en verwerkingsreferentie. Historische ontbrekende gegevens worden niet achteraf ingevuld.",
            },
        }
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})


    @app.get("/review/processing-diagnostics-detail", response_class=JSONResponse)
    def review_processing_diagnostics_detail(request: Request, document: str = "") -> JSONResponse:
        account = _require(request)
        if "reviewer" not in set(account.get("roles") or []):
            raise ConsoleError("reviewer_role_required")
        snapshot_id = document.strip()
        if not snapshot_id:
            raise ConsoleError("unknown_snapshot")
        envelope = state._envelope(snapshot_id)
        if account["account_id"] not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        objects = state.snapshot_objects(snapshot_id)
        payload = {
            "snapshot_id": snapshot_id,
            "document_id": str(envelope.get("document_id") or ""),
            "title": str(envelope.get("title") or ""),
            "version": str(envelope.get("version") or ""),
            "objects_revision": state.objects_revision(snapshot_id),
            "rows": processing_diagnostic_rows(objects),
        }
        return JSONResponse(payload)


    @app.get("/review/bronpassage", response_class=HTMLResponse)
    def review_bronpassage(request: Request, document: str = "", object: str = "", task: str = "") -> str:
        account = _require(request)
        chosen = document.strip()
        object_id = object.strip()
        safe_task = normalize_review_task(task)
        if not chosen or not object_id:
            raise ConsoleError("unknown_object")
        opened = state.open_source_passage(
            snapshot_id=chosen, object_id=object_id, include_document=True,
        )
        source_url = (
            f"/review/brondocument?document={quote(chosen, safe='')}"
            f"&amp;object={quote(object_id, safe='')}"
        )
        passage = researcher_visible_prose(opened.get("passage") or "")
        if opened["content_kind"] == "pdf":
            page, _ = parse_page_bbox(opened["locator_value"])
            document_html = (
                f'<p>De PDF opent op pagina {page}. Alle bronfragmenten van de geselecteerde passage zijn gemarkeerd.</p>'
                f'<object data="{source_url}#page={page}" type="application/pdf" '
                'style="width:100%;height:80vh" aria-label="Volledige richtlijn">'
                '<p>De PDF kan hier niet worden weergegeven. Gebruik de downloadlink hieronder.</p>'
                '</object>'
            )
        else:
            try:
                segments = full_document_segments(
                    opened["freeze_bytes"], opened["content_kind"],
                    opened.get("locators") or [{"locator_type": opened["locator_type"], "locator_value": opened["locator_value"]}],
                )
            except OpenOriginalError as exc:
                raise ConsoleError(exc.code) from exc
            found = any(selected and text.strip() for text, selected in segments)
            marked = "".join(
                '<mark class="broncontext-marked">' + _esc(text) + '</mark>'
                if selected else _esc(text)
                for text, selected in segments
            )
            warning = "" if found else (
                '<p class="muted">De geselecteerde passage staat hierboven; '
                'deze kon niet eenduidig in de volledige tekst worden gemarkeerd.</p>'
            )
            document_html = (
                '<p class="muted">Veilige tekstweergave van het volledige brondocument. Afbeeldingen en oorspronkelijke opmaak staan in de download.</p>' + warning + '<div class="full-source-text" style="white-space:pre-wrap">'
                + marked + '</div>'
            )
        return _page(
            f"""
            {_nav(account, "review", _counts(account))}
            <section class="room">
              <h1>Volledige richtlijn</h1>
              <p class="lead">Het vastgelegde origineel dat bij deze bronpassage hoort.</p>
              <article class="object">
                <h2>Geselecteerde bronpassage</h2>
                <p class="bronpassage-prose">{_esc(passage)}</p>
              </article>
              <section aria-label="Volledig brondocument" data-full-source>
                {document_html}
              </section>
              <p><a class="btn-secondary" href="{source_url}&amp;download=true">Download volledig origineel</a></p>
              <p><a class="btn-secondary" href="/review?document={_esc(chosen)}&amp;object={_esc(object_id)}{f'&amp;task={_esc(safe_task)}' if safe_task else ''}">Terug naar review</a></p>
            </section>
            """
        )

    @app.get("/review/brondocument")
    def review_brondocument(
        request: Request, document: str = "", object: str = "", download: bool = False,
    ) -> Response:
        _require(request)
        opened = state.open_source_passage(
            snapshot_id=document.strip(), object_id=object.strip(), include_document=True,
        )
        kind = opened["content_kind"]
        # Only PDF is displayed inline. Uploaded HTML is always an attachment;
        # the console displays an escaped, inert text projection instead.
        extension = {"pdf": "pdf", "html": "html", "boom": "json", "json": "json"}.get(kind, "txt")
        inline_pdf = kind == "pdf" and not download
        disposition = "inline" if inline_pdf else "attachment"
        display_bytes = opened["freeze_bytes"]
        if inline_pdf:
            import fitz

            # Highlight every contributing fragment on a disposable display
            # copy; the immutable source and original download are unchanged.
            locators = opened.get("locators") or [{"locator_value": opened["locator_value"]}]
            with fitz.open(stream=display_bytes, filetype="pdf") as pdf:
                for locator in locators:
                    page, bbox = parse_page_bbox(locator["locator_value"])
                    pdf_page = pdf[page - 1]
                    pdf_page.draw_rect(
                        fitz.Rect(bbox), color=(1, 0.55, 0), fill=(1, 1, 0),
                        fill_opacity=0.25, overlay=True,
                    )
                display_bytes = pdf.tobytes()
        return Response(
            display_bytes,
            media_type="application/pdf" if inline_pdf else "application/octet-stream",
            headers={
                "Content-Disposition": f'{disposition}; filename="richtlijn.{extension}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; frame-ancestors 'self'",
            },
        )

    @app.post("/review")
    def review_post(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        decision: str = Form(""),
        comment: str = Form(""),
        proposed_correction: str = Form(""),
        confirmed_object_type: str = Form(""),
        recommendation_strength: str = Form(""),
        recommendation_direction: str = Form(""),
        recommendation_strength_level: str = Form(""),
        relation_choice: list[str] = Form(default=[]),
        relation_review_ack: str = Form(""),
        suitability: str = Form(""),
        eindoordeel: str = Form(""),
        documentpositie_action: str = Form(""),
        found_under: str = Form(""),
        parent_choice: str = Form(""),
        type_action: str = Form(""),
        proposed_object_type: str = Form(""),
        snapshot_revision: str = Form(""),
        return_task: str = Form(""),
        interaction_id: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        mapped = map_eindoordeel(eindoordeel, decision)
        if eindoordeel == "later_beoordelen" or mapped == "later":
            mapped = "later"
        elif mapped not in {"approve", "revise", "reject"}:
            raise ConsoleError("invalid_review_decision")
        if mapped in {"revise", "reject"} and not comment.strip():
            raise ConsoleError("review_comment_required")
        if (suitability or "").strip() not in SUITABILITY_VALUES:
            raise ConsoleError("suitability_required")
        if type_action == "dit_klopt" and not confirmed_object_type.strip():
            confirmed_object_type = proposed_object_type
        current_rows = state.snapshot_objects(snapshot_id)
        focal = next(
            (row for row in current_rows if row.get("object_id") == object_id),
            None,
        )
        if focal is None:
            raise ConsoleError("unknown_object")
        review_path = review_path_for_klasse(state._envelope(snapshot_id)["class"])
        bindings = state.object_review_bindings(snapshot_id)
        duty = review_duty_for(
            focal,
            review_path=review_path,
            bindings=bindings,
        )
        evidence = (
            build_review_interaction_evidence(
                interaction_id=interaction_id,
                interaction_kind="contextual",
                reviewer_account_id=str(account["account_id"]),
                snapshot_id=snapshot_id,
                review_stage=str((duty or {}).get("stage") or "first_review"),
                focal=focal,
                objects=current_rows,
                review_path=review_path,
            )
            if interaction_id.strip() and mapped != "later"
            else None
        )
        try:
            state.review_object(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                object_id=object_id,
                decision=mapped,
                comment=comment,
                proposed_correction=proposed_correction,
                confirmed_object_type=confirmed_object_type.strip() or None,
                recommendation_strength=recommendation_strength.strip() or None,
                recommendation_direction=recommendation_direction.strip() or None,
                recommendation_strength_level=recommendation_strength_level.strip() or None,
                relation_choices=(
                    [relation_choice]
                    if isinstance(relation_choice, str)
                    else list(relation_choice or [])
                ),
                relation_review_ack=relation_review_ack == "1",
                suitability=suitability.strip() or None,
                eindoordeel=eindoordeel.strip() or None,
                documentpositie_action=documentpositie_action.strip() or None,
                found_under=found_under.strip() or None,
                parent_choice=parent_choice.strip() or None,
                type_action=type_action.strip() or None,
                expected_revision=snapshot_revision.strip() or None,
                interaction_evidence=evidence,
            )
        except ConsoleError as exc:
            semantic_error = exc.code in {
                "recommendation_direction_required",
                "recommendation_strength_confirmation_required",
                "recommendation_direction_evidence_missing",
                "recommendation_strength_evidence_required",
                "recommendation_strength_not_stated_conflict",
                "recommendation_semantics_confirmation_invalid",
            }
            if exc.code != SNAPSHOT_OBJECT_WRITE_CONFLICT and not semantic_error:
                raise
            # Render the same object set and revision that we compare here. A
            # second read could silently replace the posted revision after a
            # semantic validation error, hiding another reviewer's change.
            review_snapshot = state.snapshot_objects_and_revision(snapshot_id)
            if semantic_error and snapshot_revision.strip() and snapshot_revision.strip() != review_snapshot[1]:
                semantic_error = False
            if not semantic_error:
                state.refresh_objects_expected_revision(snapshot_id, review_snapshot[1])
            return HTMLResponse(
                _render_review_room(
                    state,
                    account,
                    snapshot_id,
                    object_id,
                    task=return_task,
                    counts=_counts(account),
                    draft={
                        "suitability": suitability,
                        "documentpositie_action": documentpositie_action,
                        "found_under": found_under,
                        "parent_choice": parent_choice,
                        "type_action": type_action,
                        "confirmed_object_type": confirmed_object_type,
                        "recommendation_strength": recommendation_strength,
                        "recommendation_direction": recommendation_direction,
                        "recommendation_strength_level": recommendation_strength_level,
                        "relation_choice": ([relation_choice] if isinstance(relation_choice, str) else list(relation_choice or [])),
                        "relation_review_ack": relation_review_ack,
                        "validation_error": exc.code if semantic_error else "",
                        "eindoordeel": eindoordeel,
                        "decision": decision,
                        "comment": comment,
                        "proposed_correction": proposed_correction,
                        "proposed_object_type": proposed_object_type,
                    },
                    conflict=not semantic_error,
                    snapshot=review_snapshot,
                ),
                status_code=400 if semantic_error else 409,
            )
        if mapped == "revise" and proposed_correction.strip():
            state.correct_object(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                object_id=object_id,
                patch={
                    "reason": comment or "reviewer correction",
                    "operations": [{"op": "set", "path": "content.clean_text", "value": proposed_correction.strip()}],
                },
            )
        safe_task = normalize_review_task(return_task)
        if safe_task in {"contextual", "structure", "batch", "second_review"}:
            current = state.snapshot_objects(snapshot_id)
            path = review_path_for_klasse(state._envelope(snapshot_id)["class"])
            bindings = state.object_review_bindings(snapshot_id)
            nxt = next(
                (
                    str(row.get("object_id") or "")
                    for row in current
                    if str(row.get("object_id") or "") != object_id
                    and (
                        route := reviewer_route_for(
                            row,
                            review_path=path,
                            reviewer_id=str(account.get("account_id") or ""),
                            bindings=bindings,
                        )
                    )
                    and route.get("actionable")
                    and route.get("canonical_task") == safe_task
                ),
                "",
            )
            if nxt:
                return RedirectResponse(
                    _review_location(
                        state,
                        snapshot_id,
                        nxt,
                        task=safe_task,
                    ),
                    status_code=303,
                )
            return RedirectResponse(
                _review_location(state, snapshot_id),
                status_code=303,
            )
        if not safe_task:
            nxt = state.next_review_object_id(snapshot_id, object_id)
            if nxt:
                return RedirectResponse(
                    _review_location(state, snapshot_id, nxt),
                    status_code=303,
                )
        return RedirectResponse(
            _review_location(state, snapshot_id, task=safe_task),
            status_code=303,
        )

    @app.post("/review/source-context")
    def review_source_context(request: Request, snapshot_id: str = Form(...), source_object_id: str = Form(...),
                              role: str = Form(...), target_object_ids: list[str] = Form(default=[]),
                              reason: str = Form(""), command_id: str = Form(""), snapshot_revision: str = Form(""),
                              source_checked: str = Form("")) -> RedirectResponse:
        account = _require(request)
        if source_checked != "1":
            raise ConsoleError("source_context_check_required")
        state.confirm_source_context(actor_id=account['account_id'], snapshot_id=snapshot_id,
            source_object_id=source_object_id, role=role, target_object_ids=target_object_ids,
            reason=reason, command_id=command_id, expected_revision=snapshot_revision)
        return RedirectResponse(_review_location(state, snapshot_id, source_object_id, task="inventory"), status_code=303)

    @app.post("/review/context/accept")
    def review_context_accept(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        snapshot_revision: str = Form(""),
        return_task: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        state.accept_source_continuation(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            expected_revision=snapshot_revision.strip() or None,
        )
        safe_task = normalize_review_task(return_task)
        return RedirectResponse(
            _review_location(
                state,
                snapshot_id,
                object_id,
                task=safe_task,
            ),
            status_code=303,
        )

    @app.post("/review/headings/batch-confirm")
    def review_headings_batch_confirm(
        request: Request,
        snapshot_id: str = Form(...),
        object_ids: list[str] = Form(default=[]),
        snapshot_revision: str = Form(""),
        interaction_id: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        raw = [object_ids] if isinstance(object_ids, str) else list(object_ids or [])
        try:
            current_rows = state.snapshot_objects(snapshot_id)
            by_id = {
                str(row.get("object_id") or ""): row
                for row in current_rows
            }
            members = [by_id[oid] for oid in raw if oid in by_id]
            evidence = (
                build_review_interaction_evidence(
                    interaction_id=interaction_id,
                    interaction_kind="structure",
                    reviewer_account_id=str(account["account_id"]),
                    snapshot_id=snapshot_id,
                    review_stage="first_review",
                    members=members,
                )
                if interaction_id.strip()
                else None
            )
            state.batch_confirm_headings(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                object_ids=raw,
                expected_revision=snapshot_revision.strip() or None,
                interaction_evidence=evidence,
            )
        except ConsoleError as exc:
            if exc.code != SNAPSHOT_OBJECT_WRITE_CONFLICT:
                raise
            return HTMLResponse(
                _render_review_room(
                    state,
                    account,
                    html.escape(snapshot_id, quote=True),
                    task="structure",
                    counts=_counts(account),
                    conflict=True,
                ),
                status_code=409,
            )
        return RedirectResponse(_review_location(state, snapshot_id, task="structure"), status_code=303)

    @app.post("/review/relations")
    def review_relations_post(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        relation: list[str] = Form(default=[]),
        parent_choice: str = Form(default=""),
        snapshot_revision: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        raw = [relation] if isinstance(relation, str) else list(relation or [])
        rows = []
        for item in raw:
            rel_type, sep, target = item.partition(":")
            if not sep or not rel_type or not target:
                raise ConsoleError("unknown_relation_type")
            rows.append({"relation_type": rel_type, "target_object_id": target})
        chosen_parent = (parent_choice or "").strip()
        if chosen_parent and chosen_parent != object_id:
            already = any(
                row.get("relation_type") == "child" and row.get("target_object_id") == chosen_parent
                for row in rows
            )
            if not already:
                rows.append({"relation_type": "child", "target_object_id": chosen_parent})
        state.confirm_relations(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            relations=rows,
            expected_revision=snapshot_revision.strip() or None,
        )
        return RedirectResponse(_review_location(state, snapshot_id, object_id), status_code=303)

    @app.post("/review/second-review")
    def second_review_post(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        snapshot_revision: str = Form(""),
        action: str = Form(...),
        comment: str = Form(""),
        interaction_id: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        current_rows = state.snapshot_objects(snapshot_id)
        focal = next(
            (row for row in current_rows if row.get("object_id") == object_id),
            None,
        )
        if focal is None:
            raise ConsoleError("unknown_object")
        review_path = review_path_for_klasse(state._envelope(snapshot_id)["class"])
        evidence = (
            build_review_interaction_evidence(
                interaction_id=interaction_id,
                interaction_kind="second_review",
                reviewer_account_id=str(account["account_id"]),
                snapshot_id=snapshot_id,
                review_stage="second_review",
                focal=focal,
                objects=current_rows,
                review_path=review_path,
            )
            if interaction_id.strip()
            else None
        )
        if action == "approve":
            state.approve_second_review(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                object_id=object_id,
                expected_revision=snapshot_revision.strip() or None,
                interaction_evidence=evidence,
            )
        elif action == "revise":
            if not comment.strip():
                raise ConsoleError("review_comment_required")
            state.review_object(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                object_id=object_id,
                decision="revise",
                comment=comment.strip(),
                expected_revision=snapshot_revision.strip() or None,
                interaction_evidence=evidence,
            )
        else:
            raise ConsoleError("invalid_review_decision")

        current = state.snapshot_objects(snapshot_id)
        review_path = review_path_for_klasse(state._envelope(snapshot_id)["class"])
        bindings = state.object_review_bindings(snapshot_id)
        nxt = next(
            (
                str(row.get("object_id") or "")
                for row in current
                if str(row.get("object_id") or "") != object_id
                and (
                    route := reviewer_route_for(
                        row,
                        review_path=review_path,
                        reviewer_id=str(account.get("account_id") or ""),
                        bindings=bindings,
                    )
                )
                and route.get("actionable")
                and route.get("canonical_task") == "second_review"
            ),
            "",
        )
        if nxt:
            return RedirectResponse(
                _review_location(state, snapshot_id, nxt, task="second_review"),
                status_code=303,
            )
        return RedirectResponse(
            _review_location(state, snapshot_id),
            status_code=303,
        )

    @app.get("/publish", response_class=HTMLResponse)
    def publish_get(request: Request) -> str:
        account = _require(request)
        rows = []
        for envelope in state.list_envelopes():
            considered = None
            try:
                considered = state.consider_publish(actor_id=account["account_id"], snapshot_id=envelope["snapshot_id"])
            except ConsoleError as exc:
                considered = {"blockers": [exc.code], "publish_allowed": False}
            blockers = considered.get("blockers") or []
            blocker_text = " ".join(BLOCKER_LABELS.get(code, code) for code in blockers) or "Geen extra blockers in deze kamer."
            if considered.get("state") == "published" or state.snapshot_is_published(envelope["snapshot_id"]):
                action = '<div class="banner ok">Gepubliceerd. Dit document staat in de publicatieprojectie.</div>'
            elif considered.get("publish_allowed"):
                count = int(considered.get("publishable_object_count") or 0)
                noun = "kennisobject" if count == 1 else "kennisobjecten"
                reviewed = "gereviewd" if count == 1 else "gereviewde"
                action = f'''
                  <div class="banner ok">Klaar voor publicatie: {count} {reviewed} {noun}. De bron en controles zijn geverifieerd.</div>
                  <form method="post" action="/publish" class="stack">
                    <input type="hidden" name="snapshot_id" value="{_esc(envelope['snapshot_id'])}">
                    <label class="check"><input type="checkbox" name="publish_confirmed" value="yes" required>
                      Ik bevestig publicatie van deze gereviewde kennisobjecten.</label>
                    <button type="submit">Publiceer document</button>
                  </form>
                '''
            else:
                action = f'<div class="banner warn">{_esc(blocker_text)}</div>'
            rows.append(
                f"""
                <article class="doc-card">
                  {_document_card_heading({**envelope, "status": envelope["state"]})}
                  {action}
                </article>
                """
            )
        success = ""
        if request.query_params.get("published") == "yes":
            success = '<div class="banner ok">Publicatie voltooid en zichtbaar gemaakt in de publicatieprojectie.</div>'
        return _page(
            f"""
            {_nav(account, "publish", _counts(account))}
            <section class="room">
              <h1>Publiceren</h1>
              <p class="lead">Neem hier het afzonderlijke publicatiebesluit. Alleen gereviewde kennisobjecten met een geverifieerde bron worden gepubliceerd; anders blijft publicatie geblokkeerd.</p>
              {success}
              <div class="doc-list">{"".join(rows) or '<p class="muted">Nog geen documenten.</p>'}</div>
            </section>
            """
        )

    @app.post("/publish")
    def publish_post(
        request: Request,
        snapshot_id: str = Form(...),
        publish_confirmed: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        if publish_confirmed != "yes":
            raise ConsoleError("publish_confirmation_required")
        result = state.publish(actor_id=account["account_id"], snapshot_id=snapshot_id)
        if result.get("status") != "PASS":
            blockers = result.get("blockers") or ["object_tuple_required"]
            raise ConsoleError(str(blockers[0]))
        return RedirectResponse("/publish?published=yes", status_code=303)

    @app.get("/accounts", response_class=HTMLResponse)
    def accounts_get(request: Request) -> str:
        account = _require(request)
        rows = []
        access_rows = entra.access_rows() if entra is not None else {}
        for public in sorted(state.list_accounts(), key=lambda item: item["username"]):
            role_boxes = "".join(
                f'<label class="check"><input type="checkbox" name="roles" value="{name}"'
                f'{" checked" if name in public["roles"] else ""}>{name}</label>'
                for name in ("researcher", "reviewer", "publisher")
            )
            role_form = ""
            if "publisher" in account["roles"] and entra is None:
                role_form = f"""
                  <form method="post" action="/accounts/roles">
                    <input type="hidden" name="account_id" value="{_esc(public["account_id"])}">
                    <p>Rollen wijzigen</p>
                    {role_boxes}
                    <button class="btn-secondary" type="submit">Rollen wijzigen</button>
                  </form>
                """
            if entra is not None:
                blocked = access_rows.get(public["account_id"], True)
                role_form = '<p>' + ('Geblokkeerd in Metis' if blocked else 'Microsoft-aanmelding vereist') + '</p>'
                if "publisher" in account["roles"] and public["account_id"] != account["account_id"]:
                    role_form += f"""<form method="post" action="/accounts/access">
                    <input type="hidden" name="account_id" value="{_esc(public['account_id'])}">
                    <input type="hidden" name="blocked" value="{'false' if blocked else 'true'}">
                    <button class="btn-secondary" type="submit">{'Blokkering opheffen' if blocked else 'Toegang direct blokkeren'}</button></form>"""
            if public.get("retirement"):
                role_form = '<p><b>Historisch account — aanmelden uitgeschakeld</b></p><p>Behouden voor eerdere beoordelingen en auditgegevens. Niet beschikbaar voor nieuwe reviewertoewijzingen.</p>'
            rows.append(
                f"""
                <article class="doc-card">
                  <p class="doc-title">{_esc(public["display_name"])}</p>
                  <p class="meta">
                    <span>{"Microsoft-werkaccount" if entra is not None else "gebruikersnaam " + _esc(public["username"])}</span>
                    <span>rollen <b>{", ".join(_esc(r) for r in public["roles"])}</b></span>
                  </p>
                  {role_form}
                </article>
                """
            )
        form = ""
        if "publisher" in account["roles"] and entra is None:
            form = """
              <form method="post" action="/accounts">
                <div class="sections">
                  <div class="section">
                    <h3>Nieuwe gebruiker</h3>
                    <label for="username">Gebruikersnaam</label>
                    <input id="username" name="username" required>
                    <label for="display_name">Weergavenaam</label>
                    <input id="display_name" name="display_name" required>
                    <label for="password">Wachtwoord</label>
                    <input id="password" type="password" name="password" required>
                    <label for="roles">Rol</label>
                    <select id="roles" name="roles">
                      <option value="researcher">researcher</option>
                      <option value="reviewer">reviewer</option>
                      <option value="publisher">publisher</option>
                    </select>
                    <button class="btn-primary" type="submit">Gebruiker aanmaken</button>
                  </div>
                </div>
              </form>
            """
        account_lead = (
            "Toegang en rollen worden toegekend in Microsoft Entra. Gebruikers verschijnen hier na hun eerste aanmelding. "
            "Een blokkering in Metis beëindigt hun toegang direct; opheffen geeft alleen toegang als Microsoft die nog toestaat. "
            "Rollen hieronder zijn laatst gecontroleerd bij aanmelding; Microsoft-toegang wordt na maximaal vijf minuten opnieuw gecontroleerd."
            if entra is not None else "Interne gebruikers. Alleen een publisher maakt accounts en wijzigt rollen."
        )
        return _page(
            f"""
            {_nav(account, "accounts", _counts(account))}
            <section class="room">
              <h1>Accounts</h1>
              <p class="lead">{account_lead}</p>
              {form}
              <div class="doc-list">{"".join(rows) or '<p class="muted">Nog geen accounts.</p>'}</div>
            </section>
            """
        )

    @app.post("/accounts", response_class=HTMLResponse)
    def accounts_post(
        request: Request,
        username: str = Form(...),
        display_name: str = Form(...),
        password: str = Form(...),
        roles: str = Form(...),
    ) -> HTMLResponse:
        account = _require(request)
        state.create_managed_account(
            actor_id=account["account_id"],
            username=username,
            display_name=display_name,
            password=password,
            roles=[item.strip() for item in roles.split(",") if item.strip()],
        )
        return RedirectResponse("/accounts", status_code=303)

    @app.post("/accounts/roles")
    def accounts_roles_post(
        request: Request,
        account_id: str = Form(...),
        roles: list[str] = Form(default=[]),
    ) -> RedirectResponse:
        account = _require(request)
        chosen: list[str] = []
        if isinstance(roles, str):
            chosen = [roles]
        elif roles:
            chosen = list(roles)
        if not chosen:
            raise ConsoleError("unknown_role")
        state.assign_roles(
            actor_id=account["account_id"],
            account_id=account_id,
            roles=chosen,
        )
        return RedirectResponse("/accounts", status_code=303)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "operations-console",
            "version": SERVICE_VERSION,
            "product_api": False,
            "chat_room": False,
            "nurse_frontend": False,
        }

    from src.quality_metrics_app_v1 import install_quality_routes
    install_quality_routes(app, state, _require, _page)
    from src.route_comparison_app_v1 import install_route_comparison_routes
    install_route_comparison_routes(app, state, _require, _page)
    from src.decision_review_ui_v1 import install_decision_review_routes
    install_decision_review_routes(app, state, _require, _page)
    from src.review_participation_ui_v1 import install_routes as install_participation_routes
    install_participation_routes(app, state, _require, _page)
    return app


def create_app() -> FastAPI:
    return create_console_app()
