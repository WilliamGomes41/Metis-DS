# Brononafhankelijke beslisbomen — lokale uitvoering

Class A; stateful; Rewrite risk: high. Autorisatie: oorspronkelijk ontwerp van
1 oktober 2026, vervolgens “Oke lock en start”; herbouw lokaal expliciet toegestaan
met “Doe wat het beste is voor de code”. Vervolgens is GitHub-overdracht op een
aparte branch en draft-PR geautoriseerd. Geen merge of deployment.

De volledige oorspronkelijke ontwerptekst is gelezen uit Library
`libfile_8c67c233fd64819183d1d3ad913225de`; een tekstlezing staat buiten de repository
in `/workspace/scratch/metis-ontwerp-library-tekst.md`. Oude code is niet teruggevonden.

## Eigenaarschap en belofte

SourceSnapshot bewaart immutable bytes. WorkingRevision bezit policy, graaf,
objecten en exacte reviewbindings binnen de bestaande workflowopslag. Canonieke
releaseopslag bewaart de historische bevestigde representatie; het publicatieregister
blijft de enige serving-autoriteit. UI-toestand is niet autoritair.

De opt-in policy bevat een primaire bevoegde reviewer en optional/required
assignments. Iedere required deelnemer moet exact actueel goedkeuren; risico blijft
zichtbaar maar verandert deze expliciete keuze niet. Afwezige policy betekent
ongewijzigde legacyregels. Lidmaatschap en objectgebonden policyvelden zijn
controleerbare projecties, geen tweede beleidsbron.

De graaf onderscheidt entrypoints, antwoordkeuzes (single/multiple), onvoorwaardelijk
vervolg, routebewijs en terminale stappen. Bronvorm kiest de adapter, klasse de
interpretatie. Tekst zonder grafisch bewijs bevestigt geen route. Onopgeloste
routes, onbekende doelen en onverklaarde cycli blokkeren publicatie. Review bindt
exacte objectversies en graafhash; correcties invalideren geraakt bewijs.

## Overgangen en transacties

Ingest: geverifieerde bron schrijven, daarna envelope/policy/objecten/graaf samen
committen. Een mislukte commit publiceert niets. Een bron zonder document is geen
publicatie; geen destructieve opruiming.

Review/policy/graaf: bestaande snapshotbarrière en expected revision; wijzigingen
en audit gaan samen naar de bestaande workflowtransactie. Stale commands falen;
herhaalde identieke bevestiging maakt geen extra reviewer. Ontbrekende vereiste
review blijft `in_review`. Technische fouten na curatorafronding zijn `blocked`.

Publicatie: bestaand publisher-command, huidige bindings en bron opnieuw controleren,
gesloten werkrevisie plus complete release en registry-cutover atomair. Fout voor
commit houdt vorige release actief; lokale kopieën na commit zijn herstelbaar.
Een policywijziging heropent nooit gepubliceerde historie.

## Oppervlak en migratie

Bestaand pad: ingest → `_fragments_and_spec` → objectsetcommit → `review_object` /
`approve_second_review` → review closure/readiness → `consider_publish` → lokale of
PostgreSQL-publicatie → retrievalprojectie. Alternatieve paden: reextractie,
klassewijziging, directe objecthelpers, ASGI/CLI, SQL-badges, exports en herstel.

Expand/opt-in: bestaande JSON/legacyrecords behouden hun regels. Geen backfill,
geen verwijderen, geen parallelle database. Nieuwe policy vereist expliciete keuze.
Rollback schakelt nieuwe ingest uit met een lezer die de nieuwe records begrijpt;
geen oude binary over nieuwe data. Geen cutover of verwijdering van legacycode
zonder representatieve bronproeven en native PostgreSQL-ketenbewijs.

Failure blast radius: nieuwe/open werkrevisies; historische releases blijven intact.
Een adapterpatch alleen volstaat niet: onafhankelijkheid wordt in meerdere gates
afgedwongen en de huidige proseprojectie kent geen complete boomroutes.

## Bewijsplan

Synthetische bronfixtures: PDF-inleveren, letterlijke tekst/locators, routecorrectie,
gedeelde uitkomsten, multiselect en niet-Ja/Nee-labels. Single/optional/required:
passagereview plus graafreview, ontbreken van elke required deelnemer, dezelfde
persoon tweemaal, optional correctie, risico zonder verborgen verplichting.
Verder: stale wijzigingen, herhaalde acties, reextractie/bypasses, herstart,
policywissel, behouden v1 tijdens v2, mislukte publicatie, withdrawal en herstel.
Geen visuele Mantelzorg-PDF-claim zolang originele pixels niet zijn gecontroleerd.
De volledige acceptatie is pas bereikt met werkende UI/backend/persistentieketen
en afzonderlijke controle van alternatieve schrijvers/lezers.

## Acceptatiegrenzen van deze draft

De oorspronkelijke implementatie is niet gerecupereerd; dit is een herbouw vanaf
`d6fe3cbc3335d96256969d63e878de41468496d4`. Het Mantelzorg-PDF is inhoudelijk gelezen
in Library, maar de originele bytes konden niet worden overgedragen. De eerdere
71 onderdelen en 31 verbindingen zijn niet gereproduceerd. Geen live-cutoveradvies.

De PDF-adapter inventariseert tekstblokken en rechte vectorlijnsegmenten. Raster/OCR,
gebogen pijlen en automatisch gesplitste samengestelde uitkomsten zijn niet bewezen.
Menselijke route-invoer is mogelijk; automatische routevoorstellen uit PDF zijn
nog niet geïmplementeerd. Structurele keuze- en multiselectvalidatie is aanwezig;
er is geen klinische route-evaluator en de API geeft `applicability=not_evaluated`.

Een cross-model klassewijziging van een nieuwe graaf wordt vóór schrijven geblokkeerd
met `decision_graph_class_change_requires_successor`; een opvolgerworkflow voor
die conversie moet nog worden uitgewerkt. Policywijzigingen van gepubliceerde
werkrevisies zijn eveneens geblokkeerd. Dit voorkomt verlies van routebewijs.

Native PostgreSQL-ketenbewijs staat als optionele DSN-test klaar, maar is lokaal
niet uitgevoerd: de Docker Hub-pull werd geratelimit en het openbare ECR-alternatief
gaf Forbidden. Browserinteractie is alleen via HTTP-formuliertests gecontroleerd;
geen visuele acceptatie met de echte Mantelzorg-bron. Uitgebreide native
concurrency-/rollbackproeven en representatieve bronacceptatie blijven releasegates.
