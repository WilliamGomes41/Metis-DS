import ./LAWS.bend as Laws
import ./PendingSecond.bend as P

def Laws.standalone_never_actionable(independent):
  {==}

def Laws.same_reviewer_never_actionable(route):
  match route:
    case P.Standalone{}:
      {==}
    case P.Console{}:
      {==}

def Laws.console_preserves_independent_review(independent):
  {==}
