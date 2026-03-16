#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Graph join operators (Paper 2, Section 4).

GraphGraphJoinOperator: hash join on shared vertex variable between two
graph posting lists.  Merges GraphPayload subgraph metadata (union of
subgraph_vertices/edges).

CrossParadigmGraphJoinOperator: joins a graph posting list with a
relational posting list on a vertex field / doc field match.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.graph.posting_list import GraphPayload, GraphPostingList

if TYPE_CHECKING:
    from uqa.operators.base import ExecutionContext


class GraphGraphJoinOperator:
    """Hash join on shared vertex variable between two graph posting lists.

    For each pair of entries (L, R) where L.fields[join_variable] ==
    R.fields[join_variable], produce a joined entry with merged
    GraphPayload (union of subgraph_vertices and subgraph_edges) and
    merged fields.
    """

    def __init__(
        self,
        left: object,
        right: object,
        join_variable: str,
        *,
        graph: str,
    ) -> None:
        self.left = left
        self.right = right
        self.join_variable = join_variable
        self.graph_name = graph

    def execute(self, ctx: ExecutionContext) -> GraphPostingList:
        left_gpl: GraphPostingList = self.left.execute(ctx)  # type: ignore[union-attr]
        right_gpl: GraphPostingList = self.right.execute(ctx)  # type: ignore[union-attr]

        # Build hash table from right on join_variable value
        right_by_key: dict[int, list[tuple[PostingEntry, GraphPayload | None]]] = {}
        for entry in right_gpl:
            key = entry.payload.fields.get(self.join_variable)
            if key is None:
                continue
            gp = right_gpl.get_graph_payload(entry.doc_id)
            right_by_key.setdefault(key, []).append((entry, gp))

        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        doc_id = 1

        for left_entry in left_gpl:
            left_key = left_entry.payload.fields.get(self.join_variable)
            if left_key is None:
                continue
            matches = right_by_key.get(left_key, [])
            left_gp = left_gpl.get_graph_payload(left_entry.doc_id)

            for right_entry, right_gp in matches:
                # Merge fields (left takes precedence on conflicts)
                merged_fields = dict(right_entry.payload.fields)
                merged_fields.update(left_entry.payload.fields)

                # Merge scores (sum)
                merged_score = left_entry.payload.score + right_entry.payload.score

                entry = PostingEntry(
                    doc_id,
                    Payload(score=merged_score, fields=merged_fields),
                )
                entries.append(entry)

                # Merge GraphPayload (union subgraph_vertices/edges)
                left_verts = left_gp.subgraph_vertices if left_gp else frozenset()
                left_edges = left_gp.subgraph_edges if left_gp else frozenset()
                right_verts = right_gp.subgraph_vertices if right_gp else frozenset()
                right_edges = right_gp.subgraph_edges if right_gp else frozenset()

                graph_payloads[doc_id] = GraphPayload(
                    subgraph_vertices=left_verts | right_verts,
                    subgraph_edges=left_edges | right_edges,
                    graph_name=self.graph_name,
                )
                doc_id += 1

        return GraphPostingList(entries, graph_payloads)


class CrossParadigmGraphJoinOperator:
    """Join a graph posting list with a relational posting list.

    Matches entries where the graph result's vertex_field value equals
    the relational result's doc_field value (typically a doc_id).
    """

    def __init__(
        self,
        graph_source: object,
        relational_source: object,
        vertex_field: str,
        doc_field: str,
    ) -> None:
        self.graph_source = graph_source
        self.relational_source = relational_source
        self.vertex_field = vertex_field
        self.doc_field = doc_field

    def execute(self, ctx: ExecutionContext) -> PostingList:
        graph_gpl: GraphPostingList = self.graph_source.execute(ctx)  # type: ignore[union-attr]
        rel_pl: PostingList = self.relational_source.execute(ctx)  # type: ignore[union-attr]

        # Build hash table from relational on doc_field
        rel_by_key: dict[int, list[PostingEntry]] = {}
        for entry in rel_pl:
            if self.doc_field == "doc_id":
                key = entry.doc_id
            else:
                key = entry.payload.fields.get(self.doc_field)
            if key is not None:
                rel_by_key.setdefault(key, []).append(entry)

        result: list[PostingEntry] = []
        seen_ids: set[int] = set()

        for graph_entry in graph_gpl:
            vertex_val = graph_entry.payload.fields.get(self.vertex_field)
            if vertex_val is None:
                vertex_val = graph_entry.doc_id
            matches = rel_by_key.get(vertex_val, [])
            for rel_entry in matches:
                doc_id = rel_entry.doc_id
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    merged_fields = dict(rel_entry.payload.fields)
                    merged_fields.update(graph_entry.payload.fields)
                    merged_score = graph_entry.payload.score + rel_entry.payload.score
                    result.append(
                        PostingEntry(
                            doc_id,
                            Payload(score=merged_score, fields=merged_fields),
                        )
                    )

        result.sort(key=lambda e: e.doc_id)
        return PostingList.from_sorted(result)
