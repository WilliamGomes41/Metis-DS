# #1066 — Metis uitgelegd: bijwerken naar de huidige stand, kennisobject centraal

Change class: C
Promise: De uitleg op `/over-console` beschrijft de huidige werkwijze en zet het kennisobject centraal: wat het is, waaruit het bestaat en waarom alles erom draait.
Proof: Inhoudstest die de definities toetst aan de code (soorten uit `CLOSED_OBJECT_TYPES`, statussen uit `KO_STATES`, geen "terugsturen"), de bestaande paginatests en de browserproef op 1440 en 390 px.
Touches lifecycle invariants: no
Rewrite risk: none

Part of MET-77. Verzoek William, 13 november 2026: de kennis op de pagina is
verouderd; scherp de definities aan, minder hoogover en technisch, met de nadruk
op de definitie van een kennisobject en waarom het belangrijk is.

Alleen uitlegtekst en weergave (`src/settings/metis_explained_content.py`,
`src/settings/metis_dictionary_ui.py`). Geen gedrag, opslag, autorisatie of
modelaanroep. Bestaande begrip-ID's blijven, zodat links blijven werken.

- Startpagina: eerst "Het kennisobject: de bouwsteen van Metis" met definitie,
  voorbeeld en zes redenen; daarna de keten in zes stappen volgens de huidige
  werkwijze (aanleveren, aanwijzen in de kaart, documentcontrole en bouwen,
  beoordelen, publiceren, gebruiken). De oude sectie "Wat geeft vertrouwen" is
  opgegaan in de redenen.
- Nieuwe eerste categorie "Het kennisobject": kennisobject, uitspraak, wat erbij
  hoort, onderbouwing, soort, status en versie.
- Bijgewerkt of nieuw: kandidaat, annotatiekaart, voorstel van Metis, signaal,
  brondekking, documentcontrole, bouwen, brontrouw (letterlijk), noodzakelijke
  context, inhoudelijke beoordeling (aanpassen in de kaart in plaats van
  terugsturen), tweede beoordeling (na elkaar, reviewer 2 kan afwijzen), afwijzen,
  publiceren. Lopende tekst gebruikt één term: kennisobject.
- Modeldossiers voor documentopslag, kennisobjecten en beoordeling volgen de
  huidige werking; `REFERENCE_REVISION` wijst naar `main` 9a6f199.
