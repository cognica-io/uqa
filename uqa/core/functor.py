#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Category-theoretic functors between UQA paradigms (Paper 1, Section 7).

Functors map objects and morphisms between categories while preserving
composition and identity. In UQA, each paradigm (relational, text, vector,
graph) is a category, and functors provide principled transformations.

Laws:
    F(id_A) = id_{F(A)}           (identity preservation)
    F(g . f) = F(g) . F(f)        (composition preservation)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from uqa.core.posting_list import PostingList
from uqa.core.types import Payload, PostingEntry
from uqa.graph.posting_list import GraphPayload, GraphPostingList


class Functor(ABC):
    """Abstract functor between UQA paradigms."""

    @abstractmethod
    def map_object(self, obj: Any) -> Any:
        """Map an object from source category to target category."""
        ...

    @abstractmethod
    def map_morphism(self, morphism: Any) -> Any:
        """Map a morphism (operation) from source to target category."""
        ...

    def identity(self, obj: Any) -> Any:
        """Identity morphism in the source category."""
        return obj


class GraphToRelationalFunctor(Functor):
    """Functor from Graph category to Relational category.

    Maps graph vertices to posting list entries and graph structure
    to relational tuples.
    """

    def map_object(self, obj: PostingList) -> PostingList:
        """Convert GraphPostingList to standard PostingList.

        If *obj* is already a plain PostingList (e.g. from inherited set
        operations on GraphPostingList), it is returned unchanged.
        """
        if isinstance(obj, GraphPostingList):
            return obj.to_posting_list()
        return obj

    def map_morphism(self, morphism: Any) -> Any:
        """Map a graph operation to a relational operation.

        Wraps graph operators so their output passes through map_object.
        """

        def wrapped(ctx: Any) -> PostingList:
            gpl = morphism.execute(ctx)
            if isinstance(gpl, GraphPostingList):
                return self.map_object(gpl)
            return gpl

        return wrapped


class RelationalToGraphFunctor(Functor):
    """Functor from Relational category to Graph category.

    Maps posting list entries to graph vertices, creating edges based on
    shared doc_ids or adjacency in the sorted order.
    """

    def __init__(self, edge_label: str = "adjacent") -> None:
        self.edge_label = edge_label

    def map_object(self, obj: PostingList) -> GraphPostingList:
        """Convert PostingList to GraphPostingList.

        Each entry becomes a vertex in the graph representation.
        """
        entries: list[PostingEntry] = []
        graph_payloads: dict[int, GraphPayload] = {}
        all_vids: set[int] = set()

        for entry in obj:
            all_vids.add(entry.doc_id)
            entries.append(entry)

        frozen_vids = frozenset(all_vids)
        for entry in entries:
            graph_payloads[entry.doc_id] = GraphPayload(
                subgraph_vertices=frozen_vids,
                subgraph_edges=frozenset(),
                score=entry.payload.score,
            )

        return GraphPostingList(entries, graph_payloads)

    def map_morphism(self, morphism: Any) -> Any:
        """Map a relational operation to a graph operation."""

        def wrapped(ctx: Any) -> GraphPostingList:
            pl = morphism.execute(ctx)
            if isinstance(pl, PostingList) and not isinstance(pl, GraphPostingList):
                return self.map_object(pl)
            return pl

        return wrapped


class TextToVectorFunctor(Functor):
    """Functor from Text category to Vector category.

    Maps text posting list entries (with term frequencies) to vector
    representations using TF-based encoding.
    """

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def map_object(self, obj: PostingList) -> PostingList:
        """Convert text posting list entries to vector-scored entries.

        Uses position count as a proxy for term frequency, then normalizes
        scores to [0, 1] range.
        """
        if not obj:
            return PostingList()

        entries: list[PostingEntry] = []
        max_score = 0.0

        # First pass: compute raw scores from positions
        raw_scores: list[tuple[PostingEntry, float]] = []
        for entry in obj:
            # Use position count as TF proxy, combined with existing score
            tf = len(entry.payload.positions) if entry.payload.positions else 1
            raw = float(tf) * max(entry.payload.score, 0.01)
            raw_scores.append((entry, raw))
            max_score = max(max_score, raw)

        # Second pass: normalize to [0, 1]
        for entry, raw in raw_scores:
            normalized = raw / max_score if max_score > 0 else 0.0
            new_payload = Payload(
                positions=entry.payload.positions,
                score=normalized,
                fields=dict(entry.payload.fields),
            )
            entries.append(PostingEntry(entry.doc_id, new_payload))

        return PostingList.from_sorted(entries)

    def map_morphism(self, morphism: Any) -> Any:
        """Map a text operation to a vector operation."""

        def wrapped(ctx: Any) -> PostingList:
            pl = morphism.execute(ctx)
            if isinstance(pl, PostingList):
                return self.map_object(pl)
            return pl

        return wrapped
