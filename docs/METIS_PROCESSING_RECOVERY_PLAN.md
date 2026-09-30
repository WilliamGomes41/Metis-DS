# Herstelplan: controleerbare brongebonden verwerking

Gestart op verzoek van de gebruiker; eerste implementatieopdracht #464.
Doel: bruikbare, exact brongebonden reviewpassages, niet een hoger aantal
ongecontroleerde voorstellen. Menselijke review blijft verplicht.

## Vastgesteld en nog onbekend

De onderzochte verwerking bevat 56 structurele objecten, 2 semantische voorstellen
(beide geblokkeerd op type_evidence_missing) en 167 coverage_remainders. Expliciete
aanbevelingen, DOEN, NIET DOEN en niveaulabels staan bij resttekst. V2 registreert
brongebonden veldbewijs; dat bewijst geen betere selectiedekking. De oorspronkelijke
modelinput en ruwe output zijn in deze historische export niet vastgelegd.
De oorzaak van de beperkte selectie is dus nog niet bewezen.

Aanvullende diagnose (#470): de oorspronkelijke PDF is teruggevonden en haar
SHA-256 is `2185b6502a76b76e942db2352d746a5f1193645091844fd84241dfb94ac51064`.
Herextractie levert 202 kandidaatblokken en 283 bewijsblokken. De gecombineerde
hash `5b32b417da3efd05575cdf839375b6f97048a519f6ccfe9dc84e681c2e5213ff` is exact
gelijk aan de inputhash in het opgeslagen runbewijs. De aanbeveling over de
eenzaamheidsschaal is aanwezig in die invoer; het opgeslagen voorstel bevat twee
selecties. Dit lokaliseert het selectieprobleem, maar verklaart niet waarom het
model die twee koos. De historische ruwe providerrespons ontbreekt.

Het v2-request licht nu alle betekenisvelden toe en vraagt beoordeling van alle
bronblokken, zonder steekproefselectie of vrije veldtekst. Een expliciete
niet-voltooide providerstatus wordt geweigerd vóór toepassing. De bestaande
prompt/schemahash voorkomt hergebruik van een voorstel onder het oude contract.
Dit is geen bewijs van verbeterde inhoudelijke dekking: een echte modelproef
en menselijke vergelijking blijven vereist.

Integrale vrijgave: #465, #468, #469 en het selectiewerk horen bij één herstel;
geen van deze afzonderlijke PR's is een deploymentadvies. Eén eindcontrole moet
inleveren, bronbinding, labelcontext, review, publicatie, herverwerking,
verwijdering en herstart afdekken. Reviewerbevestigde broncontext is nu gebouwd
onder het contract van #474; native ketenbewijs wordt op het definitieve PR-head
opnieuw uitgevoerd. De daadwerkelijke modelproef en menselijke referentie staan
apart beschreven in `docs/EENZAAMHEID_SEMANTIC_ACCEPTANCE.md` en blijven open.
De expliciete opdracht om de code af te ronden en te mergen wordt uitgevoerd na
de technische en lifecyclecontroles. Het ontbrekende inhoudelijke bewijs blijft
in #470 staan; de code-merge verklaart het selectieherstel niet inhoudelijk
geaccepteerd en veroorzaakt geen productie-deployment.

## Stap 1 — uitgevoerd door #464

Nieuwe geslaagde semantische runs bewaren bij het bestaande replayrecord:
het exacte requestpayload zonder transportheaders, samengevoegde output_text,
response-ID/status en input/outputtokenaantallen indien geleverd, aanvraagmoment
en deploymentmarker indien geldig. Geen credentials, reasoning of willekeurige
providerconfiguratie. De outputtekst is niet de volledige ruwe HTTP-response.
Verwerking zonder volledig valide voorstel bewaart via dit pad geen bewijs.
Dit is nadrukkelijk geen log van alle pogingen, fouten of eerdere runs.

Stateful Class B, rewrite risk none: observaties reizen mee met de bestaande
spec/envelopecommit. Geen nieuwe store, transacties, publicatiebeslissingen of
achtergrondjobs. Exacte replay behoudt oorsprongsbewijs en maakt geen nieuwe call.
Historische records zonder evidence blijven not_recorded; geen backfill.

CSV v3 verwijst met snapshot_id + revision_id naar revision.csv. Die tabel bewaart
het oorspronkelijke opaque objects_revision eenmaal, zonder het te veranderen.
De bestaande in-memory projector en MCP behouden hun objects_revision-contract.
model_calls blijft uitgesloten van MCP. De bestaande exportautorisatie geldt.
De origin call is aan proposal_hash gekoppeld; een historisch run_id wordt niet
geraden. De export stelt geen transactionele historische pipeline-snapshot voor.

Bewijs bevat dezelfde brongegevens als het document en valt onder de bestaande
documenttoegang en retentie; er komt geen publieke of afzonderlijke opslagkopie.
Zolang geen afzonderlijk runarchief is ontworpen, bewaart dit slechts het bewijs
van het laatste opgeslagen voorstel. Een nieuw voorstel kan dat vervangen.

## Vervolg 2 — selectieoorzaak vaststellen en gericht herstellen

- Verkrijg de oorspronkelijke PDF en controleer haar bronhash.
- Maak een menselijke referentieset van expliciete aanbevelingen en bronlocaties.
- Volg extractie, reconstructie, daadwerkelijk aangeboden blokken, antwoordstatus,
  voorstelvalidatie, veldbinding en toelating op dezelfde bron/configuratie.
- Controleer invoerbegrenzing, onvolledige antwoorden, verworpen voorstellen en
  criteria voor kandidaatselectie. Geen prompt/modelwijziging zonder diagnose.
- Leg voor onderbroken en mislukte pogingen een apart duurzaam lifecyclecontract
  vast voordat hiervoor writes worden toegevoegd. Ontwerp begrenzing, bewaartermijn
  en herstel; historische ontbrekende informatie blijft onbekend.
- Herstel het bewezen verliespunt. Typebewijs blijft verplicht; unclassified is
  onbeslist. Geen automatische aanvulling van ontbrekende sterkte of veldtekst.

## Vervolg 3 — bronrollen en contextkoppelingen

Eerste presentatieverbetering (#466): passageoverzicht, broncontext en
passage-export geven bij losstaand DOEN, NIET DOEN en Niveau 1–4 een afgeleide
hint `possible_source_label`. Dit is geen opgeslagen bronrol, bevestigd besluit
of koppeling. Tekst, taken, tellingen en toelatingsregels blijven gelijk.
Andere korte tekst wordt niet verborgen of automatisch als label aangemerkt.
Voor onbevestigde fragmenten blijft deze hint bestaan. #474 voegt de expliciete
reviewerbeslissing toe: label/context/niet opnemen, met letterlijke brontekst,
bronposities, bronhash, reviewer, reden en exacte doelversies. Veranderde context
maakt doelpassages opnieuw needs_review en trekt eerdere reviewbindings in.
CSV, MCP en canonieke publicatie bewaren hetzelfde objectbewijs. Geen aparte
relatiestore of automatische toekenning. Zie `docs/SOURCE_CONTEXT_REVIEW_CONTRACT.md`.

Bronfragmenten blijven exact behouden. Kop, bronlabel, inhoudelijke passage en
onbesliste tekst zijn verschillende rollen. Geen minimumwoordenaantal als filter.
Bronlabel is geen zelfstandig kennistype. DOEN is niet automatisch sterk en NIET
DOEN wordt niet gewist. Niveaulabels krijgen alleen een formele betekenis wanneer
de bron het stelsel expliciteert.

Voorstel -> bevestigen/corrigeren/afwijzen door bevoegde reviewer, met bronpositie,
doelpassageversies en reden. Een label kan meerdere passages omvatten. Nabijheid
alleen is geen bewijs, vooral bij tabellen/kolommen. Onzekere labels blijven werk;
bevestigde labels worden bij de passage getoond. Relevante tekstwijziging maakt de
koppeling opnieuw beoordeelbaar. Resttekst blijft vindbaar en is niet automatisch
beoordeeld of ongeschikt.

## Vervolg 4 — documentlifecycle en begrijpelijke status

Class A zodra reviewclosure/readiness verandert. Werk- en reviewtoestand blijven
in workflow PostgreSQL; bronbytes in immutable source store; historische releases
in canonical publication store; serving uitsluitend in publicatieregister.
Console-local state is uitsluitend reconstructeerbare presentatietoestand.

Processing -> in_review wanneer voorbereiding volledig is vastgelegd. Open
curatorbesluiten zijn geen technische blocked-status. Toon technische uitvoering,
formaatvalidatie, bronbinding, inhoudelijke toelating en menselijke review apart.
Een geslaagde modelcall mag geen claim van volledige inhoudelijke dekking worden.

Besluit + relatie + objectversies + revisie + auditbewijs committen atomisch.
Verwachte revisie voorkomt overschrijven; dubbele opdracht is idempotent. Bij fout
geen half besluit. Restart behoudt toestand; recovery maakt geen nieuwe review- of
publicatiebeslissing. Publicatie sluit de WorkingRevision met exact beoordeelde
teksten/context. Onopgeloste betekenisrelevante koppelingen verhinderen readiness.

Gepubliceerde data blijft immutable. Correcties krijgen een expliciete opvolgende
WorkingRevision. Bestaande release blijft actief tot atomische opvolgerpublicatie
of intrekking. Bewijs van ingetrokken of vervangen releases blijft bewaard en
herstart mag ze niet activeren. Geen herclassificatie bij deployment/startup.

Voor iedere Class A implementatieissue moeten alle lifecycle-VSA velden uit
docs/agents/lifecycle-vsa.md concreet zijn ingevuld, inclusief autorisatie,
begin/eindtoestand, API/UI, concurrency, fout/herstart/herstel en legacybewijs.
Dit document vervangt die contracten niet.

## Legacy, migratie en rollback

Legacy wordt de presentatie van ieder restant als gelijksoortige inhoudelijke
reviewkaart, niet het bewaren van de bron. Geen automatische herverwerking van
open werk en geen stilzwijgende overdracht van goedkeuringen bij gewijzigde context.
Verwijderen/opnieuw uploaden is geen standaard herstelpad. Fysieke bronverwijdering
moet afzonderlijk via bestaande opslag- en verwijderbewijzen worden geverifieerd.

Herstel #467 verplaatst bronopruiming naar ná de zelfstandige workflowcommit.
Rollback vóór commit mag nooit externe bronbytes verwijderen. Een bestaande
buitenste workflowtransactie wordt vóór de delete geweigerd: een savepoint is
geen definitieve commit. Cache-opruimfouten na commit herstellen geen verwijderd
document. Een crash tussen commit en cleanup kan ongebruikte bronbytes achterlaten;
automatische orphan-cleanup of een retry-outbox is hiermee niet geïmplementeerd.
Geen nieuw deletebeleid, migratie of automatische bronverwijdering bij startup.
Adapter-/transactiedoubletests en de eerdere native PostgreSQL-CI bewijzen de
volgorde; ook de finale gezamenlijke branch moet de native proeven opnieuw halen.

Stap 1 vereist geen databasewijziging. CSV v3 is expliciet versiegebonden: oude
v2-consumenten moeten de revisiejoin ondersteunen. Bestaande v2-exports blijven
v2. Bronrol/context is additieve objectmetadata zonder SQL-migratie of historische
backfill. Bij downgrade mag oude code nieuwe contextrevisies niet publiceren;
behoud JSONB/auditbewijs en hervat pas onder de nieuwe validator. Geen destructieve
omzetting. Activeer volgende stappen eerst in een gecontroleerde proef. Rollback
stopt nieuwe verwerking onder nieuw beleid maar wist geen besluiten of publicaties.

## Acceptatie voor het gehele herstelprogramma

- Referentieaanbevelingen gevonden of een expliciete beoordeelbare uitkomst.
- Alle broninhoud traceerbaar, geen nieuwe modeltekst in kennisvelden.
- Labels exact bij correcte passage(s), twijfel zichtbaar en typebewijs verplicht.
- Gedeeltelijke uitvoering niet als volledig resultaat gepresenteerd.
- Review, export, API en MCP stemmen overeen met dezelfde durable authority.
- Dubbele opdrachten, gelijktijdige writes en herstart behouden correcte toestand.
- Publicatie -> restart -> beleidsupgrade -> opvolgerreview -> atomische publicatie
  -> restart -> intrekking -> restart houdt alle lifecycle-invarianten intact.
- Historische ontbrekende evidence blijft ontbrekend.

Stap 1 afronden betekent niet dat dit gehele programma of de selectie is hersteld.
