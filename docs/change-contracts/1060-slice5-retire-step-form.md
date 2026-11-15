# #1060 slice 5 — Het oude stappenformulier helemaal weg

Change class: B
Promise: De annotatiewerkplek bestaat alleen nog uit de kaart. Het verborgen stappenformulier is weg: opmaak, script en CSS. De kaart werkt voor de medewerker precies zoals voorheen: rijen, + en −, soort, uitleg, voorstellen, opslaan, opnieuw bouwen, bronmarkeringen en toetsenbord. Opgeslagen annotaties, de kernel en het schema veranderen niet.
Proof: Alle 21 browserproeven slagen op de herschreven kaart, zonder aanpassing van hun stappen. `browser_source_first_card_check.cjs` eist nu dat de onderdelen van het stappenformulier niet meer bestaan in plaats van alleen onzichtbaar te zijn. De Python-tests rond annotatie, de annotatiepagina's en de karakterisering slagen.
Touches lifecycle invariants: no
Rewrite risk: none

Part of MET-78. Besluiten William, 15 november 2026, vastgelegd in #1060:
- “Geen adversarial audit nodig op dit moment. Start opruimen wat opgeruimd moet worden.”
- “Een schone code gaat in dit geval boven behoud.” Het ene bestaande document wordt zo nodig verwijderd en opnieuw ingeleverd.

Waarom rewrite risk none: dit raakt alleen de invoercode van de kaart in de browser. Gezag, opslag, identiteit, schema, de grens van het annotatiecommando, de kernel en de levenscyclus blijven ongewijzigd. Het enige opslagpad is hetzelfde annotatiecommando met dezelfde vorm.

## Wat verdwijnt

Alles van het stappenformulier was al onzichtbaar (`simple()` gaf altijd `true`):

- de stappenbalk en de drie taken (`showTask`, “Uitspraak kiezen / Aanvullen / Afronden”);
- de samenvatting met ‘Beantwoorden’ en ‘Aanpassen’, en de lijst ‘Niet ingevuld’;
- de veldeditor met de betekenisvelden en ontbreekredenen;
- de invoer voor richting en sterkte, met het aanwijzen van bronbewijs;
- de keuzes voor type, rol, ‘essentieel of aanvullend’, ‘onderbouwt of verklaart’ en ‘niet van toepassing’;
- de annotatiekiezer, ‘Bewaren, document en meer acties’, ‘Volgende annotatie’ en ‘Hele annotatie terugnemen’;
- ‘Betekenis voorstellen’, ‘Vorige stap’, de selectiehulpmiddelen en de lijst met gekoppelde brontekst;
- het herstel van een *essentieel verband* (opnieuw aanwijzen of terugnemen met een reden), dat in de kaart al onbereikbaar was;
- het bevestigingsvenster, dat alleen die onderdelen gebruikten;
- de bijbehorende CSS en `labels` in het veldcontract.

## Wat de kaart nu zelf bijhoudt

Wat het script uit verborgen formuliervelden las, is gewone toestand in het script geworden:

- het soort (`entry.object_type`);
- de rol bij het koppelen: + bij Uitspraak, Hoort erbij of Onderbouwing;
- ‘niet essentieel’ en ‘onderbouwt’ voor alles wat de kaart koppelt;
- ‘niet van toepassing’ (`entry.evidence_not_applicable`).

De soorten komen uit de paginadata (`state.kinds`) in plaats van uit de verborgen keuzelijst. De editor gaat van 1121 naar 691 regels.

## Niet in deze wijziging

- De kernelregel voor essentiële verbanden (opnieuw aanwijzen of reden geven). Nieuwe kaartdata kan die niet meer raken. Het opruimen daarvan is een aparte wijziging in kernel en database (Class A) en volgt als voorstel.
- Een annotatie uit het stappenformulier met een essentieel verband kan in de kaart niet meer worden hersteld. Besluit William: zo'n document wordt verwijderd en opnieuw ingeleverd.
- De praktijkproef blijft voorwaarde voor productie-uitrol (#1060).
