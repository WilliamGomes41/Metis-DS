# Gebonden context blijft context tijdens de eerste vormingsronde

Issue: #979. Part of MET-7. Change class: B. Rewrite risk: none.

## Belofte en oorzaak

Een gevalideerd voorstel kan tabel- of lijsttekst uit een latere taak als context
binden. `bounded_formation_v1.execute` berekende de taken aan het begin van de
ronde; hun selecteerbare bereiken werden daarna niet meer bijgewerkt. Daardoor
kon dezelfde context opnieuw een zelfstandige kandidaat worden. Recovery trok
die bronbereiken wel af.

Beperk iedere taak vóór de modelaanroep tot de bronbereiken die nog niet zijn
gebruikt. Laat zelfstandig overblijvende tekst selecteerbaar. Alleen zichtbare,
onzekere of afgewezen context telt niet als gebonden brongebruik.

## Mechanisme en grenzen

Het bestaande pad blijft: semantische voorbereiding → begrensde taak → provider
→ bronvalidatie → selectiebeperking → bestaande taakcommit → deterministische
materialisatie → transformatie → Admission. De enige kandidaatmaker blijft
`materialise_knowledge_candidates`. De reparatie verandert selectiegrenzen,
geen brontekst, objectidentiteit, Admission-regels of publicatiebevoegdheid.

Een tijdelijke index van exacte gebruikte intervallen wordt één keer opgebouwd
uit de bestaande voorstellen en gecommitteerde TaskResults. Daarna voegt de
uitvoering alleen het nieuw geaccepteerde resultaat toe, na de bestaande commit.
Iedere taak raadpleegt uitsluitend zijn eigen bronblokken. Er komt geen extra
volledige-documentvalidatie per taak.

Volledig gebruikte taken kosten geen modelaanroep en krijgen geen fictief
TaskResult. Gedeeltelijk gebruikte taken behouden absolute bronoffsets; volledig
gebruikte blokken blijven context. De oorspronkelijke vastgelegde planning blijft
het uitgangspunt voor voortgang. Ook budgetmeldingen vermelden alleen resterend
bronwerk. Contextlimieten blijven expliciet; bron wordt nooit afgekapt.

Na afronding komt bronvoortgang uit de bestaande `formation_accounted`-checkpoint
van exact dezelfde poging. De compacte samenvatting en detailstatus gebruiken
dezelfde projectie. Een poging zonder zo'n afronding gebruikt de actuele
TaskResult-tellers, zodat een oudere replay geen nieuwe budgetstop kan verhullen.
Er komt geen nieuw voortgangsrecord of volledige archiefread bij.

## Duurzame toestand

- Aggregate: bestaande vormingscontext en TaskResults.
- Voor/na: gewone taakresultaten binnen dezelfde context; geen schemawijziging.
- Transactie: bestaande `commit_task`, claim, revisiefence en cursor.
- Fout: een mislukte commit wordt niet toegevoegd aan de tijdelijke index.
- Herhaling/herstart: dezelfde index wordt afgeleid uit gecommitteerd brongebruik.
- Concurrentie: bestaande taakcommit en claim blijven leidend.
- Evidence: bestaande taakplanning, providerantwoorden en echte TaskResults;
  overgeslagen context veroorzaakt geen nagebootste providerresponse.

## Bewijs en resterende onzekerheid

`tests/test_initial_bound_context_v1.py` gebruikt de bestaande producer,
materialisatie, transformatie en Admission met synthetische providerantwoorden.
Vóór de reparatie falen volledige en gedeeltelijke binding; onzekere en afgewezen
context slagen als negatieve controles. De PostgreSQL-proef controleert gewone
verwerking en onderbreken/herstarten via de productieconsole.

Dit bewijst het voorkomen van dubbele selectie binnen deze keten. Het bewijst
geen klinische volledigheid of semantische juistheid van modelkeuzes. MET-7 en
de onafhankelijke bronacceptatie in #530 blijven daarom open. Ontbrekende
modulecontext, relaties tussen taken en verkeerd meegestuurde gelijknamige
koppen zijn afzonderlijke kwaliteitsproblemen. Bestaande documenten worden
niet automatisch opnieuw verwerkt.
