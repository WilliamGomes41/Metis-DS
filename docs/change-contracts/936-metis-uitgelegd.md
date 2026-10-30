# Metis uitgelegd: vindbare uitleg en modelverantwoording

Issue: #936. Class B. Rewrite risk: none.

## Belofte en bestaand mechanisme

Een ingelogde beoordelaar kan de kennisketen begrijpen, een begrip opzoeken en
de werking en bewijsgrenzen van een model nalezen op `/over-console`.
De bestaande route gebruikt `_require(request)`, de uitleg-renderer en `_page`.
`assets/brand/console.css` bepaalt de huisstijl. Er komt geen domeinmutatie bij.
Autorisatie, bronnen, kennisobjecten, beoordelingen en publicaties blijven onder
hun bestaande eigenaar. Zoektermen zijn tijdelijke URL-invoer, geen opgeslagen
vragen of modelprompts. Er worden geen modelaanroepen uitgevoerd.

## Gebruik en vorm

- `/over-console`: overzicht van de kennisketen en leesroutes.
- `/over-console?section=begrippen#begrip-brontrouw`: vaste begripslink.
- `/over-console?section=modellen&model=context`: zelfstandig modeldossier.
- `/over-console?q=uitzondering`: zoeken over begrippen en modelbeschrijvingen.

Primaire gegevensstructuren: immutable `Term`, `Category`, `Model` en
`Reference`-waarden in één inhoudsmodule. Categorieën bezitten hun begrippen;
modellen verwijzen naar begrips-ID's. Menu's, ankers en zoekresultaten worden
uit deze waarden afgeleid. De renderer ontvangt ontsmetting, sectie, zoekterm
en model-ID en levert HTML. Een lineaire tekstzoekactie past bij deze kleine,
zelden gewijzigde collectie; een zoekserver, database en cache zijn onnodig.
Git is de eigenaar van documentatieversies; runtime-gebruiksstatus wordt niet
uit de aanwezigheid van een beschrijving afgeleid. Geen concurrerende writes:
de pagina schrijft uitsluitend een response, niet naar domeinopslag.

## Afweging en scope

Variant A: gestructureerde inhoud en server-rendering in de bestaande console.
Variant B: afzonderlijk CMS met eigen redactiestatus en API. Beide zijn door
dezelfde agent uitgewerkt, zonder onafhankelijke modelreview.
Keuze A vanwege bestaande authenticatie, eenvoudige distributie, Git-review en
lage beheerlast. B zou zelfstandige redactie makkelijker maken, maar introduceert
een tweede beheeromgeving zonder bewezen behoefte. Bewuste afweging: content-
wijzigingen vereisen een repo-wijziging in ruil voor één controleerbare versie.

De bestaande huisstijl is visuele autoriteit. Read-modus: vaste inhoudsopgave,
leeskolom, native links en formulier, optionele sectieankers, één kolom op mobiel.
Er is geen JavaScript nodig om uitleg, zoeken of modeldossiers te gebruiken.
Geen live collectieaantallen of operationele modelclaims zonder actuele bron.
Modeldossiers zijn beschrijvingen ter inhoudelijke beoordeling; eigenaarsnamen
en klinische validatie worden niet verzonnen.

## Bewijsplan

| Belofte | Foutscenario | Bewijs en grens |
| --- | --- | --- |
| Alleen ingelogd, alleen lezen | Nieuwe query omzeilt login of schrijft kennis | Echte PostgreSQL/ASGI-login, alle ingangen, domeintoestand gelijk |
| Zoeken vindt uitleg | Aliassen missen, lege lijst biedt geen vervolg | Zoekresultaat en tegenvoorbeeld, vaste links, herstelactie |
| Veilige response | Zoekterm of ongeldige ID wordt HTML/pad | Escaping, begrensde invoer en afwijzing van onbekende sectie/model |
| Modelverantwoording is traceerbaar | Documentatie lijkt productiebewijs | Referenties op vastgelegde repo-versie; expliciete bewijsgrens |
| Layout is bruikbaar | Mobiele overloop of onbereikbare navigatie | Chromium op desktop en mobiel, toetsenbord, thema en zoeken |

## Volgorde en herstel

Eerst bestaande inhoud uit de renderer halen en vervangen door getypeerde,
stabiele ID's. Daarna navigatie/zoeken/modeldossiers en gerichte CSS binnen de
uitlegpagina. De eigen stylesheet wordt alleen hier geladen; het gedeelde
stylesheet en zijn versie blijven gelijk. Bestaande regressies en gerichte
browserverificatie hergebruiken.
Geen dode productcode of nieuwe infrastructuur nodig. Rollback is het terugzetten
van deze presentatie- en inhoudswijziging; geen datamigratie of dataherstel.

## Verificatie

- Volledige suite: **6438 passed, 40 skipped, 3 xfailed, 24 subtests passed**;
  16 waarschuwingen, geen onverwachte fout. Python 3.12.14,
  PostgreSQL 16.2, vier pytest-xdist-workers met elk een eigen wegwerpserver.
  Command: `pytest -q -n 4 --dist loadfile --maxfail=5`.
- De optionele Chromium-proef van deze pagina is daarnaast expliciet uitgevoerd:
  **1 passed** op Chromium 151.0.7922.173, met 1440px/390px, licht/donker,
  toetsenbord, zoekhintcontrast ≥ 4.5:1 en zoeken/navigeren zonder JavaScript.
- De gerichte inhouds- en PostgreSQL-routechecks slagen; alle begripsankers,
  verwante begrippen en modelbronbestanden zijn gecontroleerd.
- Repository preflight, release-control preflight, compileall, architectuurgrenzen
  en de zes architectuurinvarianten slagen. De PR-contractvalidator slaagt.
- Impeccable meldt geen bevindingen in de gewijzigde renderer, inhoud en eigen
  stylesheet. De eerste scan van de gedeelde CSS vond alleen bestaande regels;
  de uiteindelijke wijziging laat dat stylesheet bytegelijk.

Beelden en reproduceerstappen: `evidence/936/README.md`. De modelteksten zijn
conceptbeschrijvingen ter inhoudelijke beoordeling, geen klinische validatie of
verklaring van actuele productieconfiguratie. Geen deployment of merge uitgevoerd.
