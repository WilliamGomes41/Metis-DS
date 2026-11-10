# Leesbare bron in de annotatiewerkplek

Issue: #1017. PR: #1041.
Change class: B
Promise: De researcher leest de gepinde annotatiebron als één document met pagina's, koppen en alinea's, en wijst daaruit tekst aan via één selectiekaart.
Proof: De regressietest bewaart alle exacte bronblokken en hun tekst, vouwt de inhoudsopgave samen en toont geen bediening per blok. Gerichte PostgreSQL-tests en Chromiumproeven dekken annoteren, bouwen en corrigeren vanuit Review op desktop en mobiel. De volledige CI en toets aan de oorspronkelijke PDF blijven afzonderlijke acceptatiepunten.
Touches lifecycle invariants: no
Rewrite risk: none

## Aanleiding en oorzaak

De annotatiewerkplek presenteerde de extractie als losse bronblokken met telkens eigen selectiebediening. In de aangeleverde uitvoer waren dat 862 blokken over 46 pagina's, waaronder losse punten en cijfers uit de inhoudsopgave. Exacte ankers in de opslag waren nodig, maar de gebruiker hoefde die extractiegrenzen niet als afzonderlijke documenten te zien. De eerdere oplevering verwarde een werkende blokselector met de beloofde leesbare documentweergave.

## Herstel en grens

De renderer groepeert de bestaande gepinde blokken visueel per pagina en kop, toont de inhoudsopgave uitklapbaar en zet de selectiebediening in één kaart naast het document. Elk tekstbereik behoudt zijn blok-ID en codepointposities; opslag, rechten, review en publicatie worden niet veranderd.

De 862 blokken uit de geplakte uitvoer zijn met de nieuwe renderer gecontroleerd, maar de oorspronkelijke PDF is niet beschikbaar in deze werkruimte. De vergelijking van tekstvolledigheid en opmaak met die PDF en een echte researcherproef zijn daarom nog open. Een browserproef op voorbeelddata bewijst de bediening, geen inhoudelijke of menselijke praktijkacceptatie.

De eerste versie van de PR-beschrijving miste de verplichte change-contractvelden en de gestructureerde werkpakketoverdracht. Daardoor stopten de CI-poorten vóór de tests; de testjobs faalden vervolgens door ontbrekende suite-artefacten. De PR-beschrijving is aangevuld met de contractvelden, één werkpakketkoppeling en de actuele head-SHA zodat de controles opnieuw kunnen starten.
