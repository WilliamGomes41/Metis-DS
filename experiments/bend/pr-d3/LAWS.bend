import Base
import ./Boundary.bend as Boundary
import ./Facts.bend as Facts

# Concrete source-derived import boundary, not a proof of Python semantics.
law no_external_import_into_removed_route:
  {Boundary.closed(Facts.edges()) == True{} : Bool}

law runtime_and_script_roots_are_retained:
  {Boundary.roots_retained(Facts.roots()) == True{} : Bool}
