import Base

# IDs 0 and 1 are the removed modules. All other IDs come from Python source.
type Edge is Data:
  Import{source: U32, target: U32}

def retained(+node: U32) -> Bool:
  U32.is_ne(node, 0) && U32.is_ne(node, 1)

def edge_is_closed(edge: Edge) -> Bool:
  match edge:
    case Import{source, target}:
      retained(target) || Bool.not(retained(source))

def closed(edges: List<Edge>) -> Bool:
  match edges:
    case Nil{}:
      True{}
    case Con{head, tail}:
      # Independent checks can be evaluated in parallel.
      first rest = edge_is_closed(head) closed(tail)
      first && rest

def roots_retained(roots: List<U32>) -> Bool:
  match roots:
    case Nil{}:
      True{}
    case Con{head, tail}:
      first rest = retained(head) roots_retained(tail)
      first && rest
