#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import pyarrow as pa
    from numpy.typing import NDArray

    from uqa.core.posting_list import PostingList
    from uqa.core.types import PathExpr, Predicate
    from uqa.engine import Engine


def _posting_list_to_arrow(pl: PostingList) -> pa.Table:
    """Convert a PostingList to a ``pyarrow.Table``."""
    import pyarrow as pa

    from uqa.sql.compiler import _infer_arrow_type

    if not pl:
        return pa.table(
            {
                "_doc_id": pa.array([], type=pa.int64()),
                "_score": pa.array([], type=pa.float64()),
            }
        )

    doc_ids: list[int] = []
    scores: list[float] = []
    field_values: dict[str, list[Any]] = {}

    for entry in pl:
        doc_ids.append(entry.doc_id)
        scores.append(entry.payload.score)
        for k, v in entry.payload.fields.items():
            if k not in field_values:
                field_values[k] = [None] * len(doc_ids[:-1])
            field_values[k].append(v)
        for k in field_values:
            if k not in entry.payload.fields:
                field_values[k].append(None)

    arrays: dict[str, pa.Array] = {
        "_doc_id": pa.array(doc_ids, type=pa.int64()),
        "_score": pa.array(scores, type=pa.float64()),
    }
    for k, vals in field_values.items():
        arrays[k] = pa.array(vals, type=_infer_arrow_type(vals))

    return pa.table(arrays)


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

    def knn_calibrated(
        self,
        query: NDArray,
        k: int,
        field: str = "embedding",
        *,
        estimation_method: str = "kde",
        base_rate: float = 0.5,
        weight_source: str = "density_prior",
        bm25_query: str | None = None,
        bm25_field: str | None = None,
        density_gamma: float = 1.0,
        bandwidth_scale: float = 1.0,
    ) -> QueryBuilder:
        """KNN with likelihood ratio calibration (Paper 5, Theorem 3.1.1).

        Parameters
        ----------
        query : ndarray
            Query embedding vector.
        k : int
            Number of nearest neighbours.
        field : str
            Vector field name.
        estimation_method : str
            ``"kde"`` or ``"gmm"`` for local density estimation.
        base_rate : float
            Prior probability of relevance.
        weight_source : str
            ``"bayesian_bm25"`` (cross-modal, Section 4.3),
            ``"density_prior"``, ``"distance_gap"``, or ``"uniform"``.
        bm25_query : str or None
            Query text for BM25 cross-modal weights.
        bm25_field : str or None
            Text field for BM25 scoring.
        density_gamma : float
            Sensitivity for the IVF density prior.
        bandwidth_scale : float
            Multiplier for Silverman bandwidth (Remark 4.4.2).
            Values < 1.0 sharpen the KDE; values > 1.0 smooth it.
        """
        from uqa.operators.calibrated_vector import CalibratedVectorOperator

        op = CalibratedVectorOperator(
            query_vector=query,
            k=k,
            field=field,
            estimation_method=estimation_method,
            base_rate=base_rate,
            weight_source=weight_source,
            bm25_query=bm25_query,
            bm25_field=bm25_field,
            density_gamma=density_gamma,
            bandwidth_scale=bandwidth_scale,
        )
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

        op = TraverseOperator(start, graph=self._table, label=label, max_hops=max_hops)
        return self._chain(op)

    def temporal_traverse(
        self,
        start: int,
        label: str | None = None,
        max_hops: int = 1,
        *,
        timestamp: float | None = None,
        time_range: tuple[float, float] | None = None,
    ) -> QueryBuilder:
        """Temporal-aware graph traversal (Section 10, Paper 2)."""
        from uqa.graph.temporal_filter import TemporalFilter
        from uqa.graph.temporal_traverse import TemporalTraverseOperator

        tf = None
        if timestamp is not None or time_range is not None:
            tf = TemporalFilter(timestamp=timestamp, time_range=time_range)

        op = TemporalTraverseOperator(start, label, max_hops, tf, graph=self._table)
        return self._chain(op)

    def match_pattern(self, pattern: Any) -> QueryBuilder:
        from uqa.graph.operators import PatternMatchOperator

        op = PatternMatchOperator(pattern, graph=self._table)
        return self._chain(op)

    def rpq(self, expr: str, start: int | None = None) -> QueryBuilder:
        from uqa.graph.operators import RegularPathQueryOperator
        from uqa.graph.pattern import parse_rpq

        path_expr = parse_rpq(expr)
        op = RegularPathQueryOperator(path_expr, graph=self._table, start_vertex=start)
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
            raise ValueError("vertex_aggregate requires a graph traversal source")

        op = VertexAggregationOperator(self._root, property_name, agg_fn)
        ctx = self._engine._context_for_table(self._table)
        result_gpl = op.execute(ctx)

        if result_gpl and len(result_gpl) > 0:
            entry = next(iter(result_gpl))
            return AggregateResult(entry.payload.fields.get("_vertex_agg_result"))
        return AggregateResult(0.0)

    # -- Vector exclusion (Definition 3.3.3, Paper 1) --

    def vector_exclude(
        self, negative_vector: NDArray, threshold: float
    ) -> QueryBuilder:
        """Exclude documents similar to a negative query vector."""
        from uqa.operators.hybrid import VectorExclusionOperator

        if self._root is None:
            raise ValueError("vector_exclude requires a source query")

        op = VectorExclusionOperator(self._root, negative_vector, threshold)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Sparse thresholding (Section 6.5, Paper 4) --

    def sparse_threshold(self, threshold: float) -> QueryBuilder:
        """Apply ReLU thresholding: max(0, score - threshold) (Section 6.5, Paper 4)."""
        from uqa.operators.sparse import SparseThresholdOperator

        if self._root is None:
            raise ValueError("sparse_threshold requires a source query")

        op = SparseThresholdOperator(self._root, threshold)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- GNN integration (Paper 2 + Paper 4) --

    def message_passing(
        self,
        k_layers: int = 2,
        aggregation: str = "mean",
        property_name: str | None = None,
    ) -> QueryBuilder:
        """K-layer message-passing aggregation (Paper 2 + Paper 4)."""
        from uqa.graph.message_passing import MessagePassingOperator

        op = MessagePassingOperator(
            k_layers, aggregation, property_name, graph=self._table
        )
        return self._chain(op)

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

        op = FacetVectorOperator(field, query_vector, threshold, self._root)
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

    def path_aggregate(self, path: str | PathExpr, agg: str) -> QueryBuilder:
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
        analyzer = (
            ctx.inverted_index.get_field_analyzer(field)
            if field
            else ctx.inverted_index.analyzer
        )
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
        analyzer = (
            ctx.inverted_index.get_field_analyzer(field)
            if field
            else ctx.inverted_index.analyzer
        )
        terms = analyzer.analyze(query)
        scorer = BayesianBM25Scorer(BayesianBM25Params(), ctx.inverted_index.stats)
        op = ScoreOperator(scorer, self._root, terms)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def score_multi_field_bayesian(
        self,
        query: str,
        fields: list[str],
        weights: list[float] | None = None,
    ) -> QueryBuilder:
        """Multi-field Bayesian BM25 search (Section 12.2 #1, Paper 3)."""
        from uqa.operators.multi_field import MultiFieldSearchOperator

        op = MultiFieldSearchOperator(fields, query, weights)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def score_bayesian_with_prior(
        self,
        query: str,
        field: str | None = None,
        *,
        prior_fn: Any = None,
    ) -> QueryBuilder:
        """Bayesian BM25 scoring with external prior (Section 12.2 #6, Paper 3)."""
        from uqa.operators.primitive import TermOperator
        from uqa.scoring.bayesian_bm25 import BayesianBM25Params
        from uqa.scoring.external_prior import ExternalPriorScorer
        from uqa.sql.compiler import _ExternalPriorSearchOperator

        if prior_fn is None:
            raise ValueError("prior_fn is required for score_bayesian_with_prior")

        ctx = self._engine._context_for_table(self._table)
        idx = ctx.inverted_index
        analyzer = idx.get_field_analyzer(field) if field else idx.analyzer
        terms = analyzer.analyze(query)
        scorer = ExternalPriorScorer(BayesianBM25Params(), idx.stats, prior_fn)

        retrieval = self._root if self._root is not None else TermOperator(query, field)

        op = _ExternalPriorSearchOperator(
            retrieval, scorer, terms, field, ctx.document_store
        )
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    def learn_params(
        self,
        query: str,
        labels: list[int],
        *,
        mode: str = "balanced",
        field: str | None = None,
    ) -> dict[str, float]:
        """Learn Bayesian BM25 calibration parameters (Section 8, Paper 3).

        Delegates to Engine.learn_scoring_params().
        """
        f = field or "_default"
        return self._engine.learn_scoring_params(
            self._table, f, query, labels, mode=mode
        )

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

    def fuse_attention(
        self, *builders: QueryBuilder, alpha: float = 0.5
    ) -> QueryBuilder:
        """Attention-weighted fusion (Section 8, Paper 4)."""
        import numpy as np

        from uqa.fusion.attention import AttentionFusion
        from uqa.operators.attention import AttentionFusionOperator

        sources = [b._root for b in builders if b._root is not None]
        if len(sources) < 2:
            raise ValueError("fuse_attention requires at least 2 signals")

        n_signals = len(sources)
        attention = AttentionFusion(n_signals=n_signals, alpha=alpha)
        query_features = np.zeros(6, dtype=np.float64)

        qb = QueryBuilder(self._engine, self._table)
        qb._root = AttentionFusionOperator(sources, attention, query_features)
        return qb

    def fuse_learned(self, *builders: QueryBuilder, alpha: float = 0.5) -> QueryBuilder:
        """Learned-weight fusion (Section 8, Paper 4)."""
        from uqa.fusion.learned import LearnedFusion
        from uqa.operators.learned_fusion import LearnedFusionOperator

        sources = [b._root for b in builders if b._root is not None]
        if len(sources) < 2:
            raise ValueError("fuse_learned requires at least 2 signals")

        learned = LearnedFusion(n_signals=len(sources), alpha=alpha)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = LearnedFusionOperator(sources, learned)
        return qb

    # -- Multi-stage pipeline (Section 9, Paper 4) --

    def multi_stage(
        self, stages: list[tuple[QueryBuilder, int | float]]
    ) -> QueryBuilder:
        """Multi-stage retrieval pipeline (Section 9, Paper 4)."""
        from uqa.operators.multi_stage import MultiStageOperator

        stage_list = []
        for builder, cutoff in stages:
            if builder._root is None:
                raise ValueError("Each stage must have an operator")
            stage_list.append((builder._root, cutoff))

        op = MultiStageOperator(stage_list)
        qb = QueryBuilder(self._engine, self._table)
        qb._root = op
        return qb

    # -- Execution --

    def execute(self) -> PostingList:
        from uqa.core.posting_list import PostingList
        from uqa.planner.executor import PlanExecutor
        from uqa.planner.optimizer import QueryOptimizer

        if self._root is None:
            return PostingList()

        ctx = self._engine._context_for_table(self._table)
        optimizer = QueryOptimizer(ctx.inverted_index.stats)
        optimized = optimizer.optimize(self._root)

        executor = PlanExecutor(ctx)
        return executor.execute(optimized)

    def execute_arrow(self) -> pa.Table:
        """Execute and return results as a ``pyarrow.Table``."""
        return _posting_list_to_arrow(self.execute())

    def execute_parquet(self, path: str) -> None:
        """Execute and write results to a Parquet file at *path*."""
        import pyarrow.parquet as pq

        pq.write_table(self.execute_arrow(), path)

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
        from uqa.core.posting_list import PostingList
        from uqa.core.types import Payload, PostingEntry
        from uqa.operators.hybrid import _coverage_based_default

        posting_lists = [src.execute(context) for src in self.sources]

        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        num_docs = len(all_doc_ids)
        defaults = [_coverage_based_default(len(smap), num_docs) for smap in score_maps]

        entries = []
        for doc_id in sorted(all_doc_ids):
            probs = [smap.get(doc_id, defaults[j]) for j, smap in enumerate(score_maps)]
            fused_score = self.fusion.fuse(probs)
            entries.append(PostingEntry(doc_id, Payload(score=fused_score)))

        return PostingList(entries)

    def compose(self, other: Any) -> Any:
        from uqa.operators.base import ComposedOperator, Operator

        return ComposedOperator(cast("list[Operator]", [self, other]))

    def cost_estimate(self, stats: Any) -> float:
        return sum(
            getattr(s, "cost_estimate", lambda _: 100.0)(stats) for s in self.sources
        )


