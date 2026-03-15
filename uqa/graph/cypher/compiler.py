#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Cypher-to-PostingList compiler.

Translates a :class:`CypherQuery` AST into posting list operations on
:class:`~uqa.graph.store.GraphStore`.  This preserves UQA's core thesis
that ALL paradigms -- relational, text, vector, AND graph -- flow through
the posting list abstraction.

Execution model:
    Each Cypher clause transforms a **binding posting list** -- a
    ``GraphPostingList`` where every ``PostingEntry`` represents one
    binding row.  ``payload.fields`` carries the variable-to-value
    assignments (vertex IDs, edge IDs, scalars).

    MATCH  -> pattern matching produces a new GraphPostingList
    WHERE  -> filters entries whose fields fail the predicate
    CREATE -> mutates the GraphStore, extends fields with new bindings
    SET    -> mutates vertex/edge properties in-place
    DELETE -> removes vertices/edges from the GraphStore
    RETURN -> projects fields into result dicts
    WITH   -> projects and reshapes the binding posting list
    UNWIND -> expands list-valued fields into multiple entries
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from uqa.core.types import Edge, Payload, PostingEntry, Vertex
from uqa.graph.cypher.ast import (
    BinaryOp,
    CaseExpr,
    CreateClause,
    CypherExpr,
    CypherQuery,
    DeleteClause,
    FunctionCall,
    InList,
    IsNotNull,
    IsNull,
    ListLiteral,
    Literal,
    MapLiteral,
    MatchClause,
    MergeClause,
    NodePattern,
    OrderByItem,
    Parameter,
    PathPattern,
    PropertyAccess,
    RelPattern,
    ReturnClause,
    SetClause,
    SetItem,
    UnaryOp,
    UnwindClause,
    Variable,
    WithClause,
)
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
    from uqa.graph.index import PathIndex
    from uqa.graph.store import GraphStore

# Type alias: a binding row stored in PostingEntry.payload.fields.
# Keys are Cypher variable names, values are vertex_id (int), edge_id
# (int), or scalar values.
BindingFields = dict[str, Any]


class _VertexRef(int):
    """Marker subclass of int tagging a value as a vertex ID."""

    __slots__ = ()


class _EdgeRef(int):
    """Marker subclass of int tagging a value as an edge ID."""

    __slots__ = ()


# Sentinel for "no binding" (distinct from None which is a valid Cypher NULL)
_UNBOUND = object()


