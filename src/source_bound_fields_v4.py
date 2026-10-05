"""V4 source-bound formation contract.

Reuses the V3 literal field binding. The new contract is the source-function
separation plus an independent replay identity. It does not approve, publish,
or introduce a background knowledge type.
"""
from src.source_bound_fields_v3 import (
    ADMISSION_VERSION,
    FIELDS,
    TYPE_FIELDS,
    bind_fields,
    evidence_schema,
)

VERSION = "source-bound-fields-v4"
MODE = "semantic-source-bound-v4"

__all__ = [
    "ADMISSION_VERSION",
    "FIELDS",
    "MODE",
    "TYPE_FIELDS",
    "VERSION",
    "bind_fields",
    "evidence_schema",
]
