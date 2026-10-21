# Codeaudit: voortgang A01–A27

Open [het HTML-overzicht](metis-codeaudit-voortgang.html) lokaal in een browser.
GitHub toont een HTML-bestand als broncode; download het om de weergave te openen.
De HTML bevat een gedateerde momentopname. Iedere rij linkt naar de actuele
GitHub-issuebeschrijving, de enige bron voor de voortgang.

Het volledige interne auditrapport blijft afzonderlijk beschikbaar bij de eigenaar.
Dit repositoryoverzicht bevat uitsluitend ID's en voortgang; technische
kwetsbaarheidsdetails en productiegegevens zijn niet opgenomen.

## Voortgang aanpassen

1. Open bij het betreffende ID **Voortgang aanpassen in GitHub**.
2. Vink in de issuebeschrijving de stappen in volgorde af en voeg bewijs toe.
3. Sluit het issue pas als de oorspronkelijke gebruikershandeling in productie is
   geverifieerd. Het sluiten van een code-PR maakt het audit-ID niet automatisch klaar.

| Status | Betekenis |
| --- | --- |
| Open | Nog geen voortgang bevestigd; de huidige code moet bij triage worden gecontroleerd. |
| In uitvoering | Reparatie wordt uitgevoerd. |
| Code geverifieerd | Oorspronkelijke foutproef en relevante controles slagen; PR/commit gekoppeld. |
| Gedeployed | De reparatie zit aantoonbaar in de draaiende productieversie. |
| Afgerond | Oorspronkelijke gebruikershandeling werkt aantoonbaar in productie. |
| Status controleren | Vakjes ontbreken, staan niet in volgorde of de bronstatus is onbekend. |
| Gesloten zonder acceptatie | Het issue is gesloten zonder alle acceptatiestappen. Geen claim van herstel. |

De vakjes registreren menselijke bewijsbeoordeling; de synchronisatie verifieert
niet zelfstandig tests, draaiende versies of productiehandelingen.
Publiceer geen interne logs, broninhoud, persoonsgegevens of volledige diagnostiek
als bewijs. Gebruik een niet-gevoelige samenvatting en PR/commitverwijzingen.

## HTML bijwerken

Vereisten: Python 3 en een geïnstalleerde, aangemelde GitHub CLI (`gh`) met
leestoegang tot deze repository. Vanuit de repository:

```bash
python docs/audit/sync_progress.py
```

Het commando leest de 27 issues, valideert hun ID's en schrijft pas na volledige
succesvolle uitlezing een nieuwe HTML-momentopname. Het wijzigt geen issues en
start geen reparatie, deployment of Metis-verwerking. Bij een leesfout blijft het
vorige HTML-bestand intact. Commit de gewijzigde momentopname wanneer deze ook
voor anderen in de repository beschikbaar moet zijn; downloaden alleen geeft
geen automatische synchronisatie.

Hetzelfde commando kan met `--html /pad/naar/volledig-rapport.html` een intern
rapport met dezelfde statusvelden bijwerken. Upload dat volledige rapport niet
naar GitHub zonder expliciete toestemming voor de inhoud.

Documentatietaak: #550. Audit-ID's zijn historische bevindingen, geen automatisch
toegewezen implementatietickets. Productcode, infrastructuur en governance blijven
ongewijzigd.
