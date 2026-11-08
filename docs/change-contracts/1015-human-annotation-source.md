# HA-2a: bron aanwijzen en duurzaam hervatten

Change class: A
Promise: Een researcher bewaart meerdere exacte bronbereiken per annotatie in de bestaande WorkingRevision en hervat die selectie na herstart.
Proof: `tests/test_human_annotation_postgres.py`, inclusief HTTP, onafhankelijke consoleherstart en twee PostgreSQL-verbindingen.
Touches lifecycle invariants: yes
Rewrite risk: high

Opdracht: expliciete implementatieopdracht van William in deze sessie, 8 november
2026; #1013–1017/MET-57–61 zijn de inhoudelijke werkverdeling. Hun eerdere
"geen coding run gestart" beschrijft de ontwerpregistratie, niet deze opdracht.
Deze eerste expand-stap is geen GO voor de volledige productcutover.

## Betekenis en broncontract

Leidend: #986/MET-49: één expertise-eenheid met claim, context, bewijs en
herkomst. De eerdere zelfstandige definitie "kleinste stuk richtlijntekst" is
vervallen. Een blok is een extractie-eenheid, geen KO-grens. De eis uit
`semantic-only-formation.md` dat iedere prozaselectie van een model komt botst
met de nieuwe opdracht. Die eis blijft uitsluitend voor nog niet overgeschakeld
werk gelden; annotaties maken in deze expand-stap **geen** kandidaten.

Ankeridentiteit: snapshot + working revision + source SHA/version + immutable
prepared-extraction record hash + gereconstrueerd block-ID + halfopen codepoint-
interval. De bestaande `normalize_visible_prose` en `semantic_source_blocks`
bepalen de tekst, versie `metis-visible-prose-codepoints-v1`: whitespace wordt
samengevouwen; er vindt geen nieuwe NFC/NFKC-normalisatie plaats. Bestaande
historische offsets/hashes worden niet herberekend. De browser converteert
UTF-16 naar codepoints. Graphemegrenzen worden server-side gecontroleerd.

De browserquote is alleen een vluchtige controlegetuige. De server vergelijkt
exact op de aangegeven positie en bewaart alleen de SHA-256 van het segment;
geen quote-search of automatische herankering. Herhaalde tekst op een andere
geldige positie blijft selecteerbaar. Er komt geen nieuwe quote-export of
licentieaanname: bronweergave gebruikt de bestaande selectiebevoegdheid,
download dezelfde bestaande bronrechten. Nieuwe extractie vereist expliciet
opvolgwerk; een set verandert nooit stil van representatie.

Rollen zijn annotatievoorstellen: kern, doelgroep, context, voorwaarde,
uitzondering, toelichting, onderbouwing. Onderbouwing behoudt de bestaande
functies `supported_by` en `explains`, zonder nieuwe KO-taxonomie. De rol en
`required_for_meaning` horen bij de relatie binnen een entry; hergebruik van
een anker tussen entries behoudt afzonderlijke relaties. Gereed verlangt kern,
bestaand type en expliciet bewijs of een expliciete NVT-keuze; dit is geen
reviewbevestiging. Voorwaarden/uitzonderingen zijn hier bronrelaties. De latere
keuze A in deze sessie houdt die context bij dezelfde claim; zie het
[uitvoeringscontract](1015-human-annotation-execution.md). HA-2a maakt nog geen
kandidaatprojectie van dat besluit.

## Lifecycletransitie

