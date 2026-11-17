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

De volledige suite wordt afzonderlijk vastgelegd na afloop. Publicatie naar GitHub
of Linear is niet uitgevoerd: het aanmaken van een issue werd door automatische
goedkeuringscontrole geweigerd. De implementatie en het bewijs blijven lokaal.
