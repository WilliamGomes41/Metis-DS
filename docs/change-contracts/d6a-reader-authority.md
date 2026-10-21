# PG-lezers bij de bestaande reviewkeuze (D6a-voorwaarde)

Change class: B
Promise: een bestaande lezer wordt bij een reviewkeuze ook in de productieconsole herkend; onbekende lezers blijven geweigerd.
Proof: dezelfde upload-/reviewkeuzetests op de productieklasse met PostgreSQL, inclusief onbekende lezer en lezer/reviewer-conflict.
Touches lifecycle invariants: no
Rewrite risk: none

De migratie naar PostgreSQL liet zien dat
`OperationsConsole._chosen_review_configuration` de private `_accounts`-map
las, terwijl de productieklasse accounts via PostgreSQL beheert. De
bestaande `list_accounts()`-methode is het gedeelde leescontract: de basis
leest haar map, de PG-mixin leest de identity store. Ingest roept dezelfde
keuzevalidatie aan, met dezelfde fout `unknown_reader` en dezelfde latere
controles op reviewers en beleid. Alleen de account-ID-lookup verandert;
deze lookup schrijft geen toestand en verandert geen rollen, reviewplicht,
release, bron of serving. Bestaande mutatie-/transactiegrenzen blijven gelden.

De eerste migratierun wees vier bestaande gevallen af met `unknown_reader`.
De PG-portie bewaart die bestaande cases en toetst daarnaast dat een oude
lokale accountmap geen onbekende lezer kan legitimeren. Dit is een begrensde
Class B-reparatie die tijdens de Class C-testmigratie zichtbaar werd.
