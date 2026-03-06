#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from uqa.core.types import Payload, PostingEntry
from uqa.graph.pattern import (
    Alternation,
    Concat,
    GraphPattern,
    KleeneStar,
    Label,
    RegularPathExpr,
)
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
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
                if self.label is not None:
                    edge_ids = [
                        eid
                        for eid in (graph._adj_out.get(v, []))
                        if graph._edges[eid].label == self.label
                    ]
                else:
                    edge_ids = list(graph._adj_out.get(v, []))
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
        for vid in sorted(visited):
            entry = PostingEntry(vid, Payload(score=0.9))
            entries.append(entry)
            graph_payloads[vid] = GraphPayload(
                subgraph_vertices=frozenset(visited),
                subgraph_edges=frozenset(all_edges),
            )

        gpl = GraphPostingList(entries, graph_payloads)
        return gpl


class PatternMatchOperator:
    """Definition 2.2.2 / 5.2.2: GMatch_P

    Subgraph isomorphism pattern matching via backtracking.
    """

    def __init__(self, pattern: GraphPattern) -> None:
        self.pattern = pattern

    def execute(self, ctx: object) -> GraphPostingList:
        graph: GraphStore = ctx.graph_store  # type: ignore[attr-defined]
        variables = [vp.variable for vp in self.pattern.vertex_patterns]
        all_vertex_ids = list(graph._vertices.keys())

        matches: list[dict[str, int]] = []
        self._backtrack(graph, variables, 0, {}, all_vertex_ids, matches)

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

    def _backtrack(
        self,
        graph: GraphStore,
        variables: list[str],
        idx: int,
        assignment: dict[str, int],
        all_vertex_ids: list[int],
        matches: list[dict[str, int]],
    ) -> None:
        if idx == len(variables):
            # Check all edge constraints
            if self._check_edges(graph, assignment):
                matches.append(dict(assignment))
            return

        var = variables[idx]
        vp = self.pattern.vertex_patterns[idx]

        for vid in all_vertex_ids:
            # Ensure injective mapping (no two variables map to same vertex)
            if vid in assignment.values():
                continue
            vertex = graph.get_vertex(vid)
            if vertex is None:
                continue
            # Check vertex constraints
            if all(c(vertex) for c in vp.constraints):
                assignment[var] = vid
                self._backtrack(
                    graph, variables, idx + 1, assignment, all_vertex_ids, matches
                )
                del assignment[var]

    def _check_edges(self, graph: GraphStore, assignment: dict[str, int]) -> bool:
        for ep in self.pattern.edge_patterns:
            src_id = assignment.get(ep.source_var)
            tgt_id = assignment.get(ep.target_var)
            if src_id is None or tgt_id is None:
                return False
            # Check if there's an edge from src to tgt with matching label
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
                if edge.target_id == tgt_id:
                    if ep.label is None or edge.label == ep.label:
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
        result_pairs: list[tuple[int, int]] = []  # (start, end) pairs

        for sv in start_vertices:
            initial_nfa_states = _epsilon_closure({nfa.start})
            # Queue: (graph_vertex, nfa_states_set_as_frozenset)
            queue: deque[tuple[int, frozenset[int]]] = deque()
            initial_ids = frozenset(s.state_id for s in initial_nfa_states)
            queue.append((sv, initial_ids))
            visited_configs: set[tuple[int, frozenset[int]]] = {(sv, initial_ids)}

            # Build state_id -> _NFAState lookup
            all_nfa_states = self._collect_nfa_states(nfa)
            state_map = {s.state_id: s for s in all_nfa_states}

            # Check if start is already accepting
            if nfa.accept.state_id in initial_ids:
                result_pairs.append((sv, sv))

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

                    if nfa.accept.state_id in next_ids:
                        if (sv, neighbor) not in result_pairs:
                            result_pairs.append((sv, neighbor))

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
