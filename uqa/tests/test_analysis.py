#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for the Lucene-style text analysis pipeline.

Covers:
    - Tokenizers (Whitespace, Standard, Letter, NGram, Pattern, Keyword)
    - Token filters (LowerCase, StopWord, PorterStem, ASCIIFolding,
      Synonym, EdgeNGram, Length)
    - Char filters (HTMLStrip, Mapping, PatternReplace)
    - Analyzer composition and serialization
    - Named analyzer registry (register, get, drop, list)
    - InvertedIndex / SQLiteInvertedIndex analyzer integration
    - SQL table functions (create_analyzer, drop_analyzer, list_analyzers)
    - Query-time analyzer symmetry (same analyzer at index and query time)
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from uqa.analysis import (
    DEFAULT_ANALYZER,
    Analyzer,
    ASCIIFoldingFilter,
    EdgeNGramFilter,
    HTMLStripCharFilter,
    KeywordTokenizer,
    LengthFilter,
    LetterTokenizer,
    LowerCaseFilter,
    MappingCharFilter,
    NGramTokenizer,
    PatternReplaceCharFilter,
    PatternTokenizer,
    PorterStemFilter,
    StandardTokenizer,
    StopWordFilter,
    SynonymFilter,
    WhitespaceTokenizer,
    drop_analyzer,
    get_analyzer,
    keyword_analyzer,
    list_analyzers,
    register_analyzer,
    standard_analyzer,
    whitespace_analyzer,
)
from uqa.storage.inverted_index import InvertedIndex
from uqa.storage.sqlite_inverted_index import SQLiteInvertedIndex

# ======================================================================
# Tokenizers
# ======================================================================


class TestWhitespaceTokenizer:
    def test_basic(self):
        tok = WhitespaceTokenizer()
        assert tok.tokenize("hello world") == ["hello", "world"]

    def test_multiple_spaces(self):
        tok = WhitespaceTokenizer()
        assert tok.tokenize("  hello   world  ") == ["hello", "world"]

    def test_empty(self):
        tok = WhitespaceTokenizer()
        assert tok.tokenize("") == []

    def test_roundtrip(self):
        tok = WhitespaceTokenizer()
        d = tok.to_dict()
        assert d == {"type": "whitespace"}
        from uqa.analysis.tokenizer import Tokenizer

        restored = Tokenizer.from_dict(d)
        assert isinstance(restored, WhitespaceTokenizer)


class TestStandardTokenizer:
    def test_basic(self):
        tok = StandardTokenizer()
        assert tok.tokenize("Hello, World!") == ["Hello", "World"]

    def test_unicode(self):
        tok = StandardTokenizer()
        tokens = tok.tokenize("cafe_latte 42")
        assert tokens == ["cafe_latte", "42"]

    def test_punctuation(self):
        tok = StandardTokenizer()
        assert tok.tokenize("it's a test.") == ["it", "s", "a", "test"]

    def test_roundtrip(self):
        tok = StandardTokenizer()
        d = tok.to_dict()
        from uqa.analysis.tokenizer import Tokenizer

        assert isinstance(Tokenizer.from_dict(d), StandardTokenizer)


class TestLetterTokenizer:
    def test_basic(self):
        tok = LetterTokenizer()
        assert tok.tokenize("hello123world") == ["hello", "world"]

    def test_only_letters(self):
        tok = LetterTokenizer()
        assert tok.tokenize("42!!") == []


class TestNGramTokenizer:
    def test_bigrams(self):
        tok = NGramTokenizer(min_gram=2, max_gram=2)
        assert tok.tokenize("abc") == ["ab", "bc"]

    def test_unigrams_and_bigrams(self):
        tok = NGramTokenizer(min_gram=1, max_gram=2)
        assert tok.tokenize("ab") == ["a", "b", "ab"]

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            NGramTokenizer(min_gram=0)
        with pytest.raises(ValueError):
            NGramTokenizer(min_gram=3, max_gram=2)

    def test_roundtrip(self):
        tok = NGramTokenizer(min_gram=2, max_gram=3)
        d = tok.to_dict()
        from uqa.analysis.tokenizer import Tokenizer

        restored = Tokenizer.from_dict(d)
        assert isinstance(restored, NGramTokenizer)


