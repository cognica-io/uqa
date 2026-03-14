#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any

from uqa.core.types import Payload, PostingEntry
from uqa.graph.pattern import (
    Alternation,
    Concat,
    EdgePattern,
    GraphPattern,
    KleeneStar,
    Label,
    RegularPathExpr,
)
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
    from uqa.graph.cypher.ast import CypherQuery
    from uqa.graph.store import GraphStore


class TraverseOperator:
    """Definition 2.2.1: Traverse_{v,l,k}

    BFS from start_vertex, follow edges matching label (None = any),
    up to max_hops. Build GraphPostingList where each reached vertex
    is a separate entry.
    """

    def __init__(
        self,
        start_vertex: int,
        label: str | None = None,
        max_hops: int = 1,
    ) -> None:
        self.start_vertex = start_vertex
        self.label = label
        self.max_hops = max_hops

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        visited: set[int] = set()
        frontier: set[int] = {self.start_vertex}
        all_edges: set[int] = set()

        for _ in range(self.max_hops):
            next_frontier: set[int] = set()
            for v in frontier:
                # Collect edges and neighbors
                adj = graph._adj_out.get(v, set())
                if self.label is not None:
                    label_eids = graph._label_index.get(self.label, set())
                    edge_ids = adj & label_eids
                else:
                    edge_ids = adj
                for eid in edge_ids:
                    edge = graph._edges[eid]
                    neighbor = edge.target_id
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
                        all_edges.add(eid)
            visited.update(frontier)
            frontier = next_frontier
            if not frontier:
                break
        visited.update(frontier)

        # Build GraphPostingList: each reached vertex (excluding start) is an entry
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        frozen_visited = frozenset(visited)
        frozen_edges = frozenset(all_edges)
        for vid in sorted(visited):
            entry = PostingEntry(vid, Payload(score=0.9))
            entries.append(entry)
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=frozen_visited,
                subgraph_edges=frozen_edges,
            )

        gpl = GraphPostingList(entries, graph_payloads)
        return gpl


