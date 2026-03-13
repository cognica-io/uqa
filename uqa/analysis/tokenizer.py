#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tokenizers for the text analysis pipeline.

A Tokenizer splits text into a sequence of tokens. Each Analyzer has
exactly one Tokenizer.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class Tokenizer(ABC):
    """Base class for text tokenization."""

    @abstractmethod
    def tokenize(self, text: str) -> list[str]: ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Tokenizer:
        registry: dict[str, type[Tokenizer]] = {
            "whitespace": WhitespaceTokenizer,
            "standard": StandardTokenizer,
            "letter": LetterTokenizer,
            "ngram": NGramTokenizer,
            "pattern": PatternTokenizer,
            "keyword": KeywordTokenizer,
        }
        tok_type = d["type"]
        if tok_type not in registry:
            raise ValueError(f"Unknown tokenizer type: {tok_type!r}")
        return registry[tok_type]._from_dict(d)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> Tokenizer:
        raise NotImplementedError


class WhitespaceTokenizer(Tokenizer):
    """Split on whitespace. Equivalent to ``str.split()``."""

    def tokenize(self, text: str) -> list[str]:
        return text.split()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "whitespace"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> WhitespaceTokenizer:
        return cls()


_WORD_RE = re.compile(r"\w+", re.UNICODE)


class StandardTokenizer(Tokenizer):
    """Unicode word-boundary tokenizer.

    Splits on non-word characters, keeping sequences of alphanumeric
    and underscore characters as tokens.  Handles Unicode correctly.
    """

    def tokenize(self, text: str) -> list[str]:
        return _WORD_RE.findall(text)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "standard"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> StandardTokenizer:
        return cls()


_LETTER_RE = re.compile(r"[a-zA-Z]+")


class LetterTokenizer(Tokenizer):
    """Extract runs of ASCII letters only."""

    def tokenize(self, text: str) -> list[str]:
        return _LETTER_RE.findall(text)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "letter"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> LetterTokenizer:
        return cls()


class NGramTokenizer(Tokenizer):
    """Character-level n-gram tokenizer.

    First splits on whitespace, then generates all n-grams of length
    ``min_gram`` to ``max_gram`` from each word.
    """

    def __init__(self, min_gram: int = 1, max_gram: int = 2) -> None:
        if min_gram < 1:
            raise ValueError("min_gram must be >= 1")
        if max_gram < min_gram:
            raise ValueError("max_gram must be >= min_gram")
        self._min_gram = min_gram
        self._max_gram = max_gram

    def tokenize(self, text: str) -> list[str]:
        tokens: list[str] = []
        for word in text.split():
            for n in range(self._min_gram, self._max_gram + 1):
                for i in range(len(word) - n + 1):
                    tokens.append(word[i : i + n])
        return tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "ngram",
            "min_gram": self._min_gram,
            "max_gram": self._max_gram,
        }

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> NGramTokenizer:
        return cls(d["min_gram"], d["max_gram"])


class PatternTokenizer(Tokenizer):
    """Split text using a regular expression delimiter."""

    def __init__(self, pattern: str = r"\W+") -> None:
        self._pattern = pattern
        self._re = re.compile(pattern)

    def tokenize(self, text: str) -> list[str]:
        return [t for t in self._re.split(text) if t]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "pattern", "pattern": self._pattern}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> PatternTokenizer:
        return cls(d["pattern"])


class KeywordTokenizer(Tokenizer):
    """Emit the entire input as a single token."""

    def tokenize(self, text: str) -> list[str]:
        if not text:
            return []
        return [text]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "keyword"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> KeywordTokenizer:
        return cls()
