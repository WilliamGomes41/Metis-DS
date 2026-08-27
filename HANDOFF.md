# V&VN Data Services — Actuele handoff

**Bijgewerkt:** 2026-08-28  
**Geldend protocol:** v2.6.0  
**Authoritative remote:** `WilliamGomes41/VENVN-DS` (public during the declared MVP period)  
**Default branch:** `main`

## Actuele waarheid

- Deze repository is **alleen** V&VN Data Services: protocol, bronintegriteit, pipeline, publicatiegates, retrieval, Product API en — als goedgekeurde scope, niet als code — een interne operations console. Andere producten horen hier niet in governance of code.
- Protocol v2.6.0 is de normatieve baseline (v2.2.0 + v2.3-delta + v2.4-delta + v2.5-delta + v2.6-delta) en is live als scope. Het checksumgebonden approval-manifest staat in `data/assurance/protocol_v2_6_approval.json`. De console is niet geïmplementeerd; deze delta claimt geen bestaande UI.
- De gezaghebbende remote `WilliamGomes41/VENVN-DS` is public (`isPrivate: false`) onder de v2.5-MVP-uitzondering. Publiek is niet de latere productiestandaard; na de MVP MUST een nieuw plan private hosting of een organisatieplan herstellen.
- V&VN DS is vastgelegd als gevalideerde kennisobjecten, Product API, interne read-only inspection, en een interne operations console (v2.6, goedgekeurd-niet-gebouwd) als menselijk oppervlak over de knowledge kernel. Een zorgapp-frontend, chatbot, EPD/ECD-UI en publieke website blijven verboden. Chat hoort niet in de console.
- Het MVP is beperkt tot U1 bronverwijzing en U2 kennisrespons; U3 beslisregels, U4 patiëntspecifiek advies en U5 voorspellende/getrainde modellen zijn buiten scope.
- Extern gebruik vereist een consumentenregistratie, gebruiksovereenkomst, expliciete verantwoordelijkheden en geteste update/withdrawal-verwerking.
- PR #4 (source integrity), #5 (PDF completeness), #6 (scoped HTML), #7 (stack/G0), #8 (ontwikkelhiërarchie), #9 (v2.3-approval), #10 (integrity-kernel + runtime-entrypoints), #11 (repositoryscope), #12 (v2.4 product/distributie), #13 (v2.4-approval-evidence), #14 (GD-03 ESTABLISHED) en #16 (v2.5 MVP public-remote exception) zijn afgerond. PR #16 is squash-merged als `73c0669c8ad7c62a836e7a39666f3db33644be68` op 2026-08-27T22:10:04Z.
- Operationeel governance-record: `docs/GOVERNANCE.md` (ondergeschikt aan `PROTOCOL.md`, geen vijfde stuurlaag) met machineleesbaar GD-03-artefact `data/assurance/gd_03_c3_c6_reviewer_matrix.json`.
- GD-03 is ESTABLISHED (2026-08-27) as written: C3 min. 2 clinical+technical; C4 min. 2 evaluation+technical; C5 min. 2 security/operations+technical; C6 min. 3 clinical+technical+safety/evaluation. Reviewers onafhankelijk van de auteur; dezelfde exacte commit/snapshot. AI / Grok Bot / Metis / Implementation engineer / Auditor tellen niet mee als vereiste reviewer, keuren niet goed en publiceren niet. Het GD-03-governance-record blijft ESTABLISHED; dat record is geen nieuwe protocolversie. Benoemde GD-03-reviewers zijn niet bezet. GD-03 wordt niet heropend.
- Protocol v2.6 is een C5-wijziging (identiteit/toegang) die C3 (review/publish-loop) omvat. Benoemde C5-reviewers zijn nog niet bezet. De projecteigenaar keurde de delta goed. Retrospectieve onafhankelijke technical- en security/operations-review van PR #4, PR #5, PR #16 en deze v2.6-delta blijft verschuldigd. Er worden geen reviewers verzonnen.
- Repository-indeling (C0, 2026-08-27): historische STEP-/audit-/repair-rapporten staan in `docs/history/`. De root is het operationele oppervlak (`PROTOCOL.md`, `ROADMAP.md`, `HANDOFF.md`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md` plus code/config/build). Dit voegt geen vijfde stuurlaag toe. `output/` blijft als overgangsartefacten staan; tests gebruiken `data/fixtures/`.
- Fail-closed blijft ongewijzigd: geen bronbinaries in Git, geen secrets/keys/certs, `config/tenants.v1.json` blijft leeg, vertrouwelijke reviewartefacten blijven buiten Git, runtime-databases blijven buiten Git. `.gitignore` dekt dit en blijft staan. Fixtures, holdouts en getrackte `output/`-historie MAGEN in de publieke MVP-repo blijven; canonieke bron-HTML/PDF MAGEN dat niet.
- De exacte officiële HTML-representatie van bron 2 is lokaal geverifieerd en deterministisch geëxtraheerd.
- Bron 1 en bron 2 blijven `BLOCKED` voor publicatie zolang immutable opslag, definitieve registratie en klinische review ontbreken. Bron 2 is nog BLOCKED op duurzame immutable opslag.
- G0 Local Development is `PASS`. G0 Azure DEV blijft `BLOCKED`. G8 en Azure worden niet als `PASS` of gestart geclaimd. Console-identiteit sluit G8 niet en provisioneert geen Azure AD.
- G1 technische protection op `main` is ON. GitHub-ruleset **G1 main** (id `21686159`, aangemaakt 2026-08-27T22:10:53Z) is actief: `main` mag niet worden verwijderd; geen force-push / non-fast-forward; required status checks `test (3.12)` en `test (3.13)` (strict); pull request verplicht vóór merge; 0 vereiste goedkeurende reviews (solo owner). Protected branch, required CI en PR-workflow bestaan nu. Named GD-03-reviewers zijn niet bezet.

## Open governancepunt

GD-01, GD-02, GD-04, GD-05, GD-06 en GD-07 blijven OPEN. GD-03 is niet langer OPEN.

Benoemde individuele C3–C6-reviewers zijn een latere bezettingsstap en houden GD-03 niet OPEN. Tot die bezetting kunnen C3–C6-merges in de praktijk niet voldoen aan de vastgestelde matrix, behalve reparaties die aantoonbaar een bestaande protocolregel herstellen en eigenaarsgoedgekeurde C5-protocoldelta's (v2.5 / PR #16 en v2.6) met retrospectieve review.

PR #4, PR #5, PR #16 en Protocol v2.6 zijn C5-wijzigingen en vereisen nog retrospectieve onafhankelijke technical- en security/operations-review volgens GD-03.

Evidence: `docs/GOVERNANCE.md` en `data/assurance/gd_03_c3_c6_reviewer_matrix.json`.

## Protocolwijziging 2026-08-28 (live als scope)

Protocol v2.6 keurt een interne operations console goed als menselijk oppervlak over de knowledge kernel. Dat is een begrensde supersessie van de v2.4-lezing «geen productfrontend in deze repository». Zorgapp-frontend, chatbot, EPD/ECD-UI en publieke website blijven verboden. Chat is geen kamer in de console. Vier kamers: Ingest, Review (verplichte return-loop; uploader MUST NOT de enige vereiste reviewer zijn), Publish, Analytics (laatst). Identiteit (researcher/reviewer/publisher) is een vereiste consolecapability; provider blijft onder G0. De console bestaat niet in code. G1 blijft ON. De remote blijft public onder v2.5. Bron 2 blijft BLOCKED op immutable opslag.

## Eerstvolgende taak

1. Fase 2: exacte bron 2 (Continentie) duurzaam en immutable opslaan — exacte HTML-bytes, SHA-256, locator — en daarna klinische review. Geen Azure starten. De interne operations console is goedgekeurd-niet-gebouwd en komt ná vastlegbare bron 2-opslag, niet in plaats daarvan.
2. Retrospectieve onafhankelijke C5-review van PR #4, PR #5, PR #16 en Protocol v2.6 volgens de GD-03-matrix; daarna named reviewers bezetten.
3. Holdout B onafhankelijk vergrendelen; geen tuning daarop. GD-01 en GD-02 blijven OPEN tot die gates.
4. Na de MVP: een nieuw plan dat private hosting of een organisatieplan herstelt.
5. Pas na de MVP-gates een U1/U2-consumentencontract en partnerpilot ontwerpen.

## Hervattingsinstructie

Bij hervatting worden achtereenvolgens volledig gelezen:

1. `PROTOCOL.md` en de gekoppelde geldende protocolspecificaties, plus het ondergeschikte record `docs/GOVERNANCE.md`;
2. `ROADMAP.md`;
3. `HANDOFF.md`;
4. de relevante acceptatie- en invarianttests;
5. pas daarna de implementatiecode.

Na iedere materiële merge wordt deze handoff in dezelfde PR bijgewerkt met: mergecommit, afgeronde gate, resterende blokkades, afwijkingen en één eerstvolgende concrete taak.