class PatternMatchOperator:
    """Definition 2.2.2 / 5.2.2: GMatch_P

    Subgraph isomorphism pattern matching via backtracking with:
    - Candidate pre-computation with arc consistency pruning
    - MRV (Minimum Remaining Values) variable ordering
    - Incremental edge validation during search
    """

    def __init__(self, pattern: GraphPattern) -> None:
        self.pattern = pattern

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]

        # Pre-compute candidate sets with arc consistency filtering
        var_candidates = self._compute_candidates(graph)

        # Build edge lookup for incremental validation
        var_edges: dict[str, list[EdgePattern]] = defaultdict(list)
        for ep in self.pattern.edge_patterns:
            var_edges[ep.source_var].append(ep)
            var_edges[ep.target_var].append(ep)

        variables = [vp.variable for vp in self.pattern.vertex_patterns]
        unassigned = set(variables)
        matches: list[dict[str, int]] = []
        self._backtrack(
            graph, var_candidates, var_edges, unassigned, {}, set(), matches
        )

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for i, assignment in enumerate(matches):
            match_vertices = frozenset(assignment.values())
            match_edges = self._collect_match_edges(graph, assignment)
            doc_id = i + 1
            entry = PostingEntry(
                doc_id,
                Payload(score=0.9, fields=dict(assignment)),
            )
            entries.append(entry)
            graph_payloads[doc_id] = GraphPayload(
                subgraph_vertices=match_vertices,
                subgraph_edges=match_edges,
            )

        return GraphPostingList(entries, graph_payloads)

    def _compute_candidates(self, graph: GraphStore) -> dict[str, list[int]]:
        """Pre-compute candidate vertex IDs per variable with arc consistency.

        Step 1: Evaluate vertex constraints once for all vertices.
        Step 2: Propagate edge constraints until no further reduction
                (arc consistency fixpoint).
        """
        vp_map = {vp.variable: vp for vp in self.pattern.vertex_patterns}
        candidates: dict[str, list[int]] = {}
        for var, vp in vp_map.items():
            candidates[var] = [
                vid
                for vid, vertex in graph._vertices.items()
                if all(c(vertex) for c in vp.constraints)
            ]

        # Arc consistency: narrow candidates via edge constraints
        changed = True
        while changed:
            changed = False
            for ep in self.pattern.edge_patterns:
                src_var, tgt_var = ep.source_var, ep.target_var
                if src_var not in candidates or tgt_var not in candidates:
                    continue

                tgt_set = set(candidates[tgt_var])
                new_src = [
                    vid
                    for vid in candidates[src_var]
                    if self._has_matching_edge_out(graph, vid, tgt_set, ep)
                ]
                if len(new_src) < len(candidates[src_var]):
                    candidates[src_var] = new_src
                    changed = True

                src_set = set(candidates[src_var])
                new_tgt = [
                    vid
                    for vid in candidates[tgt_var]
                    if self._has_matching_edge_in(graph, vid, src_set, ep)
                ]
                if len(new_tgt) < len(candidates[tgt_var]):
                    candidates[tgt_var] = new_tgt
                    changed = True

        return candidates

    @staticmethod
    def _has_matching_edge_out(
        graph: GraphStore,
        src_vid: int,
        tgt_set: set[int],
        ep: EdgePattern,
    ) -> bool:
        for eid in graph._adj_out.get(src_vid, []):
            edge = graph._edges[eid]
            if edge.target_id not in tgt_set:
                continue
            if ep.label is not None and edge.label != ep.label:
                continue
            if all(c(edge) for c in ep.constraints):
                return True
        return False

    @staticmethod
    def _has_matching_edge_in(
        graph: GraphStore,
        tgt_vid: int,
        src_set: set[int],
        ep: EdgePattern,
    ) -> bool:
        for eid in graph._adj_in.get(tgt_vid, []):
            edge = graph._edges[eid]
            if edge.source_id not in src_set:
                continue
            if ep.label is not None and edge.label != ep.label:
                continue
            if all(c(edge) for c in ep.constraints):
                return True
        return False

    def _backtrack(
        self,
        graph: GraphStore,
        var_candidates: dict[str, list[int]],
        var_edges: dict[str, list[EdgePattern]],
        unassigned: set[str],
        assignment: dict[str, int],
        assigned_values: set[int],
        matches: list[dict[str, int]],
    ) -> None:
        if not unassigned:
            matches.append(dict(assignment))
            return

        # MRV: pick the unassigned variable with fewest candidates
        var = min(unassigned, key=lambda v: len(var_candidates[v]))

        for vid in var_candidates[var]:
            if vid in assigned_values:
                continue

            assignment[var] = vid
            assigned_values.add(vid)
            unassigned.discard(var)

            # Incremental edge validation
            if self._validate_edges_for(graph, var, var_edges, assignment):
                self._backtrack(
                    graph,
                    var_candidates,
                    var_edges,
                    unassigned,
                    assignment,
                    assigned_values,
                    matches,
                )

            del assignment[var]
            assigned_values.discard(vid)
            unassigned.add(var)

    @staticmethod
    def _validate_edges_for(
        graph: GraphStore,
        var: str,
        var_edges: dict[str, list[EdgePattern]],
        assignment: dict[str, int],
    ) -> bool:
        """Check edge constraints involving *var* and already-bound variables."""
        for ep in var_edges.get(var, []):
            src_id = assignment.get(ep.source_var)
            tgt_id = assignment.get(ep.target_var)
            if src_id is None or tgt_id is None:
                continue
            found = False
            for eid in graph._adj_out.get(src_id, []):
                edge = graph._edges[eid]
                if edge.target_id != tgt_id:
                    continue
                if ep.label is not None and edge.label != ep.label:
                    continue
                if all(c(edge) for c in ep.constraints):
                    found = True
                    break
            if not found:
                return False
        return True

    def _collect_match_edges(
        self, graph: GraphStore, assignment: dict[str, int]
    ) -> frozenset[int]:
        edge_ids: set[int] = set()
        for ep in self.pattern.edge_patterns:
            src_id = assignment[ep.source_var]
            tgt_id = assignment[ep.target_var]
            for eid in graph._adj_out.get(src_id, []):
                edge = graph._edges[eid]
                if edge.target_id == tgt_id and (
                    ep.label is None or edge.label == ep.label
                ):
                    edge_ids.add(eid)
                    break
        return frozenset(edge_ids)


# -- NFA types for RPQ --


class _NFAState:
    """A state in the NFA for regular path query evaluation."""

    def __init__(self, state_id: int) -> None:
        self.state_id = state_id
        self.transitions: list[tuple[str | None, _NFAState]] = []


class _NFA:
    """Thompson's construction NFA for regular path expressions."""

    def __init__(self, start: _NFAState, accept: _NFAState) -> None:
        self.start = start
        self.accept = accept


_state_counter = 0


def _new_state() -> _NFAState:
    global _state_counter
    _state_counter += 1
    return _NFAState(_state_counter)


def _reset_state_counter() -> None:
    global _state_counter
    _state_counter = 0


