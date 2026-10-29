# WP8 — actuele compacte Review-invoer

Change class: B. Rewrite risk: high. Touches lifecycle invariants: no.
Issue #905 / MET-26. Basis main `6b2374b`; WP7 is gemergd.

## Status van deze eerste stap

Geïmplementeerd: metadata gebruikt de bestaande transactioneel onderhouden
`review_read_envelope`; de Beginnen/Verder-link leest alleen distinct auditheaders.
Geen schemawijziging, nieuwe persistente facts of cutover van de kaartoracle.
WP8 blijft onvoltooid: de onderstaande facts-opzet is een ontwerprichting,
geen geïmplementeerde of geaccepteerde afleiding.

Native bewijs: een afzonderlijk gecommitteerde corrupte archiefenvelope laat
de oude metadataquery falen; dezelfde read gebruikt met de wijziging uitsluitend
de intacte compacte invoer. Herhaalde 64-KiB auditdetails (32/128 events) leveren
dezelfde afzonderlijke actorbeslissingen en minder dan 5 KiB headers op na
een nieuwe runtimecompositie. Beide PostgreSQL-productietopologieën en de
nullable legacyprojectie zijn afzonderlijk getest. Dit begrenst overdracht;
SQL moet nog iedere geselecteerde
eventpayload inspecteren. Het is geen claim dat alle database-I/O historie-onafhankelijk is.

Twee afzonderlijke read-only adversariële reviews vonden geen correctnessdefect
in deze beperkte wijziging. Zij toetsten triggeractualiteit, alternatieve
store-/fallbackroutes, reviewerconsistentie, actorprecedentie, paginering en
de bestaande auditindex. Voor de latere facts-cutover blijft de volledige
writer-, generatie-, bron- en restart/rollbackmatrix hieronder vereist.

## Vastgelegd bronbesluit voor de resterende kaartprojectie

William heeft op 29 oktober 2026 expliciet gekozen voor actuele kaarttellingen
uit de geverifieerde retained extractie en actuele reviews. De oorspronkelijke
bron wordt volledig gecontroleerd bij openen/beoordelen. Op de kaart moet
duidelijk zijn dat die bron daar niet opnieuw is gecontroleerd. Commands en
publicatie behouden hun bestaande volledige broncontrole. Dit besluit geldt
voor de latere kaartcutover; deze eerste wijziging verandert die telling nog niet.

`review_work_item` roept `review_source_fragments` aan. Die methode verifieert via
`_verified_source_bytes` de volledige oorspronkelijke bytes en hun checksum.
Bij ontbreken of mismatch vervallen contentduties in de bestaande oracle.
De bronstore biedt `load_verified`, geen goedkoop bewijs dat dezelfde bytes
nog aanwezig zijn. Azure `probe` vermeldt expliciet dat existence geen
checksumverificatie is; `overwrite=False` is geen WORM-/blobversioncontract.
Een oude geldige bronproof plus actuele existence/size kan vervanging door
andere bytes van gelijke lengte dus niet onderscheiden.

Exacte pariteit bij bronverwijdering/-corruptie én geen bronbytes lezen is
onder het oude contract onmogelijk. Het bovenstaande besluit lost dat conflict
op zonder een nieuwe bronstoregarantie te verzinnen: kaarttellingen houden
actuele reviews bij de exacte retained extractie, ook als de oorspronkelijke
bron tijdelijk niet beschikbaar is. Een bronproof verleent nooit toestemming
om te beoordelen of publiceren.

## Ground → Sketch → Agree → Implement → Scrap

Ground: workboard en navigatie laden alle objectversies, alle bindings en bronviews;
dezelfde ReviewDuty/source_accountability/projectie beslist daarna. De kaartpagina
pagineert metadata vooraf, maar verrijkt vervolgens ieder zichtbaar document diep.
`current_revisions` controleert volledige strikte afstamming; `max(position)` is
zonder bewijs geen vervanging. Exacte reviewhash omvat bijna alle objectinhoud.
`object_generation` mist legacy- en binding-only-wijzigingen.

Sketch: twee afzonderlijke bestaande agents onderzochten dynamische compacte SQL
(A) en duurzaam geverifieerde neutrale feiten (B). Geen cross-modelclaim. A alleen
kan bronmapping en exacte hashes niet controleren zonder de weggelaten inhoud.
B alleen mag geen gesynchroniseerde persoonlijke kaart-/goedkeuringsdatabase
worden. Gekozen: dynamische actuele metadata/governance/bindings/actor met kleine,
geverifieerde object-/bronfeiten bij dezelfde workflowstore. Kaartbeslissingen
blijven in de bestaande Python-eigenaren; geen tweede SQL-reglement.
Agree: uitvoering van de volgende WP is expliciet opgedragen door William.
Implement: eerst onnodige metadata-/auditarchiefreads verwijderen; daarna alleen
de werkelijk noodzakelijke bewezen feiten en hun actuele selectie verdiepen.
Scrap: herontwerpen bij een tweede lifecycleautoriteit, verborgen GET-herbouw of
volledige accountabilityberekening tijdens iedere save.

## Gebruik en eigenaarschap

```python
# Read: één consistente actuele capture, alleen zichtbare documenten.
inputs = document_store.review_card_inputs(visible_snapshot_ids)
# Bestaande kaartoracle consumeert expliciete geverifieerde invoer.
item = review_work_item(console, account=current_account, envelope=envelope,
                        inputs=inputs[snapshot_id])
# Write: bestaande store valideert en schrijft facts met dezelfde objectwrite;
# binding-only/policy/rollen blijven actuele read-time invoer.
```

