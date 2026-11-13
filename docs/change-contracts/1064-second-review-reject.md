# #1064 deel 2 — Afwijzen in de tweede review

Change class: A
Promise: Reviewer 2 kan bij vierogenreview een kennisobject afwijzen met een toelichting; het object is daarmee afgehandeld en wordt nooit gepubliceerd, zonder terugsturen.
Proof: Black-box lifecycleproef op native PostgreSQL: vierogendocument, reviewer 1 keurt goed, reviewer 2 wijst af, publicatiegereedheid en release na herstart, daarna correctie in de kaart en opnieuw bouwen.
Touches lifecycle invariants: yes
Rewrite risk: none

Part of MET-76. Besluit William, 13 november 2026: “Afwijzen moet ook bij reviewer 2
kunnen.” Status: **specificatie ter akkoord; nog geen code.**

Waarom Class A: `docs/agents/lifecycle-vsa.md` §2 noemt een ontbrekende
verplichte tweede review als reden dat een WorkingRevision niet klaar is voor
publicatie. Deze wijziging voegt een tweede manier toe om die verplichting af te
sluiten (afwijzen in plaats van goedkeuren) en raakt daarmee de reviewsluiting
die publicatie vereist.

## Huidige toestand

- `src/review/ko_transitions_v1.py`: in de status Tweede review zijn alleen
  `approve_second` en correctie toegestaan; `reject` niet.
- `src/review/ko_review_page_v1.py` en `handle_compact_review`: de reviewkaart
  toont in de tweede review geen Afwijzen en weigert `reject` met
  `invalid_review_decision`.
- `operations_console_v1.review_object` weigert elke beslissing behalve `revise`
  zolang de tweede-reviewplicht open staat (`second_review_command_required`);
  `approve_second` loopt via een eigen opdracht met een onafhankelijkheidscheck
  (`independent_second_reviewer_required`).
- Afwijzen door reviewer 1 bestaat: `validation_status: rejected`, status
  Afgewezen, verplichte toelichting, en het telt als eindbesluit voor de
  bronpassage (`review_disposition_v1.FINAL_CANDIDATE_REVIEW_STATUSES`).

## Lifecycle-specificatie (§14)

```text
Lifecycle entity: WorkingRevision (één kennisobjectversie daarbinnen)
Lifecycle transition: kennisobjectversie in Tweede review → Afgewezen
Initial durable state: een niet-gepubliceerde WorkingRevision met vierogenreview;
  de exacte huidige objectversie heeft een geldige goedkeuring van reviewer 1 en
  een open tweede-reviewplicht.
Trigger: reviewer 2 kiest op de reviewkaart van die versie ‘Afwijzen’ met een
  toelichting.
Authorization: dezelfde regels als goedkeuren in de tweede review: een benoemde
  reviewer met de tweede-reviewtaak voor dit object, die niet de eerste
  goedkeurder van deze versie is.
Validation: exacte objectversie en snapshotrevisie (bestaande versiecontrole);
  toelichting niet leeg; object nog in Tweede review; snapshot niet gepubliceerd;
  geen niet-opgebouwde correctie (bestaande databasebewaking).
Mutable entities: de objectversie (governance: validation_status rejected,
  tweede review afgerond met uitkomst afgewezen); de reviewbindingen van deze
  versie (de goedkeuring van reviewer 1 telt niet meer, blijft als historie
  bewaard); het reviewlogboek (gebeurtenis second_review_reject).
Immutable entities: SourceSnapshot, bronbytes, annotaties, bouwbewijs, eerdere
  objectversies, PublicationReleases, publicatieregister.
Workflow state before: in_review (door deze open tweede-reviewplicht).
Workflow state after: in_review als er elders nog curatorwerk open staat;
  anders ready_for_publication voor zover technische poorten slagen. Het
  afgewezen object is een eindbesluit, zoals afwijzen door reviewer 1.
Release state before: geen release voor deze WorkingRevision.
Release state after: ongewijzigd; een latere release bevat het afgewezen object
  niet.
Serving state before: niet uitgeleverd.
Serving state after: niet uitgeleverd.
Expected API result: dezelfde reviewopdracht met uitkomst afgewezen; bij
  weigering de bestaande foutcodes (versieconflict, onafhankelijkheid,
  toelichting verplicht).
Expected UI result: de reviewkaart in de tweede review toont ‘Afwijzen’ zoals in
  de eerste review; na afwijzen toont het object de status Afgewezen. Reviewer 1
  ziet het besluit met toelichting op de reviewkaart van het object.
Failure result: bij elke weigering of fout wordt niets vastgelegd; het object
  blijft in Tweede review met de goedkeuring van reviewer 1.
Restart result: na herstart is het object Afgewezen, telt de goedkeuring van
  reviewer 1 niet en is de gebeurtenis in het logboek.
Recovery result: is reviewer 1 het oneens, dan past hij de kaart aan en bouwt
  opnieuw (#1064 deel 1); de nieuwe versie begint bij de eerste review. Er is geen
  aparte terugdraairoute.
Legacy-data result: bestaande objecten in Tweede review veranderen niet tot er
  een besluit valt; bestaande afwijzingen en goedkeuringen blijven geldig.
Required black-box scenario: zie hieronder.
Explicit non-goals: terugsturen naar reviewer 1 of de medewerker; meldingen;
  afwijzen van gepubliceerde objecten; wijziging van de tweede review voor de
  beslisboom; weergave van wat reviewer 1 veranderde (#1064 punt 6, Class B).
Rewrite risk: none — de bestaande afwijzingsuitkomst, versiecontrole,
  bindingregels en het logboek worden hergebruikt; geen nieuwe autoriteit.
```

## Black-box scenario

```text
GIVEN een niet-gepubliceerd document met vierogenreview, waarin reviewer 1
      kennisobject K versie v goedkeurde en K in Tweede review staat
WHEN reviewer 2 K versie v afwijst met toelichting T
THEN is K versie v Afgewezen met T; telt de goedkeuring van reviewer 1 niet meer;
     staat second_review_reject in het logboek; houdt K de publicatiegereedheid
     niet meer tegen; bevat een release van dit document K niet; geldt dit alles
     ook na een herstart; en levert een correctie van K in de kaart plus opnieuw
     bouwen een versie v+1 op die in de eerste review staat.
```

Aanvullende proeven: reviewer 1 kan K niet zelf in de tweede review afwijzen;
afwijzen zonder toelichting en met een verouderde revisie wordt geweigerd zonder
wijziging; twee gelijktijdige tweede-reviewbesluiten (goedkeuren en afwijzen)
leveren precies één winnaar.

## Punt 7 uit de issue

“Reviewer 2 mag van zijn eigen correctie niet zowel de eerste als de tweede
review afronden.” De bestaande regel dwingt dit al af per objectversie: de
tweede goedkeurder moet een ander zijn dan de eerste goedkeurder van díe
versie. Er is geen wijziging nodig; een proef hiervoor hoort bij dit deel.
