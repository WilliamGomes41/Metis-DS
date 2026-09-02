# V&VN Data Services — Operationeel governance-record

**Status:** ondergeschikt aan `PROTOCOL.md`  
**Geldend protocol:** v2.22.0 (v2.2.0 + v2.3-delta + v2.4-delta + v2.5-delta + v2.6-delta + v2.7-delta + v2.8-delta + v2.9-delta + v2.10-delta + v2.11-delta + v2.12-delta + v2.13-delta + v2.15-delta + v2.16-delta + v2.17-delta + v2.18-delta + v2.19-delta + v2.20-delta + v2.21-delta + v2.22-delta)  
**Bijgewerkt:** 2026-09-03  
**Eigenaar:** projecteigenaar V&VN Data Services

## Plaats in de hiërarchie

Dit bestand is **geen vijfde stuurlaag**. De verplichte volgorde blijft:

`PROTOCOL.md → ROADMAP.md → acceptatietests → code`

Dit record maakt Protocol v2.2 §16 operationeel zichtbaar. Het voegt geen productregel, architectuurgrens, safety-invariant, verantwoordelijkheid of toegestane/verboden route toe. Bij conflict geldt `PROTOCOL.md` en de strengste fail-closed eis.

De statuskolom in `docs/PROTOCOL_V2_2.md` §16 is de stand **bij protocolgoedkeuring**. Latere eigenaarsbesluiten worden hier vastgelegd en wijzigen het protocolbestand niet. Dat is geen nieuwe protocolversie.

Machineleesbaar bewijs voor het enige tot nu toe vastgestelde besluit: [`data/assurance/gd_03_c3_c6_reviewer_matrix.json`](../data/assurance/gd_03_c3_c6_reviewer_matrix.json).

## Besluitenregister (Protocol v2.2 §16)

| ID | Besluit | Eigenaar | Vereiste specialistische inbreng | Deadline-gate | Status |
|---|---|---|---|---|---|
| GD-01 | Minimumomvang van de onafhankelijke holdout en vereiste high-risk-samenstelling | Projecteigenaar | Clinical governance en evaluation lead | Voordat Holdout B wordt gemaakt of aan het geëvalueerde team wordt getoond | OPEN |
| GD-02 | Statistische rapportagemethode en betrouwbaarheidsniveau voor FAR | Projecteigenaar | Evaluation/statistics reviewer | Voordat Holdout B-acceptatiecriteria worden bevroren | OPEN |
| GD-03 | Vereist aantal reviewers voor C3–C6-pull requests | Projecteigenaar | Technische en klinische governance | Voordat de volgende C3-, C4-, C5- of C6-wijziging wordt gemerged | ESTABLISHED |
| GD-04 | Maximale emergency-withdrawal-tijd en retrospectief break-glass-reviewinterval | Projecteigenaar | Clinical safety en operations | Voordat Azure DEV voor externe pilotgebruikers wordt geopend | OPEN |
| GD-05 | Ondersteunde API-depreciatieperiode | Projecteigenaar | Product/API-eigenaar | Voordat de eerste externe API-consument wordt onboarded | OPEN |
| GD-06 | Bewaartermijnen voor acquisitierecords, auditlogs, gebruikslogs en vertrouwelijk reviewbewijs | Projecteigenaar | Privacy, security en records management | Voordat Azure DEV extern pilotverkeer verwerkt | OPEN |
| GD-07 | Benoemde operationele eigenaar voor productiereleases en emergency withdrawal | Projecteigenaar | V&VN-service-eigenaarschap | Voordat een externe pilotrelease wordt geautoriseerd | OPEN |
| GD-08 | Verplicht inhoudelijk eigenaarschap en actualiteitsverantwoordelijkheid per bron en kennisfamilie | Projecteigenaar | Richtlijnorganisatie, records management en service-eigenaarschap | Voordat de eerste externe pilotrelease wordt geautoriseerd | OPEN |
| GD-09 | Voorwaarden waaronder reviewbewijs bij een nieuwe bronversie behouden mag blijven | Projecteigenaar | Clinical governance, richtlijnonderzoek en technical/evaluation | Voordat delta-review reviewtaken automatisch mag beperken | OPEN |
| GD-10 | Conflictstatussen, bronvoorrang, escalatie en fail-closed serving bij botsende bronnen | Projecteigenaar | Clinical governance, richtlijnmethodologie en product/API | Voordat meerdere bronnen dezelfde vraag in een extern pilotcorpus mogen beantwoorden | OPEN |
| GD-11 | Omvang, frequentie en blokkerende uitkomsten van end-to-end integriteitsreconciliatie | Projecteigenaar | Security/operations, technical en clinical safety | Voordat Azure DEV voor externe pilotgebruikers wordt geopend | OPEN |
| GD-12 | Minimale eisen voor trainingsdatasetmanifest, model-lineage, updates en withdrawal | Projecteigenaar | Licensing, legal/privacy, AI safety en technical | Voordat Metis-kennis voor modeltraining wordt geëxporteerd of gelicentieerd | OPEN |

OPEN-besluiten mogen niet als established of `PASS` worden behandeld. Een gemiste deadline-gate blijft `BLOCKED`. GD-08 tot en met GD-12 zijn roadmapwerk: zolang zij OPEN zijn voegen zij geen nieuw productgedrag toe en mogen zij niet als geïmplementeerd worden gepresenteerd.

## GD-03 — reviewervereisten C3–C6 (ESTABLISHED)

