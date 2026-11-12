# #1060 — De medewerker wijst aan, Metis leidt af, de reviewer bevestigt

Change class: B
Promise: Een medewerker rondt een annotatie af met alleen de uitspraak, de tekst die erbij hoort en de onderbouwingskeuze; ontbrekende zinsdelen worden signalen en houden afronden en opbouw niet tegen.
Proof: Native PostgreSQL-proef van aanwijzen tot reviewkaart voor een opsommingspunt dat op zijn inleidende zin leunt: afronden, opbouwen en beoordeelbaar zonder ingevulde zinsdelen, met de signalen zichtbaar in het toelatingsrecord.
Touches lifecycle invariants: no
Rewrite risk: high

Part of MET-75. Besluiten (GO projectlead, 12 november 2026): William neemt het
advies bij de zes besluiten uit het
[ontwerp](../architecture/annotation-source-first-model.md) voorlopig over en
geeft opdracht te bouwen. Besluit 5 (documentdekking) blijft ongemoeid. Besluit 6
(eerst meten) is niet uitvoerbaar zonder betaalde modelcalls en een beoordelaar;
het is daarom vastgelegd als voorwaarde vóór slice 4 en vóór uitrol, niet vóór
slice 1–3.

## Program-design gate

- **Bestaand mechanisme en autoriteit:** `human_annotation_v1.save` bewaart de
  invoer; `human_annotation_preview_v1.inspect_annotation` bepaalt of een
  annotatie gereed mag en of het document mag worden afgesloten;
  `materialise_knowledge_candidates` is de enige kandidaatmaker;
  `admission_gate_v1.admit_candidate` bepaalt of een kandidaat beoordeelbaar is.
  Een geblokkeerde kandidaat blijft `kandidaat` en bereikt de reviewer niet
  (`knowledge_object_state_v1`).
- **Gedragswijziging:** voor kandidaten uit menselijke annotatie worden de
  controles op zinsdelen en type-onderdelen signalen. Ze worden nog steeds
  berekend en vastgelegd, maar blokkeren gereedmelden, afsluiten en toelating
  niet meer.
- **Eén beslispunt:** de lijst signaalcodes staat op één plek bij de
  toelatingseigenaar. Inspectie en toelating gebruiken dezelfde lijst; er komt
  geen tweede gate, status of kandidaatmaker.
- **Mag muteren:** het toelatingsrecord van nieuw opgebouwde objecten krijgt een
  sleutel `signals` wanneer er signalen zijn. **Blijft gelijk:** de opgeslagen
  annotatie, het schema, kandidaattekst, identiteit, bronmapping, de canonieke
  hash (toelating valt daarbuiten), review- en publicatieregels.
- **Ongewijzigd gedrag:** alles wat brongetrouwheid bewaakt blijft blokkeren:
  niet-letterlijke bereiken, kern die bronwoorden weglaat, onopgeloste
  noodzakelijke context, ontbrekend type, richting en sterkte van een
  aanbeveling, de onderbouwingskeuze, dubbele kernen, documentdekking.

## Signaalcodes

| Code | Betekenis |
| --- | --- |
| `subject_missing`, `recommendation_subject_missing`, `predicate_missing` | Onderwerp of gezegde niet aangewezen |
| `type_contract_incomplete` en de bijbehorende `*_missing` voor handeling, doel, definitie-onderdelen | Type-onderdeel niet aangewezen |
| `supported_object_missing`, `condition_target_missing`, `exception_target_missing`, `annotation_relation_target_missing` | Niet aangewezen waar de uitspraak bij hoort |
| `incomplete_sentence`, `no_independent_claim`, `recommendation_core_incomplete` | De zin lijkt afgebroken of niet zelfstandig |

Niet in de lijst en dus blokkerend: `span_not_in_source`,
`source_fidelity_failure`, `type_evidence_missing`,
`recommendation_core_omits_source`, `recommendation_core_field_mismatch`,
`recommendation_semantics_invalid`, `recommendation_direction_missing`,
`recommendation_strength_unmapped`, `context_necessary_unresolved`.

Afwijking van het ontwerp: het type blijft verplicht vóór opbouw, omdat de
reviewkaart een bekend type nodig heeft om te kunnen goedkeuren en geen
typekeuze biedt. Metis stelt het voor; kan Metis het niet, dan is het één
gerichte vraag aan de medewerker.

## Stateful overlay

Domain entity/aggregate: annotatie binnen de annotatieset; kennisobject met zijn toelatingsrecord.
Invariant(s): exacte bronspans, onveranderlijke versies, één kandidaatmaker, review vóór publicatie, alleen een bevestigd type wordt uitgeleverd.
Durable state before: annotatie `draft`; geen object, of een object dat op een zinsdeelcode geblokkeerd zou zijn.
Durable state after: annotatie `ready`; na opbouw een toegelaten object met `signals` in het toelatingsrecord.
Transaction boundary: ongewijzigd; opslaan, afsluiten en de bundelcommit van de opbouw houden hun bestaande transacties.
Failure/recovery result: ongewijzigd; een mislukte opbouw laat annotaties en vorige objecten intact.
Duplicate execution / idempotency result: ongewijzigd; bestaande command receipts en seal.
Concurrency result: ongewijzigd; CAS op revision, generation en objectfrontier.
Audit/evidence requirement: signalen staan in het toelatingsrecord van de objectversie; geen tweede logboek.

## Mitigatie voor rewrite risk: high

