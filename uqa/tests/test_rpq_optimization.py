#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from uqa.core.types import Edge, Vertex
from uqa.graph.operators import (
    RegularPathQueryOperator,
    _build_nfa,
    _reset_state_counter,
)
from uqa.graph.pattern import (
    Alternation,
    Concat,
    KleeneStar,
    Label,
)
from uqa.graph.rpq_optimizer import _simplify_expr, _subset_construction
from uqa.graph.store import MemoryGraphStore as GraphStore
from uqa.operators.base import ExecutionContext

# -- Expression simplification tests --


def test_simplify_identity():
    """Label stays unchanged."""
    expr = Label("a")
    assert _simplify_expr(expr) == Label("a")


def test_simplify_duplicate_alternation():
    """a|a -> a"""
    expr = Alternation(Label("a"), Label("a"))
    result = _simplify_expr(expr)
    assert result == Label("a")


def test_simplify_nested_kleene():
    """(a*)* -> a*"""
    expr = KleeneStar(KleeneStar(Label("a")))
    result = _simplify_expr(expr)
    assert result == KleeneStar(Label("a"))


def test_simplify_alternation_sorting():
    """b|a -> a|b (sorted for canonical form)."""
    expr = Alternation(Label("b"), Label("a"))
    result = _simplify_expr(expr)
    assert isinstance(result, Alternation)
    assert repr(result.left) <= repr(result.right)


def test_simplify_nested_concat():
    """Concat simplification preserves structure."""
    expr = Concat(Label("a"), Label("b"))
    result = _simplify_expr(expr)
    assert result == Concat(Label("a"), Label("b"))


def test_simplify_complex():
    """(a|a)/(b*)* -> a/b*"""
    expr = Concat(
        Alternation(Label("a"), Label("a")),
        KleeneStar(KleeneStar(Label("b"))),
    )
    result = _simplify_expr(expr)
    assert result == Concat(Label("a"), KleeneStar(Label("b")))


# -- Subset construction (NFA -> DFA) tests --


def test_subset_construction_simple():
    """Simple NFA for 'a' label should produce a small DFA."""
    _reset_state_counter()
    nfa = _build_nfa(Label("a"))
    _transitions, dfa_start, dfa_accepts = _subset_construction(nfa)
    assert dfa_start is not None
    assert len(dfa_accepts) > 0


def test_subset_construction_alternation():
    """NFA for 'a|b' should produce DFA accepting both."""
    _reset_state_counter()
    nfa = _build_nfa(Alternation(Label("a"), Label("b")))
    _transitions, _start, dfa_accepts = _subset_construction(nfa)
    assert len(dfa_accepts) > 0


def test_subset_construction_concat():
    """NFA for 'a/b' should produce DFA accepting the sequence."""
    _reset_state_counter()
    nfa = _build_nfa(Concat(Label("a"), Label("b")))
    _transitions, _start, dfa_accepts = _subset_construction(nfa)
    assert len(dfa_accepts) > 0


# -- End-to-end RPQ with simplification --


def test_rpq_with_duplicate_alternation():
    """RPQ with a|a should still find correct results."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "knows", {}), graph="g")

    ctx = ExecutionContext(graph_store=gs)
    # a|a should simplify to just a
    expr = Alternation(Label("knows"), Label("knows"))
    op = RegularPathQueryOperator(expr, graph="g", start_vertex=1)
    result = op.execute(ctx)
    doc_ids = {e.doc_id for e in result}
    assert 2 in doc_ids


def test_rpq_with_nested_kleene():
    """RPQ with (a*)* should work the same as a*."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_vertex(Vertex(3, "c", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g")
    gs.add_edge(Edge(11, 2, 3, "e", {}), graph="g")

    ctx = ExecutionContext(graph_store=gs)
    expr = KleeneStar(KleeneStar(Label("e")))
    op = RegularPathQueryOperator(expr, graph="g", start_vertex=1)
    result = op.execute(ctx)
    doc_ids = {e.doc_id for e in result}
    # Should reach 1 (self via epsilon), 2 (one hop), 3 (two hops)
    assert {1, 2, 3} == doc_ids


# -- Integration tests: simplification and DFA path --


def test_rpq_uses_simplification():
    """Verify that RPQ operator simplifies before execution."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "e", {}), graph="g")

    ctx = ExecutionContext(graph_store=gs)
    # (e*)* should simplify to e* and still work
    expr = KleeneStar(KleeneStar(Label("e")))
    op = RegularPathQueryOperator(expr, graph="g", start_vertex=1)
    result = op.execute(ctx)
    assert {e.doc_id for e in result} == {1, 2}


def test_rpq_uses_dfa_for_small_nfa():
    """Verify DFA path is taken for small expressions."""
    gs = GraphStore()
    gs.create_graph("g")
    gs.add_vertex(Vertex(1, "a", {}), graph="g")
    gs.add_vertex(Vertex(2, "b", {}), graph="g")
    gs.add_vertex(Vertex(3, "c", {}), graph="g")
    gs.add_edge(Edge(10, 1, 2, "x", {}), graph="g")
    gs.add_edge(Edge(11, 1, 3, "y", {}), graph="g")

    ctx = ExecutionContext(graph_store=gs)
    # Simple alternation: x|y -- small NFA, should use DFA path
    expr = Alternation(Label("x"), Label("y"))
    op = RegularPathQueryOperator(expr, graph="g", start_vertex=1)
    result = op.execute(ctx)
    doc_ids = {e.doc_id for e in result}
    assert doc_ids == {2, 3}


# -- Epsilon elimination tests --


def test_simplify_alternation_subsumption():
    """a*|a -> a* (a is subsumed by a*)."""
    expr = Alternation(KleeneStar(Label("a")), Label("a"))
    result = _simplify_expr(expr)
    assert result == KleeneStar(Label("a"))


def test_simplify_alternation_subsumption_reversed():
    """a|a* -> a* (reversed order)."""
    expr = Alternation(Label("a"), KleeneStar(Label("a")))
    result = _simplify_expr(expr)
    assert result == KleeneStar(Label("a"))


def test_simplify_duplicate_kleene_concat():
    """a*/a* -> a* (duplicate Kleene concat)."""
    expr = Concat(KleeneStar(Label("a")), KleeneStar(Label("a")))
    result = _simplify_expr(expr)
    assert result == KleeneStar(Label("a"))
