# #836 — uitvoering van het goedgekeurde change-contract

Het volledige goedgekeurde contract staat in issue #836. Class A; Rewrite risk: high.
William heeft op 24 oktober 2026 expliciet akkoord gegeven en uitvoering toegewezen.

## Keuze en toegangspatronen

Twee vormen zijn vergeleken door dezelfde agent: gerichte JSONB-updates op de
documentenrij, en aparte records binnen dezelfde workflow-PostgreSQL-autoriteit.
De eerste behoudt TOAST-herschrijving, koppelt taakstatus aan documentbulk en
maakt pogingonafhankelijke uniciteit ingewikkeld. Daarom kiezen we aparte
records, met documentgebonden rijlocks voor mutaties en databaseconstraints.

De bestaande reservering, autorisatie, deadlines, dispatcher en activatie blijven
de domeinoperaties. De checkpointschrijver krijgt uitsluitend de taakdelta;
voorbereiding leest de exacte verwerkingscontext eenmaal en hervat uit de
gecommitteerde taakresultaten. Diagnostische replay gebruikt een geverifieerde
inputresolver. Alleen definitieve, gezamenlijk gevalideerde output mag door de
bestaande kandidaatmaker en activatiegrens.

| Gegeven | Producent / consument | Opslag en geldigheid |
| --- | --- | --- |
| Bron/extractie | bestaande bronvoorbereiding / validator | immutable snapshot + versie op record_hash; bron- en extractorcontrole |
| Inputartefact | voorbereiding / replay en taakhergebruik | referentie naar extractieversie + kleine validatorparameters; exacte inputhash |
| Poging en claim | bestaande reservering/dispatcher / checkpoint en activatie | eigen workflowrecord; actuele actor, bron/revisie, configuratie, deadline, token |
| Taakresultaat | lokale validatie / hervatten en eindpoort | immutable resultaat; uniek op inputartefact, semantische identiteit, exacte bronbereiken |
| Voortgang | taakcommit / UI | compacte afleiding; geen nieuwe autoriteit |
| Publicatie | bestaande publicatieoperatie / serving | ongewijzigde canonieke store en publicatieregistry |

## Gefaseerde uitvoering

1. Additief schema en gerichte store-operaties met native duurzaamheid/conflictproeven.
2. Contextversiegebonden writers/readers en expliciete migratie; oude gegevens blijven leesbaar.
3. Taakdelta's, lokale validatie, pogingonafhankelijke hervatting en replay/export aansluiten.
4. Crash-, concurrency-, migratie/rollback-, console- en schaalproeven en volledige controles.

Oude binaries mogen nieuwe-formatcontexten niet als leeg werk behandelen.
Rollback bewaart alle nieuwe records en gebruikt een compatibele binary of
blokkeert zulke contexten expliciet. Geen destructieve historische opschoning,
merge of deployment in deze opdracht.

## Bewijs dat fouten moet ontdekken

| Claim | Tegenproef | Vereist bewijs |
| --- | --- | --- |
| Gerichte checkpointkosten | steeds meer overige grote documenten en eerdere taken | nul archiefreads/globale lock; constante taakdelta, medianen/p95 |
| Duurzaam hergebruik | proceskill voor en na commit; nieuwe poging | na commit geen providercall voor geldig resultaat; vóór commit geen exactly-onceclaim |
| Fencing/autorisatie | oude token, verlopen poging, ingetrokken rol, gewijzigde bron/revisie | weigering zonder taak-/voortgangsmutatie |
| Exacte replay | vervangen extractieslot, corrupt/missend/incompatibel artefact | oorspronkelijke input terug of expliciete fout; geen stille herbouw |
| Eén eindpoort | veel taken, onderbreking, gerichte herstelversie | lokale taakvalidatie; gezamenlijke eindvalidatie op exacte resultaatset vóór activatie |

Status bij start: Ground en Sketch vastgesteld in contract; Agree voltooid.
Implementatie, verificatie en verwijderen van oude nieuwe-contextwrites lopen.
Nog geen acceptatie- of performanceclaim.

## Migratie- en releasebediening

