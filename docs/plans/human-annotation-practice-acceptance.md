# Praktijktoets researcher-annotatie

Status: voorbereiding bij #1017/MET-61. **Geen uitgevoerde praktijktoets.**
Technische HTML-/Unicode-fixtures bewijzen geen klinische volledigheid of lagere
menselijke werklast. HA-2a is evenmin de volledige upload-tot-API/MCP-ketenproef.
Het [technische HA-3-bewijs](../change-contracts/1016-human-annotation-review-evidence.md)
vervangt deze toets niet.

HA-4 is op 9 november 2026 gestart met een
[versiegebonden overgangsinventaris](../change-contracts/1017-human-annotation-transition.md)
op main `c985eaf376f4c686851f198f526510ca32e98b9e` (HA-3 gemerged).
De inventaris bevat de oude ingangen, behouden helpers en bewijslezers,
overgangsvolgorde en ontbrekende praktijkinvoer. Er is nog geen cutover of
praktijkmeting uitgevoerd; onderstaande voorbereiding blijft open.

## Vastleggen vóór deelname

| Gegeven | Vereiste vastlegging | Huidige status |
|---|---|---|
| Bron | Richtlijntitel, bronversie, originele bytes/hash, gebruiksrechten | Bij inhoudelijke eigenaar uitgevraagd |
| Selectietaak | Doel, beoogd gebruik, gebruikersgroep, bronbereik, selectiecriteria | Nog vast te stellen; eerste volledige proef omvat gehele bron |
| Referentie | Onafhankelijk vooraf geannoteerde claims met noodzakelijke context, voorwaarden, uitzonderingen, bewijsfuncties en vindplaatsen | Niet beschikbaar; niet door uitsluitend de deelnemende annotator te maken |
| Deelnemers | Researchers, onafhankelijke beoordelaar en adjudicator | Nog toe te wijzen |
| Beoordelingskeuze | Exacte ingestpolicy, deelnemers en aantallen | Voor beide varianten gelijk houden |
| Acceptatiegrenzen | Inhoudelijk te beoordelen fouttypen en aanvaardbare uitkomsten, vóór meting vastgesteld | Geen verzonnen kwaliteitspercentage |
| Technische versie | Code-SHA, migratiedigest, configuratie, extractor, bron-/extractiehash en gebruikte route | Bij uitvoering registreren |

## Uitvoering en vastlegging

Gebruik dezelfde bevroren bron en opdracht voor menselijke annotatie en de
bevroren historische AI-selectie. Voer oude AI-proza niet opnieuw als tweede
productroute in om een vergelijking mogelijk te maken. Verantwoord de volgorde
of verdeel gelijkwaardige brondelen om leereffecten zichtbaar te houden.

Laat de researcher uitspraak en rolbereiken aanwijzen, een onvolledig concept
pauzeren, opnieuw inloggen en hervatten, het documentoverzicht corrigeren,
afronden, de daadwerkelijk vereiste beoordeling doorlopen en bevoegd publiceren.
Controleer daarna de publieke API en de geautoriseerde MCP-projectie, en laat een onafhankelijke beoordelaar
het resultaat met de vooraf bevroren referentie vergelijken. Leg een verschil
pas als fout vast na adjudicatie; bewaar de vindplaats en reden.

Neem na de eerste bouw ook een doelbewuste correctie van het oorspronkelijke
bronobject op: wijzig een voorwaarde of bewijsfunctie in dezelfde annotatie,
pauzeer/hervat en bouw de nieuwe versie. Laat de bevoegde reviewer de nieuwe
versie beoordelen en controleer dat ongeraakte oordelen niet opnieuw worden
gevraagd. Noteer de oude en nieuwe versie, getroffen afhankelijkheden en tijd.
De correctieproef gebruikt ongepubliceerd werk; reeds gepubliceerd werk volgt
de bestaande expliciete opvolgercyclus.

Keuze A: noodzakelijke voorwaarden en uitzonderingen blijven brongebonden
context bij dezelfde claim. De referentie moet ook context uit een andere alinea
en hergebruik van onderbouwing met verschillende functies bevatten. Het huidige
MCP biedt interne werkinspectie; toegang tot een concept is geen bewijs van
publieke serving of inhoudelijke goedkeuring. Controleer die grenzen afzonderlijk.

Registreer afzonderlijk:

- ontbrekende of toegevoegde betekenis, verloren doelgroep, negatie of modaliteit;
- verkeerde of ontbrekende voorwaarde/uitzondering en de betekenis van gedeelde onderbouwing;
- verkeerde bronbinding, fout na afronding en gevonden restscope;
- annotatie-, beoordelings- en correctietijd plus totale mensentijd;
- verloren of dubbel opgeslagen werk, hervatten, navigatie en extra handelingen;
- muis-, toetsenbord- en touchbediening bij meerdere alinea's of gesplitste extractie.

Gebruik per waarneming: deelnemer/pseudoniem, taak/bronhash, begin/eind, fase,
annotation-ID/revisie, object-ID/versie waar aanwezig, referentie-ID, bevinding,
vindplaats, adjudicatie en eventuele herstelversie. Vermijd onnodige persoonsgegevens
en exporteer geen gelicentieerde quote zonder de toepasselijke gebruiksrechten.

Rapporteer aantallen én noemer per fouttype, tijden per fase, variatie tussen
deelnemers en onbeoordeelde gevallen. Minder correcties betekent niet automatisch
minder fouten: ook voorafgaand aanwijswerk en achteraf ontdekte fouten tellen mee.
Leg afzonderlijk vast: technische proef, gebruikerspraktijk, review, merge en
deployment. Geen onderdeel als gereed markeren op basis van alleen een screenshot,
een groen statechart-model of een technische fixture.
