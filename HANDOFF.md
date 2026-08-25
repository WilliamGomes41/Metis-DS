# V&VN Data Services — Actuele handoff

**Bijgewerkt:** 2026-08-25  
**Geldend protocol:** v2.2.0  
**Authoritative remote:** `WilliamGomes41/VENVN-DS`  
**Default branch:** `main`

## Actuele waarheid

- Protocol v2.2.0 is goedgekeurd voor projectgebruik.
- Step 12C repository hardening is naar `main` gebracht.
- PR #4: source integrity en PDF-provenance, gemerged.
- PR #5: PDF text-completeness gate, gemerged.
- PR #6: scoped HTML-extractie, gemerged; CI was groen.
- De exacte officiële HTML-representatie van bron 2 is lokaal geverifieerd en deterministisch geëxtraheerd.
- Bron 2 blijft `BLOCKED` voor publicatie zolang immutable opslag, definitieve registratie en klinische review ontbreken.
- Azure DEV is nog niet beschikbaar; dit blokkeert de huidige lokale/governancewerkzaamheden niet.

## Open governancepunt

GD-03 is nog niet formeel vastgesteld. Het operationele voorstel is:

| Klasse | Minimum | Verplichte rollen |
|---|---:|---|
| C3 | 2 | klinisch + technisch |
| C4 | 2 | evaluatie + technisch |
| C5 | 2 | security/operations + technisch |
| C6 | 3 | klinisch + technisch + safety/evaluatie |

Reviewers zijn onafhankelijk van de auteur en beoordelen dezelfde exacte commit of snapshot. PR #4 en PR #5 zijn C5-wijzigingen en vereisen retrospectieve onafhankelijke technische en security/operations-review.

## Eerstvolgende taak

1. GD-03 formeel vaststellen en de evidence-URL registreren.
2. Retrospectieve C5-reviews van PR #4 en PR #5 vastleggen.
3. Exacte bron 2 duurzaam en immutable opslaan.
4. Source manifest voltooien en integriteit opnieuw verifiëren.
5. Klinische review van bron 2 uitvoeren.

Geen nieuwe C3-C6-wijziging wordt gemerged voordat punt 1 is afgerond en de toepasselijke reviews compleet zijn.

## hervattingsinstructie

Bij hervatting worden achtereenvolgens volledig gelezen:

1. `PROTOCOL.md` en de gekoppelde geldende protocolspecificatie;
2. `ROADMAP.md`;
3. `HANDOFF.md`;
4. de relevante acceptatie- en invarianttests;
5. pas daarna de implementatiecode.

Na iedere materiële merge wordt deze handoff in dezelfde PR bijgewerkt met: mergecommit, afgeronde gate, resterende blokkades, afwijkingen en één eerstvolgende concrete taak.

