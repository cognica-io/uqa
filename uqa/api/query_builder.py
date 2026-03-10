#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from uqa.core.types import PathExpr, Predicate

if TYPE_CHECKING:
    from uqa.core.posting_list import GeneralizedPostingList, PostingList
    from uqa.engine import Engine


class AggregateResult:
    """Result of an aggregation query."""

    def __init__(self, value: Any):
        self.value = value

    def __repr__(self) -> str:
        return f"AggregateResult({self.value!r})"


class FacetResult:
    """Result of a facet query: mapping of value -> count."""

    def __init__(self, counts: dict[Any, int]):
        self.counts = counts

    def __repr__(self) -> str:
        return f"FacetResult({self.counts!r})"


class QueryBuilder:
    """Fluent API for constructing queries over the unified algebra (Section 13, Design Doc)."""

    def __init__(self, engine: Engine, table: str):
        self._engine = engine
        self._table = table
        self._root: Any = None

    # -- Term retrieval (Definition 3.1.1) --

    def term(self, term: str, field: str | None = None) -> QueryBuilder:
        from uqa.operators.primitive import TermOperator

        op = TermOperator(term, field)
        return self._chain(op)

    # -- Vector search (Definitions 3.1.2, 3.1.3) --

    def vector(
        self, query: NDArray, threshold: float, field: str = "embedding"
    ) -> QueryBuilder:
        from uqa.operators.primitive import VectorSimilarityOperator

        op = VectorSimilarityOperator(query, threshold, field)
        return self._chain(op)

    def knn(self, query: NDArray, k: int, field: str = "embedding") -> QueryBuilder:
        from uqa.operators.primitive import KNNOperator

        op = KNNOperator(query, k, field)
        return self._chain(op)

    # -- Boolean algebra --

    def and_(self, other: QueryBuilder) -> QueryBuilder:
        from uqa.operators.boolean import IntersectOperator

        if self._root is None or other._root is None:
            raise ValueError("Both builders must have operators before combining")
        op = IntersectOperator([self._root, other._root])
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def or_(self, other: QueryBuilder) -> QueryBuilder:
        from uqa.operators.boolean import UnionOperator

        if self._root is None or other._root is None:
            raise ValueError("Both builders must have operators before combining")
        op = UnionOperator([self._root, other._root])
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def not_(self) -> QueryBuilder:
        from uqa.operators.boolean import ComplementOperator

        if self._root is None:
            raise ValueError("Builder must have an operator before negation")
        op = ComplementOperator(self._root)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Filter (Definition 3.1.4 / 5.3.5) --

    def filter(self, field: str, predicate: Predicate) -> QueryBuilder:
        if "." in field:
            from uqa.operators.hierarchical import PathFilterOperator

            path: PathExpr = []
            for component in field.split("."):
                if component.isdigit():
                    path.append(int(component))
                else:
                    path.append(component)
            op = PathFilterOperator(path, predicate, self._root)
        else:
            from uqa.operators.primitive import FilterOperator

            op = FilterOperator(field, predicate, self._root)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Joins (Section 4, Paper 1) --

    def join(
        self,
        other: QueryBuilder,
        left_field: str,
        right_field: str,
    ) -> QueryBuilder:
        from uqa.joins.base import JoinCondition
        from uqa.joins.inner import InnerJoinOperator

        if self._root is None or other._root is None:
            raise ValueError("Both builders must have operators before joining")
        condition = JoinCondition(left_field, right_field)
        op = InnerJoinOperator(self._root, other._root, condition)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def vector_join(
        self,
        other: QueryBuilder,
        left_field: str,
        right_field: str,
        threshold: float,
    ) -> QueryBuilder:
        from uqa.joins.cross_paradigm import VectorSimilarityJoinOperator

        if self._root is None or other._root is None:
            raise ValueError("Both builders must have operators before joining")
        op = VectorSimilarityJoinOperator(
            self._root, other._root, left_field, right_field, threshold
        )
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Graph operations (Paper 2) --

    def traverse(
        self, start: int, label: str | None = None, max_hops: int = 1
    ) -> QueryBuilder:
        from uqa.graph.operators import TraverseOperator

        op = TraverseOperator(start, label, max_hops)
        return self._chain(op)

    def match_pattern(self, pattern: Any) -> QueryBuilder:
        from uqa.graph.operators import PatternMatchOperator

        op = PatternMatchOperator(pattern)
        return self._chain(op)

    def rpq(self, expr: str, start: int | None = None) -> QueryBuilder:
        from uqa.graph.pattern import parse_rpq
        from uqa.graph.operators import RegularPathQueryOperator

        path_expr = parse_rpq(expr)
        op = RegularPathQueryOperator(path_expr, start_vertex=start)
        return self._chain(op)

    def vertex_aggregate(
        self, property_name: str, agg_fn: str = "sum"
    ) -> AggregateResult:
        """Aggregate a vertex property over graph traversal results.

        Requires a prior graph operation (traverse, match_pattern, or rpq).
        Returns a single aggregated value.
        """
        from uqa.graph.operators import VertexAggregationOperator

        if self._root is None:
            raise ValueError(
                "vertex_aggregate requires a graph traversal source"
            )

        op = VertexAggregationOperator(self._root, property_name, agg_fn)
        ctx = self._engine._context_for_table(self._table)
        result_gpl = op.execute(ctx)

        if result_gpl and len(result_gpl) > 0:
            entry = next(iter(result_gpl))
            return AggregateResult(
                entry.payload.fields.get("_vertex_agg_result")
            )
        return AggregateResult(0.0)

    # -- Vector exclusion (Definition 3.3.3, Paper 1) --

    def vector_exclude(
        self, negative_vector: NDArray, threshold: float
    ) -> QueryBuilder:
        """Exclude documents similar to a negative query vector."""
        from uqa.operators.hybrid import VectorExclusionOperator

        if self._root is None:
            raise ValueError("vector_exclude requires a source query")

        op = VectorExclusionOperator(
            self._root, negative_vector, threshold
        )
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Aggregation (Section 5.1, Paper 1) --

    def aggregate(self, field: str, agg: str) -> AggregateResult:
        from uqa.operators.aggregation import (
            AggregateOperator,
            AvgMonoid,
            CountMonoid,
            MaxMonoid,
            MinMonoid,
            SumMonoid,
        )

        monoid_map = {
            "count": CountMonoid,
            "sum": SumMonoid,
            "avg": AvgMonoid,
            "min": MinMonoid,
            "max": MaxMonoid,
        }
        monoid_cls = monoid_map.get(agg.lower())
        if monoid_cls is None:
            raise ValueError(f"Unknown aggregation: {agg}")

        monoid = monoid_cls()
        agg_op = AggregateOperator(self._root, field, monoid)
        ctx = self._engine._context_for_table(self._table)
        result_pl = agg_op.execute(ctx)

        if result_pl and len(result_pl) > 0:
            entry = next(iter(result_pl))
            return AggregateResult(entry.payload.fields.get("_aggregate"))
        return AggregateResult(monoid.finalize(monoid.identity()))

    def facet(self, field: str) -> FacetResult:
        from uqa.operators.primitive import FacetOperator

        op = FacetOperator(field, self._root)
        ctx = self._engine._context_for_table(self._table)
        result_pl = op.execute(ctx)

        counts: dict[Any, int] = {}
        for entry in result_pl:
            val = entry.payload.fields.get("_facet_value")
            count = int(entry.payload.fields.get("_facet_count", 0))
            if val is not None:
                counts[val] = count
        return FacetResult(counts)

    def vector_facet(
        self, field: str, query_vector: NDArray, threshold: float
    ) -> FacetResult:
        """Facet counts conditioned on vector similarity (Definition 3.3.4)."""
        from uqa.operators.hybrid import FacetVectorOperator

        op = FacetVectorOperator(
            field, query_vector, threshold, self._root
        )
        ctx = self._engine._context_for_table(self._table)
        result_pl = op.execute(ctx)

        counts: dict[Any, int] = {}
        for entry in result_pl:
            val = entry.payload.fields.get("_facet_value")
            count = int(entry.payload.fields.get("_facet_count", 0))
            if val is not None:
                counts[val] = count
        return FacetResult(counts)

    # -- Hierarchical (Section 5.2-5.3, Paper 1) --

    def path_filter(self, path: PathExpr, predicate: Predicate) -> QueryBuilder:
        from uqa.operators.hierarchical import PathFilterOperator

        op = PathFilterOperator(path, predicate, self._root)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def path_project(self, *paths: PathExpr) -> QueryBuilder:
        from uqa.operators.hierarchical import PathProjectOperator

        op = PathProjectOperator(list(paths), self._root)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def unnest(self, path: PathExpr) -> QueryBuilder:
        from uqa.operators.hierarchical import PathUnnestOperator

        op = PathUnnestOperator(path, self._root)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def path_aggregate(
        self, path: str | PathExpr, agg: str
    ) -> QueryBuilder:
        """Per-document aggregation over nested array values (Definition 5.3.3).

        Applies an aggregation function to the array at ``path`` within each
        document.  The aggregated value is stored in each entry's payload
        field ``_path_aggregate``.
        """
        from uqa.operators.aggregation import (
            AvgMonoid,
            CountMonoid,
            MaxMonoid,
            MinMonoid,
            SumMonoid,
        )
        from uqa.operators.hierarchical import PathAggregateOperator

        monoid_map = {
            "count": CountMonoid,
            "sum": SumMonoid,
            "avg": AvgMonoid,
            "min": MinMonoid,
            "max": MaxMonoid,
        }
        monoid_cls = monoid_map.get(agg.lower())
        if monoid_cls is None:
            raise ValueError(f"Unknown aggregation: {agg}")

        if isinstance(path, str):
            path_expr: PathExpr = []
            for component in path.split("."):
                if component.isdigit():
                    path_expr.append(int(component))
                else:
                    path_expr.append(component)
        else:
            path_expr = path

        op = PathAggregateOperator(path_expr, monoid_cls(), self._root)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Scoring --

    def score_bm25(self, query: str, field: str | None = None) -> QueryBuilder:
        from uqa.operators.primitive import ScoreOperator
        from uqa.scoring.bm25 import BM25Params, BM25Scorer

        ctx = self._engine._context_for_table(self._table)
        analyzer = ctx.inverted_index.get_field_analyzer(field) if field else ctx.inverted_index.analyzer
        terms = analyzer.analyze(query)
        scorer = BM25Scorer(BM25Params(), ctx.inverted_index.stats)
        op = ScoreOperator(scorer, self._root, terms)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def score_bayesian_bm25(self, query: str, field: str | None = None) -> QueryBuilder:
        from uqa.operators.primitive import ScoreOperator
        from uqa.scoring.bayesian_bm25 import BayesianBM25Params, BayesianBM25Scorer

        ctx = self._engine._context_for_table(self._table)
        analyzer = ctx.inverted_index.get_field_analyzer(field) if field else ctx.inverted_index.analyzer
        terms = analyzer.analyze(query)
        scorer = BayesianBM25Scorer(BayesianBM25Params(), ctx.inverted_index.stats)
        op = ScoreOperator(scorer, self._root, terms)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Fusion (Paper 4) --

    def fuse_log_odds(
        self, *builders: QueryBuilder, alpha: float = 0.5
    ) -> QueryBuilder:
        from uqa.fusion.log_odds import LogOddsFusion

        fusion = LogOddsFusion(confidence_alpha=alpha)

        sources = []
        for b in builders:
            if b._root is not None:
                sources.append(b)

        if not sources:
            return self

        qb = QueryBuilder(self._engine, self._table)
        qb._root = _FusionOperator(fusion, [b._root for b in sources])
        return qb

    def fuse_prob_and(self, *builders: QueryBuilder) -> QueryBuilder:
        qb = QueryBuilder(self._engine, self._table)
        qb._root = _ProbBooleanOperator("and", [b._root for b in builders if b._root])
        return qb

    def fuse_prob_or(self, *builders: QueryBuilder) -> QueryBuilder:
        qb = QueryBuilder(self._engine, self._table)
        qb._root = _ProbBooleanOperator("or", [b._root for b in builders if b._root])
        return qb

    # -- Execution --

    def execute(self) -> PostingList:
        from uqa.planner.executor import PlanExecutor
        from uqa.planner.optimizer import QueryOptimizer
        from uqa.core.posting_list import PostingList

        if self._root is None:
            return PostingList()

        ctx = self._engine._context_for_table(self._table)
        optimizer = QueryOptimizer(ctx.inverted_index.stats)
        optimized = optimizer.optimize(self._root)

        executor = PlanExecutor(ctx)
        return executor.execute(optimized)

    def explain(self) -> str:
        from uqa.planner.executor import PlanExecutor
        from uqa.planner.optimizer import QueryOptimizer

        if self._root is None:
            return "(empty query)"

        ctx = self._engine._context_for_table(self._table)
        optimizer = QueryOptimizer(ctx.inverted_index.stats)
        optimized = optimizer.optimize(self._root)

        executor = PlanExecutor(ctx)
        return executor.explain(optimized)

    # -- Internal --

    def _chain(self, op: Any) -> QueryBuilder:
        if self._root is not None:
            from uqa.operators.boolean import IntersectOperator

            op = IntersectOperator([self._root, op])
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb


class _FusionOperator:
    """Internal operator for log-odds fusion across multiple sub-queries."""

    def __init__(self, fusion: Any, sources: list[Any]):
        self.fusion = fusion
        self.sources = sources

    def execute(self, context: Any) -> Any:
        from uqa.core.types import Payload, PostingEntry
        from uqa.core.posting_list import PostingList

        results = [src.execute(context) for src in self.sources]

        doc_scores: dict[int, list[float]] = {}
        for result in results:
            for entry in result:
                if entry.doc_id not in doc_scores:
                    doc_scores[entry.doc_id] = []
                doc_scores[entry.doc_id].append(entry.payload.score)

        entries = []
        for doc_id, scores in doc_scores.items():
            while len(scores) < len(results):
                scores.append(0.5)
            fused_score = self.fusion.fuse(scores)
            entries.append(PostingEntry(doc_id, Payload(score=fused_score)))

        return PostingList(entries)

    def compose(self, other: Any) -> Any:
        from uqa.operators.base import ComposedOperator
        return ComposedOperator([self, other])

    def cost_estimate(self, stats: Any) -> float:
        return sum(
            getattr(s, "cost_estimate", lambda _: 100.0)(stats)
            for s in self.sources
        )


class _ProbBooleanOperator:
    """Internal operator for probabilistic boolean fusion."""

    def __init__(self, mode: str, sources: list[Any]):
        self.mode = mode
        self.sources = sources

    def execute(self, context: Any) -> Any:
        from uqa.core.types import Payload, PostingEntry
        from uqa.core.posting_list import PostingList
        from uqa.fusion.boolean import ProbabilisticBoolean

        results = [src.execute(context) for src in self.sources]

        doc_scores: dict[int, list[float]] = {}
        for result in results:
            for entry in result:
                if entry.doc_id not in doc_scores:
                    doc_scores[entry.doc_id] = []
                doc_scores[entry.doc_id].append(entry.payload.score)

        entries = []
        for doc_id, scores in doc_scores.items():
            if self.mode == "and":
                while len(scores) < len(results):
                    scores.append(0.0)
                fused = ProbabilisticBoolean.prob_and(scores)
            else:
                fused = ProbabilisticBoolean.prob_or(scores)
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList(entries)

    def compose(self, other: Any) -> Any:
        from uqa.operators.base import ComposedOperator
        return ComposedOperator([self, other])

    def cost_estimate(self, stats: Any) -> float:
        return sum(
            getattr(s, "cost_estimate", lambda _: 100.0)(stats)
            for s in self.sources
        )