Lifecycle entity: bestaande ongepubliceerde WorkingRevision met SourceSnapshot.
Lifecycle transition: ontvangen bron -> gepinde annotatie-invoer -> versies van afzonderlijke selecties.
Initial durable state: ontvangen bron met ingestpolicy, zonder gevormde objecten of lopende vormingspoging.
Trigger: researcher bereidt de annotatiebron expliciet voor en bewaart een selectie.
Authorization: bestaande actuele `source_selection_v1.authorize`; geen reviewerrechten uit annotatie.
Validation: bronbytes/hash, werkrevisie, objectrevisie, extractiehash, normalisatie, blok, offsets, quote, rol en entry/set-CAS.
Mutable entities: annotatiesetgeneratie en actuele entrypointer binnen workflow PostgreSQL.
Immutable entities: bronbytes, extractie, entryversies, commandresultaten, alle bestaande objecten, oordelen en releases.
Workflow state before: processing.
Workflow state after: processing; selectie gereed is geen review of documentafsluiting.
Release state before: geen release voor dit werk; eventuele voorganger blijft gelijk.
Release state after: ongewijzigd.
Serving state before: registrybepaald.
Serving state after: ongewijzigd.
Expected API result: gecommitteerde entryrevisie/setgeneratie; duplicate geeft hetzelfde resultaat; stale geeft 409 zonder writes.
Expected UI result: bron in leesvolgorde, afzonderlijke bereiken/rollen, hervatbare concepten, expliciet gereed, overzicht en correctielinks.
Failure result: vorige opgeslagen versie blijft geldig; geen vals opgeslagen-label of gedeeltelijke entry.
Restart result: dezelfde gepinde bron, entries en commandreceipts worden uit PostgreSQL gelezen.
Recovery result: opnieuw verzenden van dezelfde command; geen impliciete extractie op GET of alternatief kandidaatpad.
Legacy-data result: bestaande AI-werksets en publicaties ongewijzigd; geen automatische takeover.
Required black-box scenario: ontvangen -> voorbereiden -> twee bronbereiken -> concept opslaan -> nieuwe console -> hervatten -> gereed -> overzicht; stale en onbevoegde mutaties laten alle objecten en ingestpolicy intact.
Explicit non-goals: HA-2b seal/job/activatie, HA-3 objectcorrectie, HA-4 globale cutover/removal en praktijkacceptatie zijn hiermee niet gereed.

## Herschrijfrisico en eigenaars

Rewrite target: duurzame menselijke selectie-invoer vóór de bestaande kandidaatvorming.
Why local patching is insufficient: browserselecties zonder gepinde extractie, CAS en serveropslag verliezen werk en kunnen op een verkeerde bronversie worden toegepast.
Current authority/writer/reader map: hieronder.
Supported runtime topologies: productiecompositie `console_asgi.build_app`, beide complete workflow PostgreSQL-consoles; bronbytes bestaande lokale immutable store of Azure-store. Geen file-storealternatief voor annotaties.
Persisted-state impact: additieve workflowtabellen; rijgerichte actuele entrypointer, append-only entryversies/commandreceipts; geen document-envelopewrite per selectie.
Compatibility/migration plan: expand met migratie 034. Bestaand werk blijft leesbaar; nieuwe annotatiesets alleen via expliciete voorbereiding. Eén selectieowner per set; bestaande AI-reservering en directe `_fragments_and_spec` weigeren voor zo'n set.
Rollback/recovery plan: bestaande serving behouden; PostgreSQL weigert objectwrites en modelpogingen op betrokken sets, ook voor een oudere writer. Migratie 034 kent nog geen human activatievariant en faalt daarom gesloten; HA-2b moet deze fence vervangen door een exact seal-/proofcontract, niet door een callerflag. Geen backfill, destructieve migratie of oude AI-fallback. Voor release is activatiebewijs van HA-2b nog vereist.
Cutover trigger: deze stap schakelt alleen expliciet voorbereide, lege werkrevisies om; globale cutover pas na HA-2b/3/4-ketenbewijs en releasebesluit.
Cleanup/decommission criteria: tijdelijke coexistence eindigt in HA-4b; geen projectgereedmelding zolang de oude onderstaande ingangen bestaan. Deze PR verwijdert ze nog niet.
Failure blast radius: betrokken ongepubliceerde werkrevisie; geen object-/review-/publicatie-mutatie.
Adversarial proof matrix: duplicate/different payload; twee tabs; stale source/extraction/object revision; Unicode/grapheme; dubbele tekst; onbevoegd; rollback; herstart; directe oude formation-ingang; geen envelope/object-writes per save.

