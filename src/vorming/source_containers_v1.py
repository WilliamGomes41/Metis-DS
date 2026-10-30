"""Typed revision containers and exact source usage, derived from one durable bundle.

No approval or serving authority lives here. Legacy source records keep their
old human-disposition policy. New records may account for narrowly recognized
document information and validated, current target context.
"""
import re
from src.request_diagnostics_v1 import diagnostic_phase

from src.vorming.source_accountability_v1 import evidence_of, is_source_record, CONTAINERS_VERSION
from src.vorming.source_bound_fields_v2 import context_matches_target, CONTEXT_KEY
from src.review.review_disposition_v1 import definitive_review_disposition

VERSION = "source-containers-v2"
SOURCE_VERSION = CONTAINERS_VERSION


def metadata_reason(text):
    """Closed whole-range rules; never exclude by chapter location alone."""
    text = text.strip()
    if re.fullmatch(r"Versie\s*:\s*\d+(?:\.\d+)*", text, re.I):
        return "document_metadata"
    if re.fullmatch(r"Datum\s*:\s*(?:\d{1,2}\s+)?(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+\d{4}", text, re.I):
        return "document_metadata"
    if re.fullmatch(r"[^\n]{1,160}\.{8,}\s*\d{1,4}", text):
        return "navigation"
    # A page footer requires the complete document label, edition indication,
    # month/year and terminal page. A word such as 'richtlijn' is insufficient.
    if re.fullmatch(r"(?:Concept)?richtlijn\s+[^\n]{1,100}\s+[–-]\s+commentaarronde\s+[a-z]+\s+20\d{2}\s+\d{1,3}", text, re.I):
        return "page_furniture"
    return None


_TOC_TITLES = (
    "Aanbevelingen", "Achtergrond", "Uitgangsvraag", "Inleiding", "Samenvatting", "Verantwoording",
    "Literatuursamenvatting", "Literatuurconclusies", "Zoeken en selecteren", "Overwegingen",
    "Van bewijs naar aanbeveling (overwegingen)", "Van bewijs naar aanbeveling", "Rationale",
    "Implementatietabel", "Kennisvragen", "Verder onderzoek", "Referenties", "Bijlagen",
)

# Person name: capitalised name parts or initials, Dutch particles, hyphenated
# double names; no sentence punctuation, so "Jansen. Gebruik ..." is not a name.
_PERSON_NAME = (r"(?:[A-ZÀ-Ý]\.\s?|[A-ZÀ-Ý][a-zà-ÿ'’]+)"
                r"(?:(?:\s?-\s?|\s)(?:[A-ZÀ-Ý]\.|[A-ZÀ-Ý][a-zà-ÿ'’]+|van|de|der|den|ten|ter|het|in|'t)){0,6}")


# Role: a profession from a closed list, optionally "in/bij een/de <work setting>"
# from a closed list. Advice in this field ("adviseert dagelijks zinkzalf") never fits.
_PROFESSIONS = (
    "Verpleegkundig specialist", "Verpleegkundige", "Wondconsulent", "Wondconsultent", "Verzorgende IG",
    "Verzorgende", "Specialist Ouderengeneeskunde", "Arts-microbioloog", "Dermatoloog", "Huisarts",
    "Ergotherapeut", "Fysiotherapeut", "Diëtist", "Apotheker", "Arts", "Onderzoeker", "Adviseur",
    "Beleidsmedewerker", "Patiëntvertegenwoordiger", "Ervaringsdeskundige",
)
_SETTINGS = (
    "ziekenhuis", "verpleeghuis", "verzorgingshuis", "thuiszorg", "wijkverpleging", "huisartsenpraktijk",
    "intra- en extramurale zorg", "intramurale zorg", "extramurale zorg", "gehandicaptenzorg", "ggz",
    "revalidatiecentrum", "eerste lijn", "tweede lijn", "langdurige zorg",
)
_ROLE = (r"(?i:" + "|".join(re.escape(p) for p in _PROFESSIONS) + r")"
         r"(?:\s(?:in|bij)\s(?:een|de|het)\s(?i:" + "|".join(re.escape(x) for x in _SETTINGS) + r"))?")

