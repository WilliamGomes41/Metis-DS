# PR 4 — A13 extractieverificatie

Dit PR maakt extractie een eigen meetbare stap: per bron wordt gesignaleerd welke kritieke structuur (tabellen, voetnoten, meerkoloms-layout, beslisboomranden) ontbreekt of onbetrouwbaar is. Alles in de keten is brongetrouw tóv de extractierepresentatie, dus fouten hier zijn voor alle latere controles onzichtbaar.

```text
Change class: B
Promise: Elke bron krijgt bij verwerking een A13-bevinding over tekstdekking, tabelstructuur en beslisboomranden ten opzichte van de PDF.
Proof: op een fixture met een weggelaten tabelrij en een beslisboom zonder tekstranden geeft extraction_findings respectievelijk table_structure_suspect en decision_edges_not_extracted.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

`audit_pdf_text_completeness.py` bestaat als los script, maar draait niet in de keten en kijkt niet naar structuur. Een passageregister dat sluit, bewijst niets over tekst die Docling nooit leverde. Bij beslisbomen staan de verbindingen vaak als vectortekening in de PDF; dan bestaat de randstructuur niet in de tekst.

## Ontwerp

- **Stateless.** `extraction_findings(pdf_evidence, fragments) -> list[Finding]`, gevoed met wat `decision_graph_v1.evidence_inventory` en de PDF-tekstlaag al opleveren.
- **Controles:** tekstdekking (tekens in PDF-tekstlaag die in geen fragment terugkomen), tabelvorm (rijen of kolommen die per pagina ongelijk tellen), voetnoten en kanttekst, en voor beslisbomen de verhouding tussen grafische verbindingen in de inventaris en randen in de graaf.
- **Uitkomst:** `UNRESOLVED`, nooit stil `PASS`, wanneer een controle niet kan draaien (bijvoorbeeld een gescande PDF zonder tekstlaag).
- **Geen nieuwe extractor.** Het PR herstelt niets aan de extractie; het meldt alleen.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_gate_a_v1.py` | `extraction_findings` toevoegen; hergebruikt `audit_pdf_text_completeness.audit` |
| `src/source_processing_dispatch_v1.py` | Bevindingen meegeven aan de bestaande verwerkingsdiagnostiek (`processing_diagnostics_v1`), niet als nieuwe status |
| `src/gnc_rule_registry_v1.py` | A13 registreren, ernst `signal` |
| `tests/test_gnc_gate_a_extraction_v1.py` | Fixtures: tabel met ontbrekende rij, tweekoloms pagina, beslisboom met alleen vectorranden |

## Wat niet verandert

De Docling-worker en zijn contract, de grens dat alleen `docling_worker_v1` Docling importeert, en elke opgeslagen fragmentrepresentatie.

## Tests en acceptatie

- [ ] Elke fixture geeft precies de verwachte bevinding.
- [ ] Een PDF zonder tekstlaag geeft `UNRESOLVED`.
- [ ] `check_architecture_boundaries.py` blijft groen.
- [ ] Schaduwrun (PR 11) toont het aandeel bronnen met A13-signalen per documenttype.