class TestPatternTokenizer:
    def test_default_pattern(self):
        tok = PatternTokenizer()
        assert tok.tokenize("hello-world") == ["hello", "world"]

    def test_custom_pattern(self):
        tok = PatternTokenizer(pattern=r",\s*")
        assert tok.tokenize("a, b, c") == ["a", "b", "c"]

    def test_roundtrip(self):
        tok = PatternTokenizer(pattern=r"\|")
        d = tok.to_dict()
        from uqa.analysis.tokenizer import Tokenizer

        restored = Tokenizer.from_dict(d)
        assert isinstance(restored, PatternTokenizer)


class TestKeywordTokenizer:
    def test_single_token(self):
        tok = KeywordTokenizer()
        assert tok.tokenize("hello world") == ["hello world"]

    def test_empty(self):
        tok = KeywordTokenizer()
        assert tok.tokenize("") == []


# ======================================================================
# Token Filters
# ======================================================================


class TestLowerCaseFilter:
    def test_basic(self):
        f = LowerCaseFilter()
        assert f.filter(["Hello", "WORLD"]) == ["hello", "world"]

    def test_roundtrip(self):
        f = LowerCaseFilter()
        d = f.to_dict()
        from uqa.analysis.token_filter import TokenFilter

        restored = TokenFilter.from_dict(d)
        assert isinstance(restored, LowerCaseFilter)


class TestStopWordFilter:
    def test_english_defaults(self):
        f = StopWordFilter()
        result = f.filter(["the", "quick", "brown", "fox"])
        assert result == ["quick", "brown", "fox"]

    def test_custom_words(self):
        f = StopWordFilter(custom_words={"quick"})
        result = f.filter(["the", "quick", "brown"])
        assert result == ["brown"]  # "the" and "quick" both removed

    def test_roundtrip(self):
        f = StopWordFilter("english", custom_words={"extra"})
        d = f.to_dict()
        from uqa.analysis.token_filter import TokenFilter

        restored = TokenFilter.from_dict(d)
        assert isinstance(restored, StopWordFilter)
        assert restored.filter(["extra"]) == []


class TestPorterStemFilter:
    def test_basic_stemming(self):
        f = PorterStemFilter()
        assert f.filter(["running"]) == ["run"]
        assert f.filter(["cats"]) == ["cat"]

    def test_complex_stemming(self):
        f = PorterStemFilter()
        result = f.filter(["connections", "generalization", "relational"])
        assert "connect" in result
        assert "gener" in result


class TestASCIIFoldingFilter:
    def test_accented_chars(self):
        f = ASCIIFoldingFilter()
        assert f.filter(["cafe"]) == ["cafe"]

    def test_roundtrip(self):
        f = ASCIIFoldingFilter()
        d = f.to_dict()
        from uqa.analysis.token_filter import TokenFilter

        restored = TokenFilter.from_dict(d)
        assert isinstance(restored, ASCIIFoldingFilter)


class TestSynonymFilter:
    def test_expansion(self):
        f = SynonymFilter({"fast": ["quick", "rapid"]})
        result = f.filter(["fast", "car"])
        assert result == ["fast", "quick", "rapid", "car"]

    def test_no_match(self):
        f = SynonymFilter({"fast": ["quick"]})
        result = f.filter(["slow", "car"])
        assert result == ["slow", "car"]

    def test_roundtrip(self):
        f = SynonymFilter({"a": ["b"]})
        d = f.to_dict()
        from uqa.analysis.token_filter import TokenFilter

        restored = TokenFilter.from_dict(d)
        assert isinstance(restored, SynonymFilter)