# Bibliographic tail of a reference: a title-cased journal name, its volume with an
# optional issue and pages, and a mandatory DOI link ("Blad , 12(3), 1-9.
# https://doi.org/…"). Without a DOI the passage stays human work.
_JOURNAL = (r"[A-Z0-9=(][^\s,]*(?:(?:\s|,\s(?=[A-Z]))(?:[A-Z0-9(&:=\-][^\s,]*"
            r"|of|and|the|de|du|des|la|le|voor|en|for|in|on|van|der|und|y|et|\u202f:))*")
_LOCATOR = (r"\s?[,.]\s?\d{1,4}(?:\sSuppl\s\d+)?\s?(?:\(\s?[\w–-]{1,12}(?:\s\d+)?\s?\))?"
            r"(?:,\s?[A-Za-z]?\d+(?:\s?[-–]\s?[A-Za-z]?\d+)?)?\s?\.?\shttps?://doi\.org/10\.\d{4,9}/\S+?[.,]?")

# Organisation: V&VN with an optional department, or a society from a closed list.
_VVN_DEPARTMENTS = (
    "Wondexpertise", "Geriatrie & Gerontologie", "Verpleegkundig Specialisten", "Verzorgenden",
    "Oncologie", "Dermatologie", "Wijkverpleging", "Kinderverpleegkunde", "Praktijkverpleegkundigen",
)
_SOCIETIES = (
    "Nederlandse Vereniging voor Dermatologie en Venerologie", "Ergotherapie Nederland (EN)",
    "Ergotherapie Nederland", "Verenso", "Nederlandse Vereniging Medische Microbiologie (NVMM)",
    "Nederlands Huisartsen Genootschap", "Koninklijk Nederlands Genootschap voor Fysiotherapie",
    "Nederlandse Vereniging van Diëtisten", "Patiëntenfederatie Nederland", "ActiZ", "Zorgthuisnl",
)
_ORGANISATION = (r"(?:V&VN(?:\s(?:" + "|".join(re.escape(x) for x in _VVN_DEPARTMENTS) + r"))?|"
                 + "|".join(re.escape(x) for x in _SOCIETIES) + r")")

# B6 (#933): closed whole-range rules for source accountability only. They never
# change formation planning, which keeps using metadata_reason.
_ACCOUNTING_RULES = (
    # Table-of-contents line: a dot leader after a heading from a closed list of
    # guideline section titles (or "Module/Hoofdstuk/Bijlage N: title"), optionally
    # behind the draft footer, or a bare leader tail with a page number. Free text
    # before a leader stays human work, however long the leader is.
    (re.compile(r"(?:(?:Concept)?richtlijn\s+[^\n.:;!?]{1,100}\s+[–-]\s+commentaarronde\s+[a-z]+\s+20\d{2}\s+)?"
                r"(?:" + "|".join(re.escape(title) for title in _TOC_TITLES)
                + r"|(?:Module|Hoofdstuk|Bijlage)\s+\d{1,2}(?::\s[^\n.:;!?]{1,120}?)?)"
                r"\s+(?:\.\s?){8,}\s*\d{0,4}|(?:\.\s?){2,}\s*\d{1,4}", re.I), "navigation"),
    (re.compile(r"(?:Concept)?richtlijn\s+[^\n.:;!?]{1,100}\s+[–-]\s+commentaarronde\s+[a-z]+\s+20\d{2}(?:\s+\d{1,3})?", re.I),
     "page_furniture"),
    # Bibliographic reference(s): a strict author list, "(2021)." or "(n.d.).", a
    # one-sentence title (no ". ", "? ", "! " or "; " inside), and the
    # journal tail above. Several complete references may follow each other.
    (re.compile(r"(?:\(PDF\)\s*)?" + (ref := r"(?:" + (author := r"(?:[a-z]{1,4}\s){0,3}[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]*(?:\s?-\s?[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]*)?"
                                     r"(?:\s[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]*){0,2},\s(?:[A-Z]\.\s?(?:-\s?[A-Z]\.\s?)?){1,5}")
                + r"(?:,\s" + author + r"){0,30}(?:,?\s(?:&|and|en)\s" + author + r")?(?:,?\set al\.)?"
                r"\s?\((?:(?:19|20)\d{2}[a-z]?|n\.d\.)\)\.\s(?:(?![.?!;]\s)[^\n])+?\.\s?" + _JOURNAL + _LOCATOR + r")")
                + r"(?:\s" + ref + r")*"), "document_metadata"),
    # "Bronnen: (Surname et al., 2022; Surname & Surname, 2019)": in-text citations only.
    (re.compile(r"Bronnen?\s*:\s*\(" + (cite := r"(?:[a-z]{1,4}\s){0,3}[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]+"
                r"(?:\s(?:et al\.|(?:&|en)\s(?:[a-z]{1,4}\s){0,3}[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]+))?,\s(?:19|20)\d{2}[a-z]?")
                + r"(?:;\s" + cite + r")*\)\.?"), "document_metadata"),
    (re.compile(r"Zie\s+bijlage\s+\d+(?:\.\d+)*\.?", re.I), "navigation"),
    # Working-group roster line: "Mw. Name, role, namens Organisation", each field
    # closed (person name, listed profession, listed organisation); nothing may follow.
    (re.compile(r"[·•\-]?\s*(?:Mw|Dhr|Mevr)\.\s+" + _PERSON_NAME + r"\s?,\s" + _ROLE + r"\s?,\s+namens\s+"
                r"(?:de\s+)?" + _ORGANISATION),
     "document_metadata"),
)


