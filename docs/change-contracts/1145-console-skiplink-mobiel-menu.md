# Skiplink en mobiel menu in de Metis-console

Change class: B
Promise: De eerste Tab maakt de link naar hoofdinhoud zichtbaar. Op smalle schermen kan de gebruiker bij de beschikbare werkruimtes en accountacties via één menu.
Proof: Chromium op 320, 390, 1360 en 1440 px controleert de eerste Tab, de bestemming van de skiplink, de menubediening, desktopnavigatie, Uitleg, Review en een foutpagina.
Touches lifecycle invariants: no
Rewrite risk: none

William geeft op 23 november 2026 opdracht voor de volgende UX-PR met “Pak hwt volgend op”. [GitHub #1145](https://github.com/WilliamGomes41/Metis-DS/issues/1145) · [Besproken ontwerp](https://github.com/WilliamGomes41/Metis-DS/issues/1045#issuecomment-7083786548)

De server blijft één navigatie en één set bestaande links produceren. De gedeelde pagina zet de skiplink vóór de kop en gebruikt een focusbaar hoofdinhoudsgebied. De passageweergave van Review sluit aan op de gedeelde kop. Uitleg behoudt zijn eigen hoofdinhoudsgebied als bestemming. De normale inhoud en foutmeldingen vallen binnen hoofdinhoud. Sessiewaarschuwingen en Raad blijven bij de navigatie.

Tot en met 860 CSS-pixels toont de gesloten kop het merk en de menuknop met de actieve werkruimte. Enter en Spatie openen of sluiten het menu. Escape sluit het en brengt focus terug naar de knop. Op brede schermen is de lijst direct bereikbaar. Als JavaScript ontbreekt blijft de lijst zichtbaar. De acties voor thema en uitloggen gebruiken hun bestaande bediening en routes. De selectie van documenten, reviewopdrachten en toegangscontrole behouden hun bestaande eigenaren.

Dit contract wijzigt de presentatie van de kop in [het desktopcontract](console-header-readability.md). Het Review-werkbord en de contrastuitzondering voor Mijn werk vallen buiten deze opdracht.
