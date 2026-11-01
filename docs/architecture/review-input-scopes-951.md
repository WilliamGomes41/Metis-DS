# Review: passage-invoer en documentbeoordeling

Een passage toont de actuele kandidaat met alle noodzakelijke verbonden context.
Een niet berekende documentbeoordeling betekent niet dat de vorming compleet is.
De bestaande vormings- en publicatieowners blijven die uitkomst bepalen.

```mermaid
flowchart TD
    GET[Passage GET] --> CAP[Repeatable-read capture: bestaande 5 seconden]
    CAP --> HEADER[Compacte documentmetadata en generatie]
    CAP --> KEYS[Actuele afhankelijkheden: generated keys uit objectpayload]
    KEYS --> HIST[Volledige historie van noodzakelijke objectidentiteiten]
    CAP --> BIND[Bindings uit hetzelfde snapshot]
    HIST --> WINDOW[Gevalideerd bronvenster]
    BIND --> PASSAGE[Passage-invoer: document niet beoordeeld]
    WINDOW --> PASSAGE
    HEADER --> PASSAGE
    PICKER[Contextkiezer] --> DTO[Pagina met weergavegegevens; geen reviewauthority]
    DTO --> PASSAGE
    SELECT[Expliciet gekozen contextdoel] --> KEYS
    DOC[Documentbeoordeling] --> FULL[Complete bron, objecten en vastgelegde poging]
    FULL --> OWNER[Bestaande vormingsowner]
    POST[Review POST] --> GUARDS[Actuele rol, bron, generatie en bestaande reviewkernel]
    GUARDS --> WRITE[Originele objectpayload en binding]
    WRITE --> DERIVE[PostgreSQL leidt keys atomair af]
    PUB[Expliciete publicatie] --> READY[Bestaande readiness en publicatieregistry]
    OWNER --> READY
```

`document_objects.payload` blijft de enige objectauthority. Migratie 031 voegt
een opgeslagen, automatisch afgeleide dependencywaarde toe. Alle oorspronkelijke
writers, inclusief directe SQL en herstel, onderhouden die waarde via PostgreSQL.
Historische edges bepalen geen actuele context; volledige historie blijft nodig
voor de lineagecontrole van geselecteerde identiteiten. De picker is geen extra
recursieve contextseed. Expliciete doelen en opgeslagen koppelingen zijn dat wel.

Bij compacte documentopslag worden pogingen en bewijsverwijzingen binnen hetzelfde
snapshot als objecten en bindings vastgelegd. Immutable bewijs wordt daarna via
die verwijzingen gelezen. Een ondertussen gestarte nieuwe poging wordt niet met
de eerdere bron/objectgeneratie gecombineerd. De legacy documentbeoordeling
behoudt haar expliciete volledige invoer tot de afzonderlijke opslagovergang.

Migratie vindt vóór de nieuwe binary plaats. Startup weigert een ontbrekende of
vervalste gewone kolom. Een oude binary kan de oorspronkelijke payload blijven
schrijven; rollback vereist geen verwijdering van bewijs of besluiten. Backup en
restore gebruiken de oorspronkelijke payload en bouwen de afleiding opnieuw op.

Dit diagram beschrijft de implementatie, geen bewijs van productieherstel.
Zie het [wijzigingscontract](../change-contracts/met42-scoped-review-inputs.md)
voor scope, compatibiliteit, metingen en de resterende live verificatie.
