# D6a — bewijs en resterende publicatie

Deze index onderscheidt uitgevoerde historische metingen van de actuele
publicatie. Class C, Rewrite risk: none. D6b is niet gestart.

## Actuele basis

De PR’s [#810](https://github.com/WilliamGomes41/Metis-DS/pull/810),
[#811](https://github.com/WilliamGomes41/Metis-DS/pull/811) en
[#812](https://github.com/WilliamGomes41/Metis-DS/pull/812) zijn gemerged in main.
Hun volledige Python 3.12/3.13-matrices en aanvullende workflows zijn groen,
zonder PostgreSQL-skips. Python 3.13 meet respectievelijk 1,8675×, 1,9358×
en 1,9496× tegen de ongewijzigde pinned baseline 9fa2004 (grens 2×).
Zie [CI-reparatie](ci-repair-810-812.json) en de uitvoer in de drie PR’s.
Dit bewijs geldt voor die gemeten revisies.

## Resterende porties

- 20: verdeeld over de oorspronkelijke afnemers; geen afzonderlijke PR.
- 21: testmigratie en golden-afnemers al opgenomen in #812. De resterende
  expliciete PostgreSQL 16-service voor characterization en bewijsindex
  staan op `codex/d6a-21-main`. De 123 huidige routes blijven behouden.
- 22: `codex/d6a-22-main` vervangt het muterende batchreview-harnas door
  echte PostgreSQL-commando’s en synchroniseert tijdelijke appconfiguratie.
  Alle oorspronkelijke 22 batchreview-scenario’s blijven behouden.

Beide PR’s richten op main; beoordeel 21 vóór 22. De tweede branch bevat
haar voorganger totdat die gemerged is. Productiecode, schema, fixture-isolatie,
TLS-controle, pinned baseline en 2×-tijdgrens blijven behouden.

## Bewijsbronnen

- [Portie- en testbestandenindex](batches.json): oorspronkelijke lokale proeven;
  de velden voor 20–22 onderscheiden reeds geleverde en resterende wijzigingen.
- [Characterization-goldenreview](characterization-golden-review.json):
  exact PG-gedrag en expliciete file_topology-goldens.
- [Eerste portie, historische metingen](first-portion-history.md): de oorspronkelijke
  metingen inclusief destijds rode SSRF-proeven, zonder ze als huidig groen bewijs
  te presenteren.
- [Publicatie van 17](publication-17-main.json), [18](publication-18-main.json) en
  [19](publication-19-main.json): gerichte lokale bewijzen van de eerdere publicatie.

Volledige CI en tijdmetingen op de nieuwe heads zijn afzonderlijke gates.
Deze index verklaart D6a niet afgerond en vervangt geen review of mergebesluit.