ReviewObjectFacts is een expliciete read-only invoerdrager, geen synthetisch
verkort object dat opnieuw wordt gehasht en geen commandinput. Een bronproof
bevat alleen bron-/tekst-/mappingvalidatie bij exact dezelfde immutable extractie;
nooit approved, complete, remaining of actorstatus. Volledige commands en closure
houden volledige objecten en bronvalidatie. De kaart verleent geen toestemming.

## Context en actualiteit

| Gegeven | Producent/eigenaar | Geldigheid | Ontbrekend/verouderd |
| --- | --- | --- | --- |
| Objectinhoud/hash | integrity kernel + bestaande documentstore | Exact native JSONB-invoerfingerprint en producercontract | Geen actuele kaart suggereren |
| Bronproof | bestaande bron-/mappingvalidators + WP7 | Exacte extractie/source/viewcontract en volledige primitive input | Geen reconstructie op GET |
| Huidige versie/afstamming | current_revisions + documentstore | Volledige gevalideerde chain, technische readgeneratie voor alle SQL-mutaties | Expliciet onbeschikbare afleiding |
| Bindings | bestaande reviewstore | Actuele capture; dezelfde exacte tuple-/menselijke-reviewerregels | Geen gecachte approval |
| Policy/context/rol | bestaande eigenaren | Actuele endpointgegevens, wederkerige links, live actor/account | Geen actor×document-persistentiestatus |
| Deelnamepresentatie | bestaand audit | Alleen relevante eventheaders; zelfde beslissingspredicate | Geen auditdetails voor een begin/verder-link |

Alle runtime objectschrijvers: concurrent apply_review_changes/write_bundle,
runtime write_bundle en legacy import. Dezelfde afleiding moet atomair volgen.
Binding delta, snapshot/whole binding replacement en backfill blijven live inputs;
ze hoeven geen objectgeneratie te bumpen. Directe SQL-governance/bindingwijzigingen
moeten actueel zichtbaar zijn; onverwachte canonical/history-SQL-mutatie moet een
oude afleiding aantoonbaar ongeldig maken. Invalidation alleen is geen voltooiing
voor een ondersteunde runtimewriter. Beheer-SQL mag geen stale kaart als current
laten gelden. De geïmporteerde legacytoestand vereist expliciete voorbereiding.

## Grenzen en mitigatie

Stateless gedrag: persoonlijke readprojectie. Afgeleide opslag, indien nodig,
is niet-authoritatief en alleen kernel/workflowstore bezit onderhoud. Durable
state vóór/na: dezelfde bron/objecten/reviews plus reproduceerbare readfeiten.
Transaction boundary: authoritywrite en bijbehorende facts/selectie atomair.
Failure/recovery: vorige geldige authority behouden; ontbrekende feiten zichtbaar,
geen fictieve nul, geen GET/startup-backfill. Idempotentie: identieke exacte input
geeft dezelfde bewijsidentiteit. Concurrency: actuele snapshot plus gecontroleerde
facts; nieuwere writers winnen, oude voorbereiding mag niet activeren.

Rewrite target: workboard/navigation readgrens. Lokale HTML-patches verwijderen
bronvoorbereiding niet. Topologieën: beide CompleteWorkflow PostgreSQL-composities,
nieuwe processen/herstart; appbron lokaal/Azure. Persisted impact: alleen additieve
niet-authoritatieve facts waar nodig. Migratie: expand, expliciete voorbereiding,
alle writers bewijzen, dan gecontroleerde readercutover. Oude reader blijft
expliciet rollbackpad; geen stille deep fallback op nieuwe incomplete projectie.
Cleanup: documentbrede verrijking en auditpayloadreads uit overgezette route.
Blast radius: kaartpresentatie, geen review-/publicatiebevoegdheid of bronmutatie.

## Bewijsplan

De eerste CI-run van PR #923 stopte bij het machineleesbare wijzigingscontract:
de PR-beschrijving miste losse `Proof`, `Touches lifecycle invariants` en
`Rewrite risk`-velden. Daardoor werden de suite-shards overgeslagen en faalden
de verzameljobs wegens ontbrekend testbewijs. De beschrijving is gecorrigeerd
en met `python scripts/validate_change_contract.py --text-file <PR-body>`
daadwerkelijk rood/groen gecontroleerd. Deze check vereist de PR-tekst;
repository_preflight alleen bewijst het PR-contract niet.

De daaropvolgende volledige suite vond op Python 3.12 én 3.13 dezelfde ene
fout in `test_metadata_page_bounds_existing_enrichment_and_history_reads`:
de pagineringstest telde alleen calls naar de vervangen archiefreader. Het
meetpunt volgt nu de compacte participatiereader, met dezelfde aantallen én
exacte document-ID's voor pagina 1/2. Een call naar de volledige archiefreader
laat de test expliciet falen. Native reproductie: eerst rood; daarna alle
negen persoonlijke-overzicht-/compacte-invoertests groen. Geen productiecode
of domeinverwachting gewijzigd door deze testreparatie.

Native HTTP-pariteit met de bestaande volledige oracle voor verschillende
reviewers, eerste/tweede review, wachten/eigen klaar, herstel/disposition, partial
formation en boom/graph. Tegenvoorbeelden: binding-only legacywriter zonder
counterbump, gewijzigde policy/rol/context/target, historische bron-/hashmutatie,
ontbrekende/corrupte facts, concurrente voorbereiding/writer, nieuw proces en
rollback. Vast paginavenster bij groeiende onafhankelijke documenten en zware
historie; meet kaart-, audit- en bron-I/O afzonderlijk. Geen source_prepare,
volledige historie/bron of GET-writes verbergen achter kleine interfaces.
Bestaande POST/lockbudgetten blijven gelden; #888/MET-17 houdt runtime/SLO-eindacceptatie.
