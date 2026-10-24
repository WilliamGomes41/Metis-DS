# Bronselectie: kleine duurzame projectie en korte overzichtstransactie (#835)

Change class: B
Promise: Het overzicht leest actuele compacte metadata zonder de envelope of pogingenhistorie; volledige detaildecodering vindt buiten de korte overzichtstransactie plaats, ook naast checkpoints.
Proof: Native idle-timeoutreproductie, grote payloads, geauthenticeerde GETs naast echte checkpoints, backfill/rollback en adversariële proeven.
Touches lifecycle invariants: no
Rewrite risk: high

## Herclassificatie vóór implementatie

William heeft in de review een samenvattingskolom, detaillezing buiten de korte
transactie en het stoppen van diagnostiekduplicatie voorgesteld. De eerste twee
horen in deze PR. Duurzame inputreferenties horen bij #836: replay_diagnostic
vereist volledige input. Alleen de hash bewaren zou dit gedrag breken. De
envelopegroei zelf wordt dus niet opgelost door #835.

De eerste queryoptimalisatie was Class B / risk none. Voor de afgeleide kolom
en gedeelde writergrens is #835 vóór implementatie heringedeeld naar B / high.

Rewrite target: de bestaande Bronselectie-projectie en haar actualisering bij documentwrites.
Why local patching is insufficient: éénmalig uitpakken blijft de volledige groeiende envelope lezen; de korte transactie bevatte bovendien volledige detaildecodering vóór een volgende query.
Current authority/writer/reader map: workflow.documents.envelope_payload en document_reviewers blijven autoriteit. De legacy importer, RuntimeStore.write_bundle/_write_document_row, ConcurrentStore.write_bundle en releaseprojection-writer, plus directe SQL-writes, schrijven deze tabel. Eén PostgreSQL-trigger onderhoudt de afleiding. list_source_selection_summaries en summary_projection/estimate lezen haar. Commands, dispatcher, bronrepresentaties, review/publicatie/serving behouden hun owners.
Supported runtime topologies: beide FastBadge CompleteWorkflow PostgreSQL-composities, concurrente store en één/twee workers per instance; bestaande lokale of Azure immutable source-adapters; geen file-workflowfallback.
Persisted-state impact: nullable JSONB-afleiding op workflow.documents, versiegebonden functie en trigger; geen wijziging van envelope-inhoud, objectrevisies, bronidentiteit, reviews of releases.
Compatibility/migration plan: additief schema+trigger terwijl de oude binary actief blijft, expliciete batchbackfill en dan readercutover. Oude writers onderhouden de afleiding ook. Ontbrekende/incompatibele projecties zijn fouten; geen envelopefallback of GET-backfill.
Rollback/recovery plan: vorige binary blijft dezelfde oorspronkelijke velden lezen/schrijven; laat kolom en trigger staan. Document en projectie rollen samen terug. Backfill is herhaalbaar en slaat gelockte rows over met expliciet remaining > 0. Geen destructieve down-migratie.
Cutover trigger: schema aanwezig, backfill gereed, native equivalentie/autorisatie/concurrency groen; productiecutover uitsluitend via afzonderlijk geautoriseerde release en livecontrole.
Cleanup/decommission criteria: actieve overzichtsquery leest geen envelope/pogingenhistorie en heeft geen oud fallbackpad. Bewaar rollbackcompatibiliteit; fysieke verwijdering is afzonderlijk later werk.
Failure blast radius: ontbrekende/stale metadata kan overzicht/status/toegang verstoren. Atomiciteit, versiecheck, trigger op directe projectiewrites en actuele reviewer-crosscheck beschermen dit. Projecties autoriseren geen commands.
Adversarial proof matrix: gewone/directe writers; gefingeerde projectie; JSON-null/reviewer-mismatch; rollback; ontbrekende projectie; dry-run/herhaalde/gelockte backfill; identieke envelope/objectrevisies; grote diagnostiek; native idle-timeout; checkpointrowlock naast GET; GET-mutatietelling; ondersteunde overrides en volledige suite.

## Actueel ontwerp

