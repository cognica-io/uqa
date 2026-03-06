from __future__ import annotations

from dataclasses import dataclass, field

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry


@dataclass(frozen=True, slots=True)
class GraphPayload:
    """Payload for graph posting list entries."""

    subgraph_vertices: frozenset[int] = field(default_factory=frozenset)
    subgraph_edges: frozenset[int] = field(default_factory=frozenset)
    score: float = 0.0


class GraphPostingList(PostingList):
    """Graph posting list with isomorphism to standard PostingList.

    The isomorphism Phi: L_G -> L (Theorem 1.1.6, Paper 2) is
    realized by the to_posting_list() / from_posting_list() methods.
    """

    def __init__(
        self,
        entries: list[PostingEntry] | None = None,
        graph_payloads: dict[int, GraphPayload] | None = None,
    ) -> None:
        super().__init__(entries)
        self._graph_payloads: dict[int, GraphPayload] = graph_payloads or {}

    def set_graph_payload(self, doc_id: int, gp: GraphPayload) -> None:
        self._graph_payloads[doc_id] = gp

    def get_graph_payload(self, doc_id: int) -> GraphPayload | None:
        return self._graph_payloads.get(doc_id)

    def to_posting_list(self) -> PostingList:
        """Phi: L_G -> L (isomorphism).

        Encodes subgraph_vertices and subgraph_edges into Payload.fields.
        """
        converted: list[PostingEntry] = []
        for entry in self._entries:
            gp = self._graph_payloads.get(entry.doc_id)
            if gp is not None:
                fields = dict(entry.payload.fields)
                fields["_graph_vertices"] = sorted(gp.subgraph_vertices)
                fields["_graph_edges"] = sorted(gp.subgraph_edges)
                payload = Payload(
                    positions=entry.payload.positions,
                    score=gp.score if gp.score != 0.0 else entry.payload.score,
                    fields=fields,
                )
                converted.append(PostingEntry(entry.doc_id, payload))
            else:
                converted.append(entry)
        return PostingList(converted)

    @classmethod
    def from_posting_list(cls, pl: PostingList) -> GraphPostingList:
        """Phi^{-1}: L -> L_G (inverse isomorphism).

        Extracts subgraph_vertices and subgraph_edges from Payload.fields.
        """
        graph_payloads: dict[int, GraphPayload] = {}
        entries: list[PostingEntry] = []
        for entry in pl.entries:
            vertices_raw = entry.payload.fields.get("_graph_vertices", [])
            edges_raw = entry.payload.fields.get("_graph_edges", [])
            gp = GraphPayload(
                subgraph_vertices=frozenset(vertices_raw),
                subgraph_edges=frozenset(edges_raw),
                score=entry.payload.score,
            )
            graph_payloads[entry.doc_id] = gp
            # Strip graph fields from payload
            fields = {
                k: v
                for k, v in entry.payload.fields.items()
                if k not in ("_graph_vertices", "_graph_edges")
            }
            payload = Payload(
                positions=entry.payload.positions,
                score=entry.payload.score,
                fields=fields,
            )
            entries.append(PostingEntry(entry.doc_id, payload))
        gpl = cls(entries, graph_payloads)
        return gpl
