#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray


DocId = int
FieldName = str
TermValue = str
PathExpr = list[str | int]


@dataclass(frozen=True, slots=True)
class Payload:
    """Posting list entry payload (positions, scores, field values)."""

    positions: tuple[int, ...] = ()
    score: float = 0.0
    fields: dict[FieldName, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PostingEntry:
    """A single entry in a posting list: (doc_id, payload)."""

    doc_id: DocId
    payload: Payload


@dataclass(frozen=True, slots=True)
class GeneralizedPostingEntry:
    """Join result entry with multi-document tuples (Definition 4.1.2, Paper 1)."""

    doc_ids: tuple[DocId, ...]
    payload: Payload


@dataclass(frozen=True, slots=True)
class Vertex:
    """Graph vertex with properties."""

    vertex_id: int
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Edge:
    """Graph edge with label and properties."""

    edge_id: int
    source_id: int
    target_id: int
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IndexStats:
    """Index-level statistics for scoring and cost estimation."""

    total_docs: int = 0
    avg_doc_length: float = 0.0
    dimensions: int = 0
    _doc_freqs: dict[tuple[str, str], int] = field(default_factory=dict)

    def doc_freq(self, field: str, term: str) -> int:
        return self._doc_freqs.get((field, term), 0)


class Predicate(ABC):
    """Abstract predicate for filter operations."""

    @abstractmethod
    def evaluate(self, value: Any) -> bool: ...


@dataclass(frozen=True, slots=True)
class Equals(Predicate):
    target: Any

    def evaluate(self, value: Any) -> bool:
        return value == self.target


@dataclass(frozen=True, slots=True)
class NotEquals(Predicate):
    target: Any

    def evaluate(self, value: Any) -> bool:
        return value != self.target


@dataclass(frozen=True, slots=True)
class GreaterThan(Predicate):
    target: Any

    def evaluate(self, value: Any) -> bool:
        return value > self.target


@dataclass(frozen=True, slots=True)
class GreaterThanOrEqual(Predicate):
    target: Any

    def evaluate(self, value: Any) -> bool:
        return value >= self.target


@dataclass(frozen=True, slots=True)
class LessThan(Predicate):
    target: Any

    def evaluate(self, value: Any) -> bool:
        return value < self.target


@dataclass(frozen=True, slots=True)
class LessThanOrEqual(Predicate):
    target: Any

    def evaluate(self, value: Any) -> bool:
        return value <= self.target


@dataclass(frozen=True, slots=True)
class InSet(Predicate):
    values: frozenset[Any]

    def evaluate(self, value: Any) -> bool:
        return value in self.values


@dataclass(frozen=True, slots=True)
class Between(Predicate):
    low: Any
    high: Any

    def evaluate(self, value: Any) -> bool:
        return self.low <= value <= self.high
