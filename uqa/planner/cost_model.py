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

# Named constants for cost estimation weights
SCORE_OVERHEAD_FACTOR = 1.1
FILTER_SCAN_FRACTION = 0.1
GROUP_BY_OVERHEAD_FACTOR = 1.5
VERTEX_AGG_FRACTION = 0.2
TRAVERSE_FRACTION = 0.1


class CostModel:
    """Operator cost estimation for query optimization (Definition 6.2.1, Paper 1)."""

    def estimate(self, op: Operator, stats: IndexStats) -> float:
        from uqa.graph.graph_embedding import GraphEmbeddingOperator
        from uqa.graph.message_passing import MessagePassingOperator
        from uqa.graph.operators import (
            PatternMatchOperator,
            RegularPathQueryOperator,
            TraverseOperator,
            VertexAggregationOperator,
        )
        from uqa.graph.temporal_pattern_match import TemporalPatternMatchOperator
        from uqa.graph.temporal_traverse import TemporalTraverseOperator
        from uqa.operators.aggregation import AggregateOperator, GroupByOperator
        from uqa.operators.attention import AttentionFusionOperator
        from uqa.operators.boolean import IntersectOperator, UnionOperator
        from uqa.operators.hybrid import (
            FacetVectorOperator,
            HybridTextVectorOperator,
            LogOddsFusionOperator,
            ProbBoolFusionOperator,
            ProbNotOperator,
            SemanticFilterOperator,
            VectorExclusionOperator,
        )
        from uqa.operators.learned_fusion import LearnedFusionOperator
        from uqa.operators.multi_field import MultiFieldSearchOperator
        from uqa.operators.multi_stage import MultiStageOperator
        from uqa.operators.primitive import (
            FilterOperator,
            IndexScanOperator,
            KNNOperator,
            ScoreOperator,
            TermOperator,
            VectorSimilarityOperator,
        )
        from uqa.operators.sparse import SparseThresholdOperator

        match op:
            case TermOperator(term=t, field=f):
                field_name = f or "_default"
                return (
                    float(stats.doc_freq(field_name, t))
                    if stats.total_docs > 0
                    else 1.0
                )
            case VectorSimilarityOperator():
                return stats.dimensions * math.log2(stats.total_docs + 1)
            case KNNOperator():
                return stats.dimensions * math.log2(stats.total_docs + 1)
            case IndexScanOperator():
                return op.cost_estimate(stats)
            case ScoreOperator(source=src):
                return self.estimate(src, stats) * SCORE_OVERHEAD_FACTOR
            case FilterOperator(source=src):
                base = float(stats.total_docs)
                if src is not None:
                    base = self.estimate(src, stats) + base * FILTER_SCAN_FRACTION
                return base
            case IntersectOperator(operands=ops):
                child_costs = [self.estimate(o, stats) for o in ops]
                return sum(child_costs) if child_costs else 0.0
            case UnionOperator(operands=ops):
                return sum(self.estimate(o, stats) for o in ops)
            case AggregateOperator():
                return float(stats.total_docs)
            case GroupByOperator():
                return float(stats.total_docs) * GROUP_BY_OVERHEAD_FACTOR
            case LogOddsFusionOperator(signals=sigs):
                return sum(self.estimate(s, stats) for s in sigs)
            case ProbBoolFusionOperator(signals=sigs):
                return sum(self.estimate(s, stats) for s in sigs)
            case AttentionFusionOperator(signals=sigs):
                return sum(self.estimate(s, stats) for s in sigs)
            case LearnedFusionOperator(signals=sigs):
                return sum(self.estimate(s, stats) for s in sigs)
            case ProbNotOperator(signal=sig):
                return self.estimate(sig, stats) + float(stats.total_docs)
            case HybridTextVectorOperator():
                return self.estimate(op.term_op, stats) + self.estimate(
                    op.vector_op, stats
                )
            case SemanticFilterOperator():
                return self.estimate(op.source, stats) + self.estimate(
                    op.vector_op, stats
                )
            case VectorExclusionOperator():
                return self.estimate(op.positive, stats) + self.estimate(
                    op.negative_op, stats
                )
            case FacetVectorOperator():
                cost = self.estimate(op.vector_op, stats)
                if op.source is not None:
                    cost += self.estimate(op.source, stats)
                return cost
            case VertexAggregationOperator():
                return float(stats.total_docs) * VERTEX_AGG_FRACTION
            case TraverseOperator():
                return float(stats.total_docs) * TRAVERSE_FRACTION
            case PatternMatchOperator():
                return float(stats.total_docs) ** 2
            case TemporalTraverseOperator():
                return float(stats.total_docs) * TRAVERSE_FRACTION
            case TemporalPatternMatchOperator():
                return float(stats.total_docs) ** 2
            case RegularPathQueryOperator():
                # Path-indexable expressions (Concat-of-Labels) are cheaper
                labels = RegularPathQueryOperator._extract_label_sequence(
                    op.path_expr
                )
                if labels is not None:
                    return float(stats.total_docs) * 0.1
                return float(stats.total_docs) ** 2
            case SparseThresholdOperator(source=src):
                return self.estimate(src, stats) * 0.5
            case MultiFieldSearchOperator():
                return float(stats.total_docs) * len(op.fields)
            case MessagePassingOperator():
                return float(stats.total_docs) * op.k_layers
            case GraphEmbeddingOperator():
                return float(stats.total_docs) * op.k_layers * 2
            case MultiStageOperator():
                return op.cost_estimate(stats)
            case _:
                return float(stats.total_docs)