def _build_nfa(expr: RegularPathExpr) -> _NFA:
    """Build an NFA from a RegularPathExpr using Thompson's construction."""
    if isinstance(expr, Label):
        start = _new_state()
        accept = _new_state()
        start.transitions.append((expr.name, accept))
        return _NFA(start, accept)

    if isinstance(expr, Concat):
        left_nfa = _build_nfa(expr.left)
        right_nfa = _build_nfa(expr.right)
        # Connect left accept to right start via epsilon
        left_nfa.accept.transitions.append((None, right_nfa.start))
        return _NFA(left_nfa.start, right_nfa.accept)

    if isinstance(expr, Alternation):
        start = _new_state()
        accept = _new_state()
        left_nfa = _build_nfa(expr.left)
        right_nfa = _build_nfa(expr.right)
        start.transitions.append((None, left_nfa.start))
        start.transitions.append((None, right_nfa.start))
        left_nfa.accept.transitions.append((None, accept))
        right_nfa.accept.transitions.append((None, accept))
        return _NFA(start, accept)

    if isinstance(expr, KleeneStar):
        start = _new_state()
        accept = _new_state()
        inner_nfa = _build_nfa(expr.inner)
        start.transitions.append((None, inner_nfa.start))
        start.transitions.append((None, accept))
        inner_nfa.accept.transitions.append((None, inner_nfa.start))
        inner_nfa.accept.transitions.append((None, accept))
        return _NFA(start, accept)

    raise TypeError(f"Unknown RegularPathExpr type: {type(expr)}")


def _epsilon_closure(states: set[_NFAState]) -> set[_NFAState]:
    """Compute epsilon closure of a set of NFA states."""
    stack = list(states)
    closure = set(states)
    while stack:
        state = stack.pop()
        for label, target in state.transitions:
            if label is None and target not in closure:
                closure.add(target)
                stack.append(target)
    return closure


class RegularPathQueryOperator:
    """Definition 5.1.2: RPQ_R

    NFA simulation for regular path expression evaluation.
    Complexity: O(|V|^2 * |R|) (Theorem 8.1.2, Paper 2).
    """

    def __init__(
        self,
        path_expr: RegularPathExpr,
        start_vertex: int | None = None,
    ) -> None:
        self.path_expr = path_expr
        self.start_vertex = start_vertex

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        _reset_state_counter()
        nfa = _build_nfa(self.path_expr)

        # Determine starting vertices
        if self.start_vertex is not None:
            start_vertices = [self.start_vertex]
        else:
            start_vertices = list(graph._vertices.keys())

        # For each start vertex, simulate NFA across graph
        # State = (graph_vertex, nfa_state)
        # BFS until reaching accepting states
        result_pairs: set[tuple[int, int]] = set()  # (start, end) pairs

        # Build state_id -> _NFAState lookup once for all start vertices.
        all_nfa_states = self._collect_nfa_states(nfa)
        state_map = {s.state_id: s for s in all_nfa_states}

        initial_nfa_states = _epsilon_closure({nfa.start})
        initial_ids = frozenset(s.state_id for s in initial_nfa_states)
        accept_id = nfa.accept.state_id

        for sv in start_vertices:
            # Queue: (graph_vertex, nfa_states_set_as_frozenset)
            queue: deque[tuple[int, frozenset[int]]] = deque()
            queue.append((sv, initial_ids))
            visited_configs: set[tuple[int, frozenset[int]]] = {(sv, initial_ids)}

            # Check if start is already accepting
            if accept_id in initial_ids:
                result_pairs.add((sv, sv))

            while queue:
                gv, nfa_state_ids = queue.popleft()
                # For each edge label from current graph vertex
                for eid in graph._adj_out.get(gv, []):
                    edge = graph._edges[eid]
                    edge_label = edge.label
                    neighbor = edge.target_id

                    # Compute next NFA states after consuming this label
                    next_nfa: set[_NFAState] = set()
                    for sid in nfa_state_ids:
                        state = state_map.get(sid)
                        if state is None:
                            continue
                        for trans_label, target in state.transitions:
                            if trans_label == edge_label:
                                next_nfa.add(target)

                    if not next_nfa:
                        continue

                    next_nfa = _epsilon_closure(next_nfa)
                    next_ids = frozenset(s.state_id for s in next_nfa)

                    if accept_id in next_ids:
                        result_pairs.add((sv, neighbor))

                    config = (neighbor, next_ids)
                    if config not in visited_configs:
                        visited_configs.add(config)
                        queue.append(config)

        # Build GraphPostingList from result pairs
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        seen_ids: set[int] = set()
        for start_v, end_v in result_pairs:
            doc_id = end_v
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                entries.append(PostingEntry(doc_id, Payload(score=0.9)))
                graph_payloads[doc_id] = GraphPayload(
                    subgraph_vertices=frozenset({start_v, end_v}),
                    subgraph_edges=frozenset(),
                )

        entries.sort(key=lambda e: e.doc_id)
        return GraphPostingList(entries, graph_payloads)

    def _collect_nfa_states(self, nfa: _NFA) -> set[_NFAState]:
        """Collect all states reachable from nfa.start."""
        visited: set[_NFAState] = set()
        stack = [nfa.start]
        while stack:
            state = stack.pop()
            if state in visited:
                continue
            visited.add(state)
            for _, target in state.transitions:
                stack.append(target)
        return visited