class TestNGramFilter:
    def test_default(self):
        from uqa.analysis.token_filter import NGramFilter

        f = NGramFilter(min_gram=2, max_gram=3)
        result = f.filter(["hello"])
        assert "he" in result
        assert "el" in result
        assert "ll" in result
        assert "lo" in result
        assert "hel" in result
        assert "ell" in result
        assert "llo" in result

    def test_short_token_dropped(self):
        from uqa.analysis.token_filter import NGramFilter

        f = NGramFilter(min_gram=2, max_gram=3)
        assert f.filter(["a"]) == []

    def test_keep_short(self):
        from uqa.analysis.token_filter import NGramFilter

        f = NGramFilter(min_gram=2, max_gram=3, keep_short=True)
        result = f.filter(["a", "hello"])
        assert result[0] == "a"
        assert "he" in result

    def test_keep_short_mixed(self):
        from uqa.analysis.token_filter import NGramFilter

        f = NGramFilter(min_gram=3, max_gram=4, keep_short=True)
        result = f.filter(["ab", "cd", "hello"])
        assert "ab" in result
        assert "cd" in result
        assert "hel" in result

    def test_roundtrip(self):
        from uqa.analysis.token_filter import NGramFilter

        f = NGramFilter(min_gram=2, max_gram=4)
        d = f.to_dict()
        assert d == {"type": "ngram", "min_gram": 2, "max_gram": 4}
        assert "keep_short" not in d
        from uqa.analysis.token_filter import TokenFilter

        restored = TokenFilter.from_dict(d)
        assert isinstance(restored, NGramFilter)
        assert restored.filter(["abc"]) == f.filter(["abc"])

    def test_roundtrip_keep_short(self):
        from uqa.analysis.token_filter import NGramFilter, TokenFilter

        f = NGramFilter(min_gram=2, max_gram=3, keep_short=True)
        d = f.to_dict()
        assert d["keep_short"] is True
        restored = TokenFilter.from_dict(d)
        assert restored.filter(["a"]) == ["a"]

    def test_validation(self):
        import pytest

        from uqa.analysis.token_filter import NGramFilter

        with pytest.raises(ValueError):
            NGramFilter(min_gram=0)
        with pytest.raises(ValueError):
            NGramFilter(min_gram=3, max_gram=2)


class TestEdgeNGramFilter:
    def test_default(self):
        f = EdgeNGramFilter(min_gram=1, max_gram=3)
        result = f.filter(["hello"])
        assert result == ["h", "he", "hel"]

    def test_min_gram(self):
        f = EdgeNGramFilter(min_gram=2, max_gram=4)
        result = f.filter(["abc"])
        assert result == ["ab", "abc"]

    def test_roundtrip(self):
        f = EdgeNGramFilter(min_gram=2, max_gram=5)
        d = f.to_dict()
        from uqa.analysis.token_filter import TokenFilter

        restored = TokenFilter.from_dict(d)
        assert isinstance(restored, EdgeNGramFilter)


class TestLengthFilter:
    def test_min_length(self):
        f = LengthFilter(min_length=3)
        assert f.filter(["a", "ab", "abc", "abcd"]) == ["abc", "abcd"]

    def test_max_length(self):
        f = LengthFilter(max_length=3)
        assert f.filter(["a", "ab", "abc", "abcd"]) == ["a", "ab", "abc"]

    def test_both(self):
        f = LengthFilter(min_length=2, max_length=3)
        assert f.filter(["a", "ab", "abc", "abcd"]) == ["ab", "abc"]


# ======================================================================
# Char Filters
# ======================================================================


