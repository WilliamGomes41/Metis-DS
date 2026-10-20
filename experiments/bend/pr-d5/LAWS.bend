import Base
import ./Evidence.bend as E
import ./Facts.bend as F

# Evidence classification only; no assertion about Python semantics or guard completeness.
law xfail_is_not_strict_pass:
  for attempts: U32
  for phases: List<Bool>
  {E.strict(E.Xfailed{}, attempts, phases) == False{} : Bool}

law skip_is_not_strict_pass:
  for attempts: U32
  for phases: List<Bool>
  {E.strict(E.Skipped{}, attempts, phases) == False{} : Bool}

law observed_lifecycles_meet_strict_evidence_condition:
  {E.complete(F.results()) == True{} : Bool}

law failure_is_not_strict_pass:
  for attempts: U32
  for phases: List<Bool>
  {E.strict(E.Failed{}, attempts, phases) == False{} : Bool}
