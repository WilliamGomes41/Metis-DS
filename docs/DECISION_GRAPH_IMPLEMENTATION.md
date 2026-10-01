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
interpretatie. Bij PDF bevestigt tekst zonder grafisch bewijs geen route; export-JSON gebruikt expliciete bronedges. Onopgeloste
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

De PDF-adapter inventariseert tekstblokken, rechte vectorlijnsegmenten en
Bezier-controlepunten. Hij stelt verbindingen voor op basis van verbonden
lijnsegmenten, pijlgeometrie en nabije letterlijke antwoordlabels. Ook omgekeerde
pijlen worden onderscheiden. Voorstellen blijven onbevestigd: ontbrekende richting,
ambigue endpoints/labels en benaderde krommen houden expliciete onzekerheid.
Er worden geen Ja/Nee-labels of verbindingen tussen pagina's geraden. Menselijke
invoer kan expliciete bronverwijzingen over pagina's heen bevestigen. De adapter
begrenst de geometrische zoekruimte; complexere pagina's blijven handmatig werk.

Policy- en klasseconversie van nieuwe grafen loopt via `create_review_successor`
en de knop "Nieuwe werkrevisie maken" op Reviewdeelname. Die hergebruikt exact
dezelfde bronbytes en bronversie, vereist reden en actuele voorgangerversie,
maakt nieuwe objectidentiteiten en nieuw reviewbewijs, en gebruikt de bestaande
`new_version`-lineage. Herhaalde identieke commands maken geen tweede opvolger.
Directe cross-model herschrijving van een bestaande graaf blijft geblokkeerd.
Legacy JSON blijft een bronadapter, ook voor een expliciete opvolger met een
andere klasse. De voorganger wordt nooit herschreven.

Lokale native tests gebruiken PostgreSQL 17.11 uit officieel ondertekende Debian-
pakketten, zonder systeeminstallatie, alleen een privésocket met peer-authenticatie.
De CI-topologie blijft PostgreSQL16; er is geen productietopologie verruimd.
Twee onafhankelijke workerruntimes oefenen gelijktijdige ingest en graaf/policy-
commando's uit. Opslagcomponenten delen de bestaande workflowtransactie; de
create-only lege expected revision wordt ook in PostgreSQL correct afgehandeld.

Resultaatbundels behouden een brongebonden container en afzonderlijke letterlijke
bulletleden. Ieder lid krijgt een eigen passagegoedkeuring; routecontext hoort bij
de bundel. De graafcontrole weigert losgekoppelde leden. Correctie van de bundelroute
invalideert ook de gekoppelde leden. De volledige release/API bevat de bundelbinding;
de proseretrieval blijft alle graafobjecten uitsluiten. Dit nieuwe gedrag geldt voor
PDF en expliciete export-JSON, zonder legacy-multibulletregels te herschrijven.

## Concrete bewijsgevallen en resterende acceptatie

Geautomatiseerde gevallen:

- Echte synthetische PDF: pijl omhoog/omlaag, letterlijk niet-Ja/Nee-label, lijn
  zonder pijlpunt, los lijnstuk en kromme met bewaarde controlepunten.
- Single en multiple choice, gedeelde uitkomst, expliciete paginaovergang;
  ontbrekende antwoorden, verzonnen label en cyclus blijven geblokkeerd.
- Lokale én native single/optional/required review met herstart, exacte
  passagegoedkeuring en afzonderlijke graafbevestiging.
- Native gelijktijdige policy/graafwijziging: één winnaar en één stale conflict;
  rollback na object-/auditwrites vóór outer commit laat alle oude staat intact.
- Native gelijktijdige identieke ingest: één snapshot; conflicterende retry faalt.
- Native v1 blijft actief tijdens v2, mislukte publicatie behoudt v1, geslaagde
  v2 schakelt de complete graaf om; historische policy/release blijft behouden.
- HTTP-formulieren voor graaf/policy/opvolger, authenticatie van graafuitlezing,
  404 na withdrawal en uitsluiting van boomobjecten uit losse proseretrieval.

Nog nodig voor volledige oorspronkelijke bronacceptatie:

1. De originele Mantelzorg-PDF-bytes in deze executor. Library-tekst is aanwezig,
   maar geen lokale bytes of visueel gecontroleerde pagina's. Geen nieuwe blinde
   downloadpoging. Kleinste input is de originele PDF hier als ondersteunde bijlage.
2. Visuele referentiecontrole van gedeelde Ja-uitkomst, Nee-vervolg, leeftijdsvraag,
   instructiestappen, paginaovergangen, multiselect op pagina4 en evaluatielabels
   op pagina5; bewijs dat iedere passage en route een disposition heeft.
3. Representatieve andere bronvarianten en beoordeling van correctiewerk; geen
   bulkverwerking. Raster/OCR blijft buiten scope. De nieuw toegevoegde splitsing
   van bulletuitkomsten naar afzonderlijk gereviewde leden van een resultaatbundel
   moet ook tegen echte bronlay-outs worden gecontroleerd.
4. Visuele browseracceptatie met de echte bron. PostgreSQL16-CI is inmiddels groen
   op Python 3.12 en 3.13. Geen productieacceptatie op basis van alleen synthetische fixtures.

Actuele negenpoortenmatrix, exacte testuitslagen, grenzen van native foutinjectie
en overdrachtsinformatie: [verificatierapport](DECISION_GRAPH_VERIFICATION.md).
