# Bronselectie: overzichtsquery en behoud van databaseoorzaken (#835)

Change class: B
Promise: Bronselectie leest dezelfde actuele compacte metadata met minder
herhaalde JSONB/TOAST-lezingen, en behoudt bij een databasefout veilige
oorzaakgegevens gekoppeld aan de bestaande request-ID.
Proof: native PostgreSQL-bufferregressie, echte geauthenticeerde HTTP-route,
gecontroleerde SQL-cancellation, reviewerautorisatie en bestaande consoleproeven.
Touches lifecycle invariants: no
Rewrite risk: none

## Opdracht en programmaontwerp

Onderdeel 1 van de expliciete structurele herstelopdracht van William. Deze PR
implementeert uitsluitend #835. Taakopslag, aanbevelingenprioriteit, hergebruik,
workeroverdracht en definitieve bronvorming behoren tot onderdelen 2–6.

De bestaande route is selection_get → source_selection_documents →
workflow_read_transaction → list_source_selection_summaries → PostgreSQL →
summary_projection → HTML. workflow.documents en document_reviewers blijven de
autoriteit. De bestaande read-only REPEATABLE READ-transactie, SQL-time-outs,
documentvolgorde, autorisatie en expliciete detaillezing blijven intact.

De query gaf al compacte output, maar gebruikte afzonderlijke JSONB-operatoren
op dezelfde grote, gecomprimeerde envelope. Daarmee wordt de TOAST-payload
herhaaldelijk gelezen en gedecomprimeerd. jsonb_to_record haalt de benodigde
velden eenmaal uit de bestaande payload; projectie en tellingen blijven in SQL.
Reviewerwaarden blijven op de oorspronkelijke JSONB-waarde gecontroleerd:
expliciete JSON null mag niet veranderen in een lege, geldige reviewercollectie.
Geen cache, schemawijziging, nieuwe autoriteit of fallback.

De HTTP-handler behield uitsluitend de generieke ConsoleError-code. Alleen bij
workflow_document_unavailable gebruikt hij nu bestaande exceptiondiagnostiek.
Die neemt maximaal vier expliciete oorzaken mee, met gevalideerde typen,
SQLSTATE en bestaande in-repository frames. Geen exceptiontekst, SQL, parameters,
broninhoud, lokale variabelen of impliciete exceptioncontext. Normale foutcodes
en HTTP-responses blijven gelijk.

## Vooraf bepaalde bewijsgrenzen

- Grote synthetische attemptdiagnostiek moet werkelijk in PostgreSQL TOAST staan.
  EXPLAIN ANALYZE/BUFFERS begrenst herhaalde payloadlezingen zonder een kwetsbare
  vaste millisecondenassertie. De oude query faalt deze controle.
- Een echte geauthenticeerde GET levert HTML zonder grote diagnostiek en verandert
  de opgeslagen envelope niet.
- Een echte native QueryCanceled onder dezelfde leesroute blijft HTTP 400 met
  dezelfde publieke code, en wordt met SQLSTATE 57014 en request-ID vastgelegd.
  Dit is gecontroleerde foutinjectie, geen reproductie van de historische oorzaak.
- Corrupte reviewerwaarden blijven geweigerd. Bestaande proeven dekken actuele
  rechten, geselecteerde details, gelijktijdigheid en read-only transacties.
- Secret/source-canaries, expliciete cause-cycli en de bestaande telemetryexport
  toetsen begrenzing en geheimhouding.

## Meting en historische onzekerheid

Dezelfde oorspronkelijke en aangepaste query zijn lokaal vergeleken op de vijf
attemptdiagnostics uit de aangeleverde Smetten-export. Alleen meetuitkomsten
worden vastgelegd; de bron-/diagnostiekpayload wordt niet in Git opgenomen.

| Pogingen | JSON-omvang | Buffer-toegangen vóór → na | SQL-uitvoering vóór → na |
|---|---:|---:|---:|
| 1 | 3.291.730 bytes | 1.111 → 334 | 34,507 → 12,154 ms |
| 3 | 11.481.040 bytes | 4.011 → 1.204 | 119,818 → 55,416 ms |
| 5 | 18.224.280 bytes | 6.321 → 1.897 | 189,269 → 85,743 ms |

Dit zijn lokale PostgreSQL 17.11-metingen, één document, warme gedeelde buffers;
geen Azure-latentiebewijs. De uiteindelijke query behoudt de originele strikte
reviewercontrole. Een eerdere experimentele variant las ook die velden eenmaal,
maar veranderde expliciete JSON-nullafhandeling en is daarom niet overgenomen.

Request 4788453f74934d52acf3226e55a3b00f is in de aangeleverde telemetrie gevonden:
18:17:25.447–18:17:43.033 UTC, HTTP 400 na 17,586 s, waarvan 15,249 s onder
document_list. De oorspronkelijke PostgreSQL-exception/SQLSTATE ontbreekt.
Het vensterarchief bevat geen PostgreSQL-serverlogregels; het overzicht vermeldt
dat serverlogdownload uitstaat. Dit bewijst geen afwezigheid van andere logging.

De lokale test met die gegevens overschrijdt de bestaande 5s-querygrens niet.
De bufferregressie en het verlies van oorzaakgegevens zijn bewezen defecten;
de exacte historische productieoorzaak en herstel daarvan blijven ONBEWEZEN.
Geen verhoging van time-outs of retries om dat te maskeren. #835 blijft open.

## Verificatie en rollback

De eerste twee gerichte regressies falen op 6cf0dc4: herhaalde payloadlezingen
(5.587 buffer-toegangen bij een fixturegrens van 1.960) en ontbrekende causes bij
een native cancellation. Na de reparatie slagen deze proeven. De uitgebreide
gerichte set slaagt: 105 passed, geen skips, inclusief Chromium en native PG17.
De volledige suite en de PostgreSQL 16-controle worden afzonderlijk vastgelegd
in de PR; deze paragraaf claimt die nog niet.

Rollback is het terugdraaien van de applicatiewijziging. Er zijn geen duurzame
writes, schemawijzigingen, migraties of gegevensconversies. De vorige binary kan
dezelfde gegevens lezen. Productieacceptatie vraagt na een afzonderlijk
geautoriseerde deployment een geauthenticeerde GET tijdens representatieve
verwerking, met requestcorrelatie, feitelijke laadtijd en behouden autorisatie.
Geen merge of deployment in deze run.
