# V&VN Data Services — Actuele handoff

**Bijgewerkt:** 2026-08-26  
**Geldend protocol:** v2.3.0  
**Authoritative remote:** `WilliamGomes41/VENVN-DS`  
**Default branch:** `main`

## Actuele waarheid

- Protocol v2.3.0 is de normatieve baseline (v2.2.0 + v2.3-delta).
- Step 12C repository hardening is naar `main` gebracht.
- PR #4 (source integrity), #5 (PDF completeness), #6 (scoped HTML), #7 (stack/G0), #8 (ontwikkelhiërarchie) en #9 (v2.3-approval) zijn afgerond in **deze** repository. PR-nummers #92–#94 horen bij `quire-bind` en zijn geen DS-gates.
- De exacte officiële HTML-representatie van bron 2 is lokaal geverifieerd en deterministisch geëxtraheerd.
- Bron 1 en bron 2 blijven `BLOCKED` voor publicatie zolang immutable opslag, definitieve registratie en klinische review ontbreken.
- G0 Local Development is `PASS`. G0 Azure DEV blijft `BLOCKED`.
- G1 branch protection op `main` is nog niet afdwingbaar onder het huidige repositoryplan (`BLOCKED`).
- Phase 4B Reliability Observatory / UI-pause is **quire-bind**, niet V&VN Data Services. Die status is op 2026-08-25 ten onrechte in deze handoff gezet en is hier hersteld.

## Open governancepunt

GD-03 is nog niet formeel vastgesteld. Het operationele voorstel is:

| Klasse | Minimum | Verplichte rollen |
|---|---:|---|
| C3 | 2 | klinisch + technisch |
| C4 | 2 | evaluatie + technisch |
| C5 | 2 | security/operations + technisch |
| C6 | 3 | klinisch + technisch + safety/evaluatie |

Reviewers zijn onafhankelijk van de auteur en beoordelen dezelfde exacte commit of snapshot. PR #4 en PR #5 zijn C5-wijzigingen en vereisen retrospectieve onafhankelijke technische en security/operations-review.

## Technische reparatie 2026-08-26

Bestaande protocolregel (exact review snapshot + één canonical hash) was in `canonical_store.py` nog de pre-kernel, partiële hash. Dat is een bug t.o.v. de geldende norm, geen nieuwe productregel.

Tegelijk hersteld:

- CLI `serve` / `serve-api` zodat Docker-entrypoints bestaan.
- Inspection search gebruikt dezelfde answerability-gate als de Product API.
- CLI `audit-current` defaults wijzen naar fixtures, niet naar `output/`.

## Eerstvolgende taak

1. Deze herstel-PR mergen nadat CI groen is.
2. GD-03 formeel vaststellen en de evidence-URL registreren.
3. Branch protection op `main` aanzetten (G1) en afgeronde feature branches opruimen.
4. Exacte bron 2 duurzaam en immutable opslaan; daarna klinische review.
5. Holdout B onafhankelijk vergrendelen; geen tuning daarop.

Geen nieuwe C3–C6-wijziging wordt gemerged voordat punt 2 is afgerond, behalve reparaties die aantoonbaar een bestaande protocolregel herstellen.

## Hervattingsinstructie

Bij hervatting worden achtereenvolgens volledig gelezen:

1. `PROTOCOL.md` en de gekoppelde geldende protocolspecificatie;
2. `ROADMAP.md`;
3. `HANDOFF.md`;
4. de relevante acceptatie- en invarianttests;
5. pas daarna de implementatiecode.

Na iedere materiële merge wordt deze handoff in dezelfde PR bijgewerkt met: mergecommit, afgeronde gate, resterende blokkades, afwijkingen en één eerstvolgende concrete taak.
