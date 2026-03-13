#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Character filters for the text analysis pipeline.

A CharFilter transforms raw text before tokenization. Multiple char
filters can be chained in an Analyzer pipeline.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class CharFilter(ABC):
    """Base class for character-level text transformations."""

    @abstractmethod
    def filter(self, text: str) -> str: ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CharFilter:
        registry: dict[str, type[CharFilter]] = {
            "html_strip": HTMLStripCharFilter,
            "mapping": MappingCharFilter,
            "pattern_replace": PatternReplaceCharFilter,
        }
        cf_type = d["type"]
        if cf_type not in registry:
            raise ValueError(f"Unknown char filter type: {cf_type!r}")
        return registry[cf_type]._from_dict(d)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> CharFilter:
        raise NotImplementedError


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITIES: dict[str, str] = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
    "&nbsp;": " ",
}


class HTMLStripCharFilter(CharFilter):
    """Strip HTML tags and convert common HTML entities."""

    def filter(self, text: str) -> str:
        text = _HTML_TAG_RE.sub(" ", text)
        for entity, replacement in _HTML_ENTITIES.items():
            text = text.replace(entity, replacement)
        return text

    def to_dict(self) -> dict[str, Any]:
        return {"type": "html_strip"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> HTMLStripCharFilter:
        return cls()


class MappingCharFilter(CharFilter):
    """Apply string-level character replacements.

    Longer keys are replaced first to avoid partial matches.
    """

    def __init__(self, mapping: dict[str, str]) -> None:
        # Sort by key length descending for longest-match-first.
        self._mapping = dict(
            sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
        )

    def filter(self, text: str) -> str:
        for old, new in self._mapping.items():
            text = text.replace(old, new)
        return text

    def to_dict(self) -> dict[str, Any]:
        return {"type": "mapping", "mapping": self._mapping}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> MappingCharFilter:
        return cls(d["mapping"])


class PatternReplaceCharFilter(CharFilter):
    """Replace text matching a regular expression."""

    def __init__(self, pattern: str, replacement: str = "") -> None:
        self._pattern = pattern
        self._replacement = replacement
        self._re = re.compile(pattern)

    def filter(self, text: str) -> str:
        return self._re.sub(self._replacement, text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "pattern_replace",
            "pattern": self._pattern,
            "replacement": self._replacement,
        }

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> PatternReplaceCharFilter:
        return cls(d["pattern"], d.get("replacement", ""))
