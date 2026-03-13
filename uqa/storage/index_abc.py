#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Abstract base class for all index types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.posting_list import PostingList
    from uqa.core.types import Predicate
    from uqa.storage.index_types import IndexDef
    from uqa.storage.managed_connection import SQLiteConnection


class Index(ABC):
    """Abstract index that supports predicate scans and cost estimation."""

    def __init__(self, index_def: IndexDef, conn: SQLiteConnection) -> None:
        self._index_def = index_def
        self._conn = conn

    @property
    def index_def(self) -> IndexDef:
        return self._index_def

    @abstractmethod
    def scan(self, predicate: Predicate) -> PostingList:
        """Scan the index using a predicate and return matching doc IDs."""
        ...

    @abstractmethod
    def estimate_cardinality(self, predicate: Predicate) -> int:
        """Estimate the number of rows matching the predicate."""
        ...

    @abstractmethod
    def scan_cost(self, predicate: Predicate) -> float:
        """Estimate the cost of scanning with this predicate."""
        ...

    @abstractmethod
    def build(self) -> None:
        """Create the physical index structure."""
        ...

    @abstractmethod
    def drop(self) -> None:
        """Drop the physical index structure."""
        ...
