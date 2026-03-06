#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.operators.base import ExecutionContext, Operator


class AggregationMonoid(ABC):
    """Aggregation function with monoid structure for decomposition.

    Per Section 5.1 of Paper 1, aggregation functions form monoids
    enabling parallel decomposition (Theorem 5.1.5).
    """

    @abstractmethod
    def identity(self) -> Any: ...

    @abstractmethod
    def accumulate(self, state: Any, value: Any) -> Any: ...

    @abstractmethod
    def combine(self, state_a: Any, state_b: Any) -> Any: ...

    @abstractmethod
    def finalize(self, state: Any) -> Any: ...


class CountMonoid(AggregationMonoid):
    def identity(self) -> int:
        return 0

    def accumulate(self, state: int, value: Any) -> int:
        return state + 1

    def combine(self, state_a: int, state_b: int) -> int:
        return state_a + state_b

    def finalize(self, state: int) -> int:
        return state


class SumMonoid(AggregationMonoid):
    def identity(self) -> float:
        return 0.0

    def accumulate(self, state: float, value: float) -> float:
        return state + value

    def combine(self, state_a: float, state_b: float) -> float:
        return state_a + state_b

    def finalize(self, state: float) -> float:
        return state


class AvgMonoid(AggregationMonoid):
    """Avg = (sum, count) pair -- monoid over tuples."""

    def identity(self) -> tuple[float, int]:
        return (0.0, 0)

    def accumulate(self, state: tuple[float, int], value: float) -> tuple[float, int]:
        return (state[0] + value, state[1] + 1)

    def combine(
        self, state_a: tuple[float, int], state_b: tuple[float, int]
    ) -> tuple[float, int]:
        return (state_a[0] + state_b[0], state_a[1] + state_b[1])

    def finalize(self, state: tuple[float, int]) -> float:
        if state[1] == 0:
            return 0.0
        return state[0] / state[1]


class MinMonoid(AggregationMonoid):
    def identity(self) -> float:
        return float("inf")

    def accumulate(self, state: float, value: float) -> float:
        return min(state, value)

    def combine(self, state_a: float, state_b: float) -> float:
        return min(state_a, state_b)

    def finalize(self, state: float) -> float:
        return state


class MaxMonoid(AggregationMonoid):
    def identity(self) -> float:
        return float("-inf")

    def accumulate(self, state: float, value: float) -> float:
        return max(state, value)

    def combine(self, state_a: float, state_b: float) -> float:
        return max(state_a, state_b)

    def finalize(self, state: float) -> float:
        return state


class AggregateOperator(Operator):
    """Applies a monoid aggregation over a posting list field."""

    def __init__(self, source: Operator, field: str, monoid: AggregationMonoid) -> None:
        self.source = source
        self.field = field
        self.monoid = monoid

    def execute(self, context: ExecutionContext) -> PostingList:
        source_pl = self.source.execute(context)
        doc_store = context.document_store

        state = self.monoid.identity()
        for entry in source_pl:
            value = None
            if doc_store is not None:
                value = doc_store.get_field(entry.doc_id, self.field)
            if value is not None:
                state = self.monoid.accumulate(state, value)

        result_value = self.monoid.finalize(state)
        # Return a single-entry posting list with the aggregation result
        result_entry = PostingEntry(
            doc_id=0,
            payload=Payload(
                score=float(result_value) if isinstance(result_value, (int, float)) else 0.0,
                fields={"_aggregate_field": self.field, "_aggregate": result_value},
            ),
        )
        return PostingList([result_entry])


class GroupByOperator(Operator):
    """Group documents by a field and aggregate another field."""

    def __init__(
        self,
        source: Operator,
        group_field: str,
        agg_field: str,
        monoid: AggregationMonoid,
    ) -> None:
        self.source = source
        self.group_field = group_field
        self.agg_field = agg_field
        self.monoid = monoid

    def execute(self, context: ExecutionContext) -> PostingList:
        source_pl = self.source.execute(context)
        doc_store = context.document_store
        if doc_store is None:
            return PostingList()

        groups: dict[str, Any] = {}
        for entry in source_pl:
            group_value = doc_store.get_field(entry.doc_id, self.group_field)
            if group_value is None:
                continue
            group_key = str(group_value)
            if group_key not in groups:
                groups[group_key] = self.monoid.identity()
            agg_value = doc_store.get_field(entry.doc_id, self.agg_field)
            if agg_value is not None:
                groups[group_key] = self.monoid.accumulate(groups[group_key], agg_value)

        entries: list[PostingEntry] = []
        for i, (group_key, state) in enumerate(sorted(groups.items())):
            result_value = self.monoid.finalize(state)
            entries.append(PostingEntry(
                doc_id=i,
                payload=Payload(
                    score=float(result_value) if isinstance(result_value, (int, float)) else 0.0,
                    fields={
                        "_group_key": group_key,
                        "_group_field": self.group_field,
                        "_aggregate_result": result_value,
                    },
                ),
            ))
        return PostingList(entries)