class VertexAggregationOperator:
    """Definition 2.2.3: Aggregate vertex properties over traversal results.

    Given a traversal result (GraphPostingList), aggregates a specified
    vertex property across all reached vertices using a provided
    aggregation function.

    Returns a GraphPostingList with a single entry containing the
    aggregated result.
    """

    def __init__(
        self,
        source: TraverseOperator | PatternMatchOperator | RegularPathQueryOperator,
        property_name: str,
        agg_fn: str = "sum",
    ) -> None:
        self.source = source
        self.property_name = property_name
        self.agg_fn = agg_fn

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        source_gpl = self.source.execute(ctx)

        vertex_ids: set[int] = set()
        for entry in source_gpl:
            gp = source_gpl.get_graph_payload(entry.doc_id)
            if gp is not None:
                vertex_ids.update(gp.subgraph_vertices)

        values: list[Any] = []
        for vid in sorted(vertex_ids):
            vertex = graph.get_vertex(vid)
            if vertex is not None:
                val = vertex.properties.get(self.property_name)
                if val is not None:
                    values.append(val)

        result = self._aggregate(values)

        entries = [
            PostingEntry(
                0,
                Payload(
                    score=float(result) if isinstance(result, (int, float)) else 0.0,
                    fields={
                        "_vertex_agg_property": self.property_name,
                        "_vertex_agg_fn": self.agg_fn,
                        "_vertex_agg_result": result,
                        "_vertex_agg_count": len(values),
                    },
                ),
            )
        ]
        return GraphPostingList(
            entries,
            {
                0: GraphPayload(
                    subgraph_vertices=frozenset(vertex_ids),
                    subgraph_edges=frozenset(),
                )
            },
        )

    def _aggregate(self, values: list[Any]) -> Any:
        if not values:
            return 0.0
        numeric = [float(v) for v in values]
        if self.agg_fn == "sum":
            return sum(numeric)
        if self.agg_fn == "avg":
            return sum(numeric) / len(numeric)
        if self.agg_fn == "min":
            return min(numeric)
        if self.agg_fn == "max":
            return max(numeric)
        if self.agg_fn == "count":
            return len(values)
        return sum(numeric)


class CypherQueryOperator:
    """Execute an openCypher query against a named graph.

    Integrates into the operator tree alongside TraverseOperator and
    RegularPathQueryOperator.  The execute() method runs the Cypher
    compiler and returns a GraphPostingList with projected fields.

    When *col_names* is provided (from the SQL ``AS`` clause), the
    Cypher result keys are remapped positionally to the SQL column
    names so downstream physical operators see the expected names.
    """

    def __init__(
        self,
        graph: GraphStore,
        query: CypherQuery,
        params: dict[str, Any] | None = None,
        col_names: list[str] | None = None,
    ) -> None:
        self.graph = graph
        self.query = query
        self.params = params or {}
        self.col_names = col_names

    def execute(self, ctx: object) -> GraphPostingList:
        from uqa.graph.cypher.compiler import CypherCompiler

        compiler = CypherCompiler(self.graph, params=self.params)
        gpl = compiler.execute_posting_list(self.query)

        if self.col_names is None:
            return gpl

        # Remap Cypher result keys to AS clause column names.
        cypher_keys: list[str] | None = None
        remapped_entries: list[PostingEntry] = []
        remapped_payloads: dict[int, GraphPayload] = {}

        for entry in gpl:
            old_fields = entry.payload.fields
            if cypher_keys is None:
                cypher_keys = list(old_fields.keys())
            new_fields: dict[str, Any] = {}
            for i, col in enumerate(self.col_names):
                if col in old_fields:
                    new_fields[col] = old_fields[col]
                elif i < len(cypher_keys):
                    new_fields[col] = old_fields.get(cypher_keys[i])
            new_entry = PostingEntry(
                entry.doc_id,
                Payload(score=entry.payload.score, fields=new_fields),
            )
            remapped_entries.append(new_entry)
            gp = gpl.get_graph_payload(entry.doc_id)
            if gp is not None:
                remapped_payloads[entry.doc_id] = gp

        return GraphPostingList(remapped_entries, remapped_payloads)
