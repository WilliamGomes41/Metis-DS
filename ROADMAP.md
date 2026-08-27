# V&VN Data Services — Technische roadmap

## Functie

Deze roadmap bepaalt de uitvoeringsvolgorde van de geldende norm uit `PROTOCOL.md`. De roadmap mag het protocol niet afzwakken of stilzwijgend uitbreiden. `HANDOFF.md` bevat de actuele voortgang; deze roadmap bevat de geplande volgorde en stopvoorwaarden.

Deze repository is uitsluitend V&VN Data Services. Status, fasen of UI van andere producten horen niet in dit document.

## Niet-onderhandelbare doelen

- Fail-closed bronintegriteit en publicatie.
- Retrieval en answerability blijven gescheiden.
- Onafhankelijke no-answer-acceptatie richt zich op `FAR = 0%`.
- Holdout A wordt niet gebruikt voor tuning of een nieuwe onafhankelijkheidsclaim.
- Alleen actieve, gepubliceerde, entitled en herleidbare kennis mag een ondersteund resultaat vormen.
- Eén integrity-kernel is de hash-autoriteit voor review-snapshot, store-import en publicatiegate.
- Het DS-MVP blijft beperkt tot U1 bronverwijzing en U2 kennisrespons.
- Technische toegang is nooit automatisch een licentie, V&VN-goedkeuring of toestemming voor modeltraining.

## Fasen naar MVP

### Fase 1 — Repository en governance-baseline

Status: grotendeels afgerond; governance-nazorg open.

- Gezaghebbende remote `WilliamGomes41/VENVN-DS`; tijdens de gedeclareerde MVP-periode MAG die public zijn (Protocol v2.5). Publiek is niet de latere productiestandaard.
- CI, repository-preflight en architectuur-invarianttests.
- Protocol v2.5.0 vastgesteld (v2.2 + v2.3-delta + v2.4-delta + v2.5-delta), inclusief G0, product-/distributiegrenzen en de MVP-uitzondering voor een publieke remote.
- Ontwikkelhiërarchie en handoffdiscipline geborgd.
- Stackbaseline en machineleesbaar infrastructuurmanifest aanwezig.
- G0 Local Development: `PASS`; G0 Azure DEV: `BLOCKED` totdat open keuzes zijn opgelost.
- Integrity kernel als enige canonical-hash voor store én publication gate (herstel 2026-08-26).
- GD-03 reviewervereisten ESTABLISHED (2026-08-27); evidence in `docs/GOVERNANCE.md`. Named reviewers blijven een latere bezettingsstap.
- Historische STEP-/audit-/repair-rapporten verplaatst naar `docs/history/` (2026-08-27); de root is het operationele oppervlak, geen vijfde stuurlaag.
- Retrospectieve onafhankelijke review van de C5-wijzigingen in PR #4, PR #5 en Protocol v2.5.
- G1 blijft `BLOCKED` totdat de remote public is en branch protection aanstaat: required CI `test (3.12)` en `test (3.13)`, PR verplicht, geen force-push, `main` niet verwijderbaar. Direct daarna volgt duurzame opslag van bron 2.

Stopvoorwaarde: C3–C6-merges vereisen de vastgestelde GD-03-matrix en onafhankelijke menselijke reviewers op dezelfde commit/snapshot; named reviewers zijn nog niet bezet. Bugfixes van bestaande protocolregels blijven toegestaan. Protocol v2.5 is een eigenaarsgoedgekeurde C5-delta met retrospectieve technical- en security/operations-review, hetzelfde patroon als PR #4 en PR #5; GD-03 blijft ESTABLISHED.

### Fase 2 — Canonieke bron 2

Status: technische acquisitie en extractie ontwikkeld; menselijke en duurzame opslagstappen open.

- Exacte officiële bronrepresentatie duurzaam en immutable opslaan.
- Source manifest voltooien en integriteit opnieuw verifiëren.
- Deterministische extractie en object-diff genereren.
- Klinische review uitvoeren op de exacte snapshot en afgeleide objecten.
- Alleen na alle gates goedkeuren en publiceren.

Stopvoorwaarde: ontbrekende bytes, checksum, immutable locator, provenance of review houdt publicatie `BLOCKED`.

### Fase 3 — Evaluatie en onafhankelijke acceptatie

Status: nog uit te voeren.

- Development set vastleggen zonder holdoutcontaminatie.
- Holdout B onafhankelijk ontwerpen, vergrendelen en hashen.
- Answerable en moeilijke no-answer-cases opnemen, inclusief relationele, numerieke, populatie- en versieconflicten.
- Onafhankelijke acceptatie uitvoeren zonder tuning op holdout B.
- Release alleen bij alle protocolgates en `FAR = 0%` binnen de afgesproken scope.

Stopvoorwaarde: geen onafhankelijkheidsclaim op basis van Holdout A of de development/golden set.

### Fase 4 — MVP-servicelaag

Status: deels aanwezig (Product API + interne inspection); afronden na Fase 2–3.

- Product API uitsluitend voeden met `supported` evidence.
- Inspection en Product API gebruiken dezelfde answerability-gate.
- Abstention en reason codes zichtbaar maken.
- End-to-end validatie van query tot bronverwijzing.
- Stabiele object-ID's, bronversie, status en canonical links leveren.
- API/schema versieerbaar maken en contracttests voor provenance en withdrawal toevoegen.
- Logging en audittrail zonder vertrouwelijke bron- of reviewdata te lekken.
- Geen product-frontend in deze repository. Inspection is intern en read-only.

Stopvoorwaarde: geen generation/LLM in deze service; similarity is nooit answerability; U3–U5 zijn buiten MVP.

### Fase 5 — Azure DEV en operationele gereedheid

Status: `BLOCKED` onder G0 Azure DEV totdat toegang, eigenaarschap, kosten en platformbesluiten beschikbaar zijn.

- Infrastructuurmanifest per gekozen Azure-component afronden: provider/product, regio, data boundary, identity/secrets, eigenaar en kosten.
- Azure DEV inrichten met immutable bronopslag en gescheiden runtime-opslag.
- Deployment reproduceerbaar koppelen aan commit, protocolversie en build-ID.
- Security-, rollback-, withdrawal- en incidenttest uitvoeren.
- MVP-go/no-go assurance-record afronden.

Stopvoorwaarde: geen Azure-provisioning zolang G0 Azure DEV `BLOCKED` is.

### Fase 6 — Externe integratiepilot

Status: gepland na PASS van toepasselijke bron-, acceptance- en operationele gates.

- Eén richtlijn of expliciet begrensde bronset.
- Eén U1- of U2-toepassing.
- Eén zorgorganisatie, één leverancier/ontwikkelpartner en één gebruikersgroep.
- Consumentenregistratie en gebruiksovereenkomst vastleggen.
- Attribution, updates, supersession, withdrawal en incidentmelding end-to-end testen.
- Vooraf veiligheids-, gebruiks- en stopcriteria vaststellen.

Stopvoorwaarde: geen externe toegang zonder juridische, privacy/security- en verantwoordelijkheidstoets; geen U3–U5 zonder nieuwe protocolbeslissing en toepasselijke C3–C6-review.

## Scopebeheer

Nieuwe functionaliteit komt alleen in de roadmap nadat is vastgesteld dat deze door het huidige protocol wordt gedekt. Buiten scope voor de eerste MVP zijn uitbreidingen die de onafhankelijke acceptatie, bronintegriteit of fail-closed publicatie omzeilen of vertragen, elke product-UI of ander product dat niet V&VN Data Services is, beslisregels, patiëntspecifiek advies en modeltraining.
