#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Index type definitions for the storage layer."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class IndexType(enum.Enum):
    BTREE = "btree"
    GIN = "gin"
    INVERTED = "inverted"
    HNSW = "hnsw"
    IVF = "ivf"
    GRAPH = "graph"
    RTREE = "rtree"


@dataclass(frozen=True, slots=True)
class IndexDef:
    """Definition of an index on a table."""

    name: str
    index_type: IndexType
    table_name: str
    columns: tuple[str, ...]
    parameters: dict[str, Any] = field(default_factory=dict)
