# Protocol 4.3.1 — afstemming met de codebase

Change class: C
Promise: Het actuele protocol beschrijft de bestaande veiligheids- en publicatiegrenzen correct en maakt resterende implementatiekloven zichtbaar.
Proof: Gerichte document-, policy-, PostgreSQL-, hervat- en publicatieproeven, plus bytecontrole van de vorige protocoltekst.
Touches lifecycle invariants: no
Rewrite risk: none

Dit is document- en contractonderhoud met gerichte contracttests. De enige runtimewijziging is de protocolidentiteitsconstante; reviewbesluiten, publicatievoorwaarden, opgeslagen gegevens, schema's en serving-overgangen worden niet gewijzigd. De correctie raakt wel de beschreven governance en wordt daarom expliciet getoetst. Deployment, productieacceptatie en historische datamigratie vallen buiten deze opdracht. William heeft in deze sessie expliciet opdracht gegeven de afstemming op main te brengen; merge volgt uitsluitend na de toepasselijke checks.

## Besluit en bewijsgrens

Oorspronkelijk onderzocht op Git-basis `0bbd58f2aa2b1f4a9e6dff288458ec76b4809c56`. Voor integratie is de wijziging op actuele main `1d0dc8cf27528d18dd93227370996d3ebcf45d05` geplaatst; nieuwere productcode en de GitHub–Linear-overdrachtscheck zijn behouden. Protocol 4.3.0 dateerde van vóór het reeds geïmplementeerde vier-ogenbesluit van 2026-10-23. §6.3 beschreef daardoor een zwakkere regel dan de huidige code: een expliciete policy zou de inhoudsgebonden tweede beoordeling kunnen uitschakelen. Protocol 4.3.1 corrigeert dit, beschrijft de bestaande idempotente publicatieherhaling en verduidelijkt autoriteit en bewijsgrenzen. De code wordt niet aangepast aan de verouderde tekst.

De vorige protocoltekst is bytegelijk bewaard als [snapshot](../history/protocol-v4.3/PROTOCOL_BEFORE_ALIGNMENT_2026-11-01.md), SHA-256 `1eaeae0da519c90c09375eb67809bdac5f73d000a790d3e740308b51f1ca003d`. De actuele protocolidentiteit en codeconstante worden 4.3.1. Historische releases en fixtures worden niet herschreven. De constante alleen bewijst geen duurzame protocolversie in releases.

De onderstaande koppeling betreft de genoemde regels en routes. Zij is geen volledige codeaudit en geen verklaring dat alle protocolinvarianten in productie bewezen zijn. Open werk blijft uitsluitend in [de roadmap](../../ROADMAP.md) geprioriteerd.

## Koppeling tussen norm, code en bewijs