Rewrite target: de verplichtingen van menselijke annotatie-invoer en de toelatingsregels voor kandidaten uit menselijke annotatie.
Why local patching is insufficient: de invoer volgt het interne controleformulier. Een echte passage (opsommingspunt met inleidende zin) is daardoor niet af te ronden; elke reparatie aan de kaart laat die oorzaak staan.
Current authority/writer/reader map: autoriteit invoer `human_annotation_v1.save`; inspectie `human_annotation_preview_v1`; enige kandidaatmaker `knowledge_materialisation_v1`; toelating `admission_gate_v1.admit_candidate`, aangeroepen via `apply_admission_gate` vanuit `human_annotation_materialisation_v1`, `operations_console_v1` (drie plaatsen), `source_context_review_v1` en `revision_workflow`. Lezers van het toelatingsresultaat: `knowledge_object_state_v1`, `knowledge_path_v1`, `review_duty_v1`, `review_context_v1`, `proportionate_review_v1`, `domain_dimensions_v1`, `review_card_facts_v1`, `deterministic_review_repair_v1`. De wijziging zit in `admit_candidate` zelf, zodat elke aanroeper hetzelfde resultaat krijgt.
Supported runtime topologies: console met PostgreSQL-workflowopslag; opbouw via de bestaande dispatcher en worker; dezelfde code in beide.
Persisted-state impact: geen schemawijziging en geen backfill. Nieuwe objecten kunnen `metadata.admission.signals` bevatten; de sleutel ontbreekt wanneer er geen signalen zijn, zodat het record van bestaande objecten bij herberekening gelijk blijft. De canonieke hash sluit toelating uit.
Compatibility/migration plan: additief. Bestaande annotaties en objecten veranderen niet. Het oude formulier blijft bereikbaar tot slice 5.
Rollback/recovery plan: code terugdraaien. Objecten die onder de nieuwe regel met signalen zijn toegelaten, zijn herkenbaar aan `signals`; onder de oude regel worden zij bij herberekening weer kandidaat en vragen aanvulling in de annotatie. Geen dataverlies; wel werk. Daarom geen uitrol naar productie vóór de praktijkproef.
Cutover trigger: per slice een eigen PR; productie-uitrol pas na slice 3 en een praktijkproef met een echte richtlijn.
Cleanup/decommission criteria: het oude formulier en de vervallen invoervelden verdwijnen in slice 5, nadat de praktijkproef is geaccepteerd en geen open annotatie ze nog nodig heeft.
Failure blast radius: alleen kandidaten met `field_formation_mode` van menselijke annotatie. De beslisboomroute en historische AI-objecten houden hun regels.
Adversarial proof matrix: zie hieronder.

| Poging om de belofte te breken | Verwacht |
| --- | --- |
| Niet-menselijke kandidaat met ontbrekend gezegde | Blijft geblokkeerd |
| Menselijke kandidaat met een veld dat niet letterlijk in de bron staat | Blijft geblokkeerd |
| Menselijke aanbeveling zonder richting | Blijft geblokkeerd |
| Menselijke kandidaat met signaal én blokkerende code | Geblokkeerd; signaal apart vastgelegd |
| Herberekening van een bestaand toegelaten object | Identiek toelatingsrecord |
| Toelating via elke andere aanroeper (`revision_workflow`, console, contextreview) | Zelfde resultaat als via de opbouw |
| Annotatie gereedmelden met ontbrekend type | Geweigerd |
| Documentafsluiting met alleen signalen | Toegestaan; signalen in het overzicht |

## Slices

1. **Kern (deze PR):** signaalbeleid in toelating en inspectie; de controle-API
   geeft signalen apart terug; de kaart toont ze zonder afronden te blokkeren.
2. **Kaart:** drie regels (uitspraak, hoort erbij, onderbouwing); afleiding
   door Metis op de achtergrond; één vraag als het type ontbreekt.
3. **Review:** signalen als tekst op bestaande plekken van de reviewkaart.
4. **Contextvoorstel uit de omgeving.** Voorwaarde: meting van de
   voorstelkwaliteit (besluit 6).
5. **Opruimen:** oud formulier en vervallen invoervelden weg, na geaccepteerde
   praktijkproef.

Vóór merge van elke slice die toelating raakt: een aparte adversarial review
volgens `docs/agents/continuous-development.md`.

## Slice 2 uitgevoerd: de kaart met drie regels

De standaardkaart toont Uitspraak, Hoort erbij en Onderbouwing. De medewerker
selecteert tekst in de bron en kiest waar die voor is; Metis leidt type en
onderdelen op de achtergrond af met de bestaande voorstelquery. Dezelfde save,
controle en afrondregels worden gebruikt; er is geen nieuwe route of opslag.

- **Opslag van de drie keuzes in het bestaande contract:** de uitspraak als
  kernbereik; “hoort erbij” als contextbereik met de bestaande rol `context`,
  vastgelegd als essentieel; onderbouwing als bereik met functie `supported_by`,
  of de bestaande vlag `evidence_not_applicable`.
- **Label:** de medewerker ziet “Staat niet in de bron”; de opgeslagen vlag en
  de formulering op de reviewkaart zijn ongewijzigd.
- **Eén vraag bij uitval:** kan Metis het type niet bepalen, dan vraagt de kaart
  alleen het type.
- **Signalen** staan in de regel waar ze over gaan: “leunt mogelijk op andere
  tekst” bij Hoort erbij, “afgebroken zin” bij Uitspraak. Signalen voor de
  reviewer komen in slice 3.
- **Het stappenformulier** blijft bereikbaar via “Uitgebreid formulier openen”
  en wordt gebruikt voor bronstukken zonder uitspraak en voor zeldzame
  controlepunten. De keuze wordt per browser onthouden.

Open voor slice 5 (besluit nodig): het weghalen van gekoppelde tekst loopt nog
via de bestaande verplichting om opnieuw aan te wijzen of een reden te geven.
Die regel is vastgelegd in kernel en database en is hier niet gewijzigd.
