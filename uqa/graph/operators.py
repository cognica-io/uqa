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
    BoundedLabel,
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

DEFAULT_GRAPH_SCORE: float = 0.9
_EMPTY: frozenset[int] = frozenset()

# Lazy-loaded RPQ optimizer functions (avoid circular import)
_rpq_simplify = None
_rpq_subset = None


def _get_rpq_optimizer() -> tuple[Any, Any]:
    global _rpq_simplify, _rpq_subset
    if _rpq_simplify is None:
        from uqa.graph.rpq_optimizer import _simplify_expr, _subset_construction

        _rpq_simplify = _simplify_expr
        _rpq_subset = _subset_construction
    return _rpq_simplify, _rpq_subset


class TraverseOperator:
    """Definition 2.2.1: Traverse_{v,l,k}

    BFS from start_vertex, follow edges matching label (None = any),
    up to max_hops. Build GraphPostingList where each reached vertex
    is a separate entry.
    """

    def __init__(
        self,
        start_vertex: int,
        *,
        graph: str,
        label: str | None = None,
        max_hops: int = 1,
        vertex_predicate: object | None = None,
        score: float = DEFAULT_GRAPH_SCORE,
    ) -> None:
        self.start_vertex = start_vertex
        self.label = label
        self.max_hops = max_hops
        self.graph_name = graph
        self.vertex_predicate = vertex_predicate
        self.score = score

    def execute(self, ctx: object) -> GraphPostingList:
        gs: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        visited: set[int] = set()
        frontier: set[int] = {self.start_vertex}
        all_edges: set[int] = set()

        # Cache partition and edges dict for tight-loop access
        g = self.graph_name
        part = gs.partition(g)
        edges = gs._edges
        label_eids = (
            part.label_index.get(self.label, _EMPTY) if self.label is not None else None
        )

        for _ in range(self.max_hops):
            next_frontier: set[int] = set()
            for v in frontier:
                adj = part.adj_out.get(v, _EMPTY)
                edge_ids = adj & label_eids if label_eids is not None else adj
                for eid in edge_ids:
                    edge = edges[eid]
                    neighbor = edge.target_id
                    if neighbor in visited:
                        continue
                    if self.vertex_predicate is not None and callable(
                        self.vertex_predicate
                    ):
                        vtx = gs.get_vertex(neighbor)
                        if vtx is not None and not self.vertex_predicate(vtx):
                            continue
                    next_frontier.add(neighbor)
                    all_edges.add(eid)
            visited.update(frontier)
            frontier = next_frontier
            if not frontier:
                break
        visited.update(frontier)

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        frozen_visited = frozenset(visited)
        frozen_edges = frozenset(all_edges)
        for vid in sorted(visited):
            entry = PostingEntry(vid, Payload(score=self.score))
            entries.append(entry)
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=frozen_visited,
                subgraph_edges=frozen_edges,
                graph_name=g,
            )

        return GraphPostingList(entries, graph_payloads)


