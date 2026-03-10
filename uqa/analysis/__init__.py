#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Text analysis pipeline (Lucene-style).

Pipeline: text -> CharFilter* -> Tokenizer -> TokenFilter* -> tokens
"""

from uqa.analysis.analyzer import (
    Analyzer,
    DEFAULT_ANALYZER,
    drop_analyzer,
    get_analyzer,
    keyword_analyzer,
    list_analyzers,
    register_analyzer,
    standard_analyzer,
    standard_cjk_analyzer,
    whitespace_analyzer,
)
from uqa.analysis.char_filter import (
    CharFilter,
    HTMLStripCharFilter,
    MappingCharFilter,
    PatternReplaceCharFilter,
)
from uqa.analysis.token_filter import (
    ASCIIFoldingFilter,
    EdgeNGramFilter,
    LengthFilter,
    LowerCaseFilter,
    NGramFilter,
    PorterStemFilter,
    StopWordFilter,
    SynonymFilter,
    TokenFilter,
)
from uqa.analysis.tokenizer import (
    KeywordTokenizer,
    LetterTokenizer,
    NGramTokenizer,
    PatternTokenizer,
    StandardTokenizer,
    Tokenizer,
    WhitespaceTokenizer,
)

__all__ = [
    # Analyzer
    "Analyzer",
    "DEFAULT_ANALYZER",
    "drop_analyzer",
    "get_analyzer",
    "keyword_analyzer",
    "list_analyzers",
    "register_analyzer",
    "standard_analyzer",
    "standard_cjk_analyzer",
    "whitespace_analyzer",
    # CharFilter
    "CharFilter",
    "HTMLStripCharFilter",
    "MappingCharFilter",
    "PatternReplaceCharFilter",
    # TokenFilter
    "ASCIIFoldingFilter",
    "EdgeNGramFilter",
    "LengthFilter",
    "LowerCaseFilter",
    "NGramFilter",
    "PorterStemFilter",
    "StopWordFilter",
    "SynonymFilter",
    "TokenFilter",
    # Tokenizer
    "KeywordTokenizer",
    "LetterTokenizer",
    "NGramTokenizer",
    "PatternTokenizer",
    "StandardTokenizer",
    "Tokenizer",
    "WhitespaceTokenizer",
]
