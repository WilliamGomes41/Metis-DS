# Metis governance

**Status:** actief onder Protocol v4.3.1 — enige vigerende protocolnorm

**Datum:** 2026-11-01 (afstemming met bestaande code; protocolversie 4.3.1)

Dit bestand is het compacte operationele governance-register. Het licht de toepassing van het protocol toe.

## Huidige autoriteit

De sturingsvolgorde is:

`PROTOCOL.md → acceptatietests → code`

Daarbij geldt:

1. `PROTOCOL.md` — actuele product-, veiligheids- en governance-invarianten;
2. acceptatie- en regressietests — uitvoerbaar bewijs;
3. code, configuratie en infrastructuur — implementatie.

Protocol-v2-delta's, oude roadmaps, approval-manifests en de pre-v3 governance blijven auditbewijs. Zij zijn niet aanvullend normatief onder V4. De volledige pre-v3 governance staat in `docs/history/protocol-v2/GOVERNANCE_PRE_V3_2026-09-10.md`.

## Besluitdiscipline

- Een blijvende product- of veiligheidsinvariant wordt rechtstreeks in `PROTOCOL.md` verwerkt en waar mogelijk door een gedragstest bewezen.
- Een nog open wijziging, experiment of beslispoort staat in [GitHub Issues](https://github.com/WilliamGomes41/Metis-DS/issues).
- Afgeronde of gesupersedeerde besluitgeschiedenis gaat naar `docs/history/`, changelog of auditrapport.
- Er wordt geen nieuwe keten van protocoldelta's opgebouwd.
- Een tijdelijke deployment- of incidentworkaround wordt niet automatisch architectuurwet.
- Een experiment mag geen canonieke publicatie uitvoeren. `KEEP`, `ITERATE` en `PROCEED` zijn geen implementatie-autorisatie. De Audit-eindstatus is `READY FOR IMPLEMENTATION`; ontwikkeling, GitHub, merge, deploy en publicatie blijven buiten Metis. Er is geen APPLY-executor.

## Auditgrens

Historische protocolbestanden staan met ongewijzigde bytes onder `docs/history/`. Relatieve compatibiliteitslinks op de oude V2-paden houden padgebonden approval-manifests en historische verwijzingen leesbaar. De approval-manifests blijven ongewijzigd. Dat behoudt reproduceerbaarheid zonder een aanvullende actuele stuurlaag te maken.

Historische V2-regressietests mogen de bevroren pre-v3 rootdocumenten toetsen. V3-regressietests toetsen uitsluitend de actuele rootnorm.

## Afstemming en bewijs

De [afstemmingsnotitie van 2026-11-01](audit/protocol-code-alignment-2026-11-01.md) koppelt de gecontroleerde protocolregels aan code en tests. Zij is bewijs, geen aanvullende norm of verklaring van productieacceptatie. Volg het resterende werk voor routevastlegging en inhoudelijke acceptatie in [het projectissue voor kennisvorming en bewijs](https://github.com/WilliamGomes41/Metis-DS/issues/877).
