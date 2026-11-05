# KO-1: één afgeleide toestand per kennisobject (#995)

`src/review/knowledge_object_state_v1.py` leidt per huidige objectrevisie één toestand af uit de statechart. Er wordt niets geschreven.

De autoriteiten blijven waar ze zijn:

| Wat | Waar |
|---|---|
| Goedkeuring | Bindingen in `workflow.publish_authorizations`, via `review_stage` |
| Reviewoordeel | `metadata.review_passage` en `passage_register` |
| Release | De canonieke publicatietabellen, via `document_release_serving_status` |

## Velden naar toestand

De regels worden van boven naar beneden gelezen. De eerste regel die past, geeft de toestand.

| # | Voorwaarde | Toestand |
|---|---|---|
| 0 | Document, kop, bronrecord (`candidate_lifecycle` is `structure` of `source`) of een `path` in een beslisboom | geen kennisobject |
| 1 | `validation_status = superseded` | Vervangen |
| 2 | `validation_status = rejected` | Afgewezen |
| 3 | `validation_status = revise` (oude werkwijze) | Kandidaat, plus `legacy_revise_persisted` |
| 4 | `approved` en de eerste review is nog open | In review, plus `approved_without_current_binding` (geen geldige binding) of `approved_mirror_with_open_first_review` (wel een) |
| 5 | `approved` en de tweede review is open | Tweede review |
| 6 | `approved` en de release van het document is `published`, `superseded` of `withdrawn` | Gepubliceerd, Vervangen of Ingetrokken |
| 7 | `approved` | Goedgekeurd |

Bij elke `approved`-rij wordt de exacte huidige binding apart gecontroleerd, ook als er geen open reviewstap is, bijvoorbeeld omdat de bronverwijzing niet meer klopt. Zonder binding volgt `approved_without_current_binding`, wat de toestand ook is.
| 8 | `candidate_lifecycle = materialisation_failed` | Kandidaat |
| 9 | Toelating noemt `context_necessary_unresolved` | Context open |
| 10 | Toelating geblokkeerd om een andere reden | Kandidaat |
| 11 | Geen voorgestelde of bevestigde `supported_by`- of `explains`-relatie | Bewijs open |
| 12 | De eerste review is open | In review |
| 13 | De tweede review is open | Tweede review |
| 14 | Anders | Samengesteld |

Regel 11 volgt het besluit van 5 november 2026: bewijs is verplicht voor elk type.

De uitweg "niet van toepassing" bestaat nog niet. KO-4 voegt die toe als vastgelegde keuze.

## Ongeldige combinaties

| Code | Betekenis |
|---|---|
| `approved_without_current_binding` | De spiegel zegt `approved`, maar er is geen geldige binding op deze exacte revisie |
| `approved_mirror_with_open_first_review` | De spiegel zegt `approved` en er is nog een geldige binding, maar de eerste review is weer open, bijvoorbeeld na het vervangen van de eerste reviewer |
| `approved_with_passage_not_assessed` | Goedgekeurd terwijl de passage nog `not_yet_assessed` is |
| `legacy_revise_persisted` | Er staat een opgeslagen `revise` |
| `second_review_mirror_disagrees` | De spiegel `governance.second_review` zegt klaar, maar de bindingen niet |
| `approval_outside_suitability` | Een goedkeuring bij een geschiktheid die goedkeuren uitsluit |
| `register_disagrees_with_review` | De passage-registratie wijkt af van de beoordeelde geschiktheid |
| `disposition_invalid` | `definitive_review_disposition` is ongeldig |

Eén combinatie meet KO-1 bewust niet: "gepubliceerd maar niet goedgekeurd". Daarvoor is het publicatieregister per object nodig, en dat komt in KO-3 (#991, besluit per object).

## Telscript

```bash
python scripts/ko_state_inventory.py --counts-only        # regels
python scripts/ko_state_inventory.py --counts-only --json # één JSON-object
```

Het telscript gebruikt `compose_console()`, dezelfde opbouw als `build_app`, maar zonder opstartmigratie of reconciliatie. Elke PostgreSQL-sessie start met `default_transaction_read_only=on`.

Het telscript drukt alleen tellingen af. Exitcode 2 betekent dat een kennisobject geen toestand kreeg.

## Bewijs in deze PR

- `tests/test_ko_state_derivation.py` heeft één geval per toestand en per ongeldige code, plus deze checks:
  - elke toestand is bereikbaar;
  - de afleiding schrijft niets;
  - de tellingen bevatten geen id's;
  - de vijf losse "finaal"-sets zijn gelijk aan de ene definitie.
- `tests/test_ko_state_derivation_postgres.py` loopt door de echte console:
  - verse ingest;
  - goedkeuring;
  - de volledig beoordeelde fixture;
  - publiceren, herstarten en intrekken;
  - het telscript zelf;
  - een schrijfweigering van de alleen-lezen-sessie.

## Bevinding voor KO-4

Na een verse ingest van de continentie-fixture is de verdeling: Kandidaat 1, Bewijs open 2, en de rest 0.

Zonder gekoppelde onderbouwing staat dus het merendeel in Bewijs open. Draai daarom eerst dit telscript in productie, en beslis daarna of bestaande objecten onder de oude regel vallen, voordat KO-4 de wachter afdwingt.

## Regressie

De regressie draaide over de 76 testbestanden die `console_asgi`, `build_app`, de reviewplicht, de "finaal"-sets, `candidate_lifecycle` of `definitive_review_disposition` raken. Uitslag: 1412 geslaagd, 19 overgeslagen, 3 gefaald.

| Gefaalde test | Oorzaak | Stand |
|---|---|---|
| `test_dead_code_removal_v1` | Een redencode droeg de naam van een verwijderde functie | Hersteld in 43c12ad; slaagt nu |
| Twee `test_wave_c_deploy_packaging`-gevallen | Lokale kloon mist de volledige geschiedenis; het pakketscript weigert dan bewust met `console_build_requires_full_history` | CI heeft de volledige geschiedenis |