def accounting_reason(text):
    """Machine reason for source accountability; whole range only, never location."""
    reason = metadata_reason(text)
    if reason:
        return reason
    text = text.strip()
    return next((reason for rule, reason in _ACCOUNTING_RULES if rule.fullmatch(text)), None)


def _covers(ref, spans):
    cursor = ref["start"]
    for s in sorted((s for s in spans if s["block_id"] == ref["block_id"]), key=lambda s:s["start"]):
        if s["start"] > cursor:
            break
        cursor = max(cursor, s["end"])
    return cursor >= ref["end"]


def bound_context_valid(obj, *, fragments=None):
    """Intrinsic context evidence, shared by full validation and card preparation."""
    from src.review.review_card_facts_v1 import ReviewFactSources
    if isinstance(fragments, ReviewFactSources):
        return fragments.proof_for(obj)['bound_context']
    from src.review.knowledge_path_v1 import spans_are_exact
    from src.vorming.source_bound_fields_v2 import validated_context, CONTEXT_ROLES, CONTEXT_REASONS
    raw = (obj.get('metadata') or {}).get(CONTEXT_KEY)
    if raw is None:
        return True
    if not isinstance(raw, dict):
        return False
    try:
        valid = context_matches_target(obj)
        entries = raw.get('entries')
        valid = valid and all(isinstance(entry, dict)
            and set(entry) == {'role', 'span', 'unresolved_reason', 'text', 'source_mapping', 'source_refs'}
            and entry['role'] in CONTEXT_ROLES
            and entry['unresolved_reason'] in (None, *CONTEXT_REASONS)
            and isinstance(entry['text'], str)
            and isinstance(entry['source_mapping'], list)
            and isinstance(entry['source_refs'], list)
            and (spans_are_exact([entry['span']]) or
                 (entry['span'] is None and entry['unresolved_reason'] is not None))
            for entry in entries or [])
        if valid and fragments is not None:
            validated_context(obj, fragments, (obj.get('source') or {}).get('source_checksum'))
        return valid
    except (KeyError, TypeError, ValueError):
        return False


