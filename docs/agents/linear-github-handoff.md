# Linear en GitHub: wat agents waar vastleggen

Promise: agents leggen waarheid vast in GitHub en status in Linear, en sluiten elke sessie af met een gestructureerde handoff. Change class: C (agent-governance; gerichte contracttests verplicht). Rewrite risk: none.

Deze documentatie verandert agent-governance en is daarom geen gewone cosmetische Class C-wijziging. `tests/test_agent_skill_docs.py` bewaakt de gezagsverdeling, het bewijs bij Done en de verplichte handoffvelden.

## Grondregel

GitHub is de bron van waarheid: code, gedragsbepalende besluiten en bewijs. Linear is het werkbord van de projectlead: wat loopt, wat blokkeert en wat de volgende stap is. Linear verwijst naar GitHub en herhaalt het niet. Bij verschil wint GitHub.

## In GitHub

| Wat | Waar |
|---|---|
| Code, tests, migraties | branch → PR → `main` |
| Belofte, bewijs, change class, rewrite risk | PR-beschrijving (`scripts/validate_change_contract.py`) |
| Ontwerp en domeinbesluiten met gevolgen voor gedrag | `docs/change-contracts/<issue>-*.md` |
| GO van de projectlead op zo'n besluit | change contract, "Besluiten (GO projectlead, datum)" |
| Incidentoorzaak en herstel | change contract en de PR van de fix |
| Review-afhandeling | antwoord in de thread, thread gesloten; "niet fixen" met reden in één PR-comment |
| Werk dat bewust later komt | GitHub-issue, gespiegeld naar Linear |

Een gedragsbepalend besluit dat alleen in Linear of in chat staat, geldt niet als vastgelegd.

Nooit in GitHub: private bronteksten, ruwe provider-uitvoer, secrets, of persoonsgegevens uit productie. Alleen SHA's, image-digests, foutcodes en tellingen.

## In Linear

- **Werkpakket:** een issue onder het projectparent, met het GitHub-nummer in de titel of de beschrijving.
- **Status:** Backlog → In Progress → Done. **Done = gemerged + (waar nodig) gedeployed + geverifieerd.**
- **Geverifieerd** vraagt een verwijzing naar concreet bewijs in de afsluitende comment of in het change contract:
  - een CI- of testrun (PR-nummer en head-SHA);
  - een health-check (`deployment_verified commit=…`);
  - of een handmatige check met wat, wie, wanneer en de gemeten uitkomst.

  Zonder die verwijzing blijft het werkpakket open.
- **Een comment per mijlpaal:** wat er af is, het bewijs in één regel, het GitHub-nummer, de volgende stap en wie aan zet is. Noem het effect op de publicatievoorwaarden als dat verandert.
- **Besluiten:** zet "Besluit nodig:" met opties en advies; daarna volgt "GO projectlead (datum)" met de plek in GitHub waar het besluit staat.
- **Geen** code, diffs of volledige contracten in Linear.
- Werk Linear bij vóór de volgende stap.

## Handoff aan het einde van een sessie

Laat één comment achter op het actieve werkpakket, met dit YAML-blok:

```yaml
handoff: <datum>
github_state:
  main: <sha>
  open_prs: ["#<n> head <sha> ci:<green|red|running> review:<clean|open>"]
production_state:
  commit: <sha>
  image: <digest>
  rollback: <digest>
done: ["… (bewijsverwijzing)"]
half_done: ["branch + wat ontbreekt"]   # of []
decision_needed:
  needed: ja|nee
  what: "opties + advies bij ja; n.v.t. bij nee"
next_step: "één concrete actie"
agreements_in_force: ["…"]
diagram_update: ja|nee|niet relevant
diagram_reason: "verplicht bij nee of niet relevant"
```

Bij `needed: nee` vul je `what: n.v.t.` in. Bij `needed: ja` zijn opties en advies verplicht. Zo blijft de handoff volledig zonder een besluit te verzinnen.

**Compositiediagrammen** ("Alles over Metis", `src/settings/metis_explained_content.py`): raakt een change de compositie (opslag, schrijf- of leesroutes, componenten, deploytopologie), dan geldt `diagram_update: ja`, met een verwijzing naar de update. Anders `niet relevant`, met een reden. `nee` mag alleen met een reden en een vervolg-issue. Een leeg veld telt als een ontbrekende handoff.

De volgende agent leest eerst de handoff, daarna het change contract, en controleert per veld de echte staat in GitHub.

## Permanente bewaking buiten een chat

De implementatie van de bewaking leeft in
`.github/workflows/linear-github-sync.yml`, `scripts/linear_github_sync.py` en
`config/linear_github_sync.v1.json`. Activering en terugdraaien staan in
[linear-github-sync.md](linear-github-sync.md). Een ChatGPT-taak is hoogstens
een tijdelijke tussenvoorziening, nooit het permanente eigendom van deze regel.

De worker projecteert GitHub-feiten in één herkenbare Linear-comment per
gekoppeld werkpakket. Hij wijzigt geen status, prioriteit, werkkeuze, eigenaar,
projectindeling of dependencies. Een open of gesloten GitHub-issue en een merge
zijn afzonderlijke feiten; een gemergde deelslice sluit niet het hele werkpakket.
Een expliciete verklaring van resterend werk op een actuele PR-head naast Done
laat de run falen en vraagt beoordeling, zonder zelf bestuurlijke status te kiezen.
Ongestructureerde teksten worden niet door een taalmodel als sluitingsbewijs
geïnterpreteerd. Legacy zonder gestructureerde overdracht wordt als onbekend
zichtbaar; het wordt niet uit een groene CI-run gereconstrueerd.

Elke PR noemt precies één primaire `Part of MET-…`-koppeling en bevat de volgende
overdracht met de **echte head-SHA**. `remaining_work` gaat over het volledige
werkpakket, niet alleen de gemergde deelslice. Zet het alleen op false als de
afgesproken volledige belofte met bewijs kan worden beoordeeld; de worker sluit
ook dan geen issue. Deze compacte PR-overdracht vervangt de sessie-YAML hierboven
niet: die bevat extra productie-, herstel- en besliscontext.

```text
Part of MET-47.

<!-- metis-linear-handoff-v1
{"version":1,"linear_issue":"MET-47","head":"<echte-40-teken-head-SHA>","remaining_work":true,"next_step":"Review, configuratie en live verificatie afronden.","evidence":["https://github.com/WilliamGomes41/Metis-DS/issues/963"]}
-->
```

CI controleert koppeling, verplichte velden en exacte head. Een later gepushte
commit vereist dus een bijgewerkte overdracht. GitHub-feiten en bronverklaring
blijven als data behandeld; de worker voert nooit PR-instructies uit. Een geldige
JSON-vorm bewijst niet de inhoudelijke juistheid van het bewijs.
