# Publicatiebewijs — diagnostics slice 4

Deze diagnose wijzigt geen publicatievoorwaarden of domeintoestand. De canonical
publication store bewijst een opgeslagen release; de publication registry bepaalt
of de exacte objectversies actief zijn. Een publicatierespons en een logmelding
zijn geen vervanging voor deze lezingen.

## Een document observeren

Een ingelogde publisher kan bij Publiceren **Publicatiebewijs downloaden** kiezen,
of rechtstreeks deze beheerroute gebruiken:

`GET /source-selection/publication-evidence?document=<snapshot_id>`

Dit werkt onafhankelijk van het berekenen van de volledige publicatiepagina.
De route leest het geselecteerde document, de release en maximaal 2048 actieve
objecttuples. Zij reconstrueert geen bron en voert geen review, herstel of
publicatiecontrole uit. Uitval van de registry verbergt een reeds waargenomen
canonical release niet. Een niet-beschikbare authority wordt expliciet gemeld.

Het bestand bevat read-timestamps, runtime/build-identiteit, snapshot, bronhash,
revisiehash, release-ID en exacte object-ID/versie/hash-tuples. Geen broninhoud,
accountnamen, opslaglocators of exceptionteksten. Onafhankelijke lezingen worden
omsloten door controles maar vormen geen atomair database-moment.

## Eén dossier

```sh
python scripts/export_section_incident.py \
  --publication before.json \
  --publication-after-restart after.json \
  --publication-route route.json \
  --output new-incident-directory
```

De bestaande `--browser`, `--application`, `--platform`, `--processing` en
`--evidence` blijven bruikbaar. Meegeleverd browserbewijs heeft voorrang op het
browserdeel uit route.json. Verwerkings- en blokkadebewijs worden op snapshot en
bronhash gekoppeld, nooit alleen op tijd. Bij een afwijkende context blijft de
integrale claim geblokkeerd. De export overschrijft geen bestaande directory.

Alle JSON-invoer heeft de bestaande grens van 8 MiB. Itemsets bevatten maximaal
2048 unieke objecten; ongeldige/oversized sets worden geweigerd. Invoerhashes staan
in incident.json. De exporter bewaart alleen compacte identiteit en uitslagen,
geen ongeredigeerde route-invoer. Bewaar de originele beveiligde observaties volgens
de bestaande incident-retentie; de exporter introduceert geen eigen bewaartermijn.

## Aanvullend routebewijs

`route.json` heeft schema `publication-route-evidence-v1`. Dit is vastgelegd
verificatiebewijs, geen door diagnostics verleende uitvoeringsbevoegdheid.

| Veld | Vereist bewijs |
| --- | --- |
| snapshot_id, source_hash, review_revision_sha256 | Exacte document- en reviewidentiteit |
| browser_incident | Slice-1 incident voor /publish: bruikbaar, respons gekoppeld via request-ID, zonder ontbrekend/tegenstrijdig bewijs |
| reviewed_items | Exacte publiceerbare object-ID, object_version, content_hash uit de gecontroleerde reviewcontext |
| readiness | Bestaande backendcontrole: publication_ready en publish_allowed waar, blockers leeg, revision_sha256 en observed_at |
| publish_command | Vastgelegde status PASS, dezelfde release/snapshot/bron/revisie, request_id, started_at en finished_at |
| product_readbacks | Twee echte Product HTTP-readbacks met status 200, synthetic_fixture false, release-ID, exacte items, observed_at en waargenomen runtime_id; vóór en na procesherstart |

De commandtijd moet de canonical published_at omsluiten, readiness gaat vooraf,
en de authority/readback-waarnemingen volgen. Een andere runtime_id plus een
latere waarneming is nodig voor procesherstartbewijs. Een nieuw console-object in
hetzelfde proces telt daarvoor niet. De exacte release en objecttuples moeten na
de herstart gelijk blijven. De Product API mag in een ander proces draaien dan
de console; koppeling berust op release en exacte tuples, niet op gelijke proces-ID’s. Gekopieerde of gemanipuleerde operatorgegevens worden
niet cryptografisch geauthenticeerd door de projector; die bewijsgrens staat in
ieder rapport.

`end_to_end_proven` is uitsluitend waar als al deze controles slagen. Bij gewone
observatie ontbreken browser, command/reviewbinding en Product HTTP terecht.
Een inactieve historische release kan bestaan zonder dat zij nog wordt uitgeleverd.
Een verloren HTTP-respons kan samengaan met een al opgeslagen canonical release.
Controleer daarom eerst opgeslagen toestand vóór een publicatie opnieuw uitvoeren.

## Verificatiegrens

De regressies gebruiken een representatieve HTML-bron, bestaande review/gates,
publicatie, retries en de echte console- en Product-ASGI-routes. Zij injecteren
canonical/source teststores; dit bewijst de toepassingsroute, geen native
PostgreSQL/Azure-transactie of productieherstart. De tests onderscheiden nieuw
console-object en echte procesidentiteit expliciet. Productieacceptatie vereist
nog een gecontroleerde representatieve bron en vastgelegd restart/readbackbewijs
op de bedoelde deployment. Er wordt geen productiepublicatie gestart door tests.

### Publicatiegrenzen automatisch verbinden

POST /publish heeft dezelfde aanvraagdiagnostiek als de bestaande verwerkingsopdracht.
Onder het bestaande publicatieslot schrijft Metis best-effort `publication_checked`,
`publication_submitted`, `publication_committed` en `publication_completed`. Het
bestaande controleresultaat wordt hergebruikt; er wordt geen tweede gate aangeroepen.
De records bevatten compacte identiteit en exacte aangeboden tuples. Telemetriefalen
maakt een geldige publicatie niet ongedaan. Ontbrekende records blijven een bewijsleemte.

Met `--application application.jsonl` verbindt de exporter deze vier grenzen op de
exacte aanvraagidentiteit, bron, revisie en release. Bij meerdere passende aanvragen
is `--request-id <id>` noodzakelijk. Dubbelen, ontbrekende grenzen, weggelaten items
of een ongeldige volgorde worden geen complete publicatieverklaring. Deze opgenomen
grensrecords hebben voorrang op handmatig aangeleverde readiness/command-gegevens.
De bestaande route-input blijft nodig voor echte Product HTTP-readbacks; het
browserincident wordt vanuit de bestaande `--browser`-keten toegevoegd.
