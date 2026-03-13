#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Analyzer -- the composable text analysis pipeline.

An Analyzer chains CharFilters, a Tokenizer, and TokenFilters into a
single ``analyze(text) -> list[str]`` call.  Built-in presets replicate
Lucene's standard analyzers while allowing full user customization.
"""

from __future__ import annotations

import json
from typing import Any

from uqa.analysis.char_filter import CharFilter
from uqa.analysis.token_filter import (
    ASCIIFoldingFilter,
    LowerCaseFilter,
    NGramFilter,
    PorterStemFilter,
    StopWordFilter,
    TokenFilter,
)
from uqa.analysis.tokenizer import (
    KeywordTokenizer,
    StandardTokenizer,
    Tokenizer,
    WhitespaceTokenizer,
)


class Analyzer:
    """Composable text analysis pipeline.

    Pipeline: text -> CharFilter* -> Tokenizer -> TokenFilter* -> tokens
    """

    def __init__(
        self,
        tokenizer: Tokenizer | None = None,
        token_filters: list[TokenFilter] | None = None,
        char_filters: list[CharFilter] | None = None,
    ) -> None:
        self._tokenizer = tokenizer or WhitespaceTokenizer()
        self._token_filters = list(token_filters) if token_filters else []
        self._char_filters = list(char_filters) if char_filters else []

    @property
    def tokenizer(self) -> Tokenizer:
        return self._tokenizer

    @property
    def token_filters(self) -> list[TokenFilter]:
        return self._token_filters

    @property
    def char_filters(self) -> list[CharFilter]:
        return self._char_filters

    def analyze(self, text: str) -> list[str]:
        """Run the full analysis pipeline and return tokens."""
        for cf in self._char_filters:
            text = cf.filter(text)
        tokens = self._tokenizer.tokenize(text)
        for tf in self._token_filters:
            tokens = tf.filter(tokens)
        return tokens

    def to_dict(self) -> dict[str, Any]:
        """Serialize the pipeline configuration to a dict."""
        return {
            "tokenizer": self._tokenizer.to_dict(),
            "token_filters": [tf.to_dict() for tf in self._token_filters],
            "char_filters": [cf.to_dict() for cf in self._char_filters],
        }

    def to_json(self) -> str:
        """Serialize the pipeline configuration to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Analyzer:
        """Deserialize an Analyzer from a dict."""
        tokenizer = Tokenizer.from_dict(d["tokenizer"])
        token_filters = [TokenFilter.from_dict(tf) for tf in d.get("token_filters", [])]
        char_filters = [CharFilter.from_dict(cf) for cf in d.get("char_filters", [])]
        return cls(tokenizer, token_filters, char_filters)

    @classmethod
    def from_json(cls, s: str) -> Analyzer:
        """Deserialize an Analyzer from a JSON string."""
        return cls.from_dict(json.loads(s))


# -- Built-in presets -------------------------------------------------------


def whitespace_analyzer() -> Analyzer:
    """WhitespaceTokenizer + LowerCaseFilter.

    Produces the same output as ``text.lower().split()`` -- the default
    behavior prior to the analysis pipeline.
    """
    return Analyzer(
        tokenizer=WhitespaceTokenizer(),
        token_filters=[LowerCaseFilter()],
    )


def standard_analyzer(language: str = "english") -> Analyzer:
    """StandardTokenizer + LowerCase + ASCIIFolding + StopWord + PorterStem.

    Full-featured analyzer for Latin-script languages.
    """
    return Analyzer(
        tokenizer=StandardTokenizer(),
        token_filters=[
            LowerCaseFilter(),
            ASCIIFoldingFilter(),
            StopWordFilter(language),
            PorterStemFilter(),
        ],
    )


def standard_cjk_analyzer(language: str = "english") -> Analyzer:
    """Standard analyzer with NGram(2, 3) for CJK text.

    Extends the standard pipeline with character-level bigram/trigram
    generation, enabling substring matching for CJK scripts where words
    are not delimited by whitespace.
    """
    return Analyzer(
        tokenizer=StandardTokenizer(),
        token_filters=[
            LowerCaseFilter(),
            ASCIIFoldingFilter(),
            StopWordFilter(language),
            PorterStemFilter(),
            NGramFilter(min_gram=2, max_gram=3, keep_short=True),
        ],
    )


def keyword_analyzer() -> Analyzer:
    """KeywordTokenizer with no filters.

    The entire input becomes a single token, unmodified.
    """
    return Analyzer(tokenizer=KeywordTokenizer())


# -- Global default ---------------------------------------------------------

DEFAULT_ANALYZER = standard_analyzer()

# -- Named analyzer registry ------------------------------------------------

_BUILTIN_ANALYZERS: dict[str, Analyzer] = {
    "whitespace": whitespace_analyzer(),
    "standard": standard_analyzer(),
    "standard_cjk": standard_cjk_analyzer(),
    "keyword": keyword_analyzer(),
}

_custom_analyzers: dict[str, Analyzer] = {}


def register_analyzer(name: str, analyzer: Analyzer) -> None:
    """Register a named analyzer."""
    if name in _BUILTIN_ANALYZERS:
        raise ValueError(f"Cannot overwrite built-in analyzer: {name!r}")
    _custom_analyzers[name] = analyzer


def get_analyzer(name: str) -> Analyzer:
    """Look up a named analyzer (built-in or custom)."""
    if name in _custom_analyzers:
        return _custom_analyzers[name]
    if name in _BUILTIN_ANALYZERS:
        return _BUILTIN_ANALYZERS[name]
    raise ValueError(f"Unknown analyzer: {name!r}")


def drop_analyzer(name: str) -> None:
    """Remove a custom analyzer."""
    if name in _BUILTIN_ANALYZERS:
        raise ValueError(f"Cannot drop built-in analyzer: {name!r}")
    if name not in _custom_analyzers:
        raise ValueError(f"Analyzer does not exist: {name!r}")
    del _custom_analyzers[name]


def list_analyzers() -> list[str]:
    """Return names of all registered analyzers."""
    return sorted(set(_BUILTIN_ANALYZERS) | set(_custom_analyzers))
