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
