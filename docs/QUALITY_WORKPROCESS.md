# Kwaliteit & werkproces

Instellingen → Kwaliteit & werkproces meet bestaand werk zonder extra registratie.
De meting adviseert niet over publicatie en verandert geen reviewbevoegdheid,
canonieke objecthash, Admission, vierogenregel of publicatiepoort.

## Domein en gegevensgrens

Een bronversie heeft nul of meer verwerkingsruns. Een vastgelegde run bindt de
bronhash, kandidaten met object-ID/versie/hash en hun oorspronkelijke inhoud,
feitelijke route en beschikbare extractie-/modelconfiguratie. Het bewijs wordt
in de bestaande envelope-transactie opgeslagen. Reviewbesluiten met bestaande
interactiebewijzen krijgen in dezelfde commit vergelijkingsbewijs. Correcties
krijgen een afzonderlijk gebeurtenistype, naast het bestaande revisiebewijs.

Deterministische, semantisch geselecteerde en resterende bronpassages blijven
onderscheiden. Een bron kan gemengd zijn; de direct-bruikbaarheidsmeting gebruikt
de route van het oorspronkelijke voorstel, niet de huidige omgevingsinstelling.
Semantische replay wordt als replay vastgelegd en is geen nieuwe modelaanroep.
Oude gegevens zonder bewijs blijven onbekend. Een cross-model-herverwerking
legt alleen de daadwerkelijk aanwezige route-/configuratiegegevens vast.

De weergave omvat alleen bronnen waarvan de aangemelde gebruiker uploader of
benoemde reviewer is. Ook een publisher krijgt hier niet automatisch alle bronnen.
De gegevens worden onder de bestaande store-lock gelezen; PostgreSQL gebruikt
één repeatable-read-transactie over de gebonden workflow stores. Alleen uniek
herleidbare legacy-events worden aan een bron toegeschreven. Herroepen toegang
verbergt eerdere rapporten met die bronnen. Geen ranglijst van individuele reviewers.

## Meetdefinities 1.0.0

- Direct bruikbaar: eerste inhoudelijke beslissing per oorspronkelijke kandidaat
  en run is goedkeuring, zonder verschil in tekst, type, kennisrelaties of
  aanbevelingsbetekenis en zonder tussenliggende objectversie. Uitstel en
  structuurbeoordelingen tellen niet mee. Teller, noemer en vergelijkingsdekking
  zijn apart zichtbaar; een onvolledige vergelijking geeft geen percentage.
- Menselijke beslisinteracties: bestaande review-interactie-ID's; een batch telt
  eenmaal, objectbesluiten afzonderlijk. Dit meet geen leestijd, klikken of alle
  menselijke inspanning. Legacy-besluiten zonder interactiebewijs blijven apart.
- Herstel: expliciete correcties en herstelverzoeken afzonderlijk. Gewijzigde
  velden, afwijzingen en correcties na een eerdere goedkeuring zijn signalen;
  zij bewijzen geen klinische fout of fout van een specifieke verwerkingsroute.
- Open werk: huidige niet-afgehandelde bronpassages, inclusief nog benodigde
  review volgens de bestaande ReviewDuty-logica. Leeftijd betreft de onafgehandelde
  bron sinds ingest, niet een verzonnen starttijd van de taak.
- Doorlooptijd: ingest tot eerste vastgelegde publicatie per bron. Geen exacte
  meting tot publicatiegereed zolang dat overgangstijdstip niet wordt vastgelegd.
- Inhoudelijke kwaliteit: geen score voor klinische correctheid. Zonder uniforme
  probleemclassificatie wordt de foutfrequentie als niet meetbaar gerapporteerd.

De periode selecteert het ingestcohort in UTC. Activiteit betreft het werk aan die
bronnen tot de gegevensgrens; open werk is een momentopname. Routeverschillen zijn
beschrijvend: verschillen in bronnen, risico en omvang kunnen de uitkomst verklaren.
Niet-geregistreerde fouten vóór een duurzame ingestcommit vallen buiten de telling.
Splitsen/samenvoegen krijgt zonder expliciete afstamming geen gegokte koppeling.

## Volledige rapportlifecycle

1. Openen van de pagina verzamelt een toegestane momentopname en filters.
2. De berekeningssleutel bindt gebruiker, invoer, filters, UTC-waarnemingsdag en
   definitieversie. Ongewijzigde invoer op dezelfde dag hergebruikt het rapport;
   de oorspronkelijke, exacte gegevensgrens blijft zichtbaar.
3. De aanvraag wordt duurzaam `requested`, daarna `running` met pogingnummer.
4. Succes wordt atomair `available`, inclusief bevroren invoer en resultaat.
   Beschikbare rapporten worden nooit herberekend of overschreven.
5. Een berekeningsfout wordt `failed`. De pagina toont geen fictief leeg succes.
   Opnieuw openen probeert dezelfde invoer opnieuw; eerdere pogingen blijven bestaan.
6. Exclusieve lokale bestandslocks of PostgreSQL advisory locks verhinderen een
   dubbele berekening. Een afgebroken proces verliest zijn lock. De volgende
   claimant bewaart de achtergelaten poging als `interrupted` en begint een nieuwe.
7. Gewijzigde invoer of meetdefinitie levert een nieuw rapport. Eerdere beschikbare
   resultaten blijven in de historie zichtbaar zolang de gebruiker toegang heeft.

Er is geen achtergrondworker, wachtrij of tweede workflowmotor. Berekeningen zijn
synchroon en afgeleid. Een nieuwe definitie gaat via code, tests en release; de
instellingenpagina kan de meetregels of autoriteitsregels niet veranderen.

## Opslag en uitrol

Lokale runtime: `quality_reports/`, meegenomen in de bestaande categorie
`derived_projections` voor backup/restore. PostgreSQL: additive migratie
`013_quality_measurements.sql`, opgenomen in de gecontroleerde migratieplanning.
De tabel bevat eigen rapporten en bevroren invoer; er is geen lokale fallback als
PostgreSQL onbereikbaar is of de tabel ontbreekt. De rest van de console blijft
bruikbaar en de rapportpagina meldt dat de meting niet beschikbaar is.

Terugrollen kan de pagina en de aanmaak van nieuw bewijs uitschakelen; bestaande
rapporten en aanvullende envelope-/ledgergegevens hoeven niet verwijderd te worden.
Gebruik voor opschoning de normale beheerprocedure; deze feature voert geen
verwijdering van rapporthistorie uit. Nieuwe meetdefinities vereisen een hoger
`DEFINITION_VERSION` en passende regressietests.

De implementatie bereidt code en migratie voor. Er is geen toestemming gegeven
voor migraties of deployment op de live omgeving.
