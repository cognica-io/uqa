#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Search result highlighting for full-text queries.

Provides term markup and fragment extraction for displaying search
results with matched terms visually emphasized.

The highlighter re-tokenizes the original text to locate word
boundaries, runs each token through the same analysis pipeline used
for indexing, and checks whether the analyzed form matches any query
term.  Matched spans are wrapped with configurable tags.

When *max_fragments* > 0, only the best snippets around matches are
returned instead of the full text.
"""

from __future__ import annotations

import re
from typing import Any

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def extract_query_terms(query_string: str) -> list[str]:
    """Extract searchable terms from an FTS query string.

    Parses the query using the FTS grammar and collects all term and
    phrase tokens, ignoring boolean operators and vector literals.
    """
    from uqa.sql.fts_query import (
        FTSParser,
        tokenize,
    )

    try:
        tokens = tokenize(query_string)
        ast = FTSParser(tokens).parse()
    except (ValueError, IndexError):
        # Fallback: treat the whole string as space-separated terms
        return [
            t for t in query_string.split() if t.lower() not in ("and", "or", "not")
        ]

    terms: list[str] = []
    _collect_terms(ast, terms)
    return terms


def _collect_terms(node: Any, out: list[str]) -> None:
    """Walk the FTS AST and collect all term/phrase text."""
    from uqa.sql.fts_query import (
        AndNode,
        NotNode,
        OrNode,
        PhraseNode,
        TermNode,
    )

    if isinstance(node, TermNode):
        out.append(node.term)
    elif isinstance(node, PhraseNode):
        out.extend(node.phrase.split())
    elif isinstance(node, AndNode):
        _collect_terms(node.left, out)
        _collect_terms(node.right, out)
    elif isinstance(node, OrNode):
        _collect_terms(node.left, out)
        _collect_terms(node.right, out)
    elif isinstance(node, NotNode):
        _collect_terms(node.operand, out)
    # VectorNode: no text terms to collect


def highlight(
    text: str,
    query_terms: list[str],
    *,
    start_tag: str = "<b>",
    end_tag: str = "</b>",
    max_fragments: int = 0,
    fragment_size: int = 150,
    analyzer: Any = None,
) -> str:
    """Highlight query terms in the original text.

    Tokenizes *text* to find word boundaries, checks each token against
    *query_terms* after applying the *analyzer* (or simple lowercasing
    when no analyzer is provided), and wraps matching spans with
    *start_tag* / *end_tag*.

    When *max_fragments* > 0, extracts the best fragments around matches
    instead of returning the full text.  Each fragment is at most
    *fragment_size* characters.

    Returns the original text unmodified when *query_terms* is empty.
    """
    if not text or not query_terms:
        return text or ""

    # Build the set of analyzed query terms for matching
    analyzed_terms: set[str] = set()
    if analyzer is not None:
        for qt in query_terms:
            for t in analyzer.analyze(qt):
                analyzed_terms.add(t)
    else:
        for qt in query_terms:
            analyzed_terms.add(qt.lower())

    if not analyzed_terms:
        return text

    # Tokenize the original text to get (start, end) character offsets
    match_spans: list[tuple[int, int]] = []
    for m in _WORD_RE.finditer(text):
        token = m.group()
        if analyzer is not None:
            analyzed = analyzer.analyze(token)
            if analyzed and any(t in analyzed_terms for t in analyzed):
                match_spans.append((m.start(), m.end()))
        else:
            if token.lower() in analyzed_terms:
                match_spans.append((m.start(), m.end()))

    if not match_spans:
        if max_fragments > 0:
            end = min(len(text), fragment_size)
            suffix = "..." if end < len(text) else ""
            return text[:end] + suffix
        return text

    if max_fragments > 0:
        return _build_fragments(
            text, match_spans, start_tag, end_tag, max_fragments, fragment_size
        )

    return _build_full_highlight(text, match_spans, start_tag, end_tag)


def _build_full_highlight(
    text: str,
    match_spans: list[tuple[int, int]],
    start_tag: str,
    end_tag: str,
) -> str:
    """Build the full text with matched spans wrapped in tags."""
    parts: list[str] = []
    prev_end = 0
    for start, end in match_spans:
        parts.append(text[prev_end:start])
        parts.append(start_tag)
        parts.append(text[start:end])
        parts.append(end_tag)
        prev_end = end
    parts.append(text[prev_end:])
    return "".join(parts)


def _build_fragments(
    text: str,
    match_spans: list[tuple[int, int]],
    start_tag: str,
    end_tag: str,
    max_fragments: int,
    fragment_size: int,
) -> str:
    """Extract and highlight the best fragments around matches."""
    half = fragment_size // 2

    # Group nearby matches into clusters
    clusters: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for span in match_spans:
        if current and span[0] - current[-1][1] > half:
            clusters.append(current)
            current = [span]
        else:
            current.append(span)
    if current:
        clusters.append(current)

    # Select top clusters by match density, then sort by position
    clusters.sort(key=lambda c: len(c), reverse=True)
    selected = clusters[:max_fragments]
    selected.sort(key=lambda c: c[0][0])

    fragments: list[str] = []
    for cluster in selected:
        center = (cluster[0][0] + cluster[-1][1]) // 2
        frag_start = max(0, center - half)
        frag_end = min(len(text), center + half)

        # Snap to word boundaries
        if frag_start > 0:
            space = text.find(" ", frag_start)
            if space != -1 and space < frag_start + 30:
                frag_start = space + 1
        if frag_end < len(text):
            space = text.rfind(" ", frag_end - 30, frag_end)
            if space != -1:
                frag_end = space

        # Collect match spans within this fragment
        frag_matches = [
            (s - frag_start, e - frag_start)
            for s, e in cluster
            if s >= frag_start and e <= frag_end
        ]
        frag_text = text[frag_start:frag_end]
        highlighted = _build_full_highlight(frag_text, frag_matches, start_tag, end_tag)

        prefix = "..." if frag_start > 0 else ""
        suffix = "..." if frag_end < len(text) else ""
        fragments.append(f"{prefix}{highlighted}{suffix}")

    return " ".join(fragments)