class PatternMatchOperator:
    """Definition 2.2.2 / 5.2.2: GMatch_P

    Subgraph isomorphism pattern matching via backtracking with:
    - Candidate pre-computation with arc consistency pruning
    - MRV (Minimum Remaining Values) variable ordering
    - Incremental edge validation during search
    """

    def __init__(
        self,
        pattern: GraphPattern,
        *,
        graph: str,
        score: float = DEFAULT_GRAPH_SCORE,
    ) -> None:
        self.pattern = pattern
        self.graph_name = graph
        self.score = score

    def execute(self, ctx: object) -> GraphPostingList:
        gs: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        g = self.graph_name

        # Check subgraph index cache (Section 9.1, Paper 2)
        subgraph_index = getattr(ctx, "subgraph_index", None)
        if subgraph_index is not None:
            cached = subgraph_index.lookup(self.pattern)
            if cached is not None:
                return self._build_from_cached(cached, g, self.score)

        var_candidates = self._compute_candidates(gs, g)

        # Separate positive and negated edge patterns
        positive_edges: list[EdgePattern] = []
        negated_edges: list[EdgePattern] = []
        for ep in self.pattern.edge_patterns:
            if ep.negated:
                negated_edges.append(ep)
            else:
                positive_edges.append(ep)

        var_edges: dict[str, list[EdgePattern]] = defaultdict(list)
        for ep in positive_edges:
            var_edges[ep.source_var].append(ep)
            var_edges[ep.target_var].append(ep)

        variables = [vp.variable for vp in self.pattern.vertex_patterns]
        unassigned = set(variables)
        matches: list[dict[str, int]] = []
        self._backtrack(
            gs, g, var_candidates, var_edges, unassigned, {}, set(), matches
        )

        # Post-filter: remove matches that violate negated edge constraints
        if negated_edges:
            filtered: list[dict[str, int]] = []
            for assignment in matches:
                if self._check_negated_edges(gs, g, negated_edges, assignment):
                    filtered.append(assignment)
            matches = filtered

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for i, assignment in enumerate(matches):
            match_vertices = frozenset(assignment.values())
            match_edges = self._collect_match_edges(gs, g, assignment)
            doc_id = i + 1
            entry = PostingEntry(
                doc_id,
                Payload(score=self.score, fields=dict(assignment)),
            )
            entries.append(entry)
            graph_payloads[doc_id] = GraphPayload(
                subgraph_vertices=match_vertices,
                subgraph_edges=match_edges,
                graph_name=g,
            )

        return GraphPostingList(entries, graph_payloads)

    @staticmethod
    def _build_from_cached(
        cached: set[frozenset[int]],
        graph_name: str,
        score: float = DEFAULT_GRAPH_SCORE,
    ) -> GraphPostingList:
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for i, vertex_set in enumerate(
            sorted(cached, key=lambda s: tuple(sorted(s))), 1
        ):
            entry = PostingEntry(
                i,
                Payload(score=score, fields={}),
            )
            entries.append(entry)
            graph_payloads[i] = GraphPayload(
                subgraph_vertices=vertex_set,
                subgraph_edges=frozenset(),
                graph_name=graph_name,
            )
        return GraphPostingList(entries, graph_payloads)

    def _compute_candidates(self, gs: GraphStore, g: str) -> dict[str, list[int]]:
        vp_map = {vp.variable: vp for vp in self.pattern.vertex_patterns}
        candidates: dict[str, list[int]] = {}
        graph_vids = gs.vertex_ids_in_graph(g)
        for var, vp in vp_map.items():
            candidates[var] = [
                vid
                for vid in graph_vids
                if vid in gs._vertices
                and all(c(gs._vertices[vid]) for c in vp.constraints)
            ]

        # Arc consistency (skip negated edges -- they are checked post-match)
        changed = True
        while changed:
            changed = False
            for ep in self.pattern.edge_patterns:
                if ep.negated:
                    continue
                src_var, tgt_var = ep.source_var, ep.target_var
                if src_var not in candidates or tgt_var not in candidates:
                    continue

                tgt_set = set(candidates[tgt_var])
                new_src = [
                    vid
                    for vid in candidates[src_var]
                    if self._has_matching_edge_out(gs, g, vid, tgt_set, ep)
                ]
                if len(new_src) < len(candidates[src_var]):
                    candidates[src_var] = new_src
                    changed = True

                src_set = set(candidates[src_var])
                new_tgt = [
                    vid
                    for vid in candidates[tgt_var]
                    if self._has_matching_edge_in(gs, g, vid, src_set, ep)
                ]
                if len(new_tgt) < len(candidates[tgt_var]):
                    candidates[tgt_var] = new_tgt
                    changed = True

        return candidates

    @staticmethod
    def _has_matching_edge_out(
        gs: GraphStore,
        g: str,
        src_vid: int,
        tgt_set: set[int],
        ep: EdgePattern,
    ) -> bool:
        for eid in gs.out_edge_ids(src_vid, graph=g):
            edge = gs.get_edge(eid)
            if edge is None:
                continue
            if edge.target_id not in tgt_set:
                continue
            if ep.label is not None and edge.label != ep.label:
                continue
            if all(c(edge) for c in ep.constraints):
                return True
        return False

    @staticmethod
    def _has_matching_edge_in(
        gs: GraphStore,
        g: str,
        tgt_vid: int,
        src_set: set[int],
        ep: EdgePattern,
    ) -> bool:
        for eid in gs.in_edge_ids(tgt_vid, graph=g):
            edge = gs.get_edge(eid)
            if edge is None:
                continue
            if edge.source_id not in src_set:
                continue
            if ep.label is not None and edge.label != ep.label:
                continue
            if all(c(edge) for c in ep.constraints):
                return True
        return False

    def _backtrack(
        self,
        gs: GraphStore,
        g: str,
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

        var = min(unassigned, key=lambda v: len(var_candidates[v]))

        for vid in var_candidates[var]:
            if vid in assigned_values:
                continue

            assignment[var] = vid
            assigned_values.add(vid)
            unassigned.discard(var)

            if self._validate_edges_for(gs, g, var, var_edges, assignment):
                self._backtrack(
                    gs,
                    g,
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
        gs: GraphStore,
        g: str,
        var: str,
        var_edges: dict[str, list[EdgePattern]],
        assignment: dict[str, int],
    ) -> bool:
        for ep in var_edges.get(var, []):
            src_id = assignment.get(ep.source_var)
            tgt_id = assignment.get(ep.target_var)
            if src_id is None or tgt_id is None:
                continue
            found = False
            for eid in gs.out_edge_ids(src_id, graph=g):
                edge = gs.get_edge(eid)
                if edge is None:
                    continue
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

    @staticmethod
    def _check_negated_edges(
        gs: GraphStore,
        g: str,
        negated_edges: list[EdgePattern],
        assignment: dict[str, int],
    ) -> bool:
        """Return True if the assignment satisfies all negated edge constraints.

        A negated edge means "there must NOT exist such an edge".
        """
        for ep in negated_edges:
            src_id = assignment.get(ep.source_var)
            tgt_id = assignment.get(ep.target_var)
            if src_id is None or tgt_id is None:
                continue
            for eid in gs.out_edge_ids(src_id, graph=g):
                edge = gs.get_edge(eid)
                if edge is None:
                    continue
                if edge.target_id != tgt_id:
                    continue
                if ep.label is not None and edge.label != ep.label:
                    continue
                if all(c(edge) for c in ep.constraints):
                    # Found a matching edge for a negated pattern -- invalid
                    return False
        return True

    def _collect_match_edges(
        self, gs: GraphStore, g: str, assignment: dict[str, int]
    ) -> frozenset[int]:
        edge_ids: set[int] = set()
        for ep in self.pattern.edge_patterns:
            if ep.negated:
                continue
            src_id = assignment[ep.source_var]
            tgt_id = assignment[ep.target_var]
            for eid in gs.out_edge_ids(src_id, graph=g):
                edge = gs.get_edge(eid)
                if (
                    edge is not None
                    and edge.target_id == tgt_id
                    and (ep.label is None or edge.label == ep.label)
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

    if isinstance(expr, BoundedLabel):
        start = _new_state()
        current_end = start

        for _ in range(expr.min_hops):
            inner_nfa = _build_nfa(expr.inner)
            current_end.transitions.append((None, inner_nfa.start))
            current_end = inner_nfa.accept

        accept = _new_state()

        if expr.min_hops == expr.max_hops:
            current_end.transitions.append((None, accept))
        else:
            current_end.transitions.append((None, accept))
            for _ in range(expr.max_hops - expr.min_hops):
                inner_nfa = _build_nfa(expr.inner)
                current_end.transitions.append((None, inner_nfa.start))
                inner_nfa.accept.transitions.append((None, accept))
                current_end = inner_nfa.accept

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
        *,
        graph: str,
        start_vertex: int | None = None,
        score: float = DEFAULT_GRAPH_SCORE,
    ) -> None:
        self.path_expr = path_expr
        self.start_vertex = start_vertex
        self.graph_name = graph
        self.score = score

    def execute(self, ctx: object) -> GraphPostingList:
        indexed_result = self._try_index_lookup(ctx)
        if indexed_result is not None:
            return indexed_result

        simplify_expr, subset_construction = _get_rpq_optimizer()

        gs: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        g = self.graph_name
        _reset_state_counter()

        # Step 1: Simplify expression
        simplified = simplify_expr(self.path_expr)
        nfa = _build_nfa(simplified)

        # Cache partition and edges for tight-loop access
        part = gs.partition(g)
        edges_dict = gs._edges

        if self.start_vertex is not None:
            start_vertices = [self.start_vertex]
        else:
            start_vertices = sorted(part.vertex_ids)

        result_pairs: set[tuple[int, int]] = set()

        all_nfa_states = self._collect_nfa_states(nfa)

        # Step 2: Try DFA conversion for small NFAs (<= 32 states)
        if len(all_nfa_states) <= 32:
            dfa_transitions, dfa_start, dfa_accepts = subset_construction(nfa)
            result_pairs = self._simulate_dfa(
                part,
                edges_dict,
                start_vertices,
                dfa_transitions,
                dfa_start,
                dfa_accepts,
            )
        else:
            # Fall back to NFA simulation for large NFAs
            state_map = {s.state_id: s for s in all_nfa_states}

            initial_nfa_states = _epsilon_closure({nfa.start})
            initial_ids = frozenset(s.state_id for s in initial_nfa_states)
            accept_id = nfa.accept.state_id

            for sv in start_vertices:
                queue: deque[tuple[int, frozenset[int]]] = deque()
                queue.append((sv, initial_ids))
                visited_configs: set[tuple[int, frozenset[int]]] = {(sv, initial_ids)}

                if accept_id in initial_ids:
                    result_pairs.add((sv, sv))

                while queue:
                    gv, nfa_state_ids = queue.popleft()
                    for eid in part.adj_out.get(gv, _EMPTY):
                        edge = edges_dict[eid]
                        edge_label = edge.label
                        neighbor = edge.target_id

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

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        seen_ids: set[int] = set()
        for start_v, end_v in result_pairs:
            doc_id = end_v
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                entries.append(PostingEntry(doc_id, Payload(score=self.score)))
                graph_payloads[doc_id] = GraphPayload(
                    subgraph_vertices=frozenset({start_v, end_v}),
                    subgraph_edges=frozenset(),
                    graph_name=g,
                )

        entries.sort(key=lambda e: e.doc_id)
        return GraphPostingList(entries, graph_payloads)

    @staticmethod
    def _simulate_dfa(
        part: object,
        edges_dict: dict[int, Any],
        start_vertices: list[int],
        dfa_transitions: dict[frozenset[int], dict[str, frozenset[int]]],
        dfa_start: frozenset[int],
        dfa_accepts: set[frozenset[int]],
    ) -> set[tuple[int, int]]:
        """DFA-based simulation -- deterministic, no epsilon transitions."""
        adj_out = part.adj_out  # type: ignore[attr-defined]
        result_pairs: set[tuple[int, int]] = set()

        for sv in start_vertices:
            queue: deque[tuple[int, frozenset[int]]] = deque()
            queue.append((sv, dfa_start))
            visited: set[tuple[int, frozenset[int]]] = {(sv, dfa_start)}

            if dfa_start in dfa_accepts:
                result_pairs.add((sv, sv))

            while queue:
                gv, dfa_state = queue.popleft()
                trans = dfa_transitions.get(dfa_state, {})

                for eid in adj_out.get(gv, _EMPTY):
                    edge = edges_dict[eid]
                    next_state = trans.get(edge.label)
                    if next_state is None:
                        continue

                    neighbor = edge.target_id
                    if next_state in dfa_accepts:
                        result_pairs.add((sv, neighbor))

                    config = (neighbor, next_state)
                    if config not in visited:
                        visited.add(config)
                        queue.append(config)

        return result_pairs

    def _collect_nfa_states(self, nfa: _NFA) -> set[_NFAState]:
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

    def _try_index_lookup(self, ctx: object) -> GraphPostingList | None:
        labels = self._extract_label_sequence(self.path_expr)
        if labels is None:
            return None

        path_index = getattr(ctx, "path_index", None)
        if path_index is None:
            return None

        pairs = path_index.lookup(labels)
        if pairs is None:
            return None

        if self.start_vertex is not None:
            pairs = {(s, e) for s, e in pairs if s == self.start_vertex}

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        seen_ids: set[int] = set()
        for start_v, end_v in pairs:
            doc_id = end_v
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                entries.append(PostingEntry(doc_id, Payload(score=self.score)))
                graph_payloads[doc_id] = GraphPayload(
                    subgraph_vertices=frozenset({start_v, end_v}),
                    subgraph_edges=frozenset(),
                    graph_name=self.graph_name,
                )
        entries.sort(key=lambda e: e.doc_id)
        return GraphPostingList(entries, graph_payloads)

    @staticmethod
    def _extract_label_sequence(expr: RegularPathExpr) -> list[str] | None:
        if isinstance(expr, Label):
            return [expr.name]
        if isinstance(expr, Concat):
            left = RegularPathQueryOperator._extract_label_sequence(expr.left)
            right = RegularPathQueryOperator._extract_label_sequence(expr.right)
            if left is None or right is None:
                return None
            return left + right
        return None


class WeightedPathQueryOperator:
    """RPQ with cumulative edge weight tracking and predicate filtering."""

    def __init__(
        self,
        path_expr: RegularPathExpr,
        *,
        graph: str,
        weight_property: str = "weight",
        aggregate_fn: str = "sum",
        predicate: object | None = None,
        start_vertex: int | None = None,
        score: float = DEFAULT_GRAPH_SCORE,
    ) -> None:
        self.path_expr = path_expr
        self.weight_property = weight_property
        self.aggregate_fn = aggregate_fn
        self.predicate = predicate
        self.start_vertex = start_vertex
        self.graph_name = graph
        self.score = score

    def execute(self, ctx: object) -> GraphPostingList:
        gs: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        g = self.graph_name
        _reset_state_counter()
        nfa = _build_nfa(self.path_expr)

        # Cache partition and edges for tight-loop access
        part = gs.partition(g)
        edges_dict = gs._edges

        if self.start_vertex is not None:
            start_vertices = [self.start_vertex]
        else:
            start_vertices = sorted(part.vertex_ids)

        all_nfa_states = self._collect_nfa_states(nfa)
        state_map = {s.state_id: s for s in all_nfa_states}

        initial_nfa_states = _epsilon_closure({nfa.start})
        initial_ids = frozenset(s.state_id for s in initial_nfa_states)
        accept_id = nfa.accept.state_id

        result_entries: dict[int, float] = {}

        for sv in start_vertices:
            queue: deque[tuple[int, frozenset[int], float]] = deque()
            init_weight = 0.0
            queue.append((sv, initial_ids, init_weight))
            visited: set[tuple[int, frozenset[int]]] = {(sv, initial_ids)}

            if accept_id in initial_ids and self._check_predicate(init_weight):
                self._update_result(result_entries, sv, init_weight)

            while queue:
                gv, nfa_state_ids, cum_weight = queue.popleft()

                for eid in part.adj_out.get(gv, _EMPTY):
                    edge = edges_dict[eid]
                    edge_label = edge.label
                    neighbor = edge.target_id

                    edge_weight = float(edge.properties.get(self.weight_property, 0.0))
                    new_weight = self._aggregate(cum_weight, edge_weight)

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

                    if accept_id in next_ids and self._check_predicate(new_weight):
                        self._update_result(result_entries, neighbor, new_weight)

                    config = (neighbor, next_ids)
                    if config not in visited:
                        visited.add(config)
                        queue.append((neighbor, next_ids, new_weight))

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        for vid in sorted(result_entries.keys()):
            weight = result_entries[vid]
            entries.append(
                PostingEntry(
                    vid, Payload(score=self.score, fields={"path_weight": weight})
                )
            )
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=frozenset({vid}),
                subgraph_edges=frozenset(),
                graph_name=g,
            )

        return GraphPostingList(entries, graph_payloads)

    def _aggregate(self, current: float, new_value: float) -> float:
        if self.aggregate_fn == "sum":
            return current + new_value
        if self.aggregate_fn == "max":
            return max(current, new_value)
        if self.aggregate_fn == "min":
            return min(current, new_value) if current != 0.0 else new_value
        return current + new_value

    def _check_predicate(self, weight: float) -> bool:
        if self.predicate is None:
            return True
        if callable(self.predicate):
            return bool(self.predicate(weight))
        return True

    def _update_result(self, result: dict[int, float], vid: int, weight: float) -> None:
        if vid not in result:
            result[vid] = weight
        elif self.aggregate_fn == "max":
            result[vid] = max(result[vid], weight)
        elif self.aggregate_fn == "min":
            result[vid] = min(result[vid], weight)

    @staticmethod
    def _collect_nfa_states(nfa: _NFA) -> set[_NFAState]:
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
    """Definition 2.2.3: Aggregate vertex properties over traversal results."""

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
        gs: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        source_gpl = self.source.execute(ctx)

        vertex_ids: set[int] = set()
        for entry in source_gpl:
            gp = source_gpl.get_graph_payload(entry.doc_id)
            if gp is not None:
                vertex_ids.update(gp.subgraph_vertices)

        values: list[Any] = []
        for vid in sorted(vertex_ids):
            vertex = gs.get_vertex(vid)
            if vertex is not None:
                val = vertex.properties.get(self.property_name)
                if val is not None:
                    values.append(val)

        result = self._aggregate(values)

        entries = [
            PostingEntry(
                0,
                Payload(
                    score=float(result) if isinstance(result, int | float) else 0.0,
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
    """Execute an openCypher query against a named graph."""

    def __init__(
        self,
        graph: GraphStore,
        query: CypherQuery,
        *,
        graph_name: str,
        params: dict[str, Any] | None = None,
        col_names: list[str] | None = None,
    ) -> None:
        self.graph = graph
        self.query = query
        self.graph_name = graph_name
        self.params = params or {}
        self.col_names = col_names

    def execute(self, ctx: object) -> GraphPostingList:
        from uqa.graph.cypher.compiler import CypherCompiler

        path_index = getattr(ctx, "path_index", None)
        compiler = CypherCompiler(
            self.graph,
            graph_name=self.graph_name,
            params=self.params,
            path_index=path_index,
        )
        gpl = compiler.execute_posting_list(self.query)

        if self.col_names is None:
            return gpl

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