| Protocolregel | Code die de regel uitvoert | Relevante proeven | Afstemming / bewijsgrens |
| --- | --- | --- | --- |
| §§4–5: brongebonden semantische voorstellen, harde toelating, geen deterministische terugval | [vormingspolicy](../../src/vorming/passage_formation_policy_v1.py), [semantische router](../../src/vorming/pre_review_semantic_v1.py) | [policy en afwijzing vervallen routes](../../tests/test_vsa_f1_passage_formation_policy.py), [broncontext en vervalst bewijs](../../tests/test_source_bound_context.py) | V2 blijft de standaard; V1/V3 zijn expliciet. Technische bronbinding bewijst geen inhoudelijke volledigheid. |
| §5.4: route behouden over poging en hervatten | [reservering en compatibiliteit](../../src/vorming/source_selection_v1.py), [overdrachtscontext](../../src/vorming/source_preparation_context_v1.py), [checkpoint](../../src/vorming/formation_checkpoint_v1.py) | [hervatten na configuratiewissel en herstart](../../tests/test_source_resume_acceptance.py) | Pogingconfiguratie wordt al opgeslagen en bewaakt. Routering vanuit een expliciete routekeuze per bron blijft open onder R4.6; het bestaande [routebindingsontwerp](../change-contracts/met-13-r46-route-binding-design.md) beschrijft de as-is-grens en de latere implementatie. |
| §6.3: inhoudsgebonden vier ogen onder iedere actuele policy | [vier-ogenpoort](../../src/review/four_eyes_v1.py), [reviewplicht](../../src/review/review_duty_v1.py), [reviewconfiguratie](../../src/review/review_configuration_v1.py) | [explicit-review, optionele en vereiste deelnemers](../../tests/test_explicit_review_policy.py), [configuratiepoort inclusief uploader/high-risk](../../tests/test_review_configuration_gate_v1.py), [beheerde deelnemers](../../tests/test_review_participation_management.py) | De oude tekst dat risicosignalen geen extra reviewplicht toevoegen is verwijderd. Historische herverificatie blijft versiegebonden; de oude regel is geen nieuwe publicatieroute. |
| §§7.2, 12: PostgreSQL-publicatieautoriteit en actieve serving-set | [duurzame publicatie](../../src/publication/durable_publication_console_v1.py), [canonieke store](../../src/publication/canonical_publication_postgres_v1.py) | [registry als serving-gate](../../tests/test_publication_registry_serving_authority_v1.py), [opvolging zonder heractivatie](../../tests/test_successor_release_cutover_v1.py) | De protocolversie ontbreekt nog als veld in het duurzame publicatiepad; R4.2 benoemt dit expliciet. |
| §7.3: actieve publicatie herhalen zonder nieuwe release; intrekking blijft gesloten | [publicatie en intrekking](../../src/publication/durable_publication_console_v1.py) | [publicatiebewijs](../../tests/test_publication_evidence_v1.py), met `test_repeat_publish_reuses_active_release_and_cannot_reactivate_withdrawal` | Herhaling mag bestaande release teruggeven en kopieën reconciliëren. De gerichte proef controleert dezelfde release, gelijkblijvende objecten en weigering na intrekking, ook na nieuwe console-instanties. |
| §7: echte bronbytes en hash nodig | [Azure-publicatiecontrole](../../src/publication/azure_authoritative_publication_console_v1.py) | [ontbrekende blob, store en hashmismatch](../../tests/test_azure_blob_publication_authority_v1.py) | Deze proeven gebruiken een gecontroleerde bronstore; zij bewijzen geen toegang tot een echte Azure-omgeving. |
| §11.1: huidige consolewerkvolgorde | [console-navigatie `_nav`](../../src/operations_console_app.py) | [actuele protocolconsistentie](../../tests/test_protocol_v4_governance.py) | De zichtbare naam is Vorming, de route blijft `/source-selection`. De documentwijziging verandert geen UI of bevoegdheden. |
| §13: PostgreSQL verplicht, één instance, één of twee workers | [consoleconstructor](../../src/operations_console_v1.py), [topologiepoort](../../src/topology_bound_v1.py) | [alleen complete PG-authority](../../tests/test_718_workflow_topology.py), [worker- en instancegrenzen](../../tests/test_topology_bound.py) | PostgreSQL is altijd verplicht. Twee workers vereisen daarnaast Azure als immutable source authority. |
| §§14–16: actuele norm en bevroren historie | [protocol](../../PROTOCOL.md), [governance](../GOVERNANCE.md), [ontwikkelworkflow](../DEVELOPMENT_WORKFLOW.md) | [versies en archiefhash](../../tests/test_protocol_v4_governance.py), [documenthiërarchie](../../tests/test_governance_document_hierarchy.py) | Documentcontroles bewaken identiteit en archiefintegriteit; gedragsproeven bewaken de productregels. |

## Afwijkingen en acceptatie

- R4.6 blijft open voor expliciete routekeuze per prozabron. De eerdere formulering dat er helemaal geen documenttoestand wordt vastgelegd was achterhaald. De norm wordt niet verlaagd tot alleen de bestaande configuratiebewaking.
- R4.2 benoemt nu dat de protocolversie nog niet duurzaam per release wordt vastgelegd. `persist_published_release` ontvangt geen protocolversie; de constante is geen opslagbewijs. Een latere implementatie moet opslag, herstart en herstel bewijzen zonder historische versies te verzinnen.
- De routewissels van 18 en 22 oktober zonder voorafgaand §10-experiment zijn reeds in R4.6 verantwoord met de oorspronkelijke besluiten en change contracts. Deze afstemming levert het ontbrekende voorafgaande experiment niet alsnog. Menselijke inhoudelijke acceptatie op bevroren bronnen en echte provideruitvoer blijft open.
- De oudere roadmapmomentopname en de live deploymentstatus zijn niet opnieuw vastgesteld. De gerichte afstemming staat afzonderlijk gedateerd, zodat de oude main-verwijzing geen actuele runtimeclaim wordt.

