#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Text analysis pipeline examples using the Python API.

Demonstrates:
  - Built-in analyzers (whitespace, standard, keyword)
  - Custom analyzer composition (CharFilter + Tokenizer + TokenFilter)
  - Per-field analyzer assignment on InvertedIndex
  - Named analyzer registry (register, get, drop, list)
  - Serialization / deserialization roundtrip
  - Analyzer integration with BM25 scoring
  - Autocomplete with EdgeNGramFilter
  - Porter stemming for morphological normalization
"""

from uqa.analysis import (
    Analyzer,
    DEFAULT_ANALYZER,
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
from uqa.engine import Engine
from uqa.storage.inverted_index import InvertedIndex


print("=" * 70)
print("Text Analysis Pipeline Examples (Python API)")
print("=" * 70)


# ==================================================================
# 1. Built-in analyzers
# ==================================================================
print("\n--- 1. Built-in Analyzers ---")

text = "The Quick Brown Fox Jumps Over The Lazy Dog"

ws = whitespace_analyzer()
print(f"  whitespace : {ws.analyze(text)}")

std = standard_analyzer()
print(f"  standard   : {std.analyze(text)}")

kw = keyword_analyzer()
print(f"  keyword    : {kw.analyze(text)}")


# ==================================================================
# 2. DEFAULT_ANALYZER is standard
# ==================================================================
print("\n--- 2. DEFAULT_ANALYZER (standard) ---")
text2 = "The Quick BROWN Fox"
result2 = DEFAULT_ANALYZER.analyze(text2)
assert "the" not in result2  # stop word removed
assert "quick" in result2
print(f"  DEFAULT_ANALYZER.analyze('{text2}')")
print(f"  Result: {result2}")


# ==================================================================
# 3. Custom analyzer: HTML content indexer
# ==================================================================
print("\n--- 3. Custom Analyzer: HTML content indexer ---")

html_analyzer = Analyzer(
    char_filters=[
        HTMLStripCharFilter(),
        MappingCharFilter({"&": "and", "@": "at"}),
    ],
    tokenizer=StandardTokenizer(),
    token_filters=[
        LowerCaseFilter(),
        StopWordFilter("english"),
        LengthFilter(min_length=2),
    ],
)

html_text = "<p>The quick &amp; <b>brown fox</b> jumps @ night</p>"
tokens = html_analyzer.analyze(html_text)
print(f"  Input : {html_text}")
print(f"  Tokens: {tokens}")


# ==================================================================
# 4. Stemming analyzer
# ==================================================================
print("\n--- 4. Stemming Analyzer ---")

stem_analyzer = Analyzer(
    tokenizer=StandardTokenizer(),
    token_filters=[LowerCaseFilter(), PorterStemFilter()],
)

sentences = [
    "running connections generalization",
    "connected runners generalized",
    "run connect general",
]
for s in sentences:
    tokens = stem_analyzer.analyze(s)
    print(f"  '{s}' -> {tokens}")
print("  (Notice how different forms reduce to the same stem)")


# ==================================================================
# 5. Autocomplete analyzer with EdgeNGram
# ==================================================================
print("\n--- 5. Autocomplete Analyzer (EdgeNGram) ---")

autocomplete_analyzer = Analyzer(
    tokenizer=StandardTokenizer(),
    token_filters=[
        LowerCaseFilter(),
        EdgeNGramFilter(min_gram=2, max_gram=8),
    ],
)

word = "transformer"
tokens = autocomplete_analyzer.analyze(word)
print(f"  '{word}' -> {tokens}")
print("  (Each prefix enables typeahead matching)")


# ==================================================================
# 6. Synonym expansion
# ==================================================================
print("\n--- 6. Synonym Expansion ---")

synonym_analyzer = Analyzer(
    tokenizer=StandardTokenizer(),
    token_filters=[
        LowerCaseFilter(),
        SynonymFilter({
            "fast": ["quick", "rapid", "swift"],
            "big": ["large", "huge", "enormous"],
        }),
    ],
)

query = "fast big car"
tokens = synonym_analyzer.analyze(query)
print(f"  '{query}' -> {tokens}")


# ==================================================================
# 7. ASCII folding for accented text
# ==================================================================
print("\n--- 7. ASCII Folding ---")

folding_analyzer = Analyzer(
    tokenizer=StandardTokenizer(),
    token_filters=[LowerCaseFilter(), ASCIIFoldingFilter()],
)

for text in ["naive", "resume", "Zurich"]:
    tokens = folding_analyzer.analyze(text)
    print(f"  '{text}' -> {tokens}")


# ==================================================================
# 8. Pattern tokenizer: CSV fields
# ==================================================================
print("\n--- 8. Pattern Tokenizer (CSV) ---")

csv_analyzer = Analyzer(
    tokenizer=PatternTokenizer(pattern=r",\s*"),
    token_filters=[LowerCaseFilter()],
)

csv_line = "Alice, Bob, Charlie, Diana"
tokens = csv_analyzer.analyze(csv_line)
print(f"  '{csv_line}' -> {tokens}")


# ==================================================================
# 9. NGram tokenizer: fuzzy matching
# ==================================================================
print("\n--- 9. NGram Tokenizer (character bigrams) ---")

ngram_analyzer = Analyzer(
    tokenizer=NGramTokenizer(min_gram=2, max_gram=3),
    token_filters=[LowerCaseFilter()],
)

word = "search"
tokens = ngram_analyzer.analyze(word)
print(f"  '{word}' -> {tokens}")


# ==================================================================
# 10. Named analyzer registry
# ==================================================================
print("\n--- 10. Named Analyzer Registry ---")

print(f"  Built-in analyzers: {list_analyzers()}")

register_analyzer("html_search", html_analyzer)
register_analyzer("stemming", stem_analyzer)
print(f"  After registering 'html_search' and 'stemming': {list_analyzers()}")

retrieved = get_analyzer("stemming")
print(f"  get_analyzer('stemming').analyze('running') -> {retrieved.analyze('running')}")

drop_analyzer("html_search")
drop_analyzer("stemming")
print(f"  After cleanup: {list_analyzers()}")


# ==================================================================
# 11. Serialization roundtrip
# ==================================================================
print("\n--- 11. Serialization Roundtrip ---")

original = Analyzer(
    char_filters=[HTMLStripCharFilter()],
    tokenizer=StandardTokenizer(),
    token_filters=[
        LowerCaseFilter(),
        StopWordFilter("english"),
        PorterStemFilter(),
    ],
)

# Serialize to dict and JSON
config = original.to_dict()
json_str = original.to_json()
print(f"  Config dict keys: {list(config.keys())}")
print(f"  JSON length: {len(json_str)} chars")

# Deserialize and verify
restored = Analyzer.from_json(json_str)
test_text = "<p>The running connections are important</p>"
assert original.analyze(test_text) == restored.analyze(test_text)
print(f"  Original  -> {original.analyze(test_text)}")
print(f"  Restored  -> {restored.analyze(test_text)}")
print("  (Identical output -- roundtrip verified)")


# ==================================================================
# 12. Per-field analyzers on InvertedIndex
# ==================================================================
print("\n--- 12. Per-Field Analyzers on InvertedIndex ---")

idx = InvertedIndex()
idx.set_field_analyzer("title", standard_analyzer())
idx.set_field_analyzer("body", Analyzer(
    tokenizer=StandardTokenizer(),
    token_filters=[LowerCaseFilter(), PorterStemFilter()],
))

idx.add_document(1, {
    "title": "The Quick Brown Fox",
    "body": "Foxes are running through the forests",
})
idx.add_document(2, {
    "title": "A Lazy Dog Sleeps",
    "body": "Dogs sleeping lazily in the sun",
})

# 'the' is a stop word -- removed from title (standard analyzer)
# but NOT from body (no stop word filter, only stem)
pl = idx.get_posting_list("title", "the")
print(f"  title/'the'    -> {len(pl)} docs (stop word removed by standard)")
pl = idx.get_posting_list("body", "the")
print(f"  body/'the'     -> {len(pl)} docs (no stop filter on body)")

# Stemming: 'run' matches 'running' in body
pl = idx.get_posting_list("body", "run")
print(f"  body/'run'     -> {len(pl)} docs (stem of 'running')")
pl = idx.get_posting_list("body", "fox")
print(f"  body/'fox'     -> {len(pl)} docs (stem of 'foxes')")

# title still has exact lowercase match
pl = idx.get_posting_list("title", "quick")
print(f"  title/'quick'  -> {len(pl)} docs (standard tokenizer)")


# ==================================================================
# 13. BM25 scoring with custom analyzer
# ==================================================================
print("\n--- 13. BM25 Scoring with Custom Analyzer ---")

engine = Engine()

engine.sql("""
    CREATE TABLE papers (
        id SERIAL PRIMARY KEY,
        title TEXT,
        abstract TEXT,
        year INTEGER
    )
