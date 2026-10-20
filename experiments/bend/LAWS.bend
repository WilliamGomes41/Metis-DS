import Base
import ./Demo.bend as Demo

# Demonstration only: identity preserves every natural number.
law identity_preserves_value:
  for n: Nat
  {Demo.identity(n) == n : Nat}