Migration 021 breidt uitsluitend uit. Zet nieuwe contexten pas na schema- en
acceptatiecontrole aan met `METIS_FORMATION_TASK_STORAGE=v1`. Het ontbreken van
die instelling laat legacy-admission intact; bestaande `task-v1`-contexten blijven
door hun versie naar de gerichte store gaan. Geen impliciete historische cutover.

`python scripts/migrate_processing_attempts.py --snapshot-id SNAPSHOT` is een
dry-run voor één document. `--apply` verplaatst de pogingen atomair naar eigen
records, vergelijkt de volledige kopie vóór het verwijderen van de inline
projectie en blokkeert lopende/gepubliceerde revisies. Historische inline-input
blijft herkenbaar als legacy in het aparte pogingrecord; zij wordt niet als een
nieuw herbruikbaar taakresultaat gepromoveerd. Dit bewaart exact replaybewijs als
de toenmalige extractieversie niet beschikbaar is. Nieuwe pogingen slaan hun
input uitsluitend via de nieuwe geverifieerde verwijzing op.

Export v16 voegt `validator_inputs.csv` toe: eenmaal de exacte invoer per
artefact, terwijl de pogingen hun verwijzing behouden. De bestaande datasets en
privacygrenzen blijven behouden. v15-exports met inline-input blijven replaybaar.
De online replay, export en het offline replay-script gebruiken dezelfde resolver.

Rollback van admission: instelling verwijderen en deze compatibele binary blijven
gebruiken; bestaande nieuwe contexten behouden hun taakrecords. Een binary van
vóór #836 mag nieuwe contexten niet verwerken: een databaseguard weigert het
terugschrijven van een inline attempts-array of het terugzetten van de versie.
Geen destructieve down-migratie. Productiebackfill en deployment zijn niet uitgevoerd.

De bestaande expliciet bevestigde verwijdering van een ongepubliceerd snapshot
verwijdert ook zijn eigen taak-/inputrecords via foreign keys. Dit voegt geen
verwijderbevoegdheid toe; de bestaande bevestiging, titelcontrole, autorisatie en
bescherming van gepubliceerd werk blijven gelden. Andere documentmutaties
gebruiken pogingversies: een oude documentkopie kan nieuwere checkpoints niet
terugschrijven. Een stale worker mag evenmin de winnende poging op failed zetten.

## Uitgevoerd bewijs

De gerichte native proeven omvatten bron-/contractbinding, inputversie/corruptie,
replay/export, echte proceskill en een nieuw workerproces, pogingonafhankelijk
hergebruik, gerichte correctie na gezamenlijke afwijzing met bewaarde historie,
gelijklopende taakcommits, stale documentwrites, rol-/claim-/deadlinefencing,
budgets zonder nieuwe voortgang, GET naast een open checkpointtransactie en
de bestaande expliciete documentverwijdering.

Een geïsoleerde mutatie verwijderde alleen de source-hashguard. De bronfencingtest
faalde dan inhoudelijk met DID NOT RAISE; na herstel slaagde dezelfde proef.
Dit bewijst één concrete guard, geen algemene foutloosheid of onafhankelijke review.

De archiefproef gebruikt 1/10/100 overige envelopes van circa 1 MB en meet
10/50/100/130 taakcommits. Het oude pad leest bij 100 overige documenten circa
114 MB JSON per checkpoint; het nieuwe circa 7 kB en een constant queryaantal.
Tijden zijn lokale waarnemingen, geen productie-SLA.

De volledige opgenomen Smetten-validatorinput (867 inhoudsfragmenten en 1.040
bewijsfragmenten) is daarnaast exact gereconstrueerd op inputhash. De vergelijking
met 130 opgenomen taakidentiteiten is reproduceerbaar met een eigen tijdelijke
PostgreSQL-testdatabase via:

`python scripts/measure_recorded_checkpoints.py --evidence-zip EXPORT.zip --output RESULT.json`

Gebruik een door `scripts/test_postgres.sh` geleverde `METIS_TEST_POSTGRES_DSN`.
De proef maakt een eigen wegwerpdatabase. Zij herhaalt opslag en inputresolutie,
doet geen live modelaanroep of PDF-herextractie en bewijst geen klinische
volledigheid van Smetten. Die inhoudelijke eindacceptatie blijft onderdeel #837.
