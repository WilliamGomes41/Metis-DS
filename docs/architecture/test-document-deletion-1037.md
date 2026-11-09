# Publisher verwijdert een testdocument

Deze functie is standaard uitgeschakeld. Alleen tijdens de expliciet
ingeschakelde testfase kan een publisher de volledige opgeslagen documentlijn
verwijderen. De console toont een voorstel en bevestiging; de kernel beslist
en schrijft alle domeingegevens in één PostgreSQL-transactie.

```mermaid
flowchart TD
    UI[Documenten: publisher] --> PREVIEW[Alle versies en publicaties tonen]
    PREVIEW --> CONFIRM[Titel, reden en testgegevens bevestigen]
    CONFIRM --> KERNEL[Kernel: rol, testmodus en actuele scope toetsen]
    KERNEL --> LOCK[Document- en publicatieautoriteiten vergrendelen]
    LOCK --> TX[Een PostgreSQL-transactie]
    TX --> RECEIPT[Append-only verwijderregistratie en snapshotfences]
    TX --> WORK[Documentlijn en bijbehorende workflowrijen verwijderen]
    TX --> CANON[Eigen canonical versies, bronbindings en releases verwijderen]
    TX --> REGISTRY[Publicatieregister: verwijderde kennis niet meer leveren]
    RECEIPT --> STALE[Oude workers en snapshotinserts weigeren]
    RECEIPT --> BACKUP[Workflowbackup versie 14 en lege-doelrestore]
    AUDIT[Bestaande globale reviewhashketen] --> KEEP[Eventinhoud behouden, document-FK losmaken]
    SOURCE[Bronbestanden en infrastructuurbackups] --> RETAIN[Bestaand bewaarbeleid]
    REGISTRY --> API[Product API en console tonen het document niet meer]
```

De identiteit komt uit `logical_document_id`, nooit uit een titelvergelijking.
Een gemengde publicatie of een verwijzing vanuit een andere documentlijn wordt
geweigerd. Lopende verwerking moet eerst gestopt zijn. Een gewijzigd voorstel
vraagt opnieuw bevestiging. Eenzelfde command ID met dezelfde inhoud geeft
dezelfde opgeslagen uitkomst; afwijkende inhoud conflicteert.

De SQL-fences blijven actief na uitschakelen van de functie of terugrollen van
applicatiecode. Workflowbackup 14 neemt de registraties op. Een oude archivevorm
met nieuwe verwijdergegevens wordt geweigerd; een expliciet oudere back-up mag
alleen via de bestaande lege-doelprocedure worden hersteld.

## Installeren en later uitschakelen

De normale containerreleaseprocedure blijft gelden. Eerst migratie 039 via het
gecontroleerde migratieplan toepassen. De migratie verwijdert geen bestaande
gegevens. Gebruik bij het controleren van de runtimegrants expliciet
`verify --runtime-role <rol> --test-document-deletion`; alleen dit profiel vraagt
de extra DELETE-grants op de canonical tabellen en operationele documentregels.
De verifier voert GRANT-statements niet uit.

Na succesvolle review en release kan de beheerder
`CONSOLE_TEST_DOCUMENT_DELETION=on` instellen. Zet deze instelling na de testfase
weer op `off`. Verwijder de receipt-/fencetabellen en triggers niet als rollback;
code terugrollen herstelt geen verwijderde documenten.

Zie het [volledige lifecyclecontract](../change-contracts/1037-publisher-test-document-deletion.md)
voor autoriteiten, fout-/herstelgedrag en bewijsgrenzen. Dit document verklaart
geen productie-uitrol of uitgevoerde verwijdering.
