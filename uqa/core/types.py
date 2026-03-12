#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import functools
import re
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
    """Graph vertex with label and properties."""

    vertex_id: int
    label: str
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


@dataclass(frozen=True, slots=True)
class IsNull(Predicate):
    """Matches when value is None.

    Note: FilterOperator must check ``is_null_predicate()`` and bypass the
    ``value is not None`` guard for this predicate to work correctly.
    """
    def evaluate(self, value: Any) -> bool:
        return value is None


@dataclass(frozen=True, slots=True)
class IsNotNull(Predicate):
    """Matches when value is not None."""
    def evaluate(self, value: Any) -> bool:
        return value is not None


@dataclass(frozen=True, slots=True)
class Like(Predicate):
    """SQL LIKE pattern match (case-sensitive).

    Translates SQL ``%`` and ``_`` wildcards into Python regex.
    """
    pattern: str

    def evaluate(self, value: Any) -> bool:
        return _like_match(str(value), self.pattern, case_sensitive=True)


@dataclass(frozen=True, slots=True)
class NotLike(Predicate):
    """SQL NOT LIKE pattern match (case-sensitive)."""
    pattern: str

    def evaluate(self, value: Any) -> bool:
        return not _like_match(str(value), self.pattern, case_sensitive=True)


@dataclass(frozen=True, slots=True)
class ILike(Predicate):
    """SQL ILIKE pattern match (case-insensitive)."""
    pattern: str

    def evaluate(self, value: Any) -> bool:
        return _like_match(str(value), self.pattern, case_sensitive=False)


@dataclass(frozen=True, slots=True)
class NotILike(Predicate):
    """SQL NOT ILIKE pattern match (case-insensitive)."""
    pattern: str

    def evaluate(self, value: Any) -> bool:
        return not _like_match(str(value), self.pattern, case_sensitive=False)


@functools.lru_cache(maxsize=256)
def _compile_like_regex(pattern: str, case_sensitive: bool) -> re.Pattern[str]:
    """Compile a SQL LIKE pattern into a cached regex."""
    regex = ""
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "%":
            regex += ".*"
        elif ch == "_":
            regex += "."
        elif ch == "\\" and i + 1 < len(pattern):
            # Escaped wildcard
            i += 1
            regex += re.escape(pattern[i])
        else:
            regex += re.escape(ch)
        i += 1
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(regex, flags)


def _like_match(value: str, pattern: str, *, case_sensitive: bool) -> bool:
    """Match a SQL LIKE pattern against a string value."""
    compiled = _compile_like_regex(pattern, case_sensitive)
    return compiled.fullmatch(value) is not None


def is_null_predicate(pred: Predicate) -> bool:
    """Return True if *pred* needs to see None values (IsNull or IsNotNull)."""
    return isinstance(pred, (IsNull, IsNotNull))
