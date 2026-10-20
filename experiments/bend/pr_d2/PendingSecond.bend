import Base

# Test-only abstraction: a pending default four-eyes duty with one exact
# current approver. Other authorization/source/tuple preconditions are assumed.
type Route is Data:
  Standalone{}
  Console{}

def actionable(route: Route, independent: Bool) -> Bool:
  match route:
    case Standalone{}:
      False{}
    case Console{}:
      independent
