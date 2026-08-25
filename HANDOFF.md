# V&VN Data Services — Actuele handoff

**Bijgewerkt:** 2026-08-25  
**Geldend protocol:** v2.3.0  
**Authoritative remote:** `WilliamGomes41/VENVN-DS`  
**Default branch:** `main`

## Actuele waarheid

- Protocol v2.3.0 is op 2026-08-25 door de projecteigenaar goedgekeurd; v2.2.0 en de v2.3-delta vormen samen de normatieve baseline.
- Step 12C repository hardening is naar `main` gebracht.
- PR #7 met stackbaseline, infrastructuurmanifest, G0 en kostencontrole is gemerged als `f1f813a240c2e75be03d2c373f43d6b7686d8164`.
- PR #8 met de protocolgestuurde ontwikkelhiërarchie is gemerged.
- PR #4: source integrity en PDF-provenance, gemerged.
- PR #5: PDF text-completeness gate, gemerged.
- PR #6: scoped HTML-extractie, gemerged; CI was groen.
- De exacte officiële HTML-representatie van bron 2 is lokaal geverifieerd en deterministisch geëxtraheerd.
- Bron 2 blijft `BLOCKED` voor publicatie zolang immutable opslag, definitieve registratie en klinische review ontbreken.
- G0 Local Development is `PASS` op basis van de vastgelegde lokale stack en manifestcontrole.
- G0 Azure DEV blijft `BLOCKED`: Azure-toegang, runtime, database, immutable bronopslag, secrets, monitoring, back-up, regio, operationeel eigenaarschap en kosten zijn nog niet volledig besloten.

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
6. Zodra Azure-toegang beschikbaar is: de open G0 Azure DEV-besluiten invullen vóór provisioning.

Geen nieuwe C3-C6-wijziging wordt gemerged voordat punt 1 is afgerond en de toepasselijke reviews compleet zijn.

## hervattingsinstructie

Bij hervatting worden achtereenvolgens volledig gelezen:

1. `PROTOCOL.md` en de gekoppelde geldende protocolspecificatie;
2. `ROADMAP.md`;
3. `HANDOFF.md`;
4. de relevante acceptatie- en invarianttests;
5. pas daarna de implementatiecode.

Na iedere materiële merge wordt deze handoff in dezelfde PR bijgewerkt met: mergecommit, afgeronde gate, resterende blokkades, afwijkingen en één eerstvolgende concrete taak.

