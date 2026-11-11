# Verwijderplan na annotatie en reviewkaart

Change class: C voor dit plan en de eerste, niet-semantische opschoonstap.
Rewrite risk: none voor die stap; latere wijzigingen krijgen hun eigen classificatie.

Opdracht William, 11 november 2026: maak het verwijderplan, koppel geschikte
GitHub-/Linear-issues en begin met opschonen. Basis: main
`d5715e61ca47554b89853f190202ad388c30ed07`; inventaris uit `f66c5acb`.
De inventaris is een kandidatenlijst, geen verwijdertoestemming per regel.

## Werkpakketten en volgorde

GitHub bevat scope, besluiten en bewijs; Linear bevat status en de volgende stap.
Het bestaande opschoonwerkpakket is [MET-11](https://linear.app/metis-phoenix/issue/MET-11),
onder het projectoverzicht [#877](https://github.com/WilliamGomes41/Metis-DS/issues/877).
De eerste uitvoering is [#1047](https://github.com/WilliamGomes41/Metis-DS/issues/1047) /
[MET-69](https://linear.app/metis-phoenix/issue/MET-69), als kind van MET-11.
De tweede batch is [#1049](https://github.com/WilliamGomes41/Metis-DS/issues/1049) /
[MET-70](https://linear.app/metis-phoenix/issue/MET-70): de
[functiegewijze bewijstabel](verwijderkandidaten-batch-2.md) onderscheidt één
verwijdering, negen behoudsbesluiten, drie migraties en drie open gevallen.
Dit plan vervangt de algemene volgorde uit de oorspronkelijke inventaris.
Onafhankelijke niet-semantische opruiming hoeft niet te wachten op productcutover;
integrale uitfasering en projectsluiting behouden hun bestaande afhankelijkheden.

| Volgorde | Werk en bestaand issue | Voorwaarde / sluitingsbewijs |
| --- | --- | --- |
| 1 | Eerste opschoonstap onder MET-11: vier ongebruikte functies, dit plan en gecorrigeerde inventaris | Geen naamreferentie in uitvoerbare repo-inhoud buiten de definitie; geen registratie/override; AST-equivalentie van behouden code; bestaande checks en tests |
| 2 | Overige A1/A2/A3-kandidaten onder MET-11 / #877 | Per symbool contract, operatorgebruik, dynamische callers en testdoel beoordelen; historische lezers en noodzakelijke testondersteuning behouden |
| 3 | Oude reviewkaart, foutweergave, gedeelde helpers en formulieren onder [#995](https://github.com/WilliamGomes41/Metis-DS/issues/995) / [MET-56](https://linear.app/metis-phoenix/issue/MET-56) | Besluit over koppen/structuur/bronrecords/boompaden; bestaande GET én POST-foutweergave, tweede review en correctie naar behouden eigenaar migreren vóór verwijderen; acceptatie bij [#990](https://github.com/WilliamGomes41/Metis-DS/issues/990) / MET-53 |
| 4 | Eén leesmodus en één opslaglayout, samen met bestaande opslag-/cutover-eigenaren [#729](https://github.com/WilliamGomes41/Metis-DS/issues/729) / MET-36 en [#953](https://github.com/WilliamGomes41/Metis-DS/issues/953) / MET-44 | Eerst operatorinventaris, ondersteunde topologieën en rollback vastleggen; compact is nog geen genomen besluit; geen opslagmigratie in stap 1 |
| 5a | HA-4a praktijkvergelijking en gecontroleerde overgang onder [#1017](https://github.com/WilliamGomes41/Metis-DS/issues/1017) / [MET-61](https://linear.app/metis-phoenix/issue/MET-61) | Bevroren referenties, inhoudelijke en gebruikersacceptatie, telling pending/claimed/expired AI-pogingen, één producer per werkrevisie, expliciete takeover en getest herstel/rollback |
| 5b | HA-4b AI-proza, oude contextpagina en exclusieve configuratie verwijderen, hetzelfde #1017 / MET-61 | Na 5a; start/reserve/dispatcher/retry/resume/directe calls/settings/scripts sluiten; correctielinks naar oorspronkelijke annotatie; boom en historische bewijslezers behouden; runtime-bypassbewijs op dezelfde head |
| 6 | Bronrollen samenvoegen onder [#942](https://github.com/WilliamGomes41/Metis-DS/issues/942) / [MET-35](https://linear.app/metis-phoenix/issue/MET-35) | Eigen Class A/high-contract en bestaande pariteits-/herstelbewijzen; groepsafhandeling blijft gekoppeld aan [#933](https://github.com/WilliamGomes41/Metis-DS/issues/933) / MET-33 en HA-4-acceptatie |
| 7 | Persistente spiegelvelden verwijderen onder KO-6, #995 / MET-56 | Schriftelijk besluit, schema-/oude-imagecompatibiliteit, back-up en herstelproef; geen dataverwijdering in dit plan uitvoeren |

De schermoverlays en dubbele adressen (B9/B11) kunnen als afzonderlijke vervolgslice
onder MET-11 worden onderzocht. Eerst alle callers, formulieren en ondersteunde
oude URL's migreren; ieder scherm behoudt één implementatie-eigenaar. Het aantal
HTTP-adressen bewijst op zichzelf geen dubbele domeinschrijver.

## Correcties uit de tweede controle

- **Audit behouden:** `AuditRetentionService`, `list_archived` en
  `PostgresAuditRegistry` vallen buiten directe verwijdering. Het bestaande
  [auditcontract](../change-contracts/audit-room-retirement.md) behoudt herstel van
  oudere back-ups en noemt uitfasering een afzonderlijke stap. Alleen testgebruik
  is geen bewijs dat dit contract vervalt.
- **Review heeft meer callers:** `review_command_response_v1.review_command_error`
  gebruikt `_render_review_card` ook voor mislukte KO-opslag. De nieuwe
  `ko_review_page_v1` gebruikt `_source_bound_fields_html`. Andere helpers dienen
  bronselectie en deterministische correctie. Verwijder geen gedeelde helper met
  de oude kaart; migreer eerst de behouden callers en bewijs fout-/conflictgedrag.
- **Twee oude tree-adressen navigeren:** `/tree/reprocess` en
  `/tree/resume-formation` verwijzen door; `/source-selection/start` reserveert de
  daadwerkelijke opdracht. `/tree/processing-recovery` is een afzonderlijke
  autorisatiehandeling. Achtergrondtaken en directe callers horen wel bij HA-4b.
- **Broncontext volgt cutover:** B3 is onderdeel van HA-4b en komt na HA-4a,
  niet vóór de overgang. Menselijke correctie blijft naar de bronannotatie gaan.
- **Consoleklassen zijn actief door overerving:** acht tussenklassen dragen
  mixins aan de productieklasse over. Eventueel afvlakken is een refactor met
  MRO-/`super()`-equivalentiebewijs, geen dode-codeverwijdering.
- **Operatorstatus hergebruiken:** het levenscyclusregister benoemt onder meer
  `protocol_approval_manifest`, `register_source_binary`, `azure_step9_cutover_v1`
  en `g2_azure_preflight` als `ACTIVE-OPERATOR`. De oude registerpaden moeten naar
  hun huidige locaties worden vertaald; geen importeur in `src` verandert die
  status niet automatisch.

## Eerste uitvoering: vier functies

| Bestand | Verwijderen | Behouden grens |
| --- | --- | --- |
| `src/integrity_kernel.py` | `validate_source_integrity` | Gebruikte hash-, bronfragment- en objectvalidatie |
| `src/operations_console_v1.py` | `session_is_expired` | Werkelijke sessievalidatie en autorisatie |
| `src/operations_console_app.py` | `knowledge_open_count` | Actuele reviewprojectie, persoonsgebonden werk en tweede-reviewtelling |
| `src/workflows/workflow_documents_cutover_v1.py` | `list_processing_history_inputs` | Gerichte historielezers en bestaande opslaggrenzen |

Geen tests verwijderen om deze stap groen te krijgen. De behouden productcode
moet AST-gelijk zijn aan de basis na uitsluitend deze vier definities weg te laten.
Het register krijgt symboolregels met deze afbakening; geen nieuwe runtimevlag.

Bewust niet in deze eerste stap:

- `storage_prepare.py`: het eerdere
  [verwijderverslag](../history/DEAD_CODE_REMOVAL.md) bewaart dit expliciet als
  OPENVRAAG-S3 wegens mogelijk extern operatorgebruik; eerst dat gebruik besluiten.
- `prior_object_audit_history`: historische lezer met bestaand behoudscontract.
- `_finalize_source_provenance`: eerst het herstelcontract en de behouden
  provenance-finalizer samen traceren.
- A2-functies, testhulpen, evaluatiegereedschap, auditretentie en alle actieve
  routes, mixins, opslaglayouts, gegevens en migraties.

## Bewijs en afronding

| Claim | Controle | Bewijsgrens |
| --- | --- | --- |
| Uitsluitend vier ongebruikte definities verdwijnen | Exacte naamzoekronde vóór/na, decorators/overrides/dynamische dispatch inspecteren, AST-vergelijking | Geen bewijs over onbekende externe Python-consumenten |
| Behouden gedrag blijft intact | Bestaande relevante sessie-, integriteits-, review- en opslagtests plus verplichte repositorychecks en volledige suite | Native PostgreSQL vereist; skips tellen niet als geslaagd databasebewijs |
| Traceerbare planning | GitHub-issue/PR ↔ Linear-kind onder MET-11; verwijzingen naar de bestaande eigenaren hierboven | Een gemergde deelslice sluit MET-11, HA-4 of KO-6 niet |

Uitvoeringsstatus en werkelijk verkregen bewijs staan in het change contract en
de PR van stap 1. Geen merge, deployment, productieconversie of betaalde modelrun
maakt deel uit van deze eerste opschoonstap.
