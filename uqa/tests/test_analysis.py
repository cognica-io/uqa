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
from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex
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

    def test_requires_synonyms_or_path(self):
        with pytest.raises(ValueError, match="must be provided"):
            SynonymFilter()

    def test_cannot_specify_both(self):
        with pytest.raises(ValueError, match="not both"):
            SynonymFilter(synonyms={"a": ["b"]}, synonyms_path="/tmp/s.txt")


class TestSynonymFilterFile:
    """Test file-based synonym loading."""

    def test_explicit_mapping(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text(
            "# vehicle synonyms\ncar => automobile, vehicle\nfast => quick, speedy\n"
        )
        f = SynonymFilter(synonyms_path=syn_file)
        assert f.filter(["car"]) == ["car", "automobile", "vehicle"]
        assert f.filter(["fast"]) == ["fast", "quick", "speedy"]
        assert f.filter(["slow"]) == ["slow"]

    def test_equivalent_synonyms(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text("car, automobile, vehicle\n")
        f = SynonymFilter(synonyms_path=syn_file)
        assert f.filter(["car"]) == ["car", "automobile", "vehicle"]
        assert f.filter(["automobile"]) == ["automobile", "car", "vehicle"]
        assert f.filter(["vehicle"]) == ["vehicle", "car", "automobile"]

    def test_mixed_formats(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text(
            "# explicit\nbig => large\n\n# equivalent\nfast, quick, speedy\n"
        )
        f = SynonymFilter(synonyms_path=syn_file)
        assert f.filter(["big"]) == ["big", "large"]
        assert f.filter(["large"]) == ["large"]  # explicit is one-way
        assert f.filter(["fast"]) == ["fast", "quick", "speedy"]
        assert f.filter(["quick"]) == ["quick", "fast", "speedy"]

    def test_blank_lines_and_comments(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text("# this is a comment\n\n   \n# another comment\na => b\n")
        f = SynonymFilter(synonyms_path=syn_file)
        assert f.filter(["a"]) == ["a", "b"]

    def test_deduplication(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text("car => automobile\ncar => automobile, vehicle\n")
        f = SynonymFilter(synonyms_path=syn_file)
        assert f.filter(["car"]) == ["car", "automobile", "vehicle"]

    def test_serialization_roundtrip(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text("car => automobile\n")
        f = SynonymFilter(synonyms_path=syn_file)
        d = f.to_dict()
        assert "synonyms_path" in d
        assert "synonyms" not in d

        from uqa.analysis.token_filter import TokenFilter

        restored = TokenFilter.from_dict(d)
        assert isinstance(restored, SynonymFilter)
        assert restored.filter(["car"]) == ["car", "automobile"]

    def test_inline_does_not_serialize_path(self):
        f = SynonymFilter(synonyms={"a": ["b"]})
        d = f.to_dict()
        assert "synonyms" in d
        assert "synonyms_path" not in d

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            SynonymFilter(synonyms_path=tmp_path / "nonexistent.txt")

    def test_single_term_line_ignored(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text("lonely\ncar, automobile\n")
        f = SynonymFilter(synonyms_path=syn_file)
        assert f.filter(["lonely"]) == ["lonely"]
        assert f.filter(["car"]) == ["car", "automobile"]

    def test_sql_create_analyzer_with_path(self, tmp_path: Path):
        syn_file = tmp_path / "synonyms.txt"
        syn_file.write_text("car, automobile, vehicle\n")
        from uqa.engine import Engine

        engine = Engine()
        config = json.dumps(
            {
                "tokenizer": {"type": "standard"},
                "token_filters": [
                    {"type": "lowercase"},
                    {"type": "synonym", "synonyms_path": str(syn_file)},
                ],
            }
        )
        engine.sql(f"SELECT * FROM create_analyzer('file_syn', '{config}')")
        engine.sql("CREATE TABLE docs (id INT, body TEXT)")
        engine.sql("CREATE INDEX idx_docs_gin ON docs USING gin (body)")
        engine.set_table_analyzer("docs", "body", "file_syn", phase="search")
        engine.sql("INSERT INTO docs (id, body) VALUES (1, 'a fast car for commuting')")
        # "automobile" expands to ["automobile", "car", "vehicle"] at search time
        result = engine.sql("SELECT id FROM docs WHERE text_match(body, 'automobile')")
        assert len(result.rows) == 1
        from uqa.analysis.analyzer import drop_analyzer

        drop_analyzer("file_syn")


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
        engine.sql("CREATE INDEX idx_articles_gin ON articles USING gin (title, body)")
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
        engine.sql("CREATE INDEX idx_docs_gin ON docs USING gin (content)")
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


# ---- Dual (index/search) analyzer tests --------------------------------


class TestDualAnalyzer:
    """Test index-time vs search-time analyzer separation."""

    def test_inverted_index_default_phase(self):
        """set_field_analyzer with phase='both' sets both dicts."""
        from uqa.analysis.analyzer import standard_analyzer
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx = InvertedIndex()
        analyzer = standard_analyzer()
        idx.set_field_analyzer("body", analyzer, phase="both")
        assert idx.get_field_analyzer("body") is analyzer
        assert idx.get_search_analyzer("body") is analyzer

    def test_inverted_index_separate_phases(self):
        """Index and search analyzers can differ for the same field."""
        from uqa.analysis.analyzer import Analyzer
        from uqa.analysis.token_filter import LowerCaseFilter, SynonymFilter
        from uqa.analysis.tokenizer import WhitespaceTokenizer
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx_analyzer = Analyzer(WhitespaceTokenizer(), [LowerCaseFilter()])
        search_analyzer = Analyzer(
            WhitespaceTokenizer(),
            [LowerCaseFilter(), SynonymFilter({"car": ["automobile"]})],
        )
        idx = InvertedIndex()
        idx.set_field_analyzer("body", idx_analyzer, phase="index")
        idx.set_field_analyzer("body", search_analyzer, phase="search")

        assert idx.get_field_analyzer("body") is idx_analyzer
        assert idx.get_search_analyzer("body") is search_analyzer

    def test_search_falls_back_to_index(self):
        """When no search analyzer is set, fall back to index analyzer."""
        from uqa.analysis.analyzer import standard_analyzer
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx = InvertedIndex()
        analyzer = standard_analyzer()
        idx.set_field_analyzer("body", analyzer, phase="index")
        assert idx.get_search_analyzer("body") is analyzer

    def test_search_falls_back_to_default(self):
        """When neither search nor index analyzer is set, use default."""
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx = InvertedIndex()
        default = idx.analyzer
        assert idx.get_search_analyzer("body") is default

    def test_invalid_phase(self):
        from uqa.analysis.analyzer import standard_analyzer
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx = InvertedIndex()
        with pytest.raises(ValueError, match="phase must be"):
            idx.set_field_analyzer("body", standard_analyzer(), phase="bad")

    def test_sqlite_inverted_index_dual_analyzer(self):
        """SQLiteInvertedIndex supports the same dual-analyzer API."""
        from uqa.analysis.analyzer import Analyzer
        from uqa.analysis.token_filter import LowerCaseFilter, SynonymFilter
        from uqa.analysis.tokenizer import WhitespaceTokenizer
        from uqa.storage.sqlite_inverted_index import SQLiteInvertedIndex

        conn = sqlite3.connect(":memory:")
        idx = SQLiteInvertedIndex(conn, "test")

        idx_analyzer = Analyzer(WhitespaceTokenizer(), [LowerCaseFilter()])
        search_analyzer = Analyzer(
            WhitespaceTokenizer(),
            [LowerCaseFilter(), SynonymFilter({"car": ["auto"]})],
        )
        idx.set_field_analyzer("body", idx_analyzer, phase="index")
        idx.set_field_analyzer("body", search_analyzer, phase="search")

        assert idx.get_field_analyzer("body") is idx_analyzer
        assert idx.get_search_analyzer("body") is search_analyzer
        conn.close()

    def test_backward_compat_no_phase(self):
        """Calling set_field_analyzer without phase sets both (backward compat)."""
        from uqa.analysis.analyzer import standard_analyzer
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx = InvertedIndex()
        analyzer = standard_analyzer()
        idx.set_field_analyzer("body", analyzer)
        assert idx.get_field_analyzer("body") is analyzer
        assert idx.get_search_analyzer("body") is analyzer


class TestTermOperatorSynonymUnion:
    """Test that TermOperator unions synonym-expanded tokens."""

    def test_synonym_expansion_finds_documents(self):
        """Search-time synonym expansion via TermOperator uses union."""
        from uqa.analysis.analyzer import Analyzer
        from uqa.analysis.token_filter import LowerCaseFilter, SynonymFilter
        from uqa.analysis.tokenizer import WhitespaceTokenizer
        from uqa.operators.base import ExecutionContext
        from uqa.operators.primitive import TermOperator
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx = InvertedIndex()
        idx_analyzer = Analyzer(WhitespaceTokenizer(), [LowerCaseFilter()])
        search_analyzer = Analyzer(
            WhitespaceTokenizer(),
            [LowerCaseFilter(), SynonymFilter({"automobile": ["car"]})],
        )
        idx.set_field_analyzer("body", idx_analyzer, phase="index")
        idx.set_field_analyzer("body", search_analyzer, phase="search")

        # Index with "car" (no synonym expansion at index time)
        idx.add_document(1, {"body": "used car for sale"})
        idx.add_document(2, {"body": "new bike for sale"})

        ctx = ExecutionContext(inverted_index=idx)
        op = TermOperator("automobile", field="body")
        result = op.execute(ctx)

        # "automobile" expands to ["automobile", "car"] via search analyzer
        # "car" matches doc 1; "automobile" matches nothing
        # Union: doc 1 found
        doc_ids = [e.doc_id for e in result]
        assert 1 in doc_ids
        assert 2 not in doc_ids

    def test_no_synonym_single_token(self):
        """Single token (no expansion) still works correctly."""
        from uqa.operators.base import ExecutionContext
        from uqa.operators.primitive import TermOperator
        from uqa.storage.inverted_index import MemoryInvertedIndex as InvertedIndex

        idx = InvertedIndex()
        idx.add_document(1, {"body": "used car for sale"})

        ctx = ExecutionContext(inverted_index=idx)
        op = TermOperator("car", field="body")
        result = op.execute(ctx)
        doc_ids = [e.doc_id for e in result]
        assert 1 in doc_ids


class TestDualAnalyzerCatalogPersistence:
    """Test that field-to-analyzer mappings survive engine restart."""

    def test_field_analyzer_persisted(self, tmp_path: Path):
        from uqa.analysis.analyzer import drop_analyzer
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")

        # Session 1: create analyzer + assign to field
        with Engine(db_path=db) as engine:
            engine.sql(
                "SELECT * FROM create_analyzer('my_stem', "
                '\'{"tokenizer": {"type": "standard"}, '
                '"token_filters": [{"type": "lowercase"}, '
                '{"type": "porter_stem"}]}\')'
            )
            engine.sql("CREATE TABLE docs (id INT, body TEXT)")
            engine.set_table_analyzer("docs", "body", "my_stem", phase="index")

        # Session 2: verify it was restored
        with Engine(db_path=db) as engine:
            analyzer = engine.get_table_analyzer("docs", "body", phase="index")
            result = analyzer.analyze("running connections")
            assert "run" in result
            assert "connect" in result

        try:
            drop_analyzer("my_stem")
        except ValueError:
            pass

    def test_search_analyzer_persisted(self, tmp_path: Path):
        from uqa.analysis.analyzer import drop_analyzer
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")

        with Engine(db_path=db) as engine:
            engine.sql(
                "SELECT * FROM create_analyzer('syn_search', "
                '\'{"tokenizer": {"type": "whitespace"}, '
                '"token_filters": [{"type": "lowercase"}, '
                '{"type": "synonym", "synonyms": '
                '{"car": ["automobile"]}}]}\')'
            )
            engine.sql("CREATE TABLE docs (id INT, body TEXT)")
            engine.set_table_analyzer("docs", "body", "syn_search", phase="search")

        with Engine(db_path=db) as engine:
            analyzer = engine.get_table_analyzer("docs", "body", phase="search")
            result = analyzer.analyze("car")
            assert "automobile" in result

        try:
            drop_analyzer("syn_search")
        except ValueError:
            pass

    def test_drop_table_removes_field_analyzers(self, tmp_path: Path):
        from uqa.analysis.analyzer import drop_analyzer
        from uqa.engine import Engine

        db = str(tmp_path / "test.db")

        with Engine(db_path=db) as engine:
            engine.sql(
                "SELECT * FROM create_analyzer('my_a', "
                '\'{"tokenizer": {"type": "standard"}, '
                '"token_filters": [{"type": "lowercase"}]}\')'
            )
            engine.sql("CREATE TABLE docs (id INT, body TEXT)")
            engine.set_table_analyzer("docs", "body", "my_a")
            engine.sql("DROP TABLE docs")

        # Reopen: no crash, table is gone
        with Engine(db_path=db) as engine:
            assert "docs" not in engine._tables

        try:
            drop_analyzer("my_a")
        except ValueError:
            pass


class TestSetTableAnalyzerSQL:
    """Test the SQL set_table_analyzer() table function."""

    def test_set_table_analyzer_default_phase(self):
        from uqa.engine import Engine

        engine = Engine()
        engine.sql(
            "SELECT * FROM create_analyzer('test_lower', "
            '\'{"tokenizer": {"type": "standard"}, '
            '"token_filters": [{"type": "lowercase"}]}\')'
        )
        engine.sql("CREATE TABLE t (id INT, body TEXT)")
        result = engine.sql(
            "SELECT * FROM set_table_analyzer('t', 'body', 'test_lower')"
        )
        assert len(result) == 1
        assert "assigned" in str(result.rows[0])

        from uqa.analysis.analyzer import drop_analyzer

        drop_analyzer("test_lower")

    def test_set_table_analyzer_with_phase(self):
        from uqa.engine import Engine

        engine = Engine()
        engine.sql(
            "SELECT * FROM create_analyzer('test_syn', "
            '\'{"tokenizer": {"type": "whitespace"}, '
            '"token_filters": [{"type": "lowercase"}, '
            '{"type": "synonym", "synonyms": '
            '{"fast": ["quick"]}}]}\')'
        )
        engine.sql("CREATE TABLE t (id INT, body TEXT)")
        result = engine.sql(
            "SELECT * FROM set_table_analyzer('t', 'body', 'test_syn', 'search')"
        )
        assert len(result) == 1
        assert "phase=search" in str(result.rows[0])

        # Verify search analyzer is set
        analyzer = engine.get_table_analyzer("t", "body", phase="search")
        tokens = analyzer.analyze("fast")
        assert "quick" in tokens

        from uqa.analysis.analyzer import drop_analyzer

        drop_analyzer("test_syn")
