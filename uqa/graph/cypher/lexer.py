#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tokenizer for the openCypher subset.

Produces a flat list of :class:`Token` values consumed by the
recursive-descent parser in ``parser.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Literals
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()

    # Identifiers and keywords
    IDENT = auto()

    # Symbols
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    LBRACKET = auto()    # [
    RBRACKET = auto()    # ]
    LBRACE = auto()      # {
    RBRACE = auto()      # }
    COLON = auto()       # :
    COMMA = auto()        # ,
    DOT = auto()          # .
    DOTDOT = auto()       # ..
    PIPE = auto()         # |
    DOLLAR = auto()       # $
    PLUS = auto()         # +
    MINUS = auto()        # -
    STAR = auto()         # *
    SLASH = auto()        # /
    PERCENT = auto()      # %
    CARET = auto()        # ^
    EQ = auto()           # =
    NEQ = auto()          # <>
    LT = auto()           # <
    GT = auto()           # >
    LTE = auto()          # <=
    GTE = auto()          # >=
    PLUS_EQ = auto()      # +=
    ARROW_RIGHT = auto()  # ->
    ARROW_LEFT = auto()   # <-
    DASH = auto()         # - (relationship connector, context-sensitive with MINUS)

    EOF = auto()


# Keywords are case-insensitive.  They are stored upper-cased so the parser
# can match with ``token.value.upper()``.
_KEYWORDS = frozenset({
    "AND", "AS", "ASC", "BY", "CASE", "CONTAINS", "CREATE", "DELETE",
    "DESC", "DETACH", "DISTINCT", "ELSE", "END", "ENDS", "EXISTS",
    "FALSE", "IN", "IS", "LIMIT", "MATCH", "MERGE", "NODE", "NOT",
    "NULL", "ON", "OPTIONAL", "OR", "ORDER", "RELATIONSHIP", "REMOVE",
    "RETURN", "SET", "SKIP", "STARTS", "THEN", "TRUE", "UNWIND",
    "WHEN", "WHERE", "WITH", "XOR",
})


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    value: str
    pos: int


def tokenize(source: str) -> list[Token]:
    """Tokenize a Cypher query string into a list of tokens."""
    tokens: list[Token] = []
    i = 0
    n = len(source)

    while i < n:
        ch = source[i]

        # Whitespace
        if ch in (" ", "\t", "\r", "\n"):
            i += 1
            continue

        # Single-line comment
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        # Block comment
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i += 2
            continue

        # String literals (single or double quoted)
        if ch in ("'", '"'):
            tok, i = _scan_string(source, i, ch)
            tokens.append(tok)
            continue

        # Numbers
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            tok, i = _scan_number(source, i)
            tokens.append(tok)
            continue

        # Identifiers and keywords
        if ch.isalpha() or ch == "_":
            tok, i = _scan_ident(source, i)
            tokens.append(tok)
            continue

        # Backtick-quoted identifiers
        if ch == "`":
            tok, i = _scan_backtick_ident(source, i)
            tokens.append(tok)
            continue

        # Multi-character symbols
        two = source[i:i + 2]
        if two == "<>":
            tokens.append(Token(TokenType.NEQ, "<>", i))
            i += 2
            continue
        if two == "<=":
            tokens.append(Token(TokenType.LTE, "<=", i))
            i += 2
            continue
        if two == ">=":
            tokens.append(Token(TokenType.GTE, ">=", i))
            i += 2
            continue
        if two == "->":
            tokens.append(Token(TokenType.ARROW_RIGHT, "->", i))
            i += 2
            continue
        if two == "<-":
            tokens.append(Token(TokenType.ARROW_LEFT, "<-", i))
            i += 2
            continue
        if two == "+=":
            tokens.append(Token(TokenType.PLUS_EQ, "+=", i))
            i += 2
            continue
        if two == "..":
            tokens.append(Token(TokenType.DOTDOT, "..", i))
            i += 2
            continue

        # Single-character symbols
        sym_map = {
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            ":": TokenType.COLON,
            ",": TokenType.COMMA,
            ".": TokenType.DOT,
            "|": TokenType.PIPE,
            "$": TokenType.DOLLAR,
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "%": TokenType.PERCENT,
            "^": TokenType.CARET,
            "=": TokenType.EQ,
            "<": TokenType.LT,
            ">": TokenType.GT,
        }
        if ch in sym_map:
            tokens.append(Token(sym_map[ch], ch, i))
            i += 1
            continue

        raise SyntaxError(f"Unexpected character {ch!r} at position {i}")

    tokens.append(Token(TokenType.EOF, "", i))
    return tokens


def _scan_string(source: str, start: int, quote: str) -> tuple[Token, int]:
    """Scan a quoted string literal, handling escape sequences."""
    i = start + 1
    n = len(source)
    parts: list[str] = []
    while i < n:
        ch = source[i]
        if ch == "\\":
            if i + 1 < n:
                esc = source[i + 1]
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
                if esc == quote:
                    parts.append(quote)
                elif esc in escape_map:
                    parts.append(escape_map[esc])
                else:
                    parts.append(esc)
                i += 2
                continue
        if ch == quote:
            # Check for doubled quote (Cypher's escape for quote inside same quote)
            if i + 1 < n and source[i + 1] == quote:
                parts.append(quote)
                i += 2
                continue
            return Token(TokenType.STRING, "".join(parts), start), i + 1
        parts.append(ch)
        i += 1
    raise SyntaxError(f"Unterminated string starting at position {start}")


def _scan_number(source: str, start: int) -> tuple[Token, int]:
    """Scan an integer or float literal."""
    i = start
    n = len(source)
    has_dot = False
    while i < n and (source[i].isdigit() or source[i] == "."):
        if source[i] == ".":
            if has_dot:
                break
            # Check if next char after dot is a digit (else it's DOTDOT or method access)
            if i + 1 < n and source[i + 1] == ".":
                break
            if i + 1 < n and not source[i + 1].isdigit():
                break
            has_dot = True
        i += 1
    # Scientific notation
    if i < n and source[i] in ("e", "E"):
        i += 1
        if i < n and source[i] in ("+", "-"):
            i += 1
        while i < n and source[i].isdigit():
            i += 1
        has_dot = True
    text = source[start:i]
    tt = TokenType.FLOAT if has_dot else TokenType.INTEGER
    return Token(tt, text, start), i


def _scan_ident(source: str, start: int) -> tuple[Token, int]:
    """Scan an identifier or keyword."""
    i = start
    n = len(source)
    while i < n and (source[i].isalnum() or source[i] == "_"):
        i += 1
    text = source[start:i]
    return Token(TokenType.IDENT, text, start), i


def _scan_backtick_ident(source: str, start: int) -> tuple[Token, int]:
    """Scan a backtick-quoted identifier ``\\`name\\```."""
    i = start + 1
    n = len(source)
    while i < n and source[i] != "`":
        i += 1
    if i >= n:
        raise SyntaxError(
            f"Unterminated backtick identifier at position {start}"
        )
    text = source[start + 1:i]
    return Token(TokenType.IDENT, text, start), i + 1


def is_keyword(token: Token, keyword: str) -> bool:
    """Check if a token is a specific keyword (case-insensitive)."""
    return token.type == TokenType.IDENT and token.value.upper() == keyword
