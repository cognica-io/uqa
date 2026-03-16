#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""RPQ expression simplification and NFA->DFA subset construction.

Section 8.2, Paper 2: Optimizations for regular path query evaluation.

- _simplify_expr: algebraic simplification rules (a|a -> a, (a*)* -> a*, etc.)
- _subset_construction: NFA to DFA conversion for small NFAs
"""

from __future__ import annotations

from uqa.graph.operators import _NFA, _epsilon_closure, _NFAState
from uqa.graph.pattern import (
    Alternation,
    Concat,
    KleeneStar,
    Label,
    RegularPathExpr,
)


def _simplify_expr(expr: RegularPathExpr) -> RegularPathExpr:
    """Algebraic simplification of regular path expressions.

    Rules:
    - a|a -> a (duplicate elimination)
    - (a*)* -> a* (nested Kleene star flattening)
    - a*|a -> a*, a|a* -> a* (epsilon elimination: a subsumed by a*)
    - a*/a* -> a* (epsilon elimination: duplicate Kleene concat)
    - Alternation operands sorted by repr for canonical form
    - Recursive simplification of sub-expressions
    """
    if isinstance(expr, Label):
        return expr

    if isinstance(expr, Alternation):
        left = _simplify_expr(expr.left)
        right = _simplify_expr(expr.right)
        # a|a -> a
        if left == right:
            return left
        # a*|a -> a* (a is subsumed by a*)
        if isinstance(left, KleeneStar) and left.inner == right:
            return left
        if isinstance(right, KleeneStar) and right.inner == left:
            return right
        # Sort for canonical form
        if repr(left) > repr(right):
            left, right = right, left
        return Alternation(left, right)

    if isinstance(expr, Concat):
        left = _simplify_expr(expr.left)
        right = _simplify_expr(expr.right)
        # a*/a* -> a* (duplicate Kleene concat elimination)
        if (
            isinstance(left, KleeneStar)
            and isinstance(right, KleeneStar)
            and left.inner == right.inner
        ):
            return left
        return Concat(left, right)

    if isinstance(expr, KleeneStar):
        inner = _simplify_expr(expr.inner)
        # (a*)* -> a*
        if isinstance(inner, KleeneStar):
            return inner
        return KleeneStar(inner)

    return expr


# DFA types
DFAState = frozenset[int]  # set of NFA state IDs
DFATransitions = dict[DFAState, dict[str, DFAState]]


def _subset_construction(
    nfa: _NFA,
) -> tuple[DFATransitions, DFAState, set[DFAState]]:
    """Convert NFA to DFA using subset construction.

    Returns (transitions, start_state, accept_states).
    Each DFA state is a frozenset of NFA state IDs.
    """
    # Collect all NFA states
    all_states: set[_NFAState] = set()
    stack = [nfa.start]
    while stack:
        s = stack.pop()
        if s in all_states:
            continue
        all_states.add(s)
        for _, target in s.transitions:
            stack.append(target)

    state_map = {s.state_id: s for s in all_states}
    accept_id = nfa.accept.state_id

    # Collect all labels (non-epsilon transitions)
    alphabet: set[str] = set()
    for s in all_states:
        for label, _ in s.transitions:
            if label is not None:
                alphabet.add(label)

    # Initial DFA state = epsilon closure of NFA start
    initial_nfa = _epsilon_closure({nfa.start})
    start_dfa: DFAState = frozenset(s.state_id for s in initial_nfa)

    transitions: DFATransitions = {}
    dfa_states: set[DFAState] = {start_dfa}
    accept_states: set[DFAState] = set()
    worklist = [start_dfa]

    if accept_id in start_dfa:
        accept_states.add(start_dfa)

    while worklist:
        current = worklist.pop()
        transitions[current] = {}

        for label in alphabet:
            # Compute move(current, label)
            next_nfa: set[_NFAState] = set()
            for sid in current:
                state = state_map.get(sid)
                if state is None:
                    continue
                for trans_label, target in state.transitions:
                    if trans_label == label:
                        next_nfa.add(target)

            if not next_nfa:
                continue

            # Epsilon closure
            closed = _epsilon_closure(next_nfa)
            next_dfa: DFAState = frozenset(s.state_id for s in closed)

            transitions[current][label] = next_dfa

            if next_dfa not in dfa_states:
                dfa_states.add(next_dfa)
                worklist.append(next_dfa)
                if accept_id in next_dfa:
                    accept_states.add(next_dfa)

    return transitions, start_dfa, accept_states
