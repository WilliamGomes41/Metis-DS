# #1125 — Bronrestjes verantwoorden in het document

**Status** · Implementatie op basis van de opdracht van William van 22 november 2026 om met het bijgewerkte ontwerp te starten.

**Class B · Rewrite risk: none.** De weergave van voorstellen is afgeleid. Bevestigen is een bestaande duurzame annotatieopdracht. Dit ontwerp verandert waar de medewerker die opdracht uitvoert en welke bestaande bronbereiken samen in één annotatie worden opgeslagen. Als de bestaande opslag, afsluiting of publicatiepoort andere voorwaarden nodig blijkt te hebben, volgt herclassificatie voordat die wijziging wordt ontworpen. Onderzocht op GitHub `main`, commit `e4cca52eaf3d9fa410eb9ef08b521a9c26dd2579`.

## Productdoel en toepassingsgebied

Een medewerker kan elke bron die de annotatieroute ondersteunt in het document zelf volledig verantwoorden. Tijdens het aanwijzen blijven de volledige brontekst en de plaats van elk fragment beschikbaar. Metis bespaart handelingen waar herkenning en groepsbevestiging helpen. Bij weinig of geen herkenning kan de medewerker ieder open bereik in het document zelf een bestemming geven. Bij volledige dekking vraagt het overzicht alleen om controle en afronding.

Herkenningsregels steunen op herbruikbare kenmerken van bronstructuur en tekst. Ze werken onafhankelijk van richtlijnnaam, bron-ID en een vaste paginapositie. De herkenningsdekking mag per bron verschillen. Een onzekere passage blijft beschikbaar voor menselijke beoordeling. De Smetten-demo geeft één concrete regressieproef voor dit algemene gedrag.

## Bestaand gedrag en eigenaarschap

- `human_annotation_ui_v1.editor` opent `/annotations` en gebruikt voor het documentoverzicht `human_annotation_build_v1.overview`. Dat overzicht gebruikt `human_annotation_preview_v1.inspect_for_overview` voor de exacte open bronbereiken en overige bevindingen. Nu toont het per open bereik een formulier naar `/annotations/source-role`.
- `human_annotation_v1.save` is de PostgreSQL-schrijfgrens voor annotaties. Een annotatie met status `ready` en een `disposition` voor `metadata` of `structure` accepteert al meerdere kernbereiken met dezelfde reden. `inspect_document` verwerkt elk opgeslagen bereik afzonderlijk als bronverantwoording. Dezelfde opdracht kan daarom één bereik of één homogene groep vastleggen.
- #933 levert de deterministische functie `source_containers_v1.accounting_reason` en het ontwerp voor bevestigen per sectie en reden. `source_context_review_v1.confirm_source_group` werkt met gevormde bronobjecten en vereist de bestaande reviewerautorisatie. Vóór de bouw zijn de leden bronbereiken zonder die objectidentiteit. De annotatieroute gebruikt daarom `accounting_reason` voor voorstellen en `human_annotation_v1.save` voor bevestiging. De bestaande revieweropdracht blijft beschikbaar op de reviewroute.
- `human_annotation_build_v1.finalize` controleert het actuele overzicht en de opgeslagen keuzes vóór het verzegelen en starten van de bouw. `publication_readiness_v1` blijft de autoriteit voor publicatiegereedheid. Afsluiten in de annotatieroute start de bouw met de bestaande vervolgbeoordeling.

## Wat de medewerker doet

1. Bij openen wijst de bestaande inspectie de open bronbereiken aan. Geef elk bereik waarop `accounting_reason` een geldige bronfunctie herkent een rustige neutrale markering en een tekstlabel met de voorgestelde categorie. Pas de regels toe op het gehele bereik. Sectie of paginapositie alleen is onvoldoende grond. Maak de overige open tekst tijdens het annoteren vindbaar via ‘Nog te beoordelen’. Wanneer de medewerker open werk bekijkt of vanuit de controlepagina terugkeert, licht de werkplek het betreffende bereik duidelijk uit. Aantoonbaar onvolledige inspectie, bijvoorbeeld bij historische annotaties, toont de bestaande bevinding en geen sluitende telling.
2. Toon de leden van elk voorstel per sectie en reden in bronvolgorde, met hun volledige tekst. De medewerker kan een lid uit de bevestiging laten, een andere reden kiezen of via de bestaande selectiekaart alsnog een uitspraak aanwijzen. Ook een bereik zonder voorstel kan de medewerker ter plekke indelen. Gebruik de bestaande bronlabels en houd bediening en focus bruikbaar met toetsenbord en op smalle schermen.
3. Bevestig de geselecteerde leden met één expliciete knop per sectie en reden. Gebruik de groepsgrens van B6 van maximaal 50 leden. Een handmatig gekozen andere reden volgt dezelfde opslagroute voor dat ene bereik. Na opslag herleest de editor de actuele toestand. Een weggelaten bereik blijft open totdat het via een bestaande route een bestemming krijgt.
4. Het documentoverzicht toont het aantal gereedstaande kennisannotaties, opgeslagen restbereiken en open bereiken afzonderlijk. Groepsbevestiging telt per bereik. Links sturen de medewerker naar het exacte bereik in het document. De knop ‘Ik ben klaar met dit document’ voert de bestaande afsluitopdracht één keer uit zodra de bestaande `can_finalize`-voorwaarden zijn vervuld.

## Opdracht, transactie en herstel

