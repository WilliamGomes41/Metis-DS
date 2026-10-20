import Base

# Installation smoke test; no Metis domain behavior is implemented here.
def identity(n: Nat) -> Nat:
  n

def main() -> Nat:
  identity(42n)