@diagnostic_phase('source_accountability')
def source_accountability(objects, *, review_path="richtlijn", bindings=None, fragments=None):
    """One read-only source role/closure/action projection for a current bundle.

    Existing evidence owns state. Missing review inputs never prove target
    approval. Structure QA and content ReviewDuty remain separate authorities.
    """
    from src.vorming.admission_gate_v1 import admission_of, is_boom_object
    from src.review.knowledge_path_v1 import content_reviewable, source_lineage_resolves, spans_are_exact
    from src.operations_console_v1 import review_lane
    from src.review.review_duty_v1 import review_duty_for, review_stage, exact_current_approver_ids
    from src.review.source_context_review_v1 import context_issues, role_of, links_of, verify_literal_source

    objects = list(objects)
    bindings = tuple(bindings or ())
    from src.review.review_card_facts_v1 import preserve_review_sources as preserve_fragments, ReviewFactSources
    fragments = preserve_fragments(fragments) if fragments is not None else None
    conflicts = context_issues(objects)
    targets = []

    def target_state(target):
        oid = str(target.get("object_id") or "")
        if oid in conflicts:
            return "invalid"
        if (target.get("governance") or {}).get("validation_status") in {"rejected", "superseded", "revise"}:
            return "retired"
        if not content_reviewable(target):
            return "invalid"
        if fragments is not None and not source_lineage_resolves(target, fragments=fragments):
            return "invalid"
        admission = admission_of(target)
        source = target.get("source") or {}
        if (admission.get("source_hash") and admission["source_hash"] != source.get("source_checksum")
                or admission.get("document_version") and admission["document_version"] != source.get("version")):
            return "invalid"
        if (fragments is not None and exact_current_approver_ids(target, bindings)
                and review_stage(target, review_path=review_path, bindings=bindings, fragments=fragments) is None):
            return "approved"
        return "pending"

    for target in objects:
        if is_source_record(target) or is_boom_object(target):
            continue
        raw = (target.get("metadata") or {}).get(CONTEXT_KEY)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            conflicts.setdefault(str(target.get("object_id") or ""), []).append("source_bound_context_invalid")
            continue
        valid = bound_context_valid(target, fragments=fragments)
        if not valid:
            conflicts.setdefault(str(target.get("object_id") or ""), []).append("source_bound_context_invalid")
        state = target_state(target) if valid else "invalid"
        entries = raw.get("entries")
        for row in entries if isinstance(entries, list) else []:
            if (isinstance(row, dict) and spans_are_exact([row.get("span")])
                    and not row.get("unresolved_reason")):
                targets.append((target, row["span"], state))

    from src.vorming.knowledge_materialisation_v1 import _read_source_blocks
    source_blocks = None
    result = {}
    for obj in objects:
        oid = str(obj.get("object_id") or "")
        if not oid:
            continue
        source_record = is_source_record(obj)
        disposition = definitive_review_disposition(obj)
        row = {"role": "unresolved", "closure": "open", "human_action": "source_disposition",
               "reason": disposition["outcome"], "target_ids": [], "kind": "unresolved",
               "accounted": False, "required": obj.get("object_type") != "document"}
        def finish(role, closure, action, reason, kind=None):
            row.update(role=role, closure=closure, human_action=action, reason=reason,
                       kind=kind or role, accounted=closure == "accounted")
            result[oid] = row

        if obj.get("object_type") == "document":
            row["required"] = False
            finish("structure", "accounted", "none", "document")
            continue
        evidence = evidence_of(obj) if source_record else {}
        invalid_source = source_record and (not evidence or not spans_are_exact(evidence.get("spans")))
        if source_record and not invalid_source and fragments is not None:
            try:
                # This projection never mutates fragments: read the full-source
                # view once instead of comparing the whole input per record.
                if source_blocks is None and not isinstance(fragments, ReviewFactSources):
                    source_blocks = _read_source_blocks(fragments, include_headings=True)
                invalid_source = not verify_literal_source(obj, fragments, (obj.get("source") or {}).get("source_checksum"),
                                                           source_blocks=source_blocks)
            except (AttributeError, KeyError, TypeError, ValueError):
                invalid_source = True
        if oid in conflicts or invalid_source:
            finish("invalid_evidence", "repair_required", "technical_repair",
                   (conflicts.get(oid) or ["source_accountability_invalid"])[0])
            continue
        # An explicit role applies regardless of candidate origin. A final
        # source-role decision does not approve its current targets.
        role = role_of(obj)
        if role.get("role") in {"label", "context"}:
            linked_targets = [target for target in objects
                              if any(link.get("source_object_id") == oid for link in links_of(target))]
            row["target_ids"] = sorted(target["object_id"] for target in linked_targets)
            states = [target_state(target) for target in linked_targets]
            if not states or "invalid" in states:
                finish("invalid_evidence", "repair_required", "technical_repair", "source_context_stale")
            elif "retired" in states:
                finish("unresolved", "open", "source_disposition", "source_context_target_retired")
            else:
                finish("linked_context", "accounted" if all(s == "approved" for s in states) else "waiting_on_target",
                       "none", "confirmed_source_context")
            continue

        if not source_record:
            # Preserve the existing boom/legacy passage closure contract. T10
            # does not reinterpret decision-tree construction or review duties.
            if review_lane(obj) == "fast":
                row["required"] = False
                finish("structure", "accounted", "none", "structure")
            elif content_reviewable(obj) and target_state(obj) == "invalid":
                finish("invalid_evidence", "repair_required", "technical_repair", "knowledge_source_invalid")
            elif disposition["final"]:
                finish("knowledge_source" if content_reviewable(obj) else "explicitly_accounted",
                       "accounted", "none", disposition["outcome"], "reviewed")
            elif content_reviewable(obj):
                if fragments is not None and not source_lineage_resolves(obj, fragments=fragments):
                    finish("invalid_evidence", "repair_required", "technical_repair", "source_lineage_incomplete")
                else:
                    finish("knowledge_source", "waiting_on_target", "none", "knowledge_review")
            elif review_duty_for(obj, review_path=review_path, bindings=bindings, fragments=fragments):
                finish("knowledge_source", "waiting_on_target", "none", "knowledge_review")
            elif (admission_of(obj).get("gate_result") == "blocked"
                  and (review_path != "boom" or (obj.get("metadata") or {}).get("decision_unit_construction"))):
                finish("unresolved", "repair_required", "technical_repair", "admission_blocked")
            else:
                finish("unresolved", "open", "source_disposition", disposition["outcome"])
            continue

        if evidence["version"] != SOURCE_VERSION:
            if disposition["final"]:
                finish("explicitly_accounted", "accounted", "none", disposition["outcome"], "reviewed")
            else:
                finish("unresolved", "open", "source_disposition", "legacy_source_policy")
            continue

        if disposition["final"]:
            finish("explicitly_accounted", "accounted", "none", disposition["outcome"], "reviewed")
            continue

        spans = evidence["spans"]
        linked = [(target, span, state) for target, span, state in targets
                  if obj.get("source", {}).get("source_checksum")
                  and target.get("source", {}).get("source_checksum") == obj.get("source", {}).get("source_checksum")
                  and any(span["block_id"] == s["block_id"]
                          and max(span["start"], s["start"]) < min(span["end"], s["end"]) for s in spans)]
        row["target_ids"] = sorted({target["object_id"] for target, _, _ in linked})
        manual = role or (obj.get("metadata", {}).get("passage_register") or {}).get("source") == "review"
        if isinstance(fragments, ReviewFactSources):
            machine_reason = fragments.proof_for(obj)['metadata_reason'] if not manual else None
        else:
            machine_reason = accounting_reason(evidence["text"]) if not manual else None
        if machine_reason:
            finish("navigation" if machine_reason == "navigation" else "document_information",
                   "accounted", "none", machine_reason, "document_information")
        elif not manual and any(state == "invalid" for _, _, state in linked):
            finish("invalid_evidence", "repair_required", "technical_repair", "source_context_stale")
        elif not manual and all(_covers(s, [span for _, span, state in linked
                                          if state in {"pending", "approved"}]) for s in spans):
            closed = all(_covers(s, [span for _, span, state in linked if state == "approved"]) for s in spans)
            finish("linked_context", "accounted" if closed else "waiting_on_target", "none", evidence["reason"])
        else:
            finish("unresolved", "open", "source_disposition", evidence["reason"])
    return result


