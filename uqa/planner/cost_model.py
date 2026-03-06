#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.types import IndexStats
    from uqa.operators.base import Operator


class CostModel:
    """Operator cost estimation for query optimization (Definition 6.2.1, Paper 1)."""

    def estimate(self, op: Operator, stats: IndexStats) -> float:
        from uqa.operators.boolean import IntersectOperator, UnionOperator
        from uqa.operators.primitive import (
            FilterOperator,
            KNNOperator,
            TermOperator,
            VectorSimilarityOperator,
        )
        from uqa.operators.aggregation import AggregateOperator, GroupByOperator
        from uqa.graph.operators import (
            TraverseOperator,
            PatternMatchOperator,
            RegularPathQueryOperator,
        )

        match op:
            case TermOperator(term=t, field=f):
                field_name = f or "_default"
                return float(stats.doc_freq(field_name, t)) if stats.total_docs > 0 else 1.0
            case VectorSimilarityOperator():
                return stats.dimensions * math.log2(stats.total_docs + 1)
            case KNNOperator():
                return stats.dimensions * math.log2(stats.total_docs + 1)
            case FilterOperator():
                return float(stats.total_docs)
            case IntersectOperator(operands=ops):
                child_costs = [self.estimate(o, stats) for o in ops]
                return min(child_costs) if child_costs else 0.0
            case UnionOperator(operands=ops):
                return sum(self.estimate(o, stats) for o in ops)
            case AggregateOperator():
                return float(stats.total_docs)
            case GroupByOperator():
                return float(stats.total_docs) * 1.5
            case TraverseOperator():
                return float(stats.total_docs) * 0.1
            case PatternMatchOperator():
                return float(stats.total_docs) ** 2
            case RegularPathQueryOperator():
                return float(stats.total_docs) ** 2
            case _:
                return float(stats.total_docs)
