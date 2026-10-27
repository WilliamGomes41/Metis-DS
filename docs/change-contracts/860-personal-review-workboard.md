# #860 — persoonlijke Review-werkvoorraad

Change class: B
Rewrite risk: none
Touches lifecycle invariants: no
Promise: De reviewer vindt eigen uitvoerbaar werk met één zichtbare primaire actie per document; wachten en geen actueel eigen werk staan apart.
Proof: Gemengde native fixture, twee actors, native/objectpariteit, onveranderde GET-state en geen extra readers/deep calls; echte browser breed/smal/toetsenbord.

## Ground

Basis main `0758ec16cabcf2230e0983c035d823e506e926b4`, na gemergde #871;
#859 is gesloten. #860 is expliciet toegewezen en na voorbereidende triage
`ready-for-agent`; geen blocking labels. Alleen deze slice, geen #861,
merge, deployment, productiemutatie of automatische doorstart.

`GET /review` wordt door `install_review_workboard` geregistreerd. De landing
`_workboard_page` selecteert/filtert/pagineert metadata, verrijkt alleen zichtbare
documenten via bestaande `review_workboard_summaries` /
`_enrich_review_workboard_summaries`, en gebruikt dezelfde `review_work_item`
als het objectpad. Objecten/bindings worden al batchgewijs geladen;
`review_work_projection` blijft eigenaar van duties/actorroute.

Huidig: primaire acties zitten achter document-disclosures en twee verschillende
dashboard-renderpaden. De kaarten mengen documentbrede voortgang, actorroute,
bronwerk en deelnemers. `started` bevat activiteiten van alle actors. Koppen
kunnen de primaire prozaactie verdringen, hoewel ze in Vorming thuishoren.

## Sketch → Agree

Echte onafhankelijke read-only verkenningen: `/root/review860_a` en
`/root/review860_b`. Gedeelde skillreferenties en Linear-agentnotes waren niet
leesbaar via de provider; hoofdskills en actuele repositorycontracten wel.

| Vorm | Correctheid / leespatroon / grens / bewijs |
| --- | --- |
| Bestaand verrijkt werkitem → één vlakke persoonlijke kaart | Gekozen: geen nieuwe query, corpuspassage, cursor of routebeleid; beide bestaande paden tonen dezelfde betekenis |
| Nieuwe actor-voortgangsprojectie met eigen totaal/afgerond | Verworpen: bestaande progress/knowledge_progress zijn documentbreed; rejection/superseded/policy/graaf maken een nieuwe persoonlijke noemer ongedefinieerd |

Geen persoonlijk percentage of afgehandeld/totaal-aantal tonen dat de bestaande
gegevens niet onderbouwen. Alleen actuele persoonlijke open duties tellen.
"Geen open werk voor jou" betekent geen huidige inhoudelijke Review-actie;
het is geen uitspraak over ieders review, bronafhandeling of publiceerbaarheid.
Wachten op de primaire of onafhankelijke reviewer blijft apart. Geen nieuwe
numerieke policy-wachtteller afleiden uit de second-review-only wachtcounter.

Gebruik bestaande task-hrefs: contextual/batch/second_review en structure voor
echte boom/path-duties. Behoud de bestaande graaf-override. Prozakoppen,
bronbestemming en herstel komen niet in de primaire Review-selectie. De huidige
relatieve inhoudelijke volgorde blijft intact; geen eerste-objectselector,
begin/resume-endpoint, redirectlaag of opgeslagen cursor.

De ledgerlezing voor zichtbare documenten bestaat al. Filter diezelfde activiteit
op huidige actor (expliciete reviewer-ID indien aanwezig, anders username/ID)
voor Beginnen/Verder beoordelen. Activiteit is geen geldigheidsbewijs en wordt
niet als persoonlijke voltooiing geteld.

Scope blijft de zichtbare/gefilterde pagina. Geen globale leegclaim op basis van
alleen die pagina en geen verrijking/sortering van onzichtbare documenten.
Zoek-/thema-/paginering en huidige autorisatie blijven behouden.

Implementatie is opgedragen; geen extra goedkeuringscheckpoint.

## Interface en invarianten

- Bestaande `review_work_item`/samenvattingen blijven ongewijzigde invoer.
  Een kleine pure landingpresentatie kiest tekst/groep/href uit bestaande velden;
  geen domeinstatus of writer. Hergebruik `_workboard_card` als formatter.
- Hoofdteller: `actionable_review_duties`, niet documentbrede `review_duties`.
  Eerste = dezelfde persoonlijke open populatie minus tweede. Prozakoppen zitten
  niet in deze hoofdteller; boom/path-duties behouden hun bestaande betekenis.
- Gesloten immutable werk krijgt geen primaire Review-actie, ook bij legacyrijen.
- Behoud kernel, policy, bevoegdheden, bindings, bron-/kandidaatidentiteit,
  revisie-, publicatie- en servingregels. Geen durable state verandert;
  stateful Class B-overlay is daarom niet van toepassing.
- Geen extra objectscan of route-/bronberekening; geen tweede ledgerreader.
  Verwijder ongebruikte deelnemersnamenlezing samen met de rosterpresentatie.
- Historische task-GETs, commands, detail-, batch- en bronopeners blijven bij
  dezelfde eigenaren. Alleen de primaire landing wordt vereenvoudigd.

## Implement → Scrap / bewijs

1. Ongewijzigde native baseline voor werkbord/duties en leesgrenzen.
2. Gemengde fixture: contextual, batch, eerste-policywachten, tweede beoordeling,
   eigen geldige goedkeuring, afgewezen/vervangen, bronwerk/herstel/kop, lege voorraad.
   Per actor verwachte object-ID's vastleggen; geen screenshotgetallen als taken.