""")

papers = [
    ("Attention Is All You Need",
     "The dominant sequence transduction models are based on complex recurrent "
     "or convolutional neural networks. We propose a new simple network "
     "architecture the Transformer based solely on attention mechanisms.",
     2017),
    ("BERT Pre-training of Deep Bidirectional Transformers",
     "We introduce BERT a method for pre-training language representations. "
     "BERT is designed to pre-train deep bidirectional representations.",
     2019),
    ("GPT-3 Language Models are Few-Shot Learners",
     "Recent work has demonstrated substantial gains on NLP tasks via "
     "pre-training on large corpus of text followed by task-specific fine-tuning.",
     2020),
    ("Scaling Laws for Neural Language Models",
     "We study empirical scaling laws for language model performance. "
     "The loss scales as a power-law with model size dataset size and compute.",
     2020),
    ("Vision Transformers for Image Recognition",
     "We show that a pure transformer applied directly to sequences of image "
     "patches can perform very well on image classification tasks.",
     2021),
]

for title, abstract, year in papers:
    engine.sql(
        f"INSERT INTO papers (title, abstract, year) VALUES "
        f"('{title}', '{abstract}', {year})"
    )

# Default search: whitespace + lowercase
result = engine.sql(
    "SELECT title, _score AS relevance "
    "FROM text_search('transformer attention', 'abstract', 'papers') "
    "ORDER BY relevance DESC"
)
print("  Query: 'transformer attention'")
for row in result.rows:
    print(f"    {row['relevance']:.4f}  {row['title']}")


# ==================================================================
# 14. Engine-level analyzer management
# ==================================================================
print("\n--- 14. Engine-Level Analyzer Management ---")

config = {
    "tokenizer": {"type": "standard"},
    "token_filters": [
        {"type": "lowercase"},
        {"type": "stop", "language": "english"},
        {"type": "porter_stem"},
    ],
    "char_filters": [],
}
engine.create_analyzer("english_stem", config)
print("  Created analyzer 'english_stem'")

# Assign to a table field
engine.set_table_analyzer("papers", "abstract", "english_stem")
print("  Assigned 'english_stem' to papers.abstract")

# Verify the analyzer is active
analyzer = engine._tables["papers"].inverted_index.get_field_analyzer("abstract")
print(f"  Analyzer pipeline: {analyzer.analyze('The transformers are running')}")

# Clean up
engine.drop_analyzer("english_stem")
print("  Dropped 'english_stem'")


print("\n" + "=" * 70)
print("All text analysis examples completed successfully.")
print("=" * 70)
