"""Bounded raw revision inputs with an independently owned historical boundary.

This value grants no permission or approval. Only its issuing document store can
consume its receipt, after checking the current database frontier and raw head.
"""
from copy import deepcopy
from types import MappingProxyType

from src.integrity_kernel import compute_canonical_object_hash


class RevisionWindow(list):
    def __init__(self, rows, *, owner, snapshot_id, frontiers):
        super().__init__(rows)
        from src.vorming.prepared_source_views_v1 import freeze
        self.owner = owner
        self.snapshot_id = snapshot_id
        self.frontiers = MappingProxyType({key: freeze(deepcopy(value)) for key, value in frontiers.items()})

    def replacing(self, rows):
        return RevisionWindow(rows, owner=self.owner, snapshot_id=self.snapshot_id, frontiers=self.frontiers)

    def __deepcopy__(self, memo):
        return self.replacing([deepcopy(row, memo) for row in self])

    def copy(self):
        return self.replacing(list(self))

    def __add__(self, rows):
        if isinstance(rows, RevisionWindow) and (
            rows.owner is not self.owner or rows.snapshot_id != self.snapshot_id
            or rows.frontiers != self.frontiers
        ):
            raise ValueError('revision_window_mismatch')
        return self.replacing(list(self) + list(rows))

    def is_anchor(self, row):
        frontier = self.frontiers.get(row['object_id'])
        if frontier is None or row['object_version'] != frontier['head_version']:
            return False
        if compute_canonical_object_hash(row) != frontier['canonical_hash']:
            raise ValueError('revision_frontier_head_changed')
        return True

    def frozen(self):
        from src.vorming.prepared_source_views_v1 import freeze
        return _FrozenRevisionWindow([freeze(deepcopy(row)) for row in self],
            owner=self.owner, snapshot_id=self.snapshot_id, frontiers=self.frontiers)


class _FrozenRevisionWindow(RevisionWindow):
    def _immutable(self, *args, **kwargs):
        from src.operations_console_v1 import ConsoleError
        raise ConsoleError('source_views_carrier_immutable')
    __setitem__ = __delitem__ = clear = pop = _immutable
    append = extend = insert = remove = sort = reverse = __iadd__ = __imul__ = _immutable
