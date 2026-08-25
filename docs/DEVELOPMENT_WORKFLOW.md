# Protocolgestuurde ontwikkelwerkwijze

## 1. Doel

Deze werkwijze voorkomt dat implementatiekeuzes stilzwijgend productregels of architectuur worden. Besluitvorming loopt van norm naar planning, actuele toestand, controleerbaar gedrag en pas daarna naar code.

## 2. Documenthiërarchie

| Laag | Vraag | Verplicht resultaat |
|---|---|---|
| `PROTOCOL.md` | Wat moet waar zijn? | Norm, grenzen, invarianten, verantwoordelijkheden en verboden gedrag |
| `ROADMAP.md` | In welke volgorde realiseren we dit? | Fasen, scope, afhankelijkheden en stopvoorwaarden |
| `HANDOFF.md` | Waar staan we nu werkelijk? | Gemergede stand, bewijs, blokkades, afwijkingen en eerstvolgende taak |
| Tests | Hoe bewijzen we conformiteit? | Gold cases, acceptatiecriteria, regressie- en invarianttests |
| Code | Hoe implementeren we het besloten gedrag? | Minimaal noodzakelijke deterministische en modelondersteunde implementatie |

Een lagere laag mag een hogere laag niet tegenspreken. Bij tegenspraak geldt de hogere laag en stopt de wijziging fail-closed.

## 3. Verplichte cyclus

1. Registreer het probleem, de failure of de gewenste wijziging.
2. Classificeer de wijziging en bepaal de hoogste geraakte protocolklasse/gate.
3. Toets of de bestaande norm het gewenste gedrag ondubbelzinnig bepaalt.
4. Wijzig eerst het protocol als een nieuwe regel, grens, verantwoordelijkheid of route nodig is.
5. Bepaal in de roadmap de volgorde, scope en stopvoorwaarden.
6. Werk de handoff bij met de actuele uitgangssituatie en één concrete volgende taak.
7. Leg vóór implementatie de relevante gold cases, acceptatietests of invarianttests vast.
8. Implementeer de kleinste wijziging die de tests en norm realiseert.
9. Voer repository-preflight, compilatie, invarianttests, volledige tests en relevante echte cases uit.
10. Controleer diff, herleidbaarheid, source integrity en vereiste menselijke review.
11. Merge alleen wanneer alle toepasselijke gates `PASS` zijn; `BLOCKED` blijft een geldige veilige uitkomst.
12. Werk in dezelfde PR de handoff bij met commit, bewijs, resterende blokkades en volgende taak.

## 4. Wanneer het protocol wel of niet verandert

Een protocolwijziging is verplicht bij:

- een nieuwe of gewijzigde productregel;
- een nieuwe architectuurgrens of toegestane route;
- een wijziging in verantwoordelijkheden van AI, deterministische code of menselijke reviewers;
- een nieuwe safety-invariant, gate, status of reden voor abstention;
- wijziging van bronintegriteit, publicatie-, entitlement-, withdrawal- of acceptatiebeleid.

Geen nieuwe protocolversie is nodig wanneer een bug aantoonbaar een bestaande regel schendt en de reparatie de norm niet uitbreidt. De PR verwijst dan naar de bestaande eis en voegt een regressietest toe.

Twijfel over de norm is geen implementatiedetail. De wijziging blijft `BLOCKED` totdat de norm is verduidelijkt.

## 5. Pull-requestcontract

Iedere materiële PR vermeldt minimaal:

- probleem en gewenste uitkomst;
- geraakte protocolsecties, lagen en hoogste wijzigingsklasse;
- protocolimpact: geen, verduidelijking of nieuwe versie;
- roadmapfase en effect op scope/stopvoorwaarden;
- handoffwijziging;
- vooraf vastgelegde tests of acceptatiecases;
- uitgevoerde preflight, CI, volledige tests en echte-casevalidatie;
- source-, schema-, publication-, answerability-, security- en privacy-impact waar toepasselijk;
- exacte commit/snapshot die iedere reviewer heeft beoordeeld;
- resterende blokkades, afwijkingen en herstelactie.

Een PR met code maar zonder vereiste test- en handoffwijziging is procesmatig incompleet.

## 6. CI-governance-invarianten

CI controleert minimaal dat:

- de vier sturende documenten bestaan;
- de hiërarchie in alle sturende documenten herkenbaar en consistent is;
- `PROTOCOL.md` naar precies één geldende versiegebonden protocolspecificatie verwijst;
- de handoff een geldend protocol, update-datum, authoritative remote, blokkades en eerstvolgende taak bevat;
- de roadmap fasen en stopvoorwaarden bevat;
- bestaande architectuur-invarianttests en de volledige testsuite blijven slagen.

Deze documenttests bewijzen geen inhoudelijke goedkeuring. Ze voorkomen wel dat de afgesproken besturingsstructuur onzichtbaar verdwijnt.