| Bestaande eigenaar/ingang | Schrijft/leest | Behandeling |
|---|---|---|
| `receive_source`/`ingest`, source store | snapshot, ingestkeuze, bytes | hergebruiken; annotatieprepare leest geverifieerde bytes |
| `_extract`, `source_preparation_context_v1`, `prepared_extraction_versions` | extractie en identiteit | hergebruiken; pin vóór selecteren, GET extraheert nooit |
| `source_selection_v1.reserve_selection`, dispatcher, `_execute_source_attempt`, retry/resume | poging en activatie | setownership afwijzen vóór oude uitvoering |
| `_fragments_and_spec`, strategies, reextract/class change | bron naar kandidaat | centrale fence voor betrokken snapshot; historische andere route nog aanwezig |
| `knowledge_materialisation_v1` | enige kandidaattekst/ID/mapping | geen wijziging of aanroep in HA-2a |
| `FormationTaskStore`, `formation_evidence_v1`, migration 029 | modelcontext/replay en activatie | menselijk bewijs vereist HA-2b; geen nepmodel/replay |
| `correct_object`, continuation, source-context review | revisies/context en invalidatie | bestaand werk intact; HA-3 sluit dezelfde editor aan |
| review policy, KO-transities en reviewbindings | exacte oordelen en deelnemers | ongewijzigd; annotatie schrijft geen oordeel |
| publication readiness, durable/Azure publication console, registry | publicatie en serving | ongewijzigd; annotaties geven geen publicatierecht |
| publieke API/MCP | registry-serving | ongewijzigd; nog geen human kandidaatset om te publiceren |
| settings route comparison, semantic safety, audit/replay | alternatieve modeluitvoering | aanwezig; volledige caller-/bypassinventaris en verwijdering verplicht vóór HA-4b |

De PStack-statechart van ontwerpbranch `1fb0e097` is gebruikt voor de scheiding
selecteren -> overzicht -> seal -> bouwen -> ingestreview. Zijn restart-stotterstap
en 80 modeltoestanden bewijzen geen databasecommit, autosave of menselijke bruikbaarheid.

## Nog afzonderlijk te bewijzen

Human FormationEvidence moet een echte versioned variant binnen de bestaande
root/FK/activatiegrens worden; de huidige `context_id NOT NULL` en replay-trigger
zijn geen human-bewijs. Geen activatie implementeren door die controles weg te laten.
Voor praktijkacceptatie zijn de bron/opdracht, inhoudelijke eigenaar en onafhankelijke
referentie bij de gebruiker uitgevraagd. Technische fixtures gelden niet als antwoord.

De fysieke contextkeuze uit #986/MET-49 is aan de gebruiker voorgelegd:

| Optie | Gevolg | Advies |
|---|---|---|
| Exacte rolbereiken als brongebonden context bij dezelfde claim | Een aangewezen voorwaarde/uitzondering wordt niet zonder afzonderlijk inhoudelijk besluit een zelfstandig KO | Aanbevolen; behoud één claim met volledige context |
| Afzonderlijke, zichtbaar gekoppelde kennisobjecten | Eigen inhoudelijke afbakening, identiteit, bewijs en review per zelfstandig object nodig | Houdbaar als #986 dit besluit; niet automatisch afleiden uit het markeren van een bereik |

De ingevoerde annotatieankers en rollen blijven bij beide opties bruikbaar.
William koos vervolgens A (“Ga met A door”): brongebonden context bij dezelfde
claim. Vastlegging en gevolg voor de verdere bouw staan in het
[uitvoeringscontract](1015-human-annotation-execution.md). De overige open
inhoudelijke vragen uit #986 worden daarmee niet als besloten beschouwd.

De caller-/recovery-inventarisatie vond vervolgens dat ketenback-up nog geen
annotatietabellen bevatte; procesherstartbewijs dekt dat niet af. De reparatie
heeft een eigen [Class A-herstelcontract](1015-human-annotation-recovery.md).
