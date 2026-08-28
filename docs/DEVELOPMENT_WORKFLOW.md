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
- infrastructure / cost impact (Protocol v2.3): `None`, existing dependency, changed dependency, new dependency, or removed dependency; bij iets anders dan `None` het infrastructuurmanifest en de stackbaseline bijwerken of expliciet blokkeren;
- exacte commit/snapshot die iedere reviewer heeft beoordeeld;
- resterende blokkades, afwijkingen en herstelactie.

Een PR met code maar zonder vereiste test- en handoffwijziging is procesmatig incompleet.

Protocol v2.6 keurt een interne operations console goed als DS-oppervlak. Een PR die console-UI, console-identiteit, review-afdwinging of publish-autorisatie toevoegt is minstens C5 spanning C3. Een zorgapp-frontend, chatbot, EPD/ECD-UI of publieke website in deze repository blijft verboden. Chat is geen consoleruimte. Deze protocol-PR implementeert geen UI.

Protocol v2.7 legt first-wave bron, object-level retrieve-and-abstain API en distributieregels vast. Alle v2.6-consoleregels blijven van kracht. Fase 2 bron 2-opslag mag niet worden overgeslagen. Geen Vercel, Neon of LLM-vendor. Deze protocol-PR implementeert geen UI en geen productcode.

Protocol v2.8 legt primaire gebruikers, klasse×familie-bronhiërarchie en console-bouwvolgorde vast. Alle v2.6-consoleregels en alle v2.7-bron-/API-/distributieregels blijven van kracht, behalve de begrensde supersessie van de bouwvolgorde: de volgende implementatie is een echte console-MVP op de bestaande kernel, geen mockup; Continentie bron 2 komt via die console binnen; duurzame immutable opslag wordt niet overgeslagen. RAG op kennisplatform-HTML is niet het product. Geen Vercel, Neon of LLM-vendor. Deze protocol-PR implementeert geen UI, geen mockup en geen productcode.

Protocol v2.9 legt taakgerichte onderzoeker-UX en de V&VN digitale stylesheet vast. Alle v2.6-kamers, v2.7-ingesttypen en v2.8-gebruikers-/hiërarchieregels blijven van kracht. De console-UX-rewrite op de bestaande kernel is nu in code (PR #25), geen Azure, geen Vercel/Neon, geen mockup; de G2-locator blijft de publicatieblocker.

Protocol v2.10 legt Documentenhierarchie, wachttaak-badges en de Accounts-kamer vast. Alle v2.6-kamers, v2.7-ingesttypen, v2.8-gebruikers-/hiërarchieregels en v2.9-UX-/huisstyleregels blijven van kracht. Het console-vervolg op de nu-in-code v2.9-UX (PR #25 gemerged) blijft verplicht: hernoemen, echte badges, Accounts; geen Azure, geen Vercel/Neon, geen mockup, geen chat, geen verpleegkundigen-UI; de G2-locator blijft de publicatieblocker. De v2.10-protocol-PR wijzigt `src/operations_console_*.py` niet en implementeert de nieuwe UI niet.

Protocol v2.11 legt geüploade HTML-freeze, weigering van live URL-HTML, verplichte source locators en fail-closed Product API zonder locator vast. Alle v2.6-kamers, v2.7-bron-/API-/distributieregels (behalve de begrensde HTML-URL-ingestzin), v2.8-gebruikers-/hiërarchieregels, v2.9-UX-/huisstyleregels en v2.10-console-/nav-/accountsregels blijven van kracht. HTML wordt niet geheel verboden. v2.11-kernelwerk blijft verplichte wet: live URL-HTML bij ingest weigeren; Product API fail-closed `supported` zonder source locator. PROTOCOL → tests → code later. Geen Azure, geen Vercel/Neon, geen mockup; de G2-locator blijft de publicatieblocker. Deze protocol-PR wijzigt `src/operations_console_*.py` en `src/product_api_*.py` niet en implementeert ingest-weigering noch API-fail-closed.

Protocol v2.12 legt extractie als structuur/provenance only, de gesloten object-typeset met unclassified-default, answerability als vraagtype × objecttype, publish-binding aan het objecttupel, en serving vanuit een atomaire gepubliceerde projectie vast. Alle v2.6–v2.11-regels blijven van kracht, behalve de begrensde supersessie van extractie-betekenis, «alleen recommendations», envelope-`review_passes`, live-governance-per-query, en de eerstvolgende implementatie. De volgende implementatie is de Implementation engineer op de bestaande kernel; DAARNA G2/Azure. v2.11-kernelwerk blijft verplichte wet en is geen supersessie van v2.12 §10. Geen Azure, geen Vercel/Neon, geen mockup; deze protocol-PR wijzigt `src/operations_console_*.py`, `src/extract_*.py` of `src/product_api_*.py` niet. GD-03 wordt niet heropend.

## 6. CI-governance-invarianten

CI controleert minimaal dat:

- de vier sturende documenten bestaan;
- de hiërarchie in alle sturende documenten herkenbaar en consistent is;
- `PROTOCOL.md` naar precies één geldende versiegebonden protocolspecificatie verwijst;
- de handoff een geldend protocol, update-datum, authoritative remote, blokkades en eerstvolgende taak bevat;
- de roadmap fasen en stopvoorwaarden bevat;
- bestaande architectuur-invarianttests en de volledige testsuite blijven slagen.

Deze documenttests bewijzen geen inhoudelijke goedkeuring. Ze voorkomen wel dat de afgesproken besturingsstructuur onzichtbaar verdwijnt.

