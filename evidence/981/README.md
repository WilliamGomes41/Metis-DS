# #981: modulecontext voor aanbevelingstaken

## Wat is veranderd

`bounded_formation_v1.tasks_for` koos context op koptekst. Elk blok met
`heading in section_path` ging mee, ook een gelijknamige kop uit een andere
module. Een zustersectie in dezelfde module, zoals Rationale, ontbrak.

Nu geldt een structurele regel:

- dezelfde sectie, zoals voorheen;
- koppen van bovenliggende secties, alleen als hun eigen pad een prefix is van
  het taakpad;
- de hele bronmodule voor een taak met een mogelijke aanbeveling (het bestaande
  inventarissignaal van het taakplan). De module is het niveau onder de gedeelde
  documentwortel, dus ook bij parsers die de documenttitel vooraan zetten.
  Blokken zonder sectiepad tellen niet mee voor die wortel;
- expliciete verwijzingen (Tabel, Figuur, Bijlage) blijven exact traceerbaar,
  ook naar een andere module.

Kandidaatbereiken blijven gescheiden van context. Een te grote context blijft
`source_task_context_limit_exceeded`, zonder afkapping. Vastgelegde taakplannen
bewaren hun `evidence_block_ids`; herstel gebruikt die en wordt niet stil herschreven.

## Meting op echte bronstructuur

Bron: de geëxporteerde `source_views` van de Smetten-richtlijn (923 fragmenten,
Docling) uit het processing-evidence-archief van de projectlead. Alleen lokaal
gebruikt; hier staan alleen aantallen.

| | trunk | head |
|---|---|---|
| taken | 146 | 146 |
| taken met een kop uit een andere module | 104 | 5 (alle via expliciete Bijlage/Tabel-verwijzing) |
| aanbevelingssectie-taken met Rationale van eigen module | 0 van 8 | 7 van 8 |
| aanbevelingssectie-taken met overwegingen van eigen module | 0 van 8 | 5 van 8 |
| contexttekens totaal | 107.408 | 350.565 |
| contexttekens maximum per taak | 6.937 | 40.511 |
| taken boven de limiet (48.000) | 0 | 0 |

De ene aanbevelingstaak zonder Rationale bevat geen mogelijke aanbeveling volgens
het inventarissignaal en krijgt daarom geen modulecontext.

Afgewezen alternatief: modulecontext voor élke taak. Dat gaf 8 van 8 met
Rationale, maar 2.860.648 contexttekens, 25 keer de bron, en dus veel duurdere
modelaanroepen.

## Niet bewezen

Of bredere context betere modelkeuzes oplevert, is hiermee niet aangetoond. Dat
blijft de onafhankelijke referentiemeting in #530.

## Moduleniveau in de meting (Codex-review)

`measure_context.py` vergelijkt modules op hetzelfde niveau dat de productiecode detecteert (`_module_depth`), niet langer vast op het eerste padniveau. De meting is twee keer gedraaid.

| Run | Gevonden moduleniveau | Resultaat |
|---|---|---|
| Echte Smetten-export (15 modules op het eerste niveau, geen titel) | 1 | Ongewijzigd: vreemde koppen 5, Rationale 7 van 8, overwegingen 5 van 8, totaal 350.565 tekens, maximaal 40.511 |
| Dezelfde blokken met de titel "Smetten" vooraan in elk pad | 2 | Identiek aan de run hierboven |

## Bekende grens: één module zonder titel

Een document met één module en zonder titel (`[module, Aanbevelingen]`) heeft dezelfde vorm als een document met titel en platte modules (`[titel, module]`). Geen structurele regel kan die twee scheiden.

Context die over modules heen lekt, is de ergste fout. Daarom wint altijd het smallere niveau. Zo'n document met één module krijgt het gedrag van trunk: de eigen sectie en de koppen erboven, zonder de zustersecties. Dat is geen achteruitgang ten opzichte van main.

De tests `test_untitled_single_module_keeps_trunk_context_and_never_leaks` en `test_titled_document_with_only_flat_modules_does_not_leak` leggen beide kanten vast.
