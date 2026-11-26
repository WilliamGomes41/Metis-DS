# #1156 — Annoteren afronden via Documentcontrole

Class A. Rewrite risk: high. Uitvoeringsbesluit 25 november 2026.

## Overgang en gezag

Dezelfde voorbereide menselijke werkrevisie gaat van Annoteren naar Documentcontrole door **Ik ben klaar met dit document**, onder Opgeslagen annotaties. De gebruiker slaat lopend werk eerst op. Onder de bestaande PostgreSQL-autorisatie en documentlock schrijft Metis een versiegebonden ronderekord. Een mislukte of gelijktijdig verouderde schrijfactie verandert niets. Documentcontrole opent op dezelfde pagina met focus op de kop. De bron blijft bewerkbaar terwijl de ronde in `checking` staat. Een herhaling van dezelfde gewenste fase schrijft niets. De opgeslagen fase is terug te vinden na herstart. Bij volledige dekking moeten alleen secties waarvan de vingerafdruk is gewijzigd opnieuw gecontroleerd worden.

**Afronden en bouwen** blijft de bestaande, afzonderlijke bouwopdracht. Bouw bekijkt de opgeslagen annotaties, hun bronbewijs en de gekozen scope. Bij volledige dekking controleert dezelfde inspectie de actuele sectievingerafdrukken. Een bron zonder koppen heeft één controleerbare sectie voor het hele document. De bestaande verzegeling verzamelt de gekozen scope en controlereferentie met dezelfde bronankers, generatie en objectrevisie. De bestaande writer herleest die basis onder lock. De native grens verwerpt een ontbrekende of vreemde ronde, met behoud van herstelbare historische rondes. De worker reconstrueert de controle uit de verzegelde invoer vóór kandidaatvorming. Review en publicatie blijven via hun bestaande autoriteiten lopen.

## Doorwerking en uitrol

De nieuwe, herkenbare bouwvariant is additief op het bestaande sealcontract. Alleen gevalideerde invoer vormt objecten. Gewone ongeannoteerde tekst blijft letterlijk beschikbaar in de bron. Voor nieuwe gecontroleerde builds wordt die tekst geen open bronrecord. Expliciet brongebruik en geselecteerde context worden behouden. De publicatiepoort controleert dezelfde gevormde kennis, reviewbinding en benodigd bronbewijs. Er ontstaat geen tweede publicatiebesluit of autoriteit.

Bij opening toont de werkplek de actuele fase. Oude overzichtlinks openen die fase zonder te schrijven. **Afronden en bouwen** is de enige bouwactie in Documentcontrole en opent na reservering het statusoverzicht voor die poging. Voor het later terugkijken van bouwopdrachten is **Bekijk status bouwopdrachten** op de kaart in Vorming de ingang. De oude bouwbasis blijft geldig voor bestaande al gebouwde documenten. De nieuwe route wordt ingeschakeld met `METIS_ANNOTATION_DOCUMENT_CHECK=1` naast `METIS_ANNOTATION_CONFIRMED_STRUCTURE=1`, nadat de gemigreerde schrijver en leesrollen zijn geverifieerd. Stop oudere schrijvers vóór activatie. Zet bij terugdraaien de nieuwe instroom uit en behoud de afhandeling van reeds vastgelegde rondes. Oudere backups krijgen een lege rondetabel. Controleer oude en nieuwe seals bij herstel. Opnieuw publiceren of werkrevisies omzetten hoort daar niet bij.

Sinds #1169 opent **Aanpassen in de kaart** voor een benoemde reviewer de exacte annotatie. **Aanpassing opslaan** gebruikt de bestaande schrijver en brengt de focus naar Documentcontrole. Bij volledige dekking geldt dezelfde regel voor sectiebevestiging als voor de annotator. Een opgeslagen correctie blokkeert goedkeuring van de geraakte versie tot de bouw voor de opgeslagen correctie is geslaagd. Een mislukte bouw houdt de correctie, de blokkade en het auditspoor in stand. Ongeraakte objecten behouden hun ID, versie en oordeel. De bestaande transportvormen voor oudere werkrevisies en terugval blijven beschikbaar tot de opruiming in #1170.

## Ketenbewijs en tegenproeven

- Beide scopes: opslaan, afsluiten zonder poging, openen na herstart, concrete controlepunten, één bouw, review en publicatiegereedheid met geldige bron.
- Volledige dekking: ontbrekende of verouderde sectiebevestiging stopt finalize. Bij selectie kunnen onbenutte bronbereiken blijven staan.
- Andere actor, oud formulier, directe finalize, tweede tab, herhaalde ontvangst, weggelaten ronde in native seal en ongeldig bronbewijs.
- Rollbacklezing van oude bewijzen, herstart en export/herstel van de versiegebonden ronde zonder publicatiemutatie.

```mermaid
flowchart LR
    A["Annoteren"] --> D["Documentcontrole op dezelfde werkrevisie"]
    C["Scope en bevestigde secties"] --> D
    D --> S["Bestaande bouwverzegeling"]
    S --> B["Bouwen"]
    B --> R["Review en bestaande publicatiecontrole"]
```

## Besluiten

Op 25 november 2026 gaf de projectlead opdracht om slice 4 te implementeren. Het besluit omvat de afzonderlijke afsluitactie vóór Documentcontrole en het vervallen van de oude afsluitroute in de nieuwe werkplek. De bouw gebruikt de opgeslagen, actuele controle. De gevolgen van eventuele fouten zijn begrensd tot de opt-in werkrevisie. Een ontbrekende of verouderde controle houdt de betreffende bouw tegen. Stop de nieuwe instroom met de schakelaar als de verificatie afwijkt.

Verwijder de oude lezer pas zodra resterende legacy werkrevisies geen toegang via het losse overzicht meer nodig hebben. Behoud de bewijslezer en replay voor oudere verzegelingen.
