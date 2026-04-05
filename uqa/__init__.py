#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.api.query_builder import QueryBuilder
    from uqa.core.posting_list import PostingList
    from uqa.core.types import Edge, Vertex
    from uqa.engine import Engine
    from uqa.graph.pattern import GraphPattern


def __getattr__(name: str):
    """Lazy imports to avoid circular / missing-module errors during parallel development."""
    _imports = {
        "Engine": ("uqa.engine", "Engine"),
        "QueryBuilder": ("uqa.api.query_builder", "QueryBuilder"),
        "PostingList": ("uqa.core.posting_list", "PostingList"),
        "Vertex": ("uqa.core.types", "Vertex"),
        "Edge": ("uqa.core.types", "Edge"),
        "GraphPattern": ("uqa.graph.pattern", "GraphPattern"),
    }
    if name in _imports:
        import importlib

        module_path, attr = _imports[name]
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    raise AttributeError(f"module 'uqa' has no attribute {name!r}")


__version__ = "0.25.3"

__all__ = [
    "Edge",
    "Engine",
    "GraphPattern",
    "PostingList",
    "QueryBuilder",
    "Vertex",
]
