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

## Titelniveau uit het parsercontract (#997)

Na #994 riep de vorming het titelniveau af uit de vorm van de paden. Dat leverde twee bekende grenzen op. Nu komt het uit wat de parser zelf heeft vastgelegd:

- **HTML** bewaart de tag van elk blok in de locator. Een `<h1>` met dieper liggende inhoud eronder is een container, bijvoorbeeld een titel met modulekoppen in `<h2>`. De module ligt dan één niveau lager. Een `<h1>` zonder iets eronder, zoals een platte bijlage, is een gewone sectie. Een titel én een bijlage-`<h1>` naast elkaar houden de modules dus gescheiden (Codex-bevinding).
- **Docling** labelt de titel apart en zet hem nooit vóór de modulekoppen. Een PDF heeft daarom geen container.

`document_title_paths(fragments)` leest de containers uit de evidence-fragmenten. De inhoudsfragmenten zijn hiervoor niet bruikbaar, omdat die geen koppen bevatten. `module_of(section, title_paths)` geeft het niveau direct onder de container terug. Zonder container is dat het eerste padniveau. De structuurgok (`module_depth`) is verwijderd.

De bronblokken veranderen niet. Hashes van bestaande taakplannen blijven dus geldig, en vastgezette plannen houden hun `evidence_block_ids`.

| Run | Container | Resultaat |
|---|---|---|
| Echte Smetten-export | geen | Vreemde koppen 5, Rationale 7 van 8, overwegingen 5 van 8, 350.565 tekens totaal, maximaal 40.511 |
| Met titel "Smetten" vóór elk pad | `Smetten` | Identiek |
| Idem, plus een bijlage `[Bijlagen]` op het hoogste niveau | `Smetten` | Identiek (147 taken) |
| Idem, met een normatieve zin in de bijlage | `Smetten` | Identiek: de bijlage is een eigen sectie en lekt niet meer |

Beide grenzen uit #994 zijn daarmee opgelost:

1. Een document met één module zonder titel krijgt nu zijn Rationale.
2. Een document met een titel en een normatieve bijlage laat de modules gescheiden.

## Moduleniveau in de meting (Codex-review)

Historisch (#994): de meting vergeleek modules op het niveau dat de toenmalige structuurregel bepaalde. Sinds #997 gebruikt `measure_context.py` `module_of` met het titelpad als tweede argument.

| Run | Gevonden moduleniveau | Resultaat |
|---|---|---|
| Echte Smetten-export (15 modules op het eerste niveau, geen titel) | 1 | Ongewijzigd: vreemde koppen 5, Rationale 7 van 8, overwegingen 5 van 8, totaal 350.565 tekens, maximaal 40.511 |
| Dezelfde blokken met de titel "Smetten" vooraan in elk pad | 2 | Identiek aan de run hierboven |
| Idem, plus een bijlage `[Bijlagen]` op het hoogste niveau | 2 | Identiek; 147 taken, waarvan de bijlage er één is zonder modulecontext |

## Historisch: grens van #994 (opgelost in #997)

Een document met één module en zonder titel (`[module, Aanbevelingen]`) heeft dezelfde vorm als een document met titel en platte modules (`[titel, module]`). Geen structurele regel kan die twee scheiden.

Context die over modules heen lekt, is de ergste fout. Daarom wint altijd het smallere niveau. Zo'n document met één module krijgt het gedrag van trunk: de eigen sectie en de koppen erboven, zonder de zustersecties. Dat is geen achteruitgang ten opzichte van main.

De tests `test_untitled_single_module_keeps_trunk_context_and_never_leaks` en `test_titled_document_with_only_flat_modules_does_not_leak` leggen beide kanten vast.
