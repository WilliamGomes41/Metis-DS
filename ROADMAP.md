# V&VN Data Services — Technische roadmap

## Functie

Deze roadmap bepaalt de uitvoeringsvolgorde van de geldende norm uit `PROTOCOL.md`. De roadmap mag het protocol niet afzwakken of stilzwijgend uitbreiden. `HANDOFF.md` bevat de actuele voortgang; deze roadmap bevat de geplande volgorde en stopvoorwaarden.

## Niet-onderhandelbare doelen

- Fail-closed bronintegriteit en publicatie.
- Retrieval en answerability blijven gescheiden.
- Onafhankelijke no-answer-acceptatie richt zich op `FAR = 0%`.
- Holdout A wordt niet gebruikt voor tuning of een nieuwe onafhankelijkheidsclaim.
- Alleen actieve, gepubliceerde, entitled en herleidbare kennis mag een ondersteund resultaat vormen.

## Fasen naar MVP

### Fase 1 — Repository en governance-baseline

Status: grotendeels afgerond; governance-nazorg open.

- Private GitHub-repository als gezaghebbende remote.
- CI, repository-preflight en architectuur-invarianttests.
- Protocol v2.3.0 vastgesteld.
- Ontwikkelhiërarchie en handoffdiscipline geborgd.

### Fase 2 — Canonieke bron 2

Status: technische acquisitie en extractie ontwikkeld; menselijke en duurzame opslagstappen open.

- Exacte officiële bronrepresentatie duurzaam en immutable opslaan.
- Source manifest voltooien en integriteit opnieuw verifiëren.
- Klinische review uitvoeren op de exacte snapshot en afgeleide objecten.

### Fase 3 — Evaluatie en onafhankelijke acceptatie

Status: nog uit te voeren.

- Development set vastleggen zonder holdoutcontaminatie.
- Holdout B onafhankelijk ontwerpen, vergrendelen en hashen.
- Onafhankelijke acceptatie uitvoeren zonder tuning op holdout B.

### Fase 4 — MVP-servicelaag

#### Phase 4B — Reliability Observatory

Status: COMPLETE

Bereikt:

- Signal Monitor contract.
- Persistence/data model.
- User-scoped repository boundary.
- Bounded production signal capture.
- Acceptance validation.

Exitvoorwaarden zijn gehaald. Reliability observability is beschikbaar zonder autonome wijziging van gedrag.

#### Phase 4C — Discovery Queue + Human Adjudication

Status: NEXT PHASE — PAUSED

Phase 4C start pas nadat UI/layout en gebruikersinteractie zijn afgerond.

Execution order:

1. UI/layout en interactiemodellen afronden.
2. Gebruikersfeedback en presentatie van reliability-signalen valideren.
3. Daarna Phase 4C Discovery Queue en Human Adjudication implementeren.

## Scopebeheer

Nieuwe functionaliteit komt alleen in de roadmap nadat is vastgesteld dat deze door het huidige protocol wordt gedekt. Buiten scope voor de eerste MVP zijn uitbreidingen die de onafhankelijke acceptatie, bronintegriteit of fail-closed publicatie omzeilen of vertragen.
