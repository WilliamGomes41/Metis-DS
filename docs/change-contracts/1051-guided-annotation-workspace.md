# #1051 — drie taken op dezelfde annotatiekernel

Change class: B
Promise: Uitspraak selecteren → Betekenis aanvullen → Controleren en afronden met één hoofdactie per taak en actuele servercontrole.
Proof: Native browser/PostgreSQL-route, herladen, fout/herstel en stale controle; bestaande documentinspectie en opslagregressies.
Touches lifecycle invariants: no
Rewrite risk: none

Part of MET-71. GO William 11 november 2026: bouw deze volledige zichtbare route.

## Keuze en gebruik

Ground: bestaande HTML/bootstrap → editor → één save-controller → domain.save,
immutable versies/heads/commands. Inspectie: human_annotation_preview_v1.
Veel herhaalde bronselecties, één annotatie tegelijk; andere tabs kunnen schrijven.

Sketch/Agree: hergebruik variant A uit annotation-workplace-guided.md: tijdelijke
taak in browser, bestaande annotatiepayload als enige duurzame waarheid. Variant B
(serverwizard met eigen opgeslagen stapstatus) verworpen: extra writer/schema en
migratie zonder domeinbehoefte. Dit zijn bestaande ontwerpvarianten, geen nieuwe
onafhankelijke agentreviews. Gebruiker heeft implementatie opgedragen; geen extra
ontwerpgoedkeuring nodig.

Gebruik: selecteer tekst → koppel kern en kies type → volgende taak. Vul de
vragen uit field_contract aan, koppel context/onderbouwing of expliciete
ontbreekreden → controleer. Alleen opgeslagen versie wordt gecontroleerd;
conceptstatus veroorzaakt geen cirkelblokkade. Correctie maakt de controle oud.
Afronden gebruikt na actuele controle uitsluitend de bestaande ready-opdracht.

Tijdelijke toestand: task 1|2|3, gekozen bestemming/bronselectie, actuele
check {annotation_id,revision,basis,findings} of null. Bestaande payload, revision,
generation en objectfrontier blijven onder één save-controller. De controle
heeft geen nieuwe authority: gedeelde per-entry-inspectie in de bestaande owner;
documentdekking, overlap tussen annotaties, seal/build en review blijven daar.

Implement: eerst bestaande inspectie delen en alleen-lezen projectie, dan de
vervangende taakbediening; bestaande kaart niet als tweede editor behouden.
Scrap: geen nieuwe wizardframework/store; bij gewijzigde domeinsemantiek stoppen.

## Stateful overlay en bewijs

Entity: bestaande annotatie/annotatieset. Voor/na: bestaande draft/ready/withdrawn
via dezelfde save-transactie; geen schema- of geschiedeniswijziging. Onzekere
retry houdt exact body en command_id; CAS weigert concurrent ouder werk. Herladen
leest alleen bevestigd werk en pending_range. Audit: bestaande immutable versies
plus receipt. Bronankers, required_links en enige kandidaatmaker blijven gelijk.

| Risico | Bewijs |
| --- | --- |
| Verkeerd gekoppelde bron of verloren werk bij stappen | Native browser selecteert/koppelt, navigeert en herlaadt; dezelfde ankers en velden |
| Opslag lijkt compleet | Controle en expliciete ready-write afzonderlijk; open punten tonen herstelactie |
| Oude check na edit/andere tab | Dirty/edit invalideert; revision/generation/objectfrontier match vóór afronden, bestaande CAS bij write |
| Inspectie verandert seal/build | Bestaande preview-/buildproeven blijven ongewijzigd qua verwachtingen |
| Onzekere opslag of dubbele klik | Bestaande flush/receipt en gerichte browserfout-/retryproef |
| Onbereikbare bediening | Desktop/mobiele viewport, toetsenbord, focus, overflow en werkelijke screenshots |

UI-skill: vastgelegde emil-design-eng; Impeccable/distill, Operate. Regelmatig
herhaalde stappen en selecties animeren niet. Website aiforui.dev geblokkeerd in
deze omgeving; lokale herkomst en pin staan in docs/agents/emil-design-skills.md.
Technisch bewijs is geen gemeten menselijk begrip, live uitrol of klinische acceptatie.

## Uitgevoerde bediening en herstel

De editor wisselt drie taaksecties; de footer toont één primaire actie. Vragen
komen uit field_contract, ontbreekredenen worden alleen na een bewuste keuze
gewijzigd. Context verwijderen ruimt uitsluitend betekenisverwijzingen op die
volledig van die verwijderde bronkoppeling afhankelijk waren; required_links
blijven onder de bestaande kernel vallen. Een kern verwijderen vraagt eerst
bevestiging en maakt de betekenisvelden opnieuw aan te wijzen. Een typewissel
blijft ongewijzigd tot bevestiging; navigeren of ander werk annuleert de open
bevestiging. Een tijdelijke herstelbestemming verhuist nooit naar een nieuwe
annotatie of kernselectie.

Na serveropslag bevat de URL de annotatie-ID. Verversen hervat daardoor die
annotatie. Niet reconstrueerbare veld-/contextbestemmingen vragen opnieuw een
keuze; een expliciete opgeslagen relationship_id kan de herstelhandeling wel
herstellen. Geen extra duurzame wizard- of browserstore.

Native opslag-, opbouw-, herstel- en reviewregressies zijn uitgevoerd; nieuwe
HTTP-/inspectieproeven controleren ongewijzigde versies/receipts, toegangsregels
en exacte basis. De browserproeven doorlopen de zichtbare route, fout/retry,
actuele controle tegenover een tweede tab, expliciet afronden, Unicode,
relatieherstel, bronrolvoorstel, documentopbouw en reviewcorrectie. De gewijzigde
routelijst bevat alleen de toegevoegde GET /annotations/check. Volledige-suite-
en CI-resultaten worden aan de PR gekoppeld; die gelden pas na werkelijk
voltooide runs. Emulatie van 390px is geen fysieke telefoontest en technische
bediening is geen onafhankelijke onderzoekeracceptatie.