def source_closure(projection):
    """Compatibility summary of a source-domain decision, with no new policy."""
    required = [oid for oid, row in projection.items() if row["required"]]
    unresolved = [oid for oid in required if projection[oid]["closure"] != "accounted"]
    return {
        "source_passage_review_complete": not unresolved,
        "review_required_source_passage_ids": required,
        "review_required_source_passage_count": len(required),
        "unresolved_source_passage_ids": unresolved,
        "unresolved_source_passage_count": len(unresolved),
    }


def source_usage(objects, *, review_path="richtlijn", bindings=None, fragments=None, projection=None):
    """Existing source-only view over the central accountability projection."""
    objects = list(objects)
    if projection is None:
        projection = source_accountability(objects, review_path=review_path, bindings=bindings, fragments=fragments)
    return {obj["object_id"]: {key: projection[obj["object_id"]][key]
            for key in ("kind", "reason", "target_ids", "accounted", "role", "closure", "human_action")}
            for obj in objects if is_source_record(obj) and obj.get("object_id") in projection}


def partition(objects, *, review_path="richtlijn", bindings=None, fragments=None, projection=None):
    """Separate access contracts over the same atomic storage bundle."""
    objects = list(objects)
    usage = source_usage(objects, review_path=review_path, bindings=bindings, fragments=fragments, projection=projection)
    knowledge, source, structure = [], [], []
    for obj in objects:
        if is_source_record(obj):
            source.append({"record": obj, "usage": usage[obj["object_id"]]})
        elif obj.get("object_type") in {"document", "heading"}:
            structure.append(obj)
        else:
            knowledge.append(obj)
    return {"version": VERSION, "knowledge": knowledge, "source": source, "structure": structure}
