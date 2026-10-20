import Base

# Evidence classification only. This is not the Python runtime or a merge gate.
type Outcome is Data:
  Passed{}
  Xfailed{}
  Skipped{}
  Failed{}

def complete(phases: List<Bool>) -> Bool:
  match phases:
    case Nil{}:
      True{}
    case Con{head, tail}:
      head && complete(tail)

def no_access(attempts: U32) -> Bool:
  U32.is_eq(attempts, 0)

def strict(outcome: Outcome, attempts: U32, phases: List<Bool>) -> Bool:
  match outcome:
    case Passed{}:
      clean full = no_access(attempts) complete(phases)
      clean && full
    case Xfailed{}:
      False{}
    case Skipped{}:
      False{}
    case Failed{}:
      False{}