class _ProbBooleanOperator:
    """Internal operator for probabilistic boolean fusion."""

    def __init__(self, mode: str, sources: list[Any]):
        self.mode = mode
        self.sources = sources

    def execute(self, context: Any) -> Any:
        from uqa.core.posting_list import PostingList
        from uqa.core.types import Payload, PostingEntry
        from uqa.fusion.boolean import ProbabilisticBoolean
        from uqa.operators.hybrid import _coverage_based_default

        posting_lists = [src.execute(context) for src in self.sources]

        all_doc_ids: set[int] = set()
        score_maps: list[dict[int, float]] = []
        for pl in posting_lists:
            smap: dict[int, float] = {}
            for entry in pl:
                smap[entry.doc_id] = entry.payload.score
                all_doc_ids.add(entry.doc_id)
            score_maps.append(smap)

        num_docs = len(all_doc_ids)
        defaults = [_coverage_based_default(len(smap), num_docs) for smap in score_maps]

        fuse_fn = (
            ProbabilisticBoolean.prob_and
            if self.mode == "and"
            else ProbabilisticBoolean.prob_or
        )
        entries = []
        for doc_id in sorted(all_doc_ids):
            probs = [smap.get(doc_id, defaults[j]) for j, smap in enumerate(score_maps)]
            fused = fuse_fn(probs)
            entries.append(PostingEntry(doc_id, Payload(score=fused)))

        return PostingList(entries)

    def compose(self, other: Any) -> Any:
        from uqa.operators.base import ComposedOperator, Operator

        return ComposedOperator(cast("list[Operator]", [self, other]))

    def cost_estimate(self, stats: Any) -> float:
        return sum(
            getattr(s, "cost_estimate", lambda _: 100.0)(stats) for s in self.sources
        )