## Verificatie

De definitieve gerichte run slaagt: **290 passed, 0 skipped, 0 failed**, één bestaande Starlette/AnyIO-deprecationwaarschuwing; 88,42 seconden. Dit omvat de nieuwe proef voor idempotente publicatie, gelijkblijvende release/objecten na een nieuwe console-instantie en afwijzing na intrekking. De eerdere begrensde run gaf 182 passes; die wordt niet bij het definitieve aantal opgeteld.

Uitgevoerd met de bestaande virtuele omgeving en lokale testserver. Eerst is `scripts/test_postgres.sh` met de ingestelde test-DSN succesvol uitgevoerd. De tests gebruiken de bestaande geïsoleerde PostgreSQL-fixtures; productieopslag en echte modelproviders zijn niet benaderd.

```sh
python -m pytest -q \
  tests/test_protocol_v4_governance.py \
  tests/test_governance_document_hierarchy.py \
  tests/test_vsa_f1_passage_formation_policy.py \
  tests/test_source_bound_context.py \
  tests/test_source_resume_acceptance.py \
  tests/test_topology_bound.py \
  tests/test_718_workflow_topology.py \
  tests/test_explicit_review_policy.py \
  tests/test_review_configuration_gate_v1.py \
  tests/test_review_participation_management.py \
  tests/test_publication_registry_serving_authority_v1.py \
  tests/test_successor_release_cutover_v1.py \
  tests/test_publication_evidence_v1.py \
  tests/test_azure_blob_publication_authority_v1.py
```

Ook geslaagd: repository-preflight (1779 bestanden op het controlemoment), architectuurgrenzen, change-contractvalidatie op deze notitie, release-control-preflight op de gewijzigde paden. De oorspronkelijke `git diff --check` controleerde alleen de toenmalige werkboom, niet de volledige commitpatch. De volledige patchcontrole tegen de parent meldt terecht trailing whitespace op regels 5–8 van de nieuwe historische snapshot: die twee spaties zijn bestaande Markdown-regeleinden en blijven voor bytegelijk auditbewijs behouden. De actieve bestanden slagen met `git diff --check origin/main -- . ":(exclude)docs/history/protocol-v4.3/PROTOCOL_BEFORE_ALIGNMENT_2026-11-01.md"`. Er is geen geslaagde volledige whitespacecontrole geclaimd voor het ongewijzigde archief. De lokale documentverwijzingen in de aangepaste stuurdocumenten/notitie bestaan; de archieftekst is daarnaast rechtstreeks met `git show HEAD:PROTOCOL.md` bytegelijk vergeleken. De werkvolgorde is vergeleken met de daadwerkelijke `rooms`-lijst van `_nav` en komt overeen.

De omgeving bevat Python 3.13.5 en PostgreSQL 17.11; de repository-CI gebruikt PostgreSQL 16. Lokale proeven op 17 vervangen daarom geen CI-bewijs op 16. Provider- en bronstorefixtures bewijzen de getoetste grenzen, niet de inhoudelijke kwaliteit van echte modeluitvoer of productieconfiguratie.

De aanvullende volledige integratieproef op de actuele main-basis en de vereiste CI-checks worden met exacte PR-head in de PR-overdracht verantwoord. De hierboven genoemde 290 gerichte passes worden niet als volledige suite of als PostgreSQL-16-bewijs gepresenteerd.

Reviewcorrectie: de actieve historie-index wijst eveneens naar 4.3.1 en noemt de nieuwe v4.3.0-snapshot. De versiecontracttest vergelijkt die index met de runtimeconstante. De volledige lokale integratierun op head `a464271231a738796258667bfaad9b4ff858a305` slaagt met 6741 passes, 40 optionele skips, 3 bestaande xfails en 24 geslaagde subtests (Python 3.13.5, PostgreSQL 17.11). De latere index-/auditcorrectie verandert geen productcode; gerichte documenttests en CI toetsen de nieuwe head.

Na deze reviewcorrectie slagen de 17 gerichte protocol-/documentcontracttests, repository-preflight, change-contractvalidatie, de whitespacecontrole van actieve bestanden en de byte-/linkcontrole van het archief en de historie-index.