3. Native summary en objectpad vergelijken. Bindinginvalidatie verandert de
   relevante persoonlijke toestand. GET laat envelope/objecten/bindings/ledger gelijk.
4. Calls/queries vergelijken; onzichtbare pagina niet verrijken. Bewijs dat de
   primaire actie zichtbaar is zonder disclosure en de bestaande werkroute opent.
5. Echte browser desktop/mobiel/keyboard, feitelijk beoordelen → refresh →
   persoonlijke teller daalt, andere actor wacht correct. Verplichte repochecks/CI.

Vervang de oude inline dashboards/disclosures in dezelfde PR; geen concurrerende
landingformatter of handmatig gesynchroniseerde tweede tellercatalogus. Als een
nieuwe geldigheids-/prioriteitsregel of gedeelde lees-/schrijfgrens nodig blijkt:
stop en herscope, niet passend maken met nieuwe opslag of een omweg.

Exact gecontroleerde SHA, uitgevoerde controles en bewijsgrenzen komen in de PR.

## Uitgevoerd acceptatiebewijs

De native fixture gebruikt de productiecompositie met PostgreSQL 16, bestaande
brongebonden selectie/materialisatie en echte reviewcommands. Eén beperkte
fixtureseed vertegenwoordigt reeds opgeslagen superseded/blocked rijen; dit is
geen tweede productkandidaatmaker en geen productwriter. De browser gebruikt
dezelfde fixture en echte HTTP-reviewformulieren.

| Document | Actor A | Actor B | Betekenis |
| --- | --- | --- | --- |
| Gemengd | 2 eerste beoordelingen | wachten op primaire reviewer | Exact de twee benoemde kandidaat-ID's; reject/superseded/blocked/kop/restbron uitgesloten |
| Wachten | wachten op onafhankelijke reviewer | 2 tweede beoordelingen | Dezelfde objectversies met A's geldige bindings |
| Klaar | geen open beoordeling | geen open beoordeling | Beide hebben geldige exacte goedkeuringen; geen publicatieclaim |
| Bronwerk | geen open beoordeling | geen open beoordeling | Bronafhandeling blijft open; geen Review-voortgang van maken |
| Vergelijkbaar | 1 eerste beoordeling via batch | wachten op primaire reviewer | Optionele deelname verandert de bestaande policy niet |

Na A's echte goedkeuring in Gemengd: A heeft 1 eerste beoordeling, B heeft
1 tweede beoordeling. B krijgt Beginnen, hoewel A al heeft gehandeld. Intrekken
van de exacte binding in de geïsoleerde fixture en herstart geeft A opnieuw
2 eerste beoordelingen en B wacht. GET/refresh houdt envelopes, objecthistorie,
bindings en ledger gelijk. Een niet-toegewezen actor ziet de expliciete lege voorraad.

De lokale callvergelijking laadt uitsluitend de oude `_workboard_page` van basis
`0758ec16cabcf2230e0983c035d823e506e926b4` in dezelfde testcompositie en vergelijkt
met de nieuwe landing, met dezelfde vijf documenten en één readscope:

| Bestaande aanroep | Basis | Wijziging |
| --- | ---: | ---: |
| review_workboard_summaries | 1 | 1 |
| _enrich_review_workboard_summaries | 1 | 1 |
| list_current_objects_batch | 1 | 1 |
| read_bindings | 1 | 1 |
| review_source_fragments | 5 | 5 |
| read_events_for_snapshots | 1 | 1 |
| list_accounts (deelnemersnamen) | 1 | 0 |
| snapshot_objects (losse diepe reader) | 0 | 0 |

Dit is een callvergelijking, geen latencybenchmark. Bestaande SQL/bytegrenzen
worden daarnaast door `test_console_read_architecture.py` en bestaande native
summarytests bewaakt. De pagineringstest verrijkt 25 zichtbare bronwerkkaarten;
de open kaart op pagina 2 wordt pas daar verrijkt. De lege melding zegt daarom
expliciet "op deze pagina". Er is geen corpusbrede sortering op actie beschikbaar.

Cleanup: de oude disclosure/taakcategoriepresentatie en deelnemersquery zijn
vervangen. De nu ongebruikte `_work_queue_link`, `_work_summary`,
`_review_activity_status` en `_projected_document_dashboard` zijn verwijderd;
de laatste drie hadden na de vervanging alleen nog testaanroepers. De tests
verwijzen nu naar de actuele persoonlijke presentatie en behouden echte
kernel-/autorisatie-/opslagasserties. Eén tautologische tekstassertie naast de
bestaande harde `review_duties == 0`-assertie vervalt. Alleen vier
Review-landing-HTML-goldens wijzigen; detailgoldens en routetabel blijven gelijk.

## Overdracht

#861 is de volgende afzonderlijk toe te wijzen slice. Deze PR introduceert geen
extra beoordelingsroute: contextual, batch, second_review, boom-structure en de
graaf-override houden hun bestaande eigenaren. De volgende slice moet op de dan
actuele main opnieuw bevoegdheden, exact-tuple-binding en revisiecontrole toetsen.
Open bewijsgrens: screenshots uit #857 zijn geen reproduceerbare productiepopulatie;
deze run stelt hun werkelijke historische aantallen niet vast. Er is geen
productiedata, deployment of volledige persoonlijke afgehandeld/totaal-noemer
onderzocht of gewijzigd.
