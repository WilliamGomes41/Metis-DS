# Actuele documentgegevens en expliciete verwerkingsinputs

De bestaande documentaggregate houdt identiteit, scalars, revisie, objectgeneratie,
bron- en proofpins en de documentlock. De compacte zijrij is dezelfde aggregate,
geen aparte workflow- of afsluitautoriteit.

```mermaid
flowchart TD
    UI[Review / Vorming / publicatie] --> D[Documentstore: actuele header]
    D --> ROW[workflow.documents: scalars, pins, revision, lock]
    D --> INPUTS[document_inputs: overige metadata, vaste refs, extractieheader]
    UI --> F[Expliciete vormingscontrole]
    UI --> Q[Gerichte kwaliteitsinput]
    UI --> S[Expliciete bronlezing]
    UI --> T[Expliciet beslisboombewijs]
    UI --> H[Geautoriseerde diagnose / export]
    F --> OWNER[FormationTaskStore: immutable archive en verzegelde leden]
    Q --> OWNER
    T --> OWNER
    S --> SOURCE[prepared_extraction_versions / bestaande bronviews]
    H --> OWNER
    H --> ORIGINAL[Behouden oorspronkelijke envelope en volledige historie]
    UI --> CMD[Bestaande review- en publicatiecommando's]
    CMD -->|review met voorbereide invoer en bronselectiecorrectie| PREP[Voorbereiden zonder schrijflock]
    PREP --> GUARD[Actuele rechten, bron en revisie controleren onder opslaglock]
    GUARD --> COMMIT[Correctie, bindings, feiten en audit in één workflowtransactie]
    CMD --> ROW
    CMD --> INPUTS
    PRODUCER[Producer: voorbereiden buiten transactielock] --> OWNER
    PRODUCER --> SOURCE
    PRODUCER --> CAS[Commit: actuele claim, bron, proof en revisie toetsen]
    CAS --> OBJECTS[Bestaande objectwriter: nieuwe rijen in begrensde groepen]
    OBJECTS --> CHECK[Exacte identiteit, positie, inhoud en mutatie-epochs toetsen]
    OBJECTS --> GENERATION[Database: objectgeneratie ophogen met het aantal geraakte rijen]
    GENERATION --> ROW
    CHECK --> ACTIVATION[Volledige activatie in één transactie]
    CAS --> ROW
    CAS --> INPUTS
```

Voor nieuwe ontvangst kiest expliciete configuratie de opslagvorm. Voor bestaande
gegevens bereidt een afzonderlijke operatie de oorspronkelijke inputs voor; een
CAS op dezelfde documentrij activeert de representatie. Reads migreren niets.
Een geactiveerde compacte representatie blijft actief als nieuwe admission wordt
uitgezet; oudere writers worden geweigerd.

Bij vorming blijven afgeronde taken afzonderlijk opgeslagen. De uiteindelijke
activatie groepeert alleen aangrenzende nieuwe objectrijen. Per SQL-statement
verhoogt de database de bestaande objectgeneratie met het exacte aantal geraakte
rijen; alle oorspronkelijke document- en objectcontroles blijven gelden. Een
mislukte activatie draait in haar geheel terug, terwijl eerder afgeronde taken
beschikbaar blijven voor hervatten. Ook bestaande schrijvers gebruiken dezelfde
generatieteller. Zie [W4](../change-contracts/729-w4-formation-database-work.md).

De beslisgraaf, reviewbesluiten en deelnameafspraken blijven actuele mutable
gegevens. Broninventory, vormingsherkomst en constructiebewijs blijven exact
bewaard. De kleine kaartprojectie is uitsluitend een weergave en levert geen
bewijs voor commando's of publicatie. De bestaande publicatieregistratie blijft
bepalen wat geleverd wordt.

Backupversie 9 neemt de compacte gegevens, refs en verzegelde archiefleden op in
de bestaande atomische workflowbackup. Productiecutover van bestaande gegevens
valt onder MET-44; dit diagram beschrijft de code en geen gedeployde omgeving.