De leesprojectie gebruikt de vastgelegde bron, actuele annotatiegeneratie en dekkingsinspectie. De browser bewaart alleen de selectie en de bedieningstoestand. Een voorstel heeft geen duurzaam effect. Een bevestiging brengt de getoonde, gekozen bereiken onder één bestaande annotatie met één reden. Elk bereik wordt gebonden aan dezelfde bronversie, blok-ID en exacte tekenposities die de medewerker ziet.

Breid het bestaande invoerpunt `/annotations/source-role` uit voor één of meer bereiken. Valideer voor opslag de bronidentiteit, de generatie, de objectrevisie, de exacte getoonde leden en hun ligging in de actuele open bereiken. Voor een groep geldt één sectie en één reden. Stuur alle gekozen bereiken in één `save` aanroep. PostgreSQL legt de annotatierevisie, de huidige versie, de generatie en het commandobewijs in dezelfde bestaande transactie vast. De bevestigde bereiken, gekozen reden en actor blijven herleidbaar via de opgeslagen revisie en het commandobewijs.

Een herhaling met hetzelfde opdracht-ID en dezelfde inhoud geeft het eerdere resultaat terug. Laat daarom een geldige herhaling door de bestaande receipt-controle afhandelen, ook als de bereiken door de eerste bevestiging inmiddels gesloten zijn. Een gewijzigde opdracht met hetzelfde ID of een tweede editor op een verouderde generatie krijgt een conflict. Bij weigering of onderbreking vóór de commit blijft de hele groep open. De gebruiker kan de actuele bron herladen en opnieuw kiezen. Open werk dat elders is opgeslagen blijft behouden.

## Acceptatiebewijs

Kies vóór het toetsen bronnen die verschillen in structuur en herkenningsdekking. Gebruik naast Smetten een anders opgebouwde praktijkrichtlijn met herhaalde bronstructuur, een bron met weinig of geen herkenbare restjes, en een gemengd geval waarin een kop of documentgegeven grenst aan klinische tekst. Een bron mag meerdere gevallen afdekken. Leg per bron bronversie, beginstand en verwachte bestemmingen vast. Vergelijk oude `main` en nieuwe code met dezelfde beginstand en rond op beide dezelfde taak af.

| Claim | Controle |
| --- | --- |
| Herkenning is bruikbaar op verschillende bronnen | Controleer welke voorstellen bij openen zichtbaar zijn. Rapporteer per bron juiste, onjuiste en ontbrekende voorstellen. Op iedere proefbron mogen nul klinisch-inhoudelijke passages als restant worden voorgesteld. Een bron met nul voorstellen blijft volledig afhandelbaar. |
| De medewerker bespaart werk als groepering mogelijk is | Tel per bron de handelingen voor bronverantwoording tot en met afronding, inclusief correcties en klikken om terug te navigeren. Verwacht minder handelingen op de praktijkbronnen met meerdere gelijksoortige restjes. Bij nul voorstellen kan alle indeling rechtstreeks in het document. |
| De Smetten-demo blijft een herkenningsregressie | Leg de 22 demobereiken met juiste categorie vooraf vast. Bij openen zijn minstens 18 van 22 bereik-categorieparen juist. |
| Een voorstel sluit geen bronbereik | Open de editor en vergelijk PostgreSQL vóór en na. Laat precies één voorstel onbevestigd, toets de bestaande afsluitopdracht en de publicatiepoort, en controleer dat geen verzegeling, bouwopdracht of publicatie ontstaat. |
| Bevestiging is exact en atomair | Bevestig een groep met één uitgesloten lid. Vergelijk de opgeslagen bereiken, reden en actor met de keuze. Herhaal dezelfde opdracht en toets ook twee editors op dezelfde generatie. Toon dat een ongeldige bevestiging geen deel van de groep opslaat. Gebruik native PostgreSQL. |
| Afronden vraagt alleen controle | Doorloop in de browser tonen, corrigeren, bevestigen, herladen en afronden. Elk semantisch bronbereik is gedekt, de schermtelling volgt de opgeslagen keuzes en de bestaande bouw start met één klik. Verifieer dat de bestaande vervolgbeoordeling en publicatievoorwaarden gelden. Controleer ook toetsenbordbediening en de bestaande smalle viewport van 390 px. |
| Bestaande bronverantwoording blijft werken | Draai de regressies uit #941 en #946 en de bestaande annotatieproeven voor source-role, afsluiting en historische overzichten. |

De bestaande `test_human_annotation_smetten_regression.py` gebruikt een synthetische bron en kan dienen als regressieproef voor klinische uitzonderingen. Voor de 18-van-22-meting is de opgeslagen demo-annotatietoestand nodig, of een reproduceerbare reconstructie ervan. Toets een nieuwe herkenningsregel met een positief voorbeeld uit een andere bron en een klinisch tegenvoorbeeld dat open moet blijven. Een uitbreiding die de automatische bronafsluiting van B6 verandert valt buiten dit ontwerp.

[#1125](https://github.com/WilliamGomes41/Metis-DS/issues/1125) · [#933](https://github.com/WilliamGomes41/Metis-DS/issues/933) · [Bestaand B6-contract](b6-groepsafhandeling-bronpassages.md) · [#1060-contract](https://github.com/WilliamGomes41/Metis-DS/blob/e4cca52eaf3d9fa410eb9ef08b521a9c26dd2579/docs/change-contracts/1060-source-first-annotation.md)
