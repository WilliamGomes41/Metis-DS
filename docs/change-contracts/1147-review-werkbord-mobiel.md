# Open beoordelingen op het mobiele Review-werkbord

Change class: B
Promise: Op het persoonlijke Review-werkbord staat bij 390 × 844 px een open reviewactie in het eerste scherm. Actieve filters blijven zichtbaar en het filterformulier is bereikbaar.
Proof: De bestaande Chromium-proef met PostgreSQL meet de eerste reviewactie vóór en na de wijziging en controleert het filterformulier, de actieve filters, de lege uitkomst en de desktoprij.
Touches lifecycle invariants: no
Rewrite risk: none

William geeft op 23 november 2026 opdracht voor deze stap met “Ga verder met implementatie”. [GitHub #1147](https://github.com/WilliamGomes41/Metis-DS/issues/1147) · [Implementatieontwerp](https://github.com/WilliamGomes41/Metis-DS/issues/1045#issuecomment-7083786548)

Op het persoonlijke werkbord volgt na de kop een compacte verwijzing naar de filters. Een actieve zoekterm en een actief thema worden daar getoond. De link brengt focus naar het ene GET-formulier na de kaarten. Vanaf 861 px verplaatst de browser hetzelfde formulier boven de resultaten en verdwijnt de korte verwijzing. De volgorde waarin toetsenbordgebruikers de bediening tegenkomen volgt de plaats op het scherm. Bij een breedtewisseling blijven ingevoerde gegevens en de focus in het formulier behouden. Zonder JavaScript blijft het formulier bereikbaar via de link.

De werkbordroute gebruikt de bestaande rolcontrole, toegewezen documenten, sortering, paginering en gefilterde leesprojectie. De formuliervelden en hun betekenis volgen de bestaande Review-route. Het tabblad Alle reviewtrajecten gebruikt zijn bestaande weergave en de Review-opdrachten behouden hun bestaande eigenaar.
