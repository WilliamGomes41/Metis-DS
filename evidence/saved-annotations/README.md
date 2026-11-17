# Opgeslagen annotaties — verificatie

Basis main: `17bce9e1823dd82ea0134047dce37f5aef67fe3c`.
Omgeving: Python 3.12, PostgreSQL 16.11 met OpenSSL, Chromium/Playwright.
Alle documenten, accounts en providerantwoorden zijn synthetische testgegevens.

- [Desktop 1440 px](saved-annotations-1440.png)
- [Mobiel 390 px](saved-annotations-390.png)
- [Gedragsresultaten](saved-annotations.json)
- [Gerichte tests: 79 passed](focused.xml)
- [Nieuwe browserroute: 1 passed](browser.xml)
- [Bestaande browserroutes: 4 passed](browser-regression.xml)
- [Na optimaliseren van de voortgangsread: 2 passed](progress.xml)

De nieuwe browserroute controleert succesvolle opslag en doorgaan, herladen,
heropenen via Enter, een geweigerde wijziging met behoud van de opgeslagen versie,
geblokkeerde navigatie bij die opslagfout, intrekking, documentcontrole en een
echte bouwopdracht. Tijdelijke onbeschikbaarheid van de statusread laat de lijst
staan en toont een melding. Na de werkelijke bouw worden beide annotaties als
beschikbaar voor Review getoond; heropenen leest dan ook de actuele objectbinding.

Dezelfde proef is in een geïsoleerde main-worktree uitgevoerd en faalt op de
ontbrekende lijst. Het is een gedragsproef met echte routes en opslag, geen
bewijs voor inhoudelijke verbetering van menselijke annotaties of een deployment.

De Impeccable-engine kon niet starten. De meegeleverde richtlijnen zijn toegepast;
er is geen detector-PASS geclaimd. Geen nieuwe productdependencies of migraties.

De volledige collectie op implementatiecommit
`b882493725fd7c3fbe26c3caa255d633226e1c22` is gecontroleerd met de canonieke
shardmerger: 8.868 tests, 8.810 geslaagd, 58 overgeslagen, geen fouten en geen
PostgreSQL-skips. De browserproeven hierboven zijn afzonderlijk uitgevoerd.
De skips betreffen optionele browser/Bend/Docling-omgevingen en drie nog niet
geïmplementeerde B23-proeven op main; ze gelden niet als geslaagd bewijs.

De eerste volledige uitvoering had één fout in een bestaande Review-batchtest:
de gemeten lockduur was 0,351 s bij een grens van 0,250 s. Zowel een gerichte
herhaling als één volledige afzonderlijke herhaling van de betrokken partitie
slaagden op ongewijzigde code en testgrenzen. De oorzaak is niet vastgesteld.
De andere drie partities zijn niet herhaald. De merger controleerde dat de vier
gebruikte rapporten samen exact de volledige collectie van dezelfde commit
dekken. [Verificatiesamenvatting](verification.json) bewaart beide uitkomsten;
[gerichte timingherhaling](batch-timing-retry.xml). De ruwe rapporten staan lokaal
in de in de samenvatting genoemde directories.

Publicatie naar GitHub
of Linear is niet uitgevoerd: het aanmaken van een issue werd door automatische
goedkeuringscontrole geweigerd. De implementatie en het bewijs blijven lokaal.
