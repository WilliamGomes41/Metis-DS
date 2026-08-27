# V&VN Data Services — Actuele handoff

**Bijgewerkt:** 2026-08-27  
**Geldend protocol:** v2.4.0  
**Authoritative remote:** `WilliamGomes41/VENVN-DS`  
**Default branch:** `main`

## Actuele waarheid

- Deze repository is **alleen** V&VN Data Services: protocol, bronintegriteit, pipeline, publicatiegates, retrieval en Product API. Andere producten horen hier niet in governance of code.
- Protocol v2.4.0 is de normatieve baseline (v2.2.0 + v2.3-delta + v2.4-delta); PR #12 is gemerged en het commitgebonden approval manifest is geregistreerd.
- V&VN DS is vastgelegd als gevalideerde kennisobjecten, Product API en interne read-only inspection.
- Het MVP is beperkt tot U1 bronverwijzing en U2 kennisrespons; U3 beslisregels, U4 patiëntspecifiek advies en U5 voorspellende/getrainde modellen zijn buiten scope.
- Extern gebruik vereist een consumentenregistratie, gebruiksovereenkomst, expliciete verantwoordelijkheden en geteste update/withdrawal-verwerking.
- PR #4 (source integrity), #5 (PDF completeness), #6 (scoped HTML), #7 (stack/G0), #8 (ontwikkelhiërarchie), #9 (v2.3-approval), #10 (integrity-kernel + runtime-entrypoints), #11 (repositoryscope) en #12 (v2.4 product/distributie) zijn afgerond.
- De exacte officiële HTML-representatie van bron 2 is lokaal geverifieerd en deterministisch geëxtraheerd.
- Bron 1 en bron 2 blijven `BLOCKED` voor publicatie zolang immutable opslag, definitieve registratie en klinische review ontbreken.
- G0 Local Development is `PASS`. G0 Azure DEV blijft `BLOCKED`.
- G1 branch protection op `main` is nog niet afdwingbaar onder het huidige repositoryplan (`BLOCKED`).

## Open governancepunt

GD-03 is nog niet formeel vastgesteld. Het operationele voorstel is:

| Klasse | Minimum | Verplichte rollen |
|---|---:|---|
| C3 | 2 | klinisch + technisch |
| C4 | 2 | evaluatie + technisch |
| C5 | 2 | security/operations + technisch |
| C6 | 3 | klinisch + technisch + safety/evaluatie |

Reviewers zijn onafhankelijk van de auteur en beoordelen dezelfde exacte commit of snapshot. PR #4 en PR #5 zijn C5-wijzigingen en vereisen retrospectieve onafhankelijke technische en security/operations-review.

## Protocolwijziging 2026-08-27

Protocol v2.4 legt de product- en distributiegrens vast. De protocolwijziging voegt geen externe consument, frontend, generation-route, patiëntdata of modeltraining toe. Implementatie van externe toegang of hogere use modes blijft afzonderlijk geclassificeerd en geblokkeerd door de toepasselijke gates en GD-03.

## Eerstvolgende taak

1. GD-03 formeel vaststellen en de evidence-URL registreren.
2. Branch protection op `main` aanzetten (G1) en afgeronde feature branches opruimen.
3. Exacte bron 2 duurzaam en immutable opslaan; daarna klinische review.
4. Holdout B onafhankelijk vergrendelen; geen tuning daarop.
5. Pas na de MVP-gates een U1/U2-consumentencontract en partnerpilot ontwerpen.

Geen nieuwe C3–C6-wijziging wordt gemerged voordat punt 1 is afgerond, behalve reparaties die aantoonbaar een bestaande protocolregel herstellen.

## Hervattingsinstructie

Bij hervatting worden achtereenvolgens volledig gelezen:

1. `PROTOCOL.md` en de gekoppelde geldende protocolspecificaties;
2. `ROADMAP.md`;
3. `HANDOFF.md`;
4. de relevante acceptatie- en invarianttests;
5. pas daarna de implementatiecode.

Na iedere materiële merge wordt deze handoff in dezelfde PR bijgewerkt met: mergecommit, afgeronde gate, resterende blokkades, afwijkingen en één eerstvolgende concrete taak.
