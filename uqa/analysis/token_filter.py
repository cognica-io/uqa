#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Token filters for the text analysis pipeline.

A TokenFilter transforms a list of tokens. Multiple filters can be
chained in an Analyzer pipeline.
"""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from typing import Any


class TokenFilter(ABC):
    """Base class for token-level transformations."""

    @abstractmethod
    def filter(self, tokens: list[str]) -> list[str]:
        ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        ...

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TokenFilter:
        registry: dict[str, type[TokenFilter]] = {
            "lowercase": LowerCaseFilter,
            "stop": StopWordFilter,
            "porter_stem": PorterStemFilter,
            "ascii_folding": ASCIIFoldingFilter,
            "synonym": SynonymFilter,
            "ngram": NGramFilter,
            "edge_ngram": EdgeNGramFilter,
            "length": LengthFilter,
        }
        tf_type = d["type"]
        if tf_type not in registry:
            raise ValueError(f"Unknown token filter type: {tf_type!r}")
        return registry[tf_type]._from_dict(d)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> TokenFilter:
        raise NotImplementedError


class LowerCaseFilter(TokenFilter):
    """Convert all tokens to lowercase."""

    def filter(self, tokens: list[str]) -> list[str]:
        return [t.lower() for t in tokens]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "lowercase"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> LowerCaseFilter:
        return cls()


# -- Stop word lists -------------------------------------------------------

_STOP_WORDS: dict[str, frozenset[str]] = {
    "english": frozenset({
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for",
        "if", "in", "into", "is", "it", "no", "not", "of", "on", "or",
        "such", "that", "the", "their", "then", "there", "these", "they",
        "this", "to", "was", "were", "will", "with", "would", "can",
        "could", "do", "does", "did", "had", "has", "have", "he", "her",
        "him", "his", "how", "i", "its", "may", "me", "my", "nor", "our",
        "own", "she", "should", "so", "some", "than", "too", "us", "very",
        "we", "what", "when", "which", "who", "whom", "why", "you", "your",
    }),
}


class StopWordFilter(TokenFilter):
    """Remove stop words from the token stream.

    Supports built-in language lists and custom word sets.
    """

    def __init__(
        self,
        language: str = "english",
        custom_words: set[str] | None = None,
    ) -> None:
        self._language = language
        self._custom_words = frozenset(custom_words) if custom_words else frozenset()
        base = _STOP_WORDS.get(language, frozenset())
        self._words = base | self._custom_words

    def filter(self, tokens: list[str]) -> list[str]:
        return [t for t in tokens if t not in self._words]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": "stop", "language": self._language}
        if self._custom_words:
            d["custom_words"] = sorted(self._custom_words)
        return d

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> StopWordFilter:
        custom = set(d["custom_words"]) if "custom_words" in d else None
        return cls(d.get("language", "english"), custom)


# -- Porter Stemmer ---------------------------------------------------------
# Reference: M. F. Porter, "An Algorithm for Suffix Stripping", 1980.


def _porter_stem(word: str) -> str:
    """Apply the Porter stemming algorithm to a single word."""
    if len(word) <= 2:
        return word

    def _cons(w: str, i: int) -> bool:
        """True if w[i] is a consonant."""
        if w[i] in "aeiou":
            return False
        if w[i] == "y":
            return i == 0 or not _cons(w, i - 1)
        return True

    def _m(w: str, j: int) -> int:
        """Measure: count VC sequences in w[0:j+1]."""
        n = 0
        i = 0
        while True:
            if i > j:
                return n
            if not _cons(w, i):
                break
            i += 1
        i += 1
        while True:
            while True:
                if i > j:
                    return n
                if _cons(w, i):
                    break
                i += 1
            i += 1
            n += 1
            while True:
                if i > j:
                    return n
                if not _cons(w, i):
                    break
                i += 1
            i += 1

    def _vowelinstem(w: str, j: int) -> bool:
        return any(not _cons(w, i) for i in range(j + 1))

    def _doublec(w: str, j: int) -> bool:
        return j >= 1 and w[j] == w[j - 1] and _cons(w, j)

    def _cvc(w: str, i: int) -> bool:
        if i < 2 or not _cons(w, i) or _cons(w, i - 1) or not _cons(w, i - 2):
            return False
        return w[i] not in "wxy"

    def _ends(w: str, s: str) -> tuple[bool, str, int]:
        length = len(s)
        if length > len(w):
            return False, w, len(w) - 1
        if w[-length:] == s:
            return True, w, len(w) - 1 - length
        return False, w, len(w) - 1

    def _setto(w: str, j: int, s: str) -> str:
        return w[: j + 1] + s

    def _r(w: str, j: int, s: str) -> str:
        if _m(w, j) > 0:
            return _setto(w, j, s)
        return w

    # Step 1a
    if word.endswith("sses"):
        word = word[:-2]
    elif word.endswith("ies"):
        word = word[:-2]
    elif not word.endswith("ss") and word.endswith("s"):
        word = word[:-1]

    # Step 1b
    if word.endswith("eed"):
        stem = word[:-3]
        if _m(word, len(stem) - 1) > 0:
            word = word[:-1]
    else:
        matched = False
        for suffix in ("ed", "ing"):
            if word.endswith(suffix) and _vowelinstem(word, len(word) - len(suffix) - 1):
                word = word[: -len(suffix)]
                matched = True
                break
        if matched:
            if word.endswith("at") or word.endswith("bl") or word.endswith("iz"):
                word += "e"
            elif _doublec(word, len(word) - 1) and word[-1] not in "lsz":
                word = word[:-1]
            elif _m(word, len(word) - 1) == 1 and _cvc(word, len(word) - 1):
                word += "e"

    # Step 1c
    if word.endswith("y") and _vowelinstem(word, len(word) - 2):
        word = word[:-1] + "i"

    # Step 2
    step2_map = {
        "ational": "ate", "tional": "tion", "enci": "ence", "anci": "ance",
        "izer": "ize", "abli": "able", "alli": "al", "entli": "ent",
        "eli": "e", "ousli": "ous", "ization": "ize", "ation": "ate",
        "ator": "ate", "alism": "al", "iveness": "ive", "fulness": "ful",
        "ousness": "ous", "aliti": "al", "iviti": "ive", "biliti": "ble",
    }
    for suffix, replacement in step2_map.items():
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if _m(word, len(stem) - 1) > 0:
                word = stem + replacement
            break

    # Step 3
    step3_map = {
        "icate": "ic", "ative": "", "alize": "al",
        "iciti": "ic", "ical": "ic", "ful": "", "ness": "",
    }
    for suffix, replacement in step3_map.items():
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if _m(word, len(stem) - 1) > 0:
                word = stem + replacement
            break

    # Step 4
    step4_suffixes = [
        "al", "ance", "ence", "er", "ic", "able", "ible", "ant",
        "ement", "ment", "ent", "ion", "ou", "ism", "ate", "iti",
        "ous", "ive", "ize",
    ]
    for suffix in step4_suffixes:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if _m(word, len(stem) - 1) > 1:
                if suffix == "ion":
                    if stem and stem[-1] in "st":
                        word = stem
                else:
                    word = stem
            break

    # Step 5a
    if word.endswith("e"):
        stem = word[:-1]
        m_val = _m(word, len(stem) - 1)
        if m_val > 1 or (m_val == 1 and not _cvc(word, len(stem) - 1)):
            word = stem

    # Step 5b
    if _m(word, len(word) - 1) > 1 and _doublec(word, len(word) - 1) and word[-1] == "l":
        word = word[:-1]

    return word


class PorterStemFilter(TokenFilter):
    """Apply the Porter stemming algorithm to each token."""

    def filter(self, tokens: list[str]) -> list[str]:
        return [_porter_stem(t) for t in tokens]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "porter_stem"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> PorterStemFilter:
        return cls()


class ASCIIFoldingFilter(TokenFilter):
    """Fold Unicode characters to their ASCII equivalents."""

    def filter(self, tokens: list[str]) -> list[str]:
        return [self._fold(t) for t in tokens]

    @staticmethod
    def _fold(token: str) -> str:
        nfkd = unicodedata.normalize("NFKD", token)
        return nfkd.encode("ascii", "ignore").decode("ascii")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "ascii_folding"}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> ASCIIFoldingFilter:
        return cls()


class SynonymFilter(TokenFilter):
    """Expand tokens with synonyms.

    For each token matching a synonym key, appends the synonym
    alternatives to the token stream.  The original token is kept.
    """

    def __init__(self, synonyms: dict[str, list[str]]) -> None:
        self._synonyms = synonyms

    def filter(self, tokens: list[str]) -> list[str]:
        result: list[str] = []
        for t in tokens:
            result.append(t)
            if t in self._synonyms:
                result.extend(self._synonyms[t])
        return result

    def to_dict(self) -> dict[str, Any]:
        return {"type": "synonym", "synonyms": self._synonyms}

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> SynonymFilter:
        return cls(d["synonyms"])


class NGramFilter(TokenFilter):
    """Emit all character n-grams of each token.

    For each token, generates every substring of length ``min_gram``
    to ``max_gram``.  Useful for CJK text where words are not
    delimited by whitespace.

    When ``keep_short`` is True (default False), tokens shorter than
    ``min_gram`` are passed through unchanged instead of being dropped.
    """

    def __init__(
        self,
        min_gram: int = 2,
        max_gram: int = 3,
        keep_short: bool = False,
    ) -> None:
        if min_gram < 1:
            raise ValueError("min_gram must be >= 1")
        if max_gram < min_gram:
            raise ValueError("max_gram must be >= min_gram")
        self._min_gram = min_gram
        self._max_gram = max_gram
        self._keep_short = keep_short

    def filter(self, tokens: list[str]) -> list[str]:
        result: list[str] = []
        for t in tokens:
            if len(t) < self._min_gram:
                if self._keep_short:
                    result.append(t)
                continue
            for n in range(self._min_gram, self._max_gram + 1):
                for i in range(len(t) - n + 1):
                    result.append(t[i : i + n])
        return result

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": "ngram",
            "min_gram": self._min_gram,
            "max_gram": self._max_gram,
        }
        if self._keep_short:
            d["keep_short"] = True
        return d

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> NGramFilter:
        return cls(d["min_gram"], d["max_gram"], d.get("keep_short", False))


class EdgeNGramFilter(TokenFilter):
    """Emit prefix n-grams of each token.

    Useful for autocomplete/typeahead search.
    """

    def __init__(self, min_gram: int = 1, max_gram: int = 20) -> None:
        self._min_gram = min_gram
        self._max_gram = max_gram

    def filter(self, tokens: list[str]) -> list[str]:
        result: list[str] = []
        for t in tokens:
            upper = min(self._max_gram, len(t))
            for n in range(self._min_gram, upper + 1):
                result.append(t[:n])
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "edge_ngram",
            "min_gram": self._min_gram,
            "max_gram": self._max_gram,
        }

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> EdgeNGramFilter:
        return cls(d["min_gram"], d["max_gram"])


class LengthFilter(TokenFilter):
    """Filter tokens by length.

    Keeps tokens with ``min_length <= len(token) <= max_length``.
    ``max_length=0`` means no upper bound.
    """

    def __init__(self, min_length: int = 0, max_length: int = 0) -> None:
        self._min_length = min_length
        self._max_length = max_length

    def filter(self, tokens: list[str]) -> list[str]:
        result: list[str] = []
        for t in tokens:
            if len(t) < self._min_length:
                continue
            if self._max_length > 0 and len(t) > self._max_length:
                continue
            result.append(t)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "length",
            "min_length": self._min_length,
            "max_length": self._max_length,
        }

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> LengthFilter:
        return cls(d["min_length"], d["max_length"])
