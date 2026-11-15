# #1060 — Toevoegen via een menu bij de selectie

Change class: B
Promise: In de annotatiekaart voeg je tekst op één manier toe. Na een selectie in de bron verschijnt direct onder de selectie een menu: Uitspraak, Hoort erbij en Onderbouwing. Zonder uitspraak toont het alleen Uitspraak. De + in de kaart verdwijnt, en daarmee de ‘ingedrukte +’ waarbij de volgende selectie wordt gekoppeld. Wat er wordt toegevoegd en met welke gevolgen, blijft gelijk: ook een extra stuk aan een uitspraak, de afleiding door Metis, de controle en de voorstellen. Alleen de manier van toevoegen verandert.
Proof: De browserproeven van de kaart lopen via het menu en leveren dezelfde opgeslagen annotaties op als voorheen: uitspraak, extra stuk, Hoort erbij, Onderbouwing, gelijktijdige tabs, mislukte opslag, review-correctie en herbouw. Nieuwe proeven eisen dat de kaart geen + meer heeft, dat het menu zonder uitspraak alleen Uitspraak toont en met uitspraak alle drie, dat het direct onder de selectie staat, dat Tab vanuit de bronpassage het menu bereikt en Escape het sluit, en dat het op een telefoonbreedte binnen het document blijft zonder zijwaarts scrollen.
Touches lifecycle invariants: no
Rewrite risk: none

Part of MET-78. Besluit William, 15 november 2026, vastgelegd in #1060 en MET-78: “Ik wil bij alles maar 1 manier, minder cognitieve belasting. Alleen moet ik zeker weten dat het hetzelfde blijft doen, dus een extra stuk aan een uitspraak etc. Alleen de manier van toevoegen verandert.”

Waarom rewrite risk none: alleen de bediening in de browser verandert. Het menu roept dezelfde functies aan als de + (`useAs` → `bindRange`). Het opslagcommando, de kernel, de database, de bouw en de review veranderen niet.

## Aanleiding

William: “je moet selecteren aan de linker kant en daarna met je muis naar de rechterkant om op de + te klikken. Dat is niet intuïtief.” Eerst + en dan selecteren deed soms niets. Zonder uitspraak deed een + zonder selectie inderdaad niets (`arm` in `human_annotation_editor.js`).

## Wat er verandert

- **Menu bij de selectie** (`#annotation-selection-menu`, `role="toolbar"`):
  - het staat in het scrollende document, direct na het bronblok en onder de selectie, en scrolt mee;
  - Tab vanuit de bronpassage bereikt het; pijltjestoetsen gaan tussen de knoppen; Escape sluit het en zet de focus terug op de passage;
  - de muis neemt bij het klikken de selectie niet weg;
  - op een telefoon staat het onder de selectie, zodat het niet botst met het eigen menu van de telefoon.
- **Weg:** de + bij Uitspraak, Hoort erbij en Onderbouwing, de toestand `armed`, de hints ‘Selecteer … in de bron’ bij een ingedrukte +, en de mobiele linktekst ‘Aanwijzing koppelen’.
- **Teksten:** de uitlegregel, de statusregel en de hint bij Onderbouwing noemen het menu in plaats van de +.
- **Blijft:** de − bij elke tekst; de + en − bij een voorstel van Metis, want dat is het beantwoorden van een voorstel en geen toevoegen uit een selectie; ‘Opslaan en naar volgend kennisobject’, dat een geselecteerde uitspraak vastlegt.
- Een opgeslagen tussenselectie (`pending_range`) krijgt geen rol ‘onderbouwing’ meer vooraf, want de keuze volgt nu ná de selectie. Ze dient alleen om de selectie te herstellen.
