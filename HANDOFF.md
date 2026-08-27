# V&VN Data Services — Actuele handoff

**Bijgewerkt:** 2026-08-27  
**Geldend protocol:** v2.5.0  
**Authoritative remote:** `WilliamGomes41/VENVN-DS`  
**Default branch:** `main`

## Actuele waarheid

- Deze repository is **alleen** V&VN Data Services: protocol, bronintegriteit, pipeline, publicatiegates, retrieval en Product API. Andere producten horen hier niet in governance of code.
- Protocol v2.5.0 is de normatieve baseline (v2.2.0 + v2.3-delta + v2.4-delta + v2.5-delta). v2.5 is de eigenaarsgoedgekeurde MVP-uitzondering: de gezaghebbende remote MAG publiek zijn tijdens een gedeclareerde MVP-periode, zodat G1-branchprotection technisch kan worden aangezet.
- Deze PR wijzigt GitHub-zichtbaarheid niet. Metis zet de remote na merge op public en zet daarna G1-protection aan. Tot die twee stappen blijft G1 `BLOCKED`.
- V&VN DS is vastgelegd als gevalideerde kennisobjecten, Product API en interne read-only inspection.
- Het MVP is beperkt tot U1 bronverwijzing en U2 kennisrespons; U3 beslisregels, U4 patiëntspecifiek advies en U5 voorspellende/getrainde modellen zijn buiten scope.
- Extern gebruik vereist een consumentenregistratie, gebruiksovereenkomst, expliciete verantwoordelijkheden en geteste update/withdrawal-verwerking.
- PR #4 (source integrity), #5 (PDF completeness), #6 (scoped HTML), #7 (stack/G0), #8 (ontwikkelhiërarchie), #9 (v2.3-approval), #10 (integrity-kernel + runtime-entrypoints), #11 (repositoryscope), #12 (v2.4 product/distributie) en #13 (v2.4-approval-evidence) zijn afgerond. PR #14 (GD-03 ESTABLISHED) is afgerond.
- Operationeel governance-record toegevoegd: `docs/GOVERNANCE.md` (ondergeschikt aan `PROTOCOL.md`, geen vijfde stuurlaag) met machineleesbaar GD-03-artefact `data/assurance/gd_03_c3_c6_reviewer_matrix.json`.
- GD-03 is ESTABLISHED (2026-08-27) as written: C3 min. 2 clinical+technical; C4 min. 2 evaluation+technical; C5 min. 2 security/operations+technical; C6 min. 3 clinical+technical+safety/evaluation. Reviewers onafhankelijk van de auteur; dezelfde exacte commit/snapshot. AI / Grok Bot / Metis tellen niet mee als vereiste reviewer, keuren niet goed en publiceren niet. Het GD-03-governance-record blijft ESTABLISHED; dat record is geen nieuwe protocolversie.
- Protocol v2.5 is een C5-wijziging (repository-identiteit/zichtbaarheid / supply-chain-toegang). Benoemde C5-reviewers zijn nog niet bezet. De projecteigenaar keurt deze delta goed. Retrospectieve onafhankelijke technical- en security/operations-review blijft verschuldigd, hetzelfde patroon als voor PR #4 en PR #5. Er worden geen reviewers verzonnen. GD-03 wordt niet heropend.
- Repository-indeling (C0, 2026-08-27): historische STEP-/audit-/repair-rapporten staan in `docs/history/`. De root is het operationele oppervlak (`PROTOCOL.md`, `ROADMAP.md`, `HANDOFF.md`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md` plus code/config/build). Dit voegt geen vijfde stuurlaag toe. `output/` blijft als overgangsartefacten staan; tests gebruiken `data/fixtures/`.
- Fail-closed blijft ongewijzigd: geen bronbinaries in Git, geen secrets/keys/certs, `config/tenants.v1.json` blijft leeg, vertrouwelijke reviewartefacten blijven buiten Git, runtime-databases blijven buiten Git. `.gitignore` dekt dit en blijft staan. Fixtures, holdouts en getrackte `output/`-historie MAGEN in de publieke MVP-repo blijven; canonieke bron-HTML/PDF MAGEN dat niet.
- De exacte officiële HTML-representatie van bron 2 is lokaal geverifieerd en deterministisch geëxtraheerd.
- Bron 1 en bron 2 blijven `BLOCKED` voor publicatie zolang immutable opslag, definitieve registratie en klinische review ontbreken.
- G0 Local Development is `PASS`. G0 Azure DEV blijft `BLOCKED`.
- G1 branch protection op `main` is nog niet afdwingbaar (`BLOCKED`) totdat de remote public is en protection aanstaat.

## Open governancepunt

GD-01, GD-02, GD-04, GD-05, GD-06 en GD-07 blijven OPEN. GD-03 is niet langer OPEN.

Benoemde individuele C3–C6-reviewers zijn een latere bezettingsstap en houden GD-03 niet OPEN. Tot die bezetting kunnen C3–C6-merges in de praktijk niet voldoen aan de vastgestelde matrix, behalve reparaties die aantoonbaar een bestaande protocolregel herstellen en de hier vastgelegde eigenaarsgoedgekeurde C5-protocoldelta v2.5 met retrospectieve review.

PR #4, PR #5 en deze v2.5-delta zijn C5-wijzigingen en vereisen nog retrospectieve onafhankelijke technical- en security/operations-review volgens GD-03.

Evidence: `docs/GOVERNANCE.md` en `data/assurance/gd_03_c3_c6_reviewer_matrix.json`.

## Protocolwijziging 2026-08-27

Protocol v2.5 ontspant v2.2 §4.1 (private remote MUST) uitsluitend voor een gedeclareerde MVP-periode op `WilliamGomes41/VENVN-DS`. Publiek is daarna niet de productiestandaard; een nieuw plan MUST private hosting of een organisatieplan herstellen. Tot dat plan bestaat, is G1-technische protection op een publieke MVP-repo geaccepteerd. G1 PASS vereist nog steeds required CI, PR-workflow en geen directe push. Deze protocolwijziging zet zichtbaarheid niet zelf om en maakt G1 niet `PASS`.

## Eerstvolgende taak

1. Repository public maken (Metis, na merge) en G1-branchprotection aanzetten: required checks `test (3.12)` en `test (3.13)`, pull request verplicht vóór merge, geen force-push, `main` niet verwijderbaar.
2. Exacte bron 2 duurzaam en immutable opslaan; daarna klinische review.
3. Retrospectieve onafhankelijke C5-review van PR #4, PR #5 en deze v2.5-delta volgens de GD-03-matrix; daarna named reviewers bezetten.
4. Holdout B onafhankelijk vergrendelen; geen tuning daarop. GD-01 en GD-02 blijven OPEN tot die gates.
5. Pas na de MVP-gates een U1/U2-consumentencontract en partnerpilot ontwerpen.

## Hervattingsinstructie

Bij hervatting worden achtereenvolgens volledig gelezen:

1. `PROTOCOL.md` en de gekoppelde geldende protocolspecificaties, plus het ondergeschikte record `docs/GOVERNANCE.md`;
2. `ROADMAP.md`;
3. `HANDOFF.md`;
4. de relevante acceptatie- en invarianttests;
5. pas daarna de implementatiecode.

Na iedere materiële merge wordt deze handoff in dezelfde PR bijgewerkt met: mergecommit, afgeronde gate, resterende blokkades, afwijkingen en één eerstvolgende concrete taak.
