#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uqa.core.posting_list import PostingList
    from uqa.operators.base import ExecutionContext, Operator


@dataclass
class ExecutionStats:
    """Statistics from plan execution."""

    operator_name: str = ""
    elapsed_ms: float = 0.0
    result_count: int = 0
    children: list[ExecutionStats] = field(default_factory=list)


class PlanExecutor:
    """Recursive tree-walking plan executor with timing stats."""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self._stats: ExecutionStats | None = None

    def execute(self, op: Operator) -> PostingList:
        """Execute an operator tree and collect stats."""
        result, stats = self._execute_with_stats(op)
        self._stats = stats
        return result

    def _execute_with_stats(self, op: Operator) -> tuple[PostingList, ExecutionStats]:
        from uqa.operators.boolean import IntersectOperator, UnionOperator, ComplementOperator
        from uqa.operators.base import ComposedOperator

        stats = ExecutionStats(operator_name=type(op).__name__)
        child_stats: list[ExecutionStats] = []

        if isinstance(op, (IntersectOperator, UnionOperator)):
            for child in op.operands:
                _, cs = self._execute_with_stats(child)
                child_stats.append(cs)
        elif isinstance(op, ComplementOperator):
            _, cs = self._execute_with_stats(op.operand)
            child_stats.append(cs)
        elif isinstance(op, ComposedOperator):
            for child in op.operators:
                _, cs = self._execute_with_stats(child)
                child_stats.append(cs)

        start = time.perf_counter()
        result = op.execute(self.context)
        elapsed = (time.perf_counter() - start) * 1000.0

        stats.elapsed_ms = elapsed
        stats.result_count = len(result)
        stats.children = child_stats

        return result, stats

    def explain(self, op: Operator, indent: int = 0) -> str:
        """Return a tree-formatted explanation of the query plan."""
        lines: list[str] = []
        self._explain_recursive(op, lines, indent)
        return "\n".join(lines)

    def _explain_recursive(self, op: Operator, lines: list[str], indent: int) -> None:
        from uqa.operators.boolean import IntersectOperator, UnionOperator, ComplementOperator
        from uqa.operators.primitive import (
            TermOperator,
            VectorSimilarityOperator,
            KNNOperator,
            FilterOperator,
            FacetOperator,
            ScoreOperator,
        )
        from uqa.operators.base import ComposedOperator

        prefix = "  " * indent

        match op:
            case TermOperator(term=t, field=f):
                lines.append(f"{prefix}TermOp(term={t!r}, field={f!r})")
            case VectorSimilarityOperator(threshold=th, field=f):
                lines.append(f"{prefix}VectorSimOp(threshold={th}, field={f!r})")
            case KNNOperator(k=k, field=f):
                lines.append(f"{prefix}KNNOp(k={k}, field={f!r})")
            case FilterOperator(field=f):
                lines.append(f"{prefix}FilterOp(field={f!r})")
                if hasattr(op, "source") and op.source is not None:
                    self._explain_recursive(op.source, lines, indent + 1)
            case IntersectOperator(operands=ops):
                lines.append(f"{prefix}Intersect")
                for child in ops:
                    self._explain_recursive(child, lines, indent + 1)
            case UnionOperator(operands=ops):
                lines.append(f"{prefix}Union")
                for child in ops:
                    self._explain_recursive(child, lines, indent + 1)
            case ComplementOperator(operand=inner):
                lines.append(f"{prefix}Complement")
                self._explain_recursive(inner, lines, indent + 1)
            case ComposedOperator(operators=ops):
                lines.append(f"{prefix}Composed")
                for child in ops:
                    self._explain_recursive(child, lines, indent + 1)
            case _:
                lines.append(f"{prefix}{type(op).__name__}")

    @property
    def last_stats(self) -> ExecutionStats | None:
        return self._stats