class TestHTMLStripCharFilter:
    def test_strip_tags(self):
        f = HTMLStripCharFilter()
        # Tags are replaced with spaces; surrounding whitespace is preserved
        result = f.filter("<p>Hello <b>world</b></p>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_no_tags(self):
        f = HTMLStripCharFilter()
        assert f.filter("plain text") == "plain text"

    def test_entities(self):
        f = HTMLStripCharFilter()
        assert f.filter("a &amp; b") == "a & b"

    def test_roundtrip(self):
        f = HTMLStripCharFilter()
        d = f.to_dict()
        from uqa.analysis.char_filter import CharFilter

        restored = CharFilter.from_dict(d)
        assert isinstance(restored, HTMLStripCharFilter)


class TestMappingCharFilter:
    def test_mapping(self):
        f = MappingCharFilter({"&": "and", "@": "at"})
        assert f.filter("you & me @ home") == "you and me at home"

    def test_roundtrip(self):
        f = MappingCharFilter({"x": "y"})
        d = f.to_dict()
        from uqa.analysis.char_filter import CharFilter

        restored = CharFilter.from_dict(d)
        assert isinstance(restored, MappingCharFilter)


class TestPatternReplaceCharFilter:
    def test_replace(self):
        f = PatternReplaceCharFilter(r"\d+", "#")
        assert f.filter("abc123def456") == "abc#def#"

    def test_roundtrip(self):
        f = PatternReplaceCharFilter(r"\s+", " ")
        d = f.to_dict()
        from uqa.analysis.char_filter import CharFilter

        restored = CharFilter.from_dict(d)
        assert isinstance(restored, PatternReplaceCharFilter)


# ======================================================================
# Analyzer
# ======================================================================


class TestAnalyzer:
    def test_default_analyzer_is_standard(self):
        """DEFAULT_ANALYZER uses the standard pipeline."""
        a = standard_analyzer()
        result = DEFAULT_ANALYZER.analyze("The Quick BROWN Fox")
        assert result == a.analyze("The Quick BROWN Fox")
        assert "the" not in result  # stop word removed
        assert "quick" in result
        assert "brown" in result
        assert "fox" in result

    def test_whitespace_analyzer(self):
        a = whitespace_analyzer()
        assert a.analyze("Hello World") == ["hello", "world"]

    def test_standard_analyzer(self):
        a = standard_analyzer()
        result = a.analyze("The quick brown fox")
        assert "the" not in result
        assert "quick" in result

    def test_standard_analyzer_stemming(self):
        a = standard_analyzer()
        result = a.analyze("Running transformers efficiently")
        assert "run" in result
        assert "transform" in result

    def test_standard_analyzer_ascii_folding(self):
        a = standard_analyzer()
        # Unicode accented characters fold to ASCII before stemming
        result = a.analyze("caf\u00e9 r\u00e9sum\u00e9")
        assert "cafe" in result
        assert "resum" in result

    def test_standard_cjk_analyzer(self):
        from uqa.analysis import standard_cjk_analyzer

        a = standard_cjk_analyzer()
        result = a.analyze("hello world")
        assert "he" in result
        assert "hel" in result
        assert "wo" in result
        assert "wor" in result

    def test_standard_cjk_analyzer_stemming(self):
        from uqa.analysis import standard_cjk_analyzer

        a = standard_cjk_analyzer()
        result = a.analyze("Running")
        assert "ru" in result
        assert "run" in result

    def test_standard_cjk_analyzer_keep_short(self):
        """Short tokens (< min_gram) are preserved by keep_short=True."""
        from uqa.analysis import standard_cjk_analyzer

        a = standard_cjk_analyzer()
        # "x marks" -> tokenize -> ["x", "marks"] -> lower -> ["x", "marks"]
        # -> ascii_fold -> ["x", "marks"] -> stop -> ["x", "marks"]
        # -> stem -> ["x", "mark"] -> ngram(2,3, keep_short=True)
        # "x" (len 1 < min_gram 2) preserved by keep_short
        result = a.analyze("x marks")
        assert "x" in result
        assert "ma" in result
        assert "mar" in result

    def test_keyword_analyzer(self):
        a = keyword_analyzer()
        assert a.analyze("hello world") == ["hello world"]

    def test_custom_pipeline(self):
        a = Analyzer(
            tokenizer=StandardTokenizer(),
            token_filters=[LowerCaseFilter(), PorterStemFilter()],
            char_filters=[HTMLStripCharFilter()],
        )
        result = a.analyze("<p>Running Connections</p>")
        assert "run" in result
        assert "connect" in result

    def test_serialization_roundtrip(self):
        a = Analyzer(
            tokenizer=StandardTokenizer(),
            token_filters=[LowerCaseFilter(), StopWordFilter("english")],
            char_filters=[HTMLStripCharFilter()],
        )
        d = a.to_dict()
        restored = Analyzer.from_dict(d)
        text = "<p>The quick brown fox</p>"
        assert restored.analyze(text) == a.analyze(text)

    def test_json_roundtrip(self):
        a = standard_analyzer()
        j = a.to_json()
        restored = Analyzer.from_json(j)
        text = "The quick brown fox"
        assert restored.analyze(text) == a.analyze(text)


# ======================================================================
# Named Analyzer Registry
# ======================================================================


class TestAnalyzerRegistry:
    def test_builtin_analyzers(self):
        names = list_analyzers()
        assert "whitespace" in names
        assert "standard" in names
        assert "standard_cjk" in names
        assert "keyword" in names

    def test_register_and_get(self):
        custom = Analyzer(
            tokenizer=LetterTokenizer(),
            token_filters=[LowerCaseFilter()],
        )
        register_analyzer("test_custom_reg", custom)
        try:
            retrieved = get_analyzer("test_custom_reg")
            assert retrieved.analyze("hello123world") == ["hello", "world"]
        finally:
            drop_analyzer("test_custom_reg")

    def test_cannot_overwrite_builtin(self):
        with pytest.raises(ValueError, match="built-in"):
            register_analyzer("standard", whitespace_analyzer())

    def test_cannot_drop_builtin(self):
        with pytest.raises(ValueError, match="built-in"):
            drop_analyzer("standard")

    def test_unknown_analyzer(self):
        with pytest.raises(ValueError, match="Unknown"):
            get_analyzer("nonexistent_analyzer_xyz")

    def test_drop_nonexistent(self):
        with pytest.raises(ValueError, match="does not exist"):
            drop_analyzer("nonexistent_analyzer_xyz")


# ======================================================================
# InvertedIndex Analyzer Integration
# ======================================================================


class TestInvertedIndexAnalyzer:
    def test_default_analyzer(self):
        idx = InvertedIndex()
        idx.add_document(1, {"title": "The Quick Brown Fox"})
        # Default is standard: stop words removed
        pl = idx.get_posting_list("title", "the")
        assert len(pl) == 0
        pl = idx.get_posting_list("title", "quick")
        assert len(pl) == 1

    def test_custom_analyzer(self):
        a = standard_analyzer()
        idx = InvertedIndex(analyzer=a)
        idx.add_document(1, {"title": "The Quick Brown Fox"})
        # "the" is a stop word -- should not be indexed
        pl = idx.get_posting_list("title", "the")
        assert len(pl) == 0
        pl = idx.get_posting_list("title", "quick")
        assert len(pl) == 1

    def test_per_field_analyzer(self):
        idx = InvertedIndex()
        idx.set_field_analyzer("title", standard_analyzer())
        idx.set_field_analyzer("body", whitespace_analyzer())
        idx.add_document(1, {"title": "The Quick Fox", "body": "The body"})
        # "the" removed from title (standard) but kept in body (whitespace)
        assert len(idx.get_posting_list("title", "the")) == 0
        assert len(idx.get_posting_list("body", "the")) == 1

    def test_get_field_analyzer(self):
        idx = InvertedIndex()
        assert idx.get_field_analyzer("title") is idx.analyzer
        custom = keyword_analyzer()
        idx.set_field_analyzer("title", custom)
        assert idx.get_field_analyzer("title") is custom
        assert idx.get_field_analyzer("body") is idx.analyzer


class TestSQLiteInvertedIndexAnalyzer:
    def _make_index(self, tmp_path: Path) -> SQLiteInvertedIndex:
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        return SQLiteInvertedIndex(conn, "test_table")

    def test_default_analyzer(self, tmp_path):
        idx = self._make_index(tmp_path)
        idx.add_document(1, {"title": "Hello World"})
        pl = idx.get_posting_list("title", "hello")
        assert len(pl) == 1

    def test_custom_analyzer(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        idx = SQLiteInvertedIndex(conn, "test_table", analyzer=standard_analyzer())
        idx.add_document(1, {"title": "The Quick Brown Fox"})
        assert len(idx.get_posting_list("title", "the")) == 0
        assert len(idx.get_posting_list("title", "quick")) == 1

    def test_per_field_analyzer(self, tmp_path):
        idx = self._make_index(tmp_path)
        idx.set_field_analyzer("title", standard_analyzer())
        idx.set_field_analyzer("body", whitespace_analyzer())
        idx.add_document(1, {"title": "The Quick Fox", "body": "The body text"})
        assert len(idx.get_posting_list("title", "the")) == 0
        assert len(idx.get_posting_list("body", "the")) == 1

    def test_tokenize_uses_analyzer(self, tmp_path):
        idx = self._make_index(tmp_path)
        # Default analyzer: standard (lowercase + stop words + stem)
        tokens = idx._tokenize("Hello World", "title")
        assert tokens == ["hello", "world"]

        # Custom field analyzer
        idx.set_field_analyzer("title", keyword_analyzer())
        tokens = idx._tokenize("Hello World", "title")
        assert tokens == ["Hello World"]


# ======================================================================
# SQL Table Functions
# ======================================================================


class TestAnalyzerSQL:
    def _engine(self):
        from uqa.engine import Engine

        return Engine()

    def test_create_and_list_analyzers(self):
        engine = self._engine()
        config = {
            "tokenizer": {"type": "standard"},
            "token_filters": [{"type": "lowercase"}],
            "char_filters": [],
        }
        result = engine.sql(
            f"SELECT * FROM create_analyzer('my_test_analyzer', '{json.dumps(config)}')"
        )
        assert len(result.rows) == 1
        assert "created" in result.rows[0]["create_analyzer"]

        result = engine.sql("SELECT * FROM list_analyzers()")
        names = [r["analyzer_name"] for r in result.rows]
        assert "my_test_analyzer" in names
        assert "standard" in names

        # Clean up
        result = engine.sql("SELECT * FROM drop_analyzer('my_test_analyzer')")
        assert "dropped" in result.rows[0]["drop_analyzer"]

    def test_analyzer_used_in_text_search(self):
        """Verify that text_search uses the inverted index's analyzer."""
        engine = self._engine()
        engine.sql(
            "CREATE TABLE articles (id SERIAL PRIMARY KEY, title TEXT, body TEXT)"
        )
        engine.sql(
            "INSERT INTO articles (title, body) VALUES "
            "('The Quick Brown Fox', 'jumps over the lazy dog')"
        )
        engine.sql(
            "INSERT INTO articles (title, body) VALUES "
            "('A slow turtle', 'walks carefully on the ground')"
        )
        # Default analyzer: whitespace + lowercase
        result = engine.sql(
            "SELECT * FROM text_search('quick fox', 'title', 'articles')"
        )
        assert len(result.rows) >= 1

    def test_query_builder_analyzer_integration(self):
        """QueryBuilder.score_bm25 uses the analyzer from inverted index."""
        from uqa.engine import Engine

        engine = Engine()
        engine.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, content TEXT)")
        engine.sql("INSERT INTO docs (content) VALUES ('hello world')")
        engine.sql("INSERT INTO docs (content) VALUES ('goodbye world')")

        results = (
            engine.query("docs")
            .term("hello", "content")
            .score_bm25("hello world")
            .execute()
        )
        assert len(results) >= 1


# ======================================================================
# Catalog Persistence
# ======================================================================


class TestAnalyzerCatalogPersistence:
    def test_save_and_load(self, tmp_path):
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")
        config = {
            "tokenizer": {"type": "standard"},
            "token_filters": [
                {"type": "lowercase"},
                {"type": "stop", "language": "english"},
            ],
            "char_filters": [],
        }

        # Create analyzer in first session
        with Engine(db_path=db) as engine:
            engine.create_analyzer("persistent_test_analyzer", config)
            names = list_analyzers()
            assert "persistent_test_analyzer" in names

        # Clean from global registry so reload proves catalog persistence
        try:
            drop_analyzer("persistent_test_analyzer")
        except ValueError:
            pass

        # Reopen and verify it was restored
        with Engine(db_path=db) as engine:
            analyzer = get_analyzer("persistent_test_analyzer")
            result = analyzer.analyze("The Quick Brown Fox")
            assert "the" not in result
            assert "quick" in result

        # Clean up
        try:
            drop_analyzer("persistent_test_analyzer")
        except ValueError:
            pass