Migration 020 voegt alleen kolom, afleidingsfunctie en trigger toe. De trigger
werkt bij INSERT en UPDATE van envelope_payload of de projectiekolom. Ook oude
binaries en directe SQL-writers onderhouden dus dezelfde afleiding; een poging
om uitsluitend de projectie te vervalsen wordt overschreven.

De projectie bevat bron/configuratiemetadata, voortgang/tellingen, alleen de
laatste poging en kleine begintijd/eindtijdparen van geslaagde initiële ingests.
Die behouden exact de waarnemingen voor de bestaande schatting. Failed/resume-
historie, validatorinput, fragmenten, voorstellen en diagnostiek ontbreken.
named_reviewers behoudt de oorspronkelijke JSON-nullbetekenis en wordt opnieuw
tegen document_reviewers gecontroleerd. De oorspronkelijke envelope blijft de
autoriteit; de projectie is uitsluitend afgeleide presentatie-invoer.

source_selection_documents sluit zijn read-only REPEATABLE READ-transactie na
de compacte lijst. Het gekozen document wordt daarna geladen en geautoriseerd.
Detailhergebruik, revisies en verse commandcontroles blijven bestaan. De 5s SQL-
en idle-limieten worden niet verruimd. De veilige expliciete foutoorzaken uit de
eerste draft blijven behouden, zonder messages, SQL, parameters of broninhoud.

## Migratie, cutover en rollback

1. Houd de vorige binary actief. Pas migration 020 toe in één expliciete
   transactie. Dit voert geen backfill of envelopeherschrijving uit.
2. Controleer de bestaande workflowdatabaseconfiguratie met
   `python scripts/backfill_source_selection_summary.py` (standaard dry-run).
3. Voer alleen met de bestaande expliciete migratieautorisatie uit:
   `python scripts/backfill_source_selection_summary.py --apply --batch-size 32`.
   Iedere batch heeft een eigen transactie. remaining > 0 door gelockte rows
   vereist expliciet herhalen; dat geldt niet als een voltooide backfill.
4. Controleer nul ontbrekende projecties en equivalente geautoriseerde output.
   Deploy daarna pas de nieuwe reader via de normale releaseprocedure.
5. Rollback gebruikt de vorige binary met kolom/trigger behouden. Verwijder geen
   bron-, review-, publicatie- of projectiegegevens.

Geen schema-, backfill- of deploymentactie is op productie uitgevoerd. Geen
startup-/GET-backfill. Gepubliceerd werk behoudt inhoud, identiteit en rechten.

## Actueel lokaal bewijs en beperkingen

Op main 6cf0dc4 wordt een geselecteerde GET rood met native
IdleInTransactionSessionTimeout / SQLSTATE 25P03. De fixture bevat grote
historische diagnostiek. Een gecontroleerde Pythonpauze tussen rowontvangst en
reviewerquery overschrijdt alleen in de test de verkorte idle-grens van 100ms
(pauze 300ms). Dit bewijst het mechanisme, niet de historische requestoorzaak.
Na de correctie is dezelfde GET 200.

Een andere proef houdt drie echte checkpointwrites via _diagnostic_writer en
StoreCommand vóór hun buitenste commit vast. Beide pagina's worden telkens
gelezen terwijl de rowlock bestaat: zes GETs 200, geen workflow-DML vanuit GET,
en de schrijver commit de juiste voortgang. Lokaal PG16: overzicht 0,022–0,026s;
detail 0,213–0,216s. Dit zijn metingen, geen SLA. De overzichtsfixture leest 10
buffers versus 5.587 op de oorspronkelijke query; de SQL-regressie verbiedt
envelope_payload en processing_attempts in de overzichtsquery.

De volledige suite-uitkomst en finale codeversie worden in de PR vastgelegd.
Eerdere groene uitslagen bewijzen de schema-uitbreiding niet. Productieacceptatie
en de oorspronkelijke PostgreSQL-fout blijven open. Het stoppen van de bulk-
duplicatie vereist de duurzame inputreferenties uit #836 en is niet uitgevoerd.

<details>
<summary>Historisch bewijs van de eerste draft, vóór de nieuwe reviewopdracht</summary>

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

</details>
