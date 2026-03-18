#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
        from uqa.operators.attention import AttentionFusionOperator
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.deep_fusion import (
            DeepFusionOperator,
            SignalLayer,
        )
        from uqa.operators.hybrid import (
            LogOddsFusionOperator,
            ProbBoolFusionOperator,
            ProbNotOperator,
        )
        from uqa.operators.learned_fusion import LearnedFusionOperator
        from uqa.operators.multi_stage import MultiStageOperator
        from uqa.operators.primitive import FilterOperator, ScoreOperator
        from uqa.operators.sparse import SparseThresholdOperator

        stats = ExecutionStats(operator_name=type(op).__name__)
        child_stats: list[ExecutionStats] = []

        if isinstance(op, IntersectOperator | UnionOperator):
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
        elif isinstance(op, AttentionFusionOperator | LearnedFusionOperator):
            for sig in op.signals:
                _, cs = self._execute_with_stats(sig)
                child_stats.append(cs)
        elif isinstance(op, LogOddsFusionOperator | ProbBoolFusionOperator):
            for sig in op.signals:
                _, cs = self._execute_with_stats(sig)
                child_stats.append(cs)
        elif isinstance(op, ProbNotOperator):
            _, cs = self._execute_with_stats(op.signal)
            child_stats.append(cs)
        elif isinstance(op, ScoreOperator):
            _, cs = self._execute_with_stats(op.source)
            child_stats.append(cs)
        elif isinstance(op, FilterOperator) and op.source is not None:
            _, cs = self._execute_with_stats(op.source)
            child_stats.append(cs)
        elif isinstance(op, SparseThresholdOperator):
            _, cs = self._execute_with_stats(op.source)
            child_stats.append(cs)
        elif isinstance(op, MultiStageOperator):
            for stage_op, _ in op.stages:
                _, cs = self._execute_with_stats(stage_op)
                child_stats.append(cs)
        elif isinstance(op, DeepFusionOperator):
            for layer in op.layers:
                if isinstance(layer, SignalLayer):
                    for sig in layer.signals:
                        _, cs = self._execute_with_stats(sig)
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
        from uqa.graph.graph_embedding import GraphEmbeddingOperator
        from uqa.graph.message_passing import MessagePassingOperator
        from uqa.graph.operators import (
            CypherQueryOperator,
            PatternMatchOperator,
            RegularPathQueryOperator,
            TraverseOperator,
        )
        from uqa.operators.attention import AttentionFusionOperator
        from uqa.operators.base import ComposedOperator
        from uqa.operators.boolean import (
            ComplementOperator,
            IntersectOperator,
            UnionOperator,
        )
        from uqa.operators.deep_fusion import (
            BatchNormLayer,
            ConvLayer,
            DeepFusionOperator,
            DenseLayer,
            DropoutLayer,
            FlattenLayer,
            PoolLayer,
            PropagateLayer,
            SignalLayer,
            SoftmaxLayer,
        )
        from uqa.operators.hybrid import (
            LogOddsFusionOperator,
            ProbBoolFusionOperator,
            ProbNotOperator,
        )
        from uqa.operators.learned_fusion import LearnedFusionOperator
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

        prefix = "  " * indent

        match op:
            case TermOperator(term=t, field=f):
                lines.append(f"{prefix}TermOp(term={t!r}, field={f!r})")
            case VectorSimilarityOperator(threshold=th, field=f):
                lines.append(f"{prefix}VectorSimOp(threshold={th}, field={f!r})")
            case KNNOperator(k=k, field=f):
                lines.append(f"{prefix}KNNOp(k={k}, field={f!r})")
            case IndexScanOperator(field=f, predicate=_p):
                lines.append(
                    f"{prefix}IndexScanOp(field={f!r}, "
                    f"index={op.index.index_def.name!r})"
                )
            case ScoreOperator(query_terms=qt, field=f):
                scorer_name = type(op.scorer).__name__
                lines.append(
                    f"{prefix}ScoreOp(scorer={scorer_name}, terms={qt!r}, field={f!r})"
                )
                self._explain_recursive(op.source, lines, indent + 1)
            case FilterOperator(field=f):
                lines.append(f"{prefix}FilterOp(field={f!r})")
                if hasattr(op, "source") and op.source is not None:
                    self._explain_recursive(op.source, lines, indent + 1)
            case LogOddsFusionOperator(signals=sigs):
                lines.append(
                    f"{prefix}LogOddsFusion(alpha={op.alpha}, signals={len(sigs)})"
                )
                for sig in sigs:
                    self._explain_recursive(sig, lines, indent + 1)
            case ProbBoolFusionOperator(signals=sigs):
                lines.append(
                    f"{prefix}ProbBoolFusion(mode={op.mode!r}, signals={len(sigs)})"
                )
                for sig in sigs:
                    self._explain_recursive(sig, lines, indent + 1)
            case ProbNotOperator(signal=sig):
                lines.append(f"{prefix}ProbNot")
                self._explain_recursive(sig, lines, indent + 1)
            case AttentionFusionOperator(signals=sigs):
                lines.append(f"{prefix}AttentionFusion(signals={len(sigs)})")
                for sig in sigs:
                    self._explain_recursive(sig, lines, indent + 1)
            case LearnedFusionOperator(signals=sigs):
                lines.append(f"{prefix}LearnedFusion(signals={len(sigs)})")
                for sig in sigs:
                    self._explain_recursive(sig, lines, indent + 1)
            case TraverseOperator():
                lines.append(
                    f"{prefix}TraverseOp(start={op.start_vertex}, "
                    f"label={op.label!r}, hops={op.max_hops})"
                )
            case PatternMatchOperator():
                n_vp = len(op.pattern.vertex_patterns)
                n_ep = len(op.pattern.edge_patterns)
                lines.append(f"{prefix}PatternMatchOp(vertices={n_vp}, edges={n_ep})")
            case RegularPathQueryOperator():
                lines.append(f"{prefix}RPQOp(start={op.start_vertex})")
            case CypherQueryOperator():
                n_clauses = len(op.query.clauses)
                lines.append(f"{prefix}CypherOp(clauses={n_clauses})")
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
            case SparseThresholdOperator(source=src):
                lines.append(f"{prefix}SparseThreshold(threshold={op.threshold})")
                self._explain_recursive(src, lines, indent + 1)
            case MessagePassingOperator():
                lines.append(
                    f"{prefix}MessagePassingOp(k={op.k_layers}, agg={op.aggregation!r})"
                )
            case GraphEmbeddingOperator():
                lines.append(
                    f"{prefix}GraphEmbeddingOp(dims={op.dimensions}, k={op.k_layers})"
                )
            case MultiStageOperator():
                lines.append(f"{prefix}MultiStage(stages={len(op.stages)})")
                for i, (stage_op, cutoff) in enumerate(op.stages):
                    lines.append(f"{prefix}  Stage {i} (cutoff={cutoff}):")
                    self._explain_recursive(stage_op, lines, indent + 2)
            case DeepFusionOperator(layers=lyrs, alpha=a, gating=g):
                lines.append(
                    f"{prefix}DeepFusion(layers={len(lyrs)}, alpha={a}, gating={g!r})"
                )
                for i, layer in enumerate(lyrs):
                    if isinstance(layer, SignalLayer):
                        lines.append(
                            f"{prefix}  Layer {i} (signals={len(layer.signals)}):"
                        )
                        for sig in layer.signals:
                            self._explain_recursive(sig, lines, indent + 2)
                    elif isinstance(layer, PropagateLayer):
                        lines.append(
                            f"{prefix}  Layer {i} "
                            f"(propagate={layer.edge_label!r}, "
                            f"agg={layer.aggregation!r}):"
                        )
                    elif isinstance(layer, ConvLayer):
                        hops = len(layer.hop_weights) - 1
                        lines.append(
                            f"{prefix}  Layer {i} "
                            f"(convolve={layer.edge_label!r}, "
                            f"hops={hops}, "
                            f"weights={list(layer.hop_weights)}):"
                        )
                    elif isinstance(layer, PoolLayer):
                        lines.append(
                            f"{prefix}  Layer {i} "
                            f"(pool={layer.edge_label!r}, "
                            f"method={layer.method!r}, "
                            f"size={layer.pool_size}):"
                        )
                    elif isinstance(layer, DenseLayer):
                        lines.append(
                            f"{prefix}  Layer {i} "
                            f"(dense={layer.input_channels}"
                            f"->{layer.output_channels}):"
                        )
                    elif isinstance(layer, FlattenLayer):
                        lines.append(f"{prefix}  Layer {i} (flatten):")
                    elif isinstance(layer, SoftmaxLayer):
                        lines.append(f"{prefix}  Layer {i} (softmax):")
                    elif isinstance(layer, BatchNormLayer):
                        lines.append(
                            f"{prefix}  Layer {i} (batch_norm, eps={layer.epsilon}):"
                        )
                    elif isinstance(layer, DropoutLayer):
                        lines.append(f"{prefix}  Layer {i} (dropout, p={layer.p}):")
            case _:
                lines.append(f"{prefix}{type(op).__name__}")

    @property
    def last_stats(self) -> ExecutionStats | None:
        return self._stats
