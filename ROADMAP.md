# V&VN Data Services — Technische roadmap

## Functie

Deze roadmap bepaalt de uitvoeringsvolgorde van de geldende norm uit `PROTOCOL.md`. De roadmap mag het protocol niet afzwakken of stilzwijgend uitbreiden. `HANDOFF.md` bevat de actuele voortgang; deze roadmap bevat de geplande volgorde en stopvoorwaarden.

Quire-bind (UI, Reliability Observatory, discovery/adjudication) heeft een eigen roadmap. Die fasen horen niet in dit document.

## Niet-onderhandelbare doelen

- Fail-closed bronintegriteit en publicatie.
- Retrieval en answerability blijven gescheiden.
- Onafhankelijke no-answer-acceptatie richt zich op `FAR = 0%`.
- Holdout A wordt niet gebruikt voor tuning of een nieuwe onafhankelijkheidsclaim.
- Alleen actieve, gepubliceerde, entitled en herleidbare kennis mag een ondersteund resultaat vormen.
- Eén integrity-kernel is de hash-autoriteit voor review-snapshot, store-import en publicatiegate.

## Fasen naar MVP

### Fase 1 — Repository en governance-baseline

Status: grotendeels afgerond; governance-nazorg open.

- Private GitHub-repository als gezaghebbende remote.
- CI, repository-preflight en architectuur-invarianttests.
- Protocol v2.3.0 vastgesteld, inclusief G0 voor infrastructuur- en kostentransparantie.
- Ontwikkelhiërarchie en handoffdiscipline geborgd.
- Stackbaseline en machineleesbaar infrastructuurmanifest aanwezig.
- G0 Local Development: `PASS`; G0 Azure DEV: `BLOCKED` totdat open keuzes zijn opgelost.
- Integrity kernel als enige canonical-hash voor store én publication gate (herstel 2026-08-26).
- GD-03 reviewervereisten formeel vaststellen.
- Retrospectieve onafhankelijke review van de C5-wijzigingen in PR #4 en PR #5.
- G1: required CI op `main`, geen directe push.

Stopvoorwaarde: geen nieuwe C3-C6-merge zolang GD-03 niet formeel is vastgesteld en vereiste reviewevidence ontbreekt, behalve bugfixes van bestaande protocolregels.

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

Status: deels aanwezig (Product API + inspection); afronden na Fase 2–3.

- Product-API/RAG-laag uitsluitend voeden met `supported` evidence.
- Inspection en Product API gebruiken dezelfde answerability-gate.
- Abstention en reason codes zichtbaar maken.
- End-to-end validatie van query tot bronverwijzing.
- Logging en audittrail zonder vertrouwelijke bron- of reviewdata te lekken.
- Visuele bot/interface hoort in `quire-bind`, niet in deze pipeline-repo.

Stopvoorwaarde: geen generation/LLM in deze service; similarity is nooit answerability.

### Fase 5 — Azure DEV en operationele gereedheid

Status: `BLOCKED` onder G0 Azure DEV totdat toegang, eigenaarschap, kosten en platformbesluiten beschikbaar zijn.

- Infrastructuurmanifest per gekozen Azure-component afronden: provider/product, regio, data boundary, identity/secrets, eigenaar en kosten.
- Azure DEV inrichten met immutable bronopslag en gescheiden runtime-opslag.
- Deployment reproduceerbaar koppelen aan commit, protocolversie en build-ID.
- Security-, rollback-, withdrawal- en incidenttest uitvoeren.
- MVP-go/no-go assurance-record afronden.

Stopvoorwaarde: geen Azure-provisioning zolang G0 Azure DEV `BLOCKED` is.

## Scopebeheer

Nieuwe functionaliteit komt alleen in de roadmap nadat is vastgesteld dat deze door het huidige protocol wordt gedekt. Buiten scope voor de eerste MVP zijn uitbreidingen die de onafhankelijke acceptatie, bronintegriteit of fail-closed publicatie omzeilen of vertragen, en product-UI die in `quire-bind` thuishoort.
