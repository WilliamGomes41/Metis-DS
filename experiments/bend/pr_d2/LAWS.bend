import Base
import ./PendingSecond.bend as P

law standalone_never_actionable:
  for independent: Bool
  {P.actionable(P.Standalone{}, independent) == False{} : Bool}

law same_reviewer_never_actionable:
  for route: P.Route
  {P.actionable(route, False{}) == False{} : Bool}

law console_preserves_independent_review:
  for independent: Bool
  {P.actionable(P.Console{}, independent) == independent : Bool}