- **Besluit:** Required reviewer count for C3–C6 pull requests, as written.
- **Status:** ESTABLISHED
- **Besluitdatum:** 2026-08-27
- **Eigenaar:** projecteigenaar V&VN Data Services
- **Protocolbasis:** Protocol v2.2 §16; geen nieuwe protocolversie
- **Specialistische inbreng:** technische en klinische governance, vastgelegd als de matrix hieronder
- **Evidence:** dit bestand en `data/assurance/gd_03_c3_c6_reviewer_matrix.json`
- **Niet onderdeel van dit besluit:** naamgeving van individuele reviewers. Dat is een latere bezettingsstap en houdt GD-03 niet OPEN.

### Reviewermatrix

| Klasse | Minimum | Verplichte rollen |
|---|---:|---|
| C3 Canonical/review | 2 | clinical + technical |
| C4 Retrieval/answerability | 2 | evaluation + technical |
| C5 Publication/security | 2 | security/operations + technical |
| C6 Generation | 3 | clinical + technical + safety/evaluation |

### Verplichte voorwaarden

- Reviewers MUST onafhankelijk zijn van de auteur.
- Reviewers beoordelen dezelfde exacte commit of snapshot.
- AI, Grok Bot en Metis MUST NOT meetellen als vereiste C3–C6-reviewer, MUST NOT goedkeuren en MUST NOT publiceren.

PR #4 en PR #5 zijn C5-wijzigingen en vereisen nog retrospectieve onafhankelijke technical- en security/operations-review volgens deze matrix. Protocol v2.9.0 blijft een geldend C3-onderdeel (taakgerichte console-UX en V&VN digitale stylesheet). Protocol v2.10.0 blijft een geldend C5-onderdeel (identiteit/toegang spanning console-kamers/nav: Documentenhierarchie, wachttaak-badges, Accounts-kamer). Protocol v2.11.0 is een eigenaarsgoedgekeurde C3-protocoldelta (bron/review/publish / retrieve-safety: geüploade HTML-freeze, weigering van live URL-HTML, verplichte source locators, fail-closed Product API zonder locator) en heropent GD-03 niet. Protocol v2.12.0 is een eigenaarsgoedgekeurde C3-protocoldelta (retrieve-safety / answerability spanning review/publish-autorisatiebinding: objecttype, reviewtupel, atomaire projectie) en heropent GD-03 niet. Protocol v2.13.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning C5 four-eyes-autorisatie (retrieve-safety / answerability / knowledge model: atomaire objecten, per-type classificatie, gesloten relaties, high-risk four-eyes) en heropent GD-03 niet. Protocol v2.15.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning ingest-provenance-validatie (bron-datum/versie op ingest pagina 1; heading-voorstel als reviewbaan-voorwaarde; reviewlijst-snippet; type-gebaseerde reviewbanen) en heropent GD-03 niet. Protocol v2.16.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety (een rommelige reviewpagina beïnvloedt beoordeling) en heropent GD-03 niet. Protocol v2.17.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety (slogan-copy, via-negativa-help, raw-HTML-bronpassage en site-chrome als objecten beïnvloeden beoordeling) en heropent GD-03 niet. Protocol v2.18.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety (dubbele kaartzin, truncated-sentence split en identieke freeze-proza als extra objecten beïnvloeden beoordeling) en heropent GD-03 niet. Protocol v2.19.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety (duizenden unclassified/Inhoud-kaarten als onderzoeker-verplichte één-voor-één-plicht is vermoeidheid, geen assurance) en heropent GD-03 niet. Protocol v2.20.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety (PROTOCOL.md is wet voor iedere richtlijn, niet Continentie-only; unpublished captured snapshots MAGEN van de operations console worden verwijderd door een geautoriseerde operator) en heropent GD-03 niet. Protocol v2.21.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety (kennisobject-grenzen; G2-status MUST live evidence zijn, geen stale static JSON; geïsoleerde test/release; herstelbaarheid) en heropent GD-03 niet. Protocol v2.22.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety (volgende-implementatievolgorde na golf A: C daarna D daarna ZIP daarna B; geïsoleerde test/release; herstelbaarheid; ZIP opent publicatie niet) en heropent GD-03 niet. Dit is geen C5-heropening van four-eyes of publish. Benoemde reviewers blijven onbezet. Metis, de Implementation engineer en de Auditor MUST NOT als GD-03-reviewers meetellen.

## Rolgrenzen (reeds in het protocol; hier alleen zichtbaar gemaakt)

Protocol v2.2 §2: AI MAY mappings of metadata voorstellen; AI MUST NOT canonical knowledge goedkeuren of publiceren.

Operationele toedeling binnen die norm:

- **Grok Bot** implementeert code pas na `protocol → roadmap → tests`. Grok Bot is geen vereiste C3–C6-reviewer, keurt niet goed en publiceert niet.
- **Metis** is de V&VN DS-assistent voor protocol, governance en organisatie. Metis is geen vereiste C3–C6-reviewer, keurt niet goed en publiceert niet.

Deze toedeling wijzigt geen protocolverantwoordelijkheid.

## Wat dit record niet doet

- Geen Azure-provisioning, geen productgedrag, geen nieuwe agent.
- Geen sluiting van GD-01, GD-02, GD-04, GD-05, GD-06 of GD-07.
- Geen override van gate-status (`PASS` / `BLOCKED` / `FAIL` / `NOT_EVALUATED`).