class CypherCompiler:
    """Execute a CypherQuery against a GraphStore, producing posting lists."""

    def __init__(
        self,
        graph: GraphStore,
        params: dict[str, Any] | None = None,
        path_index: PathIndex | None = None,
    ) -> None:
        self._graph = graph
        self._params = params or {}
        self._path_index = path_index
        self._next_doc_id = 1

    # -- Top-level execution -------------------------------------------

    def execute(self, query: CypherQuery) -> list[dict[str, Any]]:
        """Execute a Cypher query and return result rows.

        Internally everything flows through GraphPostingList.
        The final RETURN projects posting list entries into result dicts.
        """
        gpl = self.execute_posting_list(query)

        # Convert the final GraphPostingList to result dicts.
        rows: list[dict[str, Any]] = []
        for entry in gpl:
            row: dict[str, Any] = {}
            for k, v in entry.payload.fields.items():
                row[k] = v
            rows.append(row)
        return rows

    def execute_posting_list(self, query: CypherQuery) -> GraphPostingList:
        """Execute a Cypher query and return the result GraphPostingList.

        This is the operator-tree-compatible entry point: every Cypher
        clause transforms a GraphPostingList, and the final result
        (after RETURN projection) is itself a GraphPostingList with
        projected fields in each entry's payload.
        """
        # Start with a single empty binding (one entry, no fields)
        gpl = self._empty_binding()

        for clause in query.clauses:
            if isinstance(clause, MatchClause):
                gpl = self._exec_match(clause, gpl)
            elif isinstance(clause, CreateClause):
                gpl = self._exec_create(clause, gpl)
            elif isinstance(clause, MergeClause):
                gpl = self._exec_merge(clause, gpl)
            elif isinstance(clause, SetClause):
                gpl = self._exec_set(clause, gpl)
            elif isinstance(clause, DeleteClause):
                gpl = self._exec_delete(clause, gpl)
            elif isinstance(clause, ReturnClause):
                gpl = self._exec_return_posting_list(clause, gpl)
            elif isinstance(clause, WithClause):
                gpl = self._exec_with(clause, gpl)
            elif isinstance(clause, UnwindClause):
                gpl = self._exec_unwind(clause, gpl)

        return gpl

    # -- Binding posting list construction -----------------------------

    def _empty_binding(self) -> GraphPostingList:
        """Create a posting list with one entry and no fields."""
        doc_id = self._alloc_doc_id()
        entry = PostingEntry(doc_id, Payload(score=1.0, fields={}))
        gpl = GraphPostingList([entry])
        gpl.set_graph_payload(doc_id, GraphPayload())
        return gpl

    def _alloc_doc_id(self) -> int:
        did = self._next_doc_id
        self._next_doc_id += 1
        return did

    def _make_binding_entry(
        self, fields: BindingFields, vertices: frozenset[int], edges: frozenset[int]
    ) -> tuple[PostingEntry, int]:
        """Create a posting entry representing one binding row."""
        doc_id = self._alloc_doc_id()
        entry = PostingEntry(doc_id, Payload(score=1.0, fields=dict(fields)))
        return entry, doc_id

    # -- MATCH ---------------------------------------------------------

    def _exec_match(
        self, clause: MatchClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        """MATCH produces a cross-product of existing bindings with pattern matches."""
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}

        for binding_entry in bindings:
            existing_fields = dict(binding_entry.payload.fields)
            matched = self._match_patterns(clause.patterns, existing_fields)

            # Apply WHERE filter
            if clause.where is not None:
                matched = [m for m in matched if self._eval(clause.where, m)]

            if clause.optional and not matched:
                # OPTIONAL MATCH: keep existing binding with NULLs
                null_fields = dict(existing_fields)
                for pat in clause.patterns:
                    for elem in pat.elements:
                        if isinstance(elem, NodePattern) and elem.variable:
                            null_fields.setdefault(elem.variable, None)
                        elif isinstance(elem, RelPattern) and elem.variable:
                            null_fields.setdefault(elem.variable, None)
                entry, doc_id = self._make_binding_entry(
                    null_fields, frozenset(), frozenset()
                )
                entries.append(entry)
                payloads[doc_id] = GraphPayload()
            else:
                for m_fields in matched:
                    vtx_ids = frozenset(
                        v
                        for v in m_fields.values()
                        if isinstance(v, int) and self._graph.get_vertex(v) is not None
                    )
                    edge_ids = frozenset(
                        v
                        for v in m_fields.values()
                        if isinstance(v, int) and self._graph.get_edge(v) is not None
                    )
                    entry, doc_id = self._make_binding_entry(
                        m_fields, vtx_ids, edge_ids
                    )
                    entries.append(entry)
                    payloads[doc_id] = GraphPayload(
                        subgraph_vertices=vtx_ids,
                        subgraph_edges=edge_ids,
                    )

        return GraphPostingList(entries, payloads)

    def _match_patterns(
        self,
        patterns: tuple[PathPattern, ...],
        initial_fields: BindingFields,
    ) -> list[BindingFields]:
        """Match all patterns, returning combined binding field dicts."""
        results = [dict(initial_fields)]
        for pattern in patterns:
            next_results: list[BindingFields] = []
            for fields in results:
                next_results.extend(self._match_path(pattern, fields))
            results = next_results
        return results

    def _try_path_index_match(
        self, pattern: PathPattern, fields: BindingFields
    ) -> list[BindingFields] | None:
        """Try to answer a MATCH from the PathIndex.

        Only works for simple patterns: alternating (node)-[rel]->(node)
        where no relationship has properties, multiple types, or
        variable-length hops.  Returns None to fall back to BFS.
        """
        if self._path_index is None:
            return None

        elements = pattern.elements
        if len(elements) < 3:
            return None

        # Extract label sequence from alternating NodePattern/RelPattern
        labels: list[str] = []
        for i, elem in enumerate(elements):
            if i % 2 == 1:
                # Relationship pattern
                if not isinstance(elem, RelPattern):
                    return None
                if elem.properties:
                    return None
                if len(elem.types) != 1:
                    return None
                if elem.min_hops is not None or elem.max_hops is not None:
                    return None
                labels.append(elem.types[0])
            else:
                if not isinstance(elem, NodePattern):
                    return None

        if not labels:
            return None

        pairs = self._path_index.lookup(labels)
        if pairs is None:
            return None

        # Get the first and last node patterns for variable binding
        first_node = elements[0]
        last_node = elements[-1]
        assert isinstance(first_node, NodePattern)
        assert isinstance(last_node, NodePattern)

        results: list[BindingFields] = []
        for start_vid, end_vid in pairs:
            # Filter by already-bound variables
            if first_node.variable and first_node.variable in fields:
                bound_val = fields[first_node.variable]
                if isinstance(bound_val, int) and bound_val != start_vid:
                    continue

            if last_node.variable and last_node.variable in fields:
                bound_val = fields[last_node.variable]
                if isinstance(bound_val, int) and bound_val != end_vid:
                    continue

            # Check vertex label constraints
            start_vtx = self._graph.get_vertex(start_vid)
            end_vtx = self._graph.get_vertex(end_vid)
            if start_vtx is None or end_vtx is None:
                continue

            if first_node.labels and start_vtx.label not in first_node.labels:
                continue
            if last_node.labels and end_vtx.label not in last_node.labels:
                continue

            # Check property constraints on endpoint nodes
            if first_node.properties and not self._vertex_matches(
                start_vtx, first_node, fields
            ):
                continue
            if last_node.properties and not self._vertex_matches(
                end_vtx, last_node, fields
            ):
                continue

            # Check intermediate node constraints -- if any intermediate
            # node has label or property constraints, fall back to BFS
            has_intermediate_constraints = False
            for i in range(2, len(elements) - 1, 2):
                mid_node = elements[i]
                if isinstance(mid_node, NodePattern):
                    if mid_node.labels or mid_node.properties:
                        has_intermediate_constraints = True
                        break
                    if mid_node.variable and not mid_node.variable.startswith("_anon_"):
                        # Named intermediate node -- need BFS to bind it
                        has_intermediate_constraints = True
                        break
            if has_intermediate_constraints:
                return None  # Fall back for entire pattern

            new_fields = dict(fields)
            if first_node.variable:
                new_fields[first_node.variable] = _VertexRef(start_vid)
            if last_node.variable:
                new_fields[last_node.variable] = _VertexRef(end_vid)
            results.append(new_fields)

        return results

    def _match_path(
        self, pattern: PathPattern, fields: BindingFields
    ) -> list[BindingFields]:
        """Match a single path pattern against the graph."""
        elements = pattern.elements
        if not elements:
            return [dict(fields)]

        # Try path index first for simple patterns
        indexed = self._try_path_index_match(pattern, fields)
        if indexed is not None:
            return indexed

        # Assign synthetic variable names to anonymous nodes/rels so
        # that _expand_rel can track the "current vertex" through fields.
        anon_elements = self._assign_anon_vars(elements)

        first = anon_elements[0]
        assert isinstance(first, NodePattern)

        candidates = self._node_candidates(first, fields)
        current: list[BindingFields] = []
        for vtx in candidates:
            new_fields = dict(fields)
            assert first.variable is not None
            if first.variable in fields and fields[first.variable] != vtx.vertex_id:
                continue
            new_fields[first.variable] = _VertexRef(vtx.vertex_id)
            current.append(new_fields)

        # Process (rel, node) pairs
        idx = 1
        while idx < len(anon_elements):
            rel_pat = anon_elements[idx]
            node_pat = anon_elements[idx + 1]
            assert isinstance(rel_pat, RelPattern)
            assert isinstance(node_pat, NodePattern)

            next_current: list[BindingFields] = []
            for f in current:
                next_current.extend(
                    self._expand_rel(f, rel_pat, node_pat, anon_elements, idx)
                )
            current = next_current
            idx += 2

        # Strip synthetic anonymous variables from results
        anon_vars = {
            e.variable
            for e in anon_elements
            if isinstance(e, NodePattern | RelPattern)
            and e.variable
            and e.variable.startswith("_anon_")
        }
        if anon_vars:
            current = [
                {k: v for k, v in f.items() if k not in anon_vars} for f in current
            ]

        return current

    def _assign_anon_vars(
        self, elements: tuple[NodePattern | RelPattern, ...]
    ) -> tuple[NodePattern | RelPattern, ...]:
        """Assign synthetic variable names to anonymous pattern elements."""
        result: list[NodePattern | RelPattern] = []
        for elem in elements:
            if isinstance(elem, NodePattern) and elem.variable is None:
                anon_var = f"_anon_{self._alloc_doc_id()}"
                result.append(
                    NodePattern(
                        variable=anon_var,
                        labels=elem.labels,
                        properties=elem.properties,
                    )
                )
            elif isinstance(elem, RelPattern) and elem.variable is None:
                anon_var = f"_anon_{self._alloc_doc_id()}"
                result.append(
                    RelPattern(
                        variable=anon_var,
                        types=elem.types,
                        properties=elem.properties,
                        direction=elem.direction,
                        min_hops=elem.min_hops,
                        max_hops=elem.max_hops,
                    )
                )
            else:
                result.append(elem)
        return tuple(result)

    def _node_candidates(self, pat: NodePattern, fields: BindingFields) -> list[Vertex]:
        """Return candidate vertices matching a node pattern."""
        if pat.variable and pat.variable in fields:
            val = fields[pat.variable]
            if val is None:
                return []
            vtx = self._graph.get_vertex(val)
            if vtx is not None and self._vertex_matches(vtx, pat, fields):
                return [vtx]
            return []

        if pat.labels:
            candidates: list[Vertex] = []
            seen: set[int] = set()
            for label in pat.labels:
                for v in self._graph.vertices_by_label(label):
                    if v.vertex_id not in seen:
                        seen.add(v.vertex_id)
                        candidates.append(v)
        else:
            candidates = list(self._graph._vertices.values())

        return [v for v in candidates if self._vertex_matches(v, pat, fields)]

    def _vertex_matches(
        self, vertex: Vertex, pat: NodePattern, fields: BindingFields | None = None
    ) -> bool:
        if pat.labels and vertex.label not in pat.labels:
            return False
        if pat.properties:
            ctx = fields if fields is not None else {}
            for key, val_expr in pat.properties.items():
                expected = self._eval(val_expr, ctx)
                if vertex.properties.get(key) != expected:
                    return False
        return True

    def _expand_rel(
        self,
        fields: BindingFields,
        rel_pat: RelPattern,
        next_node: NodePattern,
        elements: tuple,
        idx: int,
    ) -> list[BindingFields]:
        """Expand one relationship step from the previous node."""
        # Find the previous node's vertex ID from the binding
        prev_node = elements[idx - 1]
        assert isinstance(prev_node, NodePattern)
        prev_vid = fields.get(prev_node.variable) if prev_node.variable else None
        if prev_vid is None:
            return []

        if rel_pat.min_hops is not None or rel_pat.max_hops is not None:
            return self._expand_var_length(fields, prev_vid, rel_pat, next_node)

        return self._expand_single_hop(fields, prev_vid, rel_pat, next_node)

    def _expand_single_hop(
        self,
        fields: BindingFields,
        src_vid: int,
        rel_pat: RelPattern,
        next_node: NodePattern,
    ) -> list[BindingFields]:
        results: list[BindingFields] = []

        for edge, neighbor_id in self._get_edges(src_vid, rel_pat):
            neighbor = self._graph.get_vertex(neighbor_id)
            if neighbor is None:
                continue
            if not self._vertex_matches(neighbor, next_node, fields):
                continue
            if not self._edge_matches(edge, rel_pat, fields):
                continue

            # Check consistency with already-bound variables
            new_fields = dict(fields)
            if rel_pat.variable:
                if (
                    rel_pat.variable in fields
                    and fields[rel_pat.variable] != edge.edge_id
                ):
                    continue
                new_fields[rel_pat.variable] = _EdgeRef(edge.edge_id)
            if next_node.variable:
                if (
                    next_node.variable in fields
                    and fields[next_node.variable] != neighbor.vertex_id
                ):
                    continue
                new_fields[next_node.variable] = _VertexRef(neighbor.vertex_id)
            results.append(new_fields)

        return results

    def _expand_var_length(
        self,
        fields: BindingFields,
        src_vid: int,
        rel_pat: RelPattern,
        next_node: NodePattern,
    ) -> list[BindingFields]:
        min_hops = rel_pat.min_hops if rel_pat.min_hops is not None else 1
        max_hops = rel_pat.max_hops

        results: list[BindingFields] = []
        # BFS with deque for O(1) popleft; tuple for immutable path
        frontier: deque[tuple[int, int, tuple[int, ...]]] = deque([(src_vid, 0, ())])

        while frontier:
            vid, depth, path_eids = frontier.popleft()

            if depth >= min_hops:
                vtx = self._graph.get_vertex(vid)
                if vtx is not None and self._vertex_matches(vtx, next_node, fields):
                    new_fields = dict(fields)
                    if rel_pat.variable:
                        new_fields[rel_pat.variable] = list(path_eids)
                    if next_node.variable:
                        if (
                            next_node.variable in fields
                            and fields[next_node.variable] != vid
                        ):
                            continue
                        new_fields[next_node.variable] = vid
                    results.append(new_fields)

            if max_hops is not None and depth >= max_hops:
                continue

            for edge, neighbor_id in self._get_edges(vid, rel_pat):
                if edge.edge_id in path_eids:
                    continue
                if not self._edge_matches(edge, rel_pat, fields):
                    continue
                frontier.append((neighbor_id, depth + 1, (*path_eids, edge.edge_id)))

        return results

    def _get_edges(self, vertex_id: int, rel_pat: RelPattern) -> list[tuple[Edge, int]]:
        results: list[tuple[Edge, int]] = []
        direction = rel_pat.direction

        if direction in ("right", "both"):
            for eid in self._graph._adj_out.get(vertex_id, []):
                edge = self._graph._edges[eid]
                results.append((edge, edge.target_id))
        if direction in ("left", "both"):
            for eid in self._graph._adj_in.get(vertex_id, []):
                edge = self._graph._edges[eid]
                results.append((edge, edge.source_id))

        if rel_pat.types:
            results = [(e, n) for e, n in results if e.label in rel_pat.types]
        return results

    def _edge_matches(
        self, edge: Edge, rel_pat: RelPattern, fields: BindingFields | None = None
    ) -> bool:
        if rel_pat.properties:
            ctx = fields if fields is not None else {}
            for key, val_expr in rel_pat.properties.items():
                expected = self._eval(val_expr, ctx)
                if edge.properties.get(key) != expected:
                    return False
        return True

    # -- CREATE --------------------------------------------------------

    def _exec_create(
        self, clause: CreateClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}

        for binding_entry in bindings:
            fields = dict(binding_entry.payload.fields)
            created_vids: set[int] = set()
            created_eids: set[int] = set()

            for pattern in clause.patterns:
                self._create_path(pattern, fields, created_vids, created_eids)

            entry, doc_id = self._make_binding_entry(
                fields,
                frozenset(created_vids),
                frozenset(created_eids),
            )
            entries.append(entry)
            payloads[doc_id] = GraphPayload(
                subgraph_vertices=frozenset(created_vids),
                subgraph_edges=frozenset(created_eids),
            )

        return GraphPostingList(entries, payloads)

    def _create_path(
        self,
        pattern: PathPattern,
        fields: BindingFields,
        created_vids: set[int],
        created_eids: set[int],
    ) -> None:
        elements = pattern.elements
        for i, elem in enumerate(elements):
            if isinstance(elem, NodePattern):
                if elem.variable and elem.variable in fields:
                    continue
                vtx = self._create_vertex(elem, fields)
                created_vids.add(vtx.vertex_id)
                if elem.variable:
                    fields[elem.variable] = _VertexRef(vtx.vertex_id)

            elif isinstance(elem, RelPattern):
                next_node = elements[i + 1]
                assert isinstance(next_node, NodePattern)
                # Create target if not yet bound
                if next_node.variable and next_node.variable not in fields:
                    vtx = self._create_vertex(next_node, fields)
                    created_vids.add(vtx.vertex_id)
                    if next_node.variable:
                        fields[next_node.variable] = _VertexRef(vtx.vertex_id)

                prev_node = elements[i - 1]
                assert isinstance(prev_node, NodePattern)
                src_vid = fields.get(prev_node.variable) if prev_node.variable else None
                tgt_vid = fields.get(next_node.variable) if next_node.variable else None
                if src_vid is None or tgt_vid is None:
                    continue

                edge = self._create_edge(elem, src_vid, tgt_vid, fields)
                created_eids.add(edge.edge_id)
                if elem.variable:
                    fields[elem.variable] = _EdgeRef(edge.edge_id)

    def _create_vertex(self, pat: NodePattern, fields: BindingFields) -> Vertex:
        vid = self._graph.next_vertex_id()
        label = pat.labels[0] if pat.labels else ""
        props: dict[str, Any] = {}
        if pat.properties:
            for k, v_expr in pat.properties.items():
                props[k] = self._eval(v_expr, fields)
        vtx = Vertex(vertex_id=vid, label=label, properties=props)
        self._graph.add_vertex(vtx)
        return vtx

    def _create_edge(
        self,
        rel_pat: RelPattern,
        src_vid: int,
        tgt_vid: int,
        fields: BindingFields,
    ) -> Edge:
        eid = self._graph.next_edge_id()
        label = rel_pat.types[0] if rel_pat.types else ""
        props: dict[str, Any] = {}
        if rel_pat.properties:
            for k, v_expr in rel_pat.properties.items():
                props[k] = self._eval(v_expr, fields)

        if rel_pat.direction == "left":
            src_vid, tgt_vid = tgt_vid, src_vid

        edge = Edge(
            edge_id=eid,
            source_id=src_vid,
            target_id=tgt_vid,
            label=label,
            properties=props,
        )
        self._graph.add_edge(edge)
        return edge

    # -- MERGE ---------------------------------------------------------

    def _exec_merge(
        self, clause: MergeClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}

        for binding_entry in bindings:
            fields = dict(binding_entry.payload.fields)
            matched = self._match_path(clause.pattern, fields)

            if matched:
                for m_fields in matched:
                    if clause.on_match_set:
                        for item in clause.on_match_set:
                            self._apply_set_item(item, m_fields)
                    entry, doc_id = self._make_binding_entry(
                        m_fields, frozenset(), frozenset()
                    )
                    entries.append(entry)
                    payloads[doc_id] = GraphPayload()
            else:
                created_vids: set[int] = set()
                created_eids: set[int] = set()
                self._create_path(clause.pattern, fields, created_vids, created_eids)
                if clause.on_create_set:
                    for item in clause.on_create_set:
                        self._apply_set_item(item, fields)
                entry, doc_id = self._make_binding_entry(
                    fields, frozenset(created_vids), frozenset(created_eids)
                )
                entries.append(entry)
                payloads[doc_id] = GraphPayload(
                    subgraph_vertices=frozenset(created_vids),
                    subgraph_edges=frozenset(created_eids),
                )

        return GraphPostingList(entries, payloads)

    # -- SET -----------------------------------------------------------

    def _exec_set(
        self, clause: SetClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}

        for binding_entry in bindings:
            fields = dict(binding_entry.payload.fields)
            for item in clause.items:
                self._apply_set_item(item, fields)
            entry, doc_id = self._make_binding_entry(fields, frozenset(), frozenset())
            entries.append(entry)
            payloads[doc_id] = GraphPayload()

        return GraphPostingList(entries, payloads)

    def _apply_set_item(self, item: SetItem, fields: BindingFields) -> None:
        value = self._eval(item.value, fields)

        if isinstance(item.target, PropertyAccess):
            vid_or_eid = fields.get(item.target.variable)
            if vid_or_eid is None:
                return

            vtx = (
                self._graph.get_vertex(vid_or_eid)
                if not isinstance(vid_or_eid, _EdgeRef)
                else None
            )
            if vtx is not None:
                new_props = dict(vtx.properties)
                if item.operator == "+=" and isinstance(value, dict):
                    new_props.update(value)
                else:
                    _set_nested(new_props, item.target.keys, value)
                new_vtx = Vertex(
                    vertex_id=vtx.vertex_id,
                    label=vtx.label,
                    properties=new_props,
                )
                # Write-through: add_vertex does INSERT OR REPLACE
                self._graph.add_vertex(new_vtx)
                return

            edge = (
                self._graph.get_edge(vid_or_eid)
                if not isinstance(vid_or_eid, _VertexRef)
                else None
            )
            if edge is not None:
                new_props = dict(edge.properties)
                if item.operator == "+=" and isinstance(value, dict):
                    new_props.update(value)
                else:
                    _set_nested(new_props, item.target.keys, value)
                new_edge = Edge(
                    edge_id=edge.edge_id,
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    label=edge.label,
                    properties=new_props,
                )
                self._graph.add_edge(new_edge)

        elif isinstance(item.target, Variable):
            vid = fields.get(item.target.name)
            if vid is None:
                return
            vtx = self._graph.get_vertex(vid) if not isinstance(vid, _EdgeRef) else None
            if vtx is not None and isinstance(value, dict):
                if item.operator == "+=":
                    new_props = dict(vtx.properties)
                    new_props.update(value)
                else:
                    new_props = dict(value)
                new_vtx = Vertex(
                    vertex_id=vtx.vertex_id,
                    label=vtx.label,
                    properties=new_props,
                )
                self._graph.add_vertex(new_vtx)

    # -- DELETE --------------------------------------------------------

    def _exec_delete(
        self, clause: DeleteClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        to_delete_vertices: list[int] = []
        to_delete_edges: list[int] = []

        for binding_entry in bindings:
            fields = binding_entry.payload.fields
            for expr in clause.expressions:
                val = self._eval(expr, fields)
                if val is None:
                    continue
                if isinstance(val, _VertexRef):
                    to_delete_vertices.append(val)
                elif isinstance(val, _EdgeRef):
                    to_delete_edges.append(val)
                elif isinstance(val, int):
                    if self._graph.get_vertex(val) is not None:
                        to_delete_vertices.append(val)
                    elif self._graph.get_edge(val) is not None:
                        to_delete_edges.append(val)

        for eid in to_delete_edges:
            self._graph.remove_edge(eid)

        for vid in to_delete_vertices:
            if not clause.detach:
                has_out = bool(self._graph._adj_out.get(vid, []))
                has_in = bool(self._graph._adj_in.get(vid, []))
                if has_out or has_in:
                    raise ValueError(
                        f"Cannot delete vertex {vid}: has incident edges. "
                        f"Use DETACH DELETE."
                    )
            self._graph.remove_vertex(vid)

        return bindings

    # -- RETURN --------------------------------------------------------

    def _exec_return(
        self, clause: ReturnClause, bindings: GraphPostingList
    ) -> list[dict[str, Any]]:
        """Project the binding posting list into result dicts."""
        rows: list[dict[str, Any]] = []

        for binding_entry in bindings:
            fields = binding_entry.payload.fields
            row: dict[str, Any] = {}
            for item in clause.items:
                if isinstance(item.expr, Variable) and item.expr.name == "*":
                    for k, v in fields.items():
                        row[k] = self._to_agtype(v)
                    continue
                val = self._eval(item.expr, fields)
                key = item.alias or _expr_name(item.expr)
                # Only resolve graph object IDs for raw Variable
                # references (node/edge bindings).  All other
                # expressions (property access, functions, arithmetic)
                # already evaluate to scalar values.
                if isinstance(item.expr, Variable):
                    val = self._to_agtype(val)
                row[key] = val
            rows.append(row)

        if clause.distinct:
            rows = _distinct_rows(rows)

        if clause.order_by:
            rows = self._order_by(clause.order_by, rows, bindings)

        if clause.skip:
            skip_n = self._eval(clause.skip, {})
            rows = rows[skip_n:]

        if clause.limit:
            limit_n = self._eval(clause.limit, {})
            rows = rows[:limit_n]

        return rows

    def _exec_return_posting_list(
        self, clause: ReturnClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        """Project the binding posting list into a result GraphPostingList.

        Same logic as _exec_return but produces a GraphPostingList
        with projected fields instead of plain dicts, keeping results
        within the posting list abstraction.

        ORDER BY expressions are evaluated against the original binding
        fields (before projection), since they may reference variables
        not present in the projected output.
        """
        binding_list = list(bindings)

        # Sort using original binding fields before projection.
        if clause.order_by:
            for item in reversed(clause.order_by):
                binding_list.sort(
                    key=lambda e: _sort_key(self._eval(item.expr, e.payload.fields)),
                    reverse=not item.ascending,
                )

        # Project after sorting.
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}

        for binding_entry in binding_list:
            fields = binding_entry.payload.fields
            projected: BindingFields = {}
            for item in clause.items:
                if isinstance(item.expr, Variable) and item.expr.name == "*":
                    for k, v in fields.items():
                        projected[k] = self._to_agtype(v)
                    continue
                val = self._eval(item.expr, fields)
                key = item.alias or _expr_name(item.expr)
                if isinstance(item.expr, Variable):
                    val = self._to_agtype(val)
                projected[key] = val

            entry, doc_id = self._make_binding_entry(
                projected, frozenset(), frozenset()
            )
            entries.append(entry)
            payloads[doc_id] = GraphPayload()

        gpl = GraphPostingList(entries, payloads)

        if clause.distinct:
            gpl = self._distinct_gpl(gpl)

        if clause.skip:
            skip_n = self._eval(clause.skip, {})
            gpl = self._slice_gpl(gpl, skip_n, None)

        if clause.limit:
            limit_n = self._eval(clause.limit, {})
            gpl = self._slice_gpl(gpl, 0, limit_n)

        return gpl

    # -- WITH ----------------------------------------------------------

    def _exec_with(
        self, clause: WithClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        """Project and reshape the binding posting list."""
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}

        for binding_entry in bindings:
            old_fields = binding_entry.payload.fields
            new_fields: BindingFields = {}
            for item in clause.items:
                if isinstance(item.expr, Variable) and item.expr.name == "*":
                    new_fields.update(old_fields)
                    continue
                val = self._eval(item.expr, old_fields)
                key = item.alias or _expr_name(item.expr)
                new_fields[key] = val

            entry, doc_id = self._make_binding_entry(
                new_fields, frozenset(), frozenset()
            )
            entries.append(entry)
            payloads[doc_id] = GraphPayload()

        gpl = GraphPostingList(entries, payloads)

        if clause.distinct:
            gpl = self._distinct_gpl(gpl)

        if clause.order_by:
            gpl = self._order_by_gpl(clause.order_by, gpl)

        if clause.skip:
            skip_n = self._eval(clause.skip, {})
            gpl = self._slice_gpl(gpl, skip_n, None)

        if clause.limit:
            limit_n = self._eval(clause.limit, {})
            gpl = self._slice_gpl(gpl, 0, limit_n)

        if clause.where:
            entries_out = []
            payloads_out: dict[int, GraphPayload] = {}
            for e in gpl:
                if self._eval(clause.where, e.payload.fields):
                    entries_out.append(e)
                    gp = gpl.get_graph_payload(e.doc_id)
                    if gp is not None:
                        payloads_out[e.doc_id] = gp
            gpl = GraphPostingList(entries_out, payloads_out)

        return gpl

    # -- UNWIND --------------------------------------------------------

    def _exec_unwind(
        self, clause: UnwindClause, bindings: GraphPostingList
    ) -> GraphPostingList:
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}

        for binding_entry in bindings:
            fields = binding_entry.payload.fields
            collection = self._eval(clause.expr, fields)
            if collection is None:
                continue
            for item in collection:
                new_fields = dict(fields)
                new_fields[clause.variable] = item
                entry, doc_id = self._make_binding_entry(
                    new_fields, frozenset(), frozenset()
                )
                entries.append(entry)
                payloads[doc_id] = GraphPayload()

        return GraphPostingList(entries, payloads)

    # -- AGType conversion ---------------------------------------------

    def _to_agtype(self, val: Any) -> Any:
        """Convert internal IDs to AGE-compatible result representation."""
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        if isinstance(val, _VertexRef):
            vtx = self._graph.get_vertex(val)
            if vtx is not None:
                return {
                    "id": vtx.vertex_id,
                    "label": vtx.label,
                    "properties": dict(vtx.properties),
                }
            return int(val)
        if isinstance(val, _EdgeRef):
            edge = self._graph.get_edge(val)
            if edge is not None:
                return {
                    "id": edge.edge_id,
                    "label": edge.label,
                    "start": edge.source_id,
                    "end": edge.target_id,
                    "properties": dict(edge.properties),
                }
            return int(val)
        if isinstance(val, int):
            vtx = self._graph.get_vertex(val)
            if vtx is not None:
                return {
                    "id": vtx.vertex_id,
                    "label": vtx.label,
                    "properties": dict(vtx.properties),
                }
            edge = self._graph.get_edge(val)
            if edge is not None:
                return {
                    "id": edge.edge_id,
                    "label": edge.label,
                    "start": edge.source_id,
                    "end": edge.target_id,
                    "properties": dict(edge.properties),
                }
        if isinstance(val, list):
            return [self._to_agtype(v) for v in val]
        return val

    # -- Posting list utilities ----------------------------------------

    def _distinct_gpl(self, gpl: GraphPostingList) -> GraphPostingList:
        seen: set[tuple] = set()
        entries: list[PostingEntry] = []
        payloads: dict[int, GraphPayload] = {}
        for e in gpl:
            key = tuple(sorted(e.payload.fields.items()))
            if key not in seen:
                seen.add(key)
                entries.append(e)
                gp = gpl.get_graph_payload(e.doc_id)
                if gp is not None:
                    payloads[e.doc_id] = gp
        return GraphPostingList(entries, payloads)

    def _order_by_gpl(
        self, order_items: tuple[OrderByItem, ...], gpl: GraphPostingList
    ) -> GraphPostingList:
        entry_list = list(gpl)
        for item in reversed(order_items):
            entry_list.sort(
                key=lambda e: _sort_key(self._eval(item.expr, e.payload.fields)),
                reverse=not item.ascending,
            )
        payloads = {}
        for e in entry_list:
            gp = gpl.get_graph_payload(e.doc_id)
            if gp is not None:
                payloads[e.doc_id] = gp
        return GraphPostingList(entry_list, payloads)

    def _slice_gpl(
        self, gpl: GraphPostingList, start: int, end: int | None
    ) -> GraphPostingList:
        entry_list = list(gpl)[start:end]
        payloads = {}
        for e in entry_list:
            gp = gpl.get_graph_payload(e.doc_id)
            if gp is not None:
                payloads[e.doc_id] = gp
        return GraphPostingList(entry_list, payloads)

    def _order_by(
        self,
        order_items: tuple[OrderByItem, ...],
        rows: list[dict[str, Any]],
        bindings: GraphPostingList,
    ) -> list[dict[str, Any]]:
        binding_list = list(bindings)
        paired = list(zip(rows, binding_list))
        for item in reversed(order_items):
            paired.sort(
                key=lambda p: _sort_key(self._eval(item.expr, p[1].payload.fields)),
                reverse=not item.ascending,
            )
        return [p[0] for p in paired]

    # -- Expression evaluator ------------------------------------------

    def _eval(self, expr: CypherExpr, fields: BindingFields) -> Any:
        if isinstance(expr, Literal):
            return expr.value

        if isinstance(expr, Variable):
            return fields.get(expr.name)

        if isinstance(expr, Parameter):
            return self._params.get(expr.name)

        if isinstance(expr, PropertyAccess):
            val = fields.get(expr.variable)
            if val is None:
                return None
            # Resolve through graph objects if val is an ID
            if isinstance(val, _VertexRef):
                obj = self._graph.get_vertex(val)
                if obj is not None:
                    val = obj
            elif isinstance(val, _EdgeRef):
                obj = self._graph.get_edge(val)
                if obj is not None:
                    val = obj
            elif isinstance(val, int):
                obj = self._graph.get_vertex(val) or self._graph.get_edge(val)
                if obj is not None:
                    val = obj
            for key in expr.keys:
                if isinstance(val, Vertex):
                    val = val.properties.get(key)
                elif isinstance(val, Edge):
                    val = val.properties.get(key)
                elif isinstance(val, dict):
                    val = val.get(key)
                else:
                    return None
                if val is None:
                    return None
            return val

        if isinstance(expr, BinaryOp):
            return self._eval_binary(expr, fields)

        if isinstance(expr, UnaryOp):
            return self._eval_unary(expr, fields)

        if isinstance(expr, FunctionCall):
            return self._eval_function(expr, fields)

        if isinstance(expr, InList):
            val = self._eval(expr.expr, fields)
            lst = self._eval(expr.list_expr, fields)
            if lst is None:
                return None
            return val in lst

        if isinstance(expr, IsNull):
            return self._eval(expr.expr, fields) is None

        if isinstance(expr, IsNotNull):
            return self._eval(expr.expr, fields) is not None

        if isinstance(expr, ListLiteral):
            return [self._eval(e, fields) for e in expr.elements]

        if isinstance(expr, MapLiteral):
            return {k: self._eval(v, fields) for k, v in expr.pairs}

        if isinstance(expr, CaseExpr):
            return self._eval_case(expr, fields)

        from uqa.graph.cypher.ast import ListIndex

        if isinstance(expr, ListIndex):
            lst = self._eval(expr.expr, fields)
            idx = self._eval(expr.index, fields)
            if lst is None or idx is None:
                return None
            return lst[idx]

        raise ValueError(f"Cannot evaluate expression: {type(expr).__name__}")

    def _eval_binary(self, expr: BinaryOp, fields: BindingFields) -> Any:
        op = expr.op

        if op == "AND":
            left = self._eval(expr.left, fields)
            if not left:
                return False
            return bool(self._eval(expr.right, fields))
        if op == "OR":
            left = self._eval(expr.left, fields)
            if left:
                return True
            return bool(self._eval(expr.right, fields))
        if op == "XOR":
            return bool(self._eval(expr.left, fields)) != bool(
                self._eval(expr.right, fields)
            )

        left = self._eval(expr.left, fields)
        right = self._eval(expr.right, fields)

        if left is None or right is None:
            if op == "=":
                return left is None and right is None
            if op == "<>":
                return not (left is None and right is None)
            return None

        ops: dict[str, Any] = {
            "=": lambda a, b: a == b,
            "<>": lambda a, b: a != b,
            "<": lambda a, b: a < b,
            ">": lambda a, b: a > b,
            "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "%": lambda a, b: a % b,
            "^": lambda a, b: a**b,
            "STARTS WITH": lambda a, b: str(a).startswith(str(b)),
            "ENDS WITH": lambda a, b: str(a).endswith(str(b)),
            "CONTAINS": lambda a, b: str(b) in str(a),
        }

        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            if isinstance(left, list):
                return left + (right if isinstance(right, list) else [right])
            return left + right
        if op == "/":
            if right == 0:
                return None
            if isinstance(left, int) and isinstance(right, int):
                return left // right
            return left / right
        if op in ops:
            return ops[op](left, right)

        raise ValueError(f"Unknown binary operator: {op}")

    def _eval_unary(self, expr: UnaryOp, fields: BindingFields) -> Any:
        val = self._eval(expr.operand, fields)
        if expr.op == "NOT":
            return not val
        if expr.op == "-":
            return -val if val is not None else None
        raise ValueError(f"Unknown unary operator: {expr.op}")

    def _eval_function(self, expr: FunctionCall, fields: BindingFields) -> Any:
        name = expr.name.lower()
        args = expr.args

        if name == "id":
            val = (
                fields.get(args[0].name)
                if isinstance(args[0], Variable)
                else self._eval(args[0], fields)
            )
            if isinstance(val, int):
                return val
            return None
        if name == "type":
            val = self._eval(args[0], fields)
            if isinstance(val, int):
                edge = self._graph.get_edge(val)
                if edge:
                    return edge.label
            return None
        if name == "labels":
            val = self._eval(args[0], fields)
            if isinstance(val, int):
                vtx = self._graph.get_vertex(val)
                if vtx:
                    return [vtx.label] if vtx.label else []
            return None
        if name == "label":
            val = self._eval(args[0], fields)
            if isinstance(val, int):
                vtx = self._graph.get_vertex(val)
                if vtx:
                    return vtx.label
            return None
        if name == "properties":
            val = self._eval(args[0], fields)
            if isinstance(val, int):
                vtx = self._graph.get_vertex(val)
                if vtx:
                    return dict(vtx.properties)
                edge = self._graph.get_edge(val)
                if edge:
                    return dict(edge.properties)
            return None
        if name == "keys":
            val = self._eval(args[0], fields)
            if isinstance(val, int):
                vtx = self._graph.get_vertex(val)
                if vtx:
                    return list(vtx.properties.keys())
                edge = self._graph.get_edge(val)
                if edge:
                    return list(edge.properties.keys())
            if isinstance(val, dict):
                return list(val.keys())
            return None
        if name in ("tostring", "tostr"):
            val = self._eval(args[0], fields)
            return str(val) if val is not None else None
        if name in ("tointeger", "toint"):
            val = self._eval(args[0], fields)
            return int(val) if val is not None else None
        if name == "tofloat":
            val = self._eval(args[0], fields)
            return float(val) if val is not None else None
        if name == "size":
            val = self._eval(args[0], fields)
            return len(val) if val is not None else None
        if name == "length":
            val = self._eval(args[0], fields)
            return len(val) if val is not None else None
        if name == "head":
            val = self._eval(args[0], fields)
            return val[0] if val else None
        if name == "last":
            val = self._eval(args[0], fields)
            return val[-1] if val else None
        if name == "tail":
            val = self._eval(args[0], fields)
            return val[1:] if val else []
        if name == "reverse":
            val = self._eval(args[0], fields)
            if val is None:
                return None
            return val[::-1] if isinstance(val, str) else list(reversed(val))
        if name == "range":
            start = self._eval(args[0], fields)
            end = self._eval(args[1], fields)
            step = self._eval(args[2], fields) if len(args) > 2 else 1
            return list(range(start, end + 1, step))
        if name == "abs":
            val = self._eval(args[0], fields)
            return abs(val) if val is not None else None
        if name == "coalesce":
            for a in args:
                val = self._eval(a, fields)
                if val is not None:
                    return val
            return None
        if name in ("tolower", "lower"):
            val = self._eval(args[0], fields)
            return val.lower() if isinstance(val, str) else None
        if name in ("toupper", "upper"):
            val = self._eval(args[0], fields)
            return val.upper() if isinstance(val, str) else None
        if name == "trim":
            val = self._eval(args[0], fields)
            return val.strip() if isinstance(val, str) else None
        if name == "replace":
            s = self._eval(args[0], fields)
            old = self._eval(args[1], fields)
            new = self._eval(args[2], fields)
            return s.replace(old, new) if isinstance(s, str) else None
        if name == "substring":
            s = self._eval(args[0], fields)
            start = self._eval(args[1], fields)
            if len(args) > 2:
                length = self._eval(args[2], fields)
                return s[start : start + length] if isinstance(s, str) else None
            return s[start:] if isinstance(s, str) else None
        if name == "split":
            s = self._eval(args[0], fields)
            delim = self._eval(args[1], fields)
            return s.split(delim) if isinstance(s, str) else None
        if name == "startnode":
            val = self._eval(args[0], fields)
            if isinstance(val, int):
                edge = self._graph.get_edge(val)
                if edge:
                    return edge.source_id
            return None
        if name == "endnode":
            val = self._eval(args[0], fields)
            if isinstance(val, int):
                edge = self._graph.get_edge(val)
                if edge:
                    return edge.target_id
            return None
        if name == "count":
            # count(*) handled at aggregate level; for scalar context return 1
            return 1
        if name == "collect":
            # Scalar context -- actual aggregation handled at RETURN level
            val = self._eval(args[0], fields)
            return [val]

        raise ValueError(f"Unknown function: {expr.name}")

    def _eval_case(self, expr: CaseExpr, fields: BindingFields) -> Any:
        if expr.operand is not None:
            val = self._eval(expr.operand, fields)
            for when_expr, then_expr in expr.whens:
                if val == self._eval(when_expr, fields):
                    return self._eval(then_expr, fields)
        else:
            for when_expr, then_expr in expr.whens:
                if self._eval(when_expr, fields):
                    return self._eval(then_expr, fields)
        if expr.else_expr is not None:
            return self._eval(expr.else_expr, fields)
        return None


# -- Module-level helpers --------------------------------------------------


def _set_nested(props: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    target = props
    for k in keys[:-1]:
        target = target.setdefault(k, {})
    target[keys[-1]] = value


def _expr_name(expr: CypherExpr) -> str:
    if isinstance(expr, Variable):
        return expr.name
    if isinstance(expr, PropertyAccess):
        return ".".join((expr.variable, *expr.keys))
    if isinstance(expr, FunctionCall):
        return expr.name
    return str(expr)


def _sort_key(val: Any) -> tuple:
    if val is None:
        return (0,)
    if isinstance(val, bool):
        return (1, int(val))
    if isinstance(val, int | float):
        return (2, val)
    if isinstance(val, str):
        return (3, val)
    return (4, str(val))


def _distinct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: list[tuple] = []
    result: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(sorted((k, str(v)) for k, v in row.items()))
        if key not in seen:
            seen.append(key)
            result.append(row)
    return result
