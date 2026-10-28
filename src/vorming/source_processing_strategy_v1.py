"""Explicit mutation-only source preparation strategy, installed by composition."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SourceProcessingStrategy:
    prepare: Callable
    configuration: Callable
