#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

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


__version__ = "0.10.1"

__all__ = [
    "Engine",
    "QueryBuilder",
    "PostingList",
    "Vertex",
    "Edge",
    "GraphPattern",
]
