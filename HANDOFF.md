# V&VN Data Services — Actuele handoff

**Bijgewerkt:** 2026-08-27  
**Geldend protocol:** v2.5.0  
**Authoritative remote:** `WilliamGomes41/VENVN-DS` (public during the declared MVP period)  
**Default branch:** `main`

## Actuele waarheid

- Deze repository is **alleen** V&VN Data Services: protocol, bronintegriteit, pipeline, publicatiegates, retrieval en Product API. Andere producten horen hier niet in governance of code.
- Protocol v2.5.0 is de normatieve baseline (v2.2.0 + v2.3-delta + v2.4-delta + v2.5-delta) en is live. v2.5 is de eigenaarsgoedgekeurde MVP-uitzondering: de gezaghebbende remote MAG publiek zijn tijdens een gedeclareerde MVP-periode, zodat G1-branchprotection technisch kan worden aangezet. Het checksumgebonden approval-manifest staat in `data/assurance/protocol_v2_5_approval.json`. Deze C0-standopname is geen nieuwe protocolversie.
- De gezaghebbende remote `WilliamGomes41/VENVN-DS` is public (`isPrivate: false`) onder de v2.5-MVP-uitzondering. Publiek is niet de latere productiestandaard; na de MVP MUST een nieuw plan private hosting of een organisatieplan herstellen.
- V&VN DS is vastgelegd als gevalideerde kennisobjecten, Product API en interne read-only inspection.
- Het MVP is beperkt tot U1 bronverwijzing en U2 kennisrespons; U3 beslisregels, U4 patiëntspecifiek advies en U5 voorspellende/getrainde modellen zijn buiten scope.
- Extern gebruik vereist een consumentenregistratie, gebruiksovereenkomst, expliciete verantwoordelijkheden en geteste update/withdrawal-verwerking.
- PR #4 (source integrity), #5 (PDF completeness), #6 (scoped HTML), #7 (stack/G0), #8 (ontwikkelhiërarchie), #9 (v2.3-approval), #10 (integrity-kernel + runtime-entrypoints), #11 (repositoryscope), #12 (v2.4 product/distributie), #13 (v2.4-approval-evidence), #14 (GD-03 ESTABLISHED) en #16 (v2.5 MVP public-remote exception) zijn afgerond. PR #16 is squash-merged als `73c0669c8ad7c62a836e7a39666f3db33644be68` op 2026-08-27T22:10:04Z.
- Operationeel governance-record: `docs/GOVERNANCE.md` (ondergeschikt aan `PROTOCOL.md`, geen vijfde stuurlaag) met machineleesbaar GD-03-artefact `data/assurance/gd_03_c3_c6_reviewer_matrix.json`.
- GD-03 is ESTABLISHED (2026-08-27) as written: C3 min. 2 clinical+technical; C4 min. 2 evaluation+technical; C5 min. 2 security/operations+technical; C6 min. 3 clinical+technical+safety/evaluation. Reviewers onafhankelijk van de auteur; dezelfde exacte commit/snapshot. AI / Grok Bot / Metis tellen niet mee als vereiste reviewer, keuren niet goed en publiceren niet. Het GD-03-governance-record blijft ESTABLISHED; dat record is geen nieuwe protocolversie. Benoemde GD-03-reviewers zijn niet bezet.
- Protocol v2.5 is een C5-wijziging (repository-identiteit/zichtbaarheid / supply-chain-toegang). Benoemde C5-reviewers zijn nog niet bezet. De projecteigenaar keurde de delta goed. Retrospectieve onafhankelijke technical- en security/operations-review van PR #4, PR #5 en PR #16 blijft verschuldigd. Er worden geen reviewers verzonnen. GD-03 wordt niet heropend.
- Repository-indeling (C0, 2026-08-27): historische STEP-/audit-/repair-rapporten staan in `docs/history/`. De root is het operationele oppervlak (`PROTOCOL.md`, `ROADMAP.md`, `HANDOFF.md`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md` plus code/config/build). Dit voegt geen vijfde stuurlaag toe. `output/` blijft als overgangsartefacten staan; tests gebruiken `data/fixtures/`.
- Fail-closed blijft ongewijzigd: geen bronbinaries in Git, geen secrets/keys/certs, `config/tenants.v1.json` blijft leeg, vertrouwelijke reviewartefacten blijven buiten Git, runtime-databases blijven buiten Git. `.gitignore` dekt dit en blijft staan. Fixtures, holdouts en getrackte `output/`-historie MAGEN in de publieke MVP-repo blijven; canonieke bron-HTML/PDF MAGEN dat niet.
- De exacte officiële HTML-representatie van bron 2 is lokaal geverifieerd en deterministisch geëxtraheerd.
- Bron 1 en bron 2 blijven `BLOCKED` voor publicatie zolang immutable opslag, definitieve registratie en klinische review ontbreken.
- G0 Local Development is `PASS`. G0 Azure DEV blijft `BLOCKED`. G8 en Azure worden niet als `PASS` of gestart geclaimd.
- G1 technische protection op `main` is ON. GitHub-ruleset **G1 main** (id `21686159`, aangemaakt 2026-08-27T22:10:53Z) is actief: `main` mag niet worden verwijderd; geen force-push / non-fast-forward; required status checks `test (3.12)` en `test (3.13)` (strict); pull request verplicht vóór merge; 0 vereiste goedkeurende reviews (solo owner). Protected branch, required CI en PR-workflow bestaan nu. Named GD-03-reviewers zijn niet bezet.

## Open governancepunt

GD-01, GD-02, GD-04, GD-05, GD-06 en GD-07 blijven OPEN. GD-03 is niet langer OPEN.

Benoemde individuele C3–C6-reviewers zijn een latere bezettingsstap en houden GD-03 niet OPEN. Tot die bezetting kunnen C3–C6-merges in de praktijk niet voldoen aan de vastgestelde matrix, behalve reparaties die aantoonbaar een bestaande protocolregel herstellen en de eigenaarsgoedgekeurde C5-protocoldelta v2.5 (PR #16) met retrospectieve review.

PR #4, PR #5 en PR #16 zijn C5-wijzigingen en vereisen nog retrospectieve onafhankelijke technical- en security/operations-review volgens GD-03.

Evidence: `docs/GOVERNANCE.md` en `data/assurance/gd_03_c3_c6_reviewer_matrix.json`.

## Protocolwijziging 2026-08-27 (live)

Protocol v2.5 ontspant v2.2 §4.1 (private remote MUST) uitsluitend voor een gedeclareerde MVP-periode op `WilliamGomes41/VENVN-DS`. De uitzondering is live: de remote is public. Publiek is daarna niet de productiestandaard; een nieuw plan MUST private hosting of een organisatieplan herstellen. Tot dat plan bestaat, is G1-technische protection op een publieke MVP-repo geaccepteerd. G1-technische protection (protected branch, required CI, PR-workflow, geen directe push) staat aan via ruleset `21686159`. Deze C0-standopname wijzigt het protocol niet, claimt G8 of Azure niet, en bezet geen named reviewers.

## Eerstvolgende taak

1. Fase 2: exacte bron 2 (Continentie) duurzaam en immutable opslaan — exacte HTML-bytes, SHA-256, locator — en daarna klinische review. Geen Azure starten.
2. Retrospectieve onafhankelijke C5-review van PR #4, PR #5 en PR #16 volgens de GD-03-matrix; daarna named reviewers bezetten.
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
