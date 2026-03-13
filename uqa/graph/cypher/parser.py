#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Recursive-descent parser for the openCypher subset.

Consumes tokens from :mod:`lexer` and produces an AST
(:class:`~ast.CypherQuery`).
"""

from __future__ import annotations

from uqa.graph.cypher.ast import (
    BinaryOp,
    CaseExpr,
    CreateClause,
    CypherClause,
    CypherExpr,
    CypherQuery,
    DeleteClause,
    FunctionCall,
    InList,
    IsNotNull,
    IsNull,
    ListLiteral,
    Literal,
    MatchClause,
    MergeClause,
    NodePattern,
    OrderByItem,
    Parameter,
    PathPattern,
    PropertyAccess,
    RelPattern,
    ReturnClause,
    ReturnItem,
    SetClause,
    SetItem,
    UnaryOp,
    UnwindClause,
    Variable,
    WithClause,
)
from uqa.graph.cypher.lexer import Token, TokenType, is_keyword, tokenize


class CypherParser:
    """Parse a Cypher query string into a :class:`CypherQuery` AST."""

    def __init__(self, source: str) -> None:
        self._tokens = tokenize(source)
        self._pos = 0

    # -- Helpers -------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, tt: TokenType) -> Token:
        tok = self._advance()
        if tok.type != tt:
            raise SyntaxError(
                f"Expected {tt.name}, got {tok.type.name} "
                f"({tok.value!r}) at position {tok.pos}"
            )
        return tok

    def _expect_keyword(self, keyword: str) -> Token:
        tok = self._advance()
        if not is_keyword(tok, keyword):
            raise SyntaxError(
                f"Expected keyword {keyword}, got {tok.value!r} at position {tok.pos}"
            )
        return tok

    def _match_keyword(self, keyword: str) -> bool:
        if is_keyword(self._peek(), keyword):
            self._advance()
            return True
        return False

    def _match(self, tt: TokenType) -> Token | None:
        if self._peek().type == tt:
            return self._advance()
        return None

    def _at_keyword(self, keyword: str) -> bool:
        return is_keyword(self._peek(), keyword)

    def _at_clause_start(self) -> bool:
        """True if current token starts a new clause."""
        tok = self._peek()
        if tok.type != TokenType.IDENT:
            return False
        kw = tok.value.upper()
        return kw in (
            "MATCH",
            "OPTIONAL",
            "CREATE",
            "MERGE",
            "SET",
            "DELETE",
            "DETACH",
            "RETURN",
            "WITH",
            "UNWIND",
        )

    # -- Top-level -----------------------------------------------------

    def parse(self) -> CypherQuery:
        """Parse the complete query into a CypherQuery AST."""
        clauses: list[CypherClause] = []
        while self._peek().type != TokenType.EOF:
            clauses.append(self._parse_clause())
        return CypherQuery(clauses=tuple(clauses))

    def _parse_clause(self) -> CypherClause:
        tok = self._peek()
        if not (tok.type == TokenType.IDENT):
            raise SyntaxError(
                f"Expected clause keyword, got {tok.value!r} at position {tok.pos}"
            )
        kw = tok.value.upper()

        if kw == "MATCH":
            return self._parse_match(optional=False)
        if kw == "OPTIONAL":
            self._advance()
            self._expect_keyword("MATCH")
            return self._parse_match(optional=True)
        if kw == "CREATE":
            return self._parse_create()
        if kw == "MERGE":
            return self._parse_merge()
        if kw == "SET":
            return self._parse_set()
        if kw == "DELETE":
            return self._parse_delete(detach=False)
        if kw == "DETACH":
            self._advance()
            self._expect_keyword("DELETE")
            return self._parse_delete(detach=True)
        if kw == "RETURN":
            return self._parse_return()
        if kw == "WITH":
            return self._parse_with()
        if kw == "UNWIND":
            return self._parse_unwind()

        raise SyntaxError(f"Unexpected keyword {tok.value!r} at position {tok.pos}")

    # -- MATCH ---------------------------------------------------------

    def _parse_match(self, *, optional: bool) -> MatchClause:
        if not optional:
            self._expect_keyword("MATCH")
        patterns = self._parse_pattern_list()
        where = None
        if self._match_keyword("WHERE"):
            where = self._parse_expression()
        return MatchClause(patterns=tuple(patterns), where=where, optional=optional)

    # -- CREATE --------------------------------------------------------

    def _parse_create(self) -> CreateClause:
        self._expect_keyword("CREATE")
        patterns = self._parse_pattern_list()
        return CreateClause(patterns=tuple(patterns))

    # -- MERGE ---------------------------------------------------------

    def _parse_merge(self) -> MergeClause:
        self._expect_keyword("MERGE")
        pattern = self._parse_path_pattern()
        on_create: list[SetItem] | None = None
        on_match: list[SetItem] | None = None
        while self._at_keyword("ON"):
            self._advance()
            if self._match_keyword("CREATE"):
                self._expect_keyword("SET")
                on_create = self._parse_set_items()
            elif self._match_keyword("MATCH"):
                self._expect_keyword("SET")
                on_match = self._parse_set_items()
            else:
                tok = self._peek()
                raise SyntaxError(
                    f"Expected CREATE or MATCH after ON, got "
                    f"{tok.value!r} at position {tok.pos}"
                )
        return MergeClause(
            pattern=pattern,
            on_create_set=tuple(on_create) if on_create else None,
            on_match_set=tuple(on_match) if on_match else None,
        )

    # -- SET -----------------------------------------------------------

    def _parse_set(self) -> SetClause:
        self._expect_keyword("SET")
        items = self._parse_set_items()
        return SetClause(items=tuple(items))

    def _parse_set_items(self) -> list[SetItem]:
        items: list[SetItem] = []
        items.append(self._parse_set_item())
        while self._match(TokenType.COMMA):
            items.append(self._parse_set_item())
        return items

    def _parse_set_item(self) -> SetItem:
        # Parse only the left-hand side (variable or property access),
        # stopping before = or +=.
        target = self._parse_postfix()
        if self._match(TokenType.PLUS_EQ):
            value = self._parse_expression()
            return SetItem(target=target, value=value, operator="+=")
        self._expect(TokenType.EQ)
        value = self._parse_expression()
        return SetItem(target=target, value=value, operator="=")

    # -- DELETE --------------------------------------------------------

    def _parse_delete(self, *, detach: bool) -> DeleteClause:
        if not detach:
            self._expect_keyword("DELETE")
        exprs: list[CypherExpr] = []
        exprs.append(self._parse_expression())
        while self._match(TokenType.COMMA):
            exprs.append(self._parse_expression())
        return DeleteClause(expressions=tuple(exprs), detach=detach)

    # -- RETURN --------------------------------------------------------

    def _parse_return(self) -> ReturnClause:
        self._expect_keyword("RETURN")
        distinct = self._match_keyword("DISTINCT")
        items = self._parse_return_items()
        order_by = self._parse_order_by()
        skip = self._parse_skip()
        limit = self._parse_limit()
        return ReturnClause(
            items=tuple(items),
            distinct=distinct,
            order_by=tuple(order_by) if order_by else None,
            skip=skip,
            limit=limit,
        )

    # -- WITH ----------------------------------------------------------

    def _parse_with(self) -> WithClause:
        self._expect_keyword("WITH")
        distinct = self._match_keyword("DISTINCT")
        items = self._parse_return_items()
        order_by = self._parse_order_by()
        skip = self._parse_skip()
        limit = self._parse_limit()
        where = None
        if self._match_keyword("WHERE"):
            where = self._parse_expression()
        return WithClause(
            items=tuple(items),
            distinct=distinct,
            order_by=tuple(order_by) if order_by else None,
            skip=skip,
            limit=limit,
            where=where,
        )

    # -- UNWIND --------------------------------------------------------

    def _parse_unwind(self) -> UnwindClause:
        self._expect_keyword("UNWIND")
        expr = self._parse_expression()
        self._expect_keyword("AS")
        var = self._expect(TokenType.IDENT).value
        return UnwindClause(expr=expr, variable=var)

    # -- Shared return/with pieces -------------------------------------

    def _parse_return_items(self) -> list[ReturnItem]:
        items: list[ReturnItem] = []
        # Handle RETURN *
        if self._peek().type == TokenType.STAR:
            self._advance()
            items.append(ReturnItem(expr=Variable("*"), alias=None))
            return items
        items.append(self._parse_return_item())
        while self._match(TokenType.COMMA):
            items.append(self._parse_return_item())
        return items

    def _parse_return_item(self) -> ReturnItem:
        expr = self._parse_expression()
        alias = None
        if self._match_keyword("AS"):
            alias = self._expect(TokenType.IDENT).value
        return ReturnItem(expr=expr, alias=alias)

    def _parse_order_by(self) -> list[OrderByItem] | None:
        if not self._at_keyword("ORDER"):
            return None
        self._advance()
        self._expect_keyword("BY")
        items: list[OrderByItem] = []
        items.append(self._parse_order_item())
        while self._match(TokenType.COMMA):
            items.append(self._parse_order_item())
        return items

    def _parse_order_item(self) -> OrderByItem:
        expr = self._parse_expression()
        ascending = True
        if self._match_keyword("DESC"):
            ascending = False
        elif self._match_keyword("ASC"):
            ascending = True
        return OrderByItem(expr=expr, ascending=ascending)

    def _parse_skip(self) -> CypherExpr | None:
        if self._match_keyword("SKIP"):
            return self._parse_expression()
        return None

    def _parse_limit(self) -> CypherExpr | None:
        if self._match_keyword("LIMIT"):
            return self._parse_expression()
        return None

    # -- Patterns ------------------------------------------------------

    def _parse_pattern_list(self) -> list[PathPattern]:
        patterns: list[PathPattern] = []
        patterns.append(self._parse_path_pattern())
        while self._match(TokenType.COMMA):
            patterns.append(self._parse_path_pattern())
        return patterns

    def _parse_path_pattern(self) -> PathPattern:
        elements: list[NodePattern | RelPattern] = []
        elements.append(self._parse_node_pattern())
        while self._peek().type in (
            TokenType.MINUS,
            TokenType.LT,
            TokenType.ARROW_LEFT,
        ):
            rel = self._parse_rel_pattern()
            elements.append(rel)
            elements.append(self._parse_node_pattern())
        return PathPattern(elements=tuple(elements))

    def _parse_node_pattern(self) -> NodePattern:
        self._expect(TokenType.LPAREN)
        variable = None
        labels: list[str] = []
        properties: dict[str, CypherExpr] | None = None

        # Variable name (optional)
        if self._peek().type == TokenType.IDENT and not self._at_keyword("WHERE"):
            variable = self._advance().value

        # Labels (optional, :Label1:Label2)
        while self._peek().type == TokenType.COLON:
            self._advance()
            labels.append(self._expect(TokenType.IDENT).value)

        # Properties (optional, {key: value, ...})
        if self._peek().type == TokenType.LBRACE:
            properties = self._parse_property_map()

        self._expect(TokenType.RPAREN)
        return NodePattern(
            variable=variable,
            labels=tuple(labels),
            properties=properties,
        )

    def _parse_rel_pattern(self) -> RelPattern:
        """Parse a relationship pattern between two nodes.

        Forms:
            -[...]->   right-directed
            <-[...]-   left-directed
            -[...]-    undirected
        """
        # Determine direction prefix
        if self._match(TokenType.ARROW_LEFT):
            # <-[...]- (left)
            left_arrow = True
        elif self._match(TokenType.MINUS):
            left_arrow = False
        else:
            raise SyntaxError(f"Expected - or <- at position {self._peek().pos}")

        variable = None
        types: list[str] = []
        properties: dict[str, CypherExpr] | None = None
        min_hops: int | None = None
        max_hops: int | None = None

        # Optional detail block [...]
        has_bracket = self._match(TokenType.LBRACKET) is not None
        if has_bracket:
            # Variable (optional)
            if (
                self._peek().type == TokenType.IDENT
                and self._peek().value.upper() not in _KEYWORDS
            ):
                variable = self._advance().value

            # Types (:TYPE1|TYPE2)
            if self._peek().type == TokenType.COLON:
                self._advance()
                types.append(self._expect(TokenType.IDENT).value)
                while self._match(TokenType.PIPE):
                    types.append(self._expect(TokenType.IDENT).value)

            # Variable-length *min..max
            if self._match(TokenType.STAR):
                min_hops, max_hops = self._parse_var_length()

            # Properties {key: value}
            if self._peek().type == TokenType.LBRACE:
                properties = self._parse_property_map()

            self._expect(TokenType.RBRACKET)

        # Determine direction suffix
        if left_arrow:
            # Already consumed <-, expect -
            self._expect(TokenType.MINUS)
            direction = "left"
        else:
            # Consumed -, check for ->
            if self._match(TokenType.ARROW_RIGHT):
                direction = "right"
            elif self._match(TokenType.MINUS):
                direction = "both"
            else:
                raise SyntaxError(f"Expected -> or - at position {self._peek().pos}")

        return RelPattern(
            variable=variable,
            types=tuple(types),
            properties=properties,
            direction=direction,
            min_hops=min_hops,
            max_hops=max_hops,
        )

    def _parse_var_length(self) -> tuple[int | None, int | None]:
        """Parse the variable-length part after ``*``: ``*``, ``*2``, ``*2..5``, ``*..5``, ``*2..``."""
        min_hops: int | None = None
        max_hops: int | None = None

        if self._peek().type == TokenType.INTEGER:
            min_hops = int(self._advance().value)
            if self._match(TokenType.DOTDOT):
                if self._peek().type == TokenType.INTEGER:
                    max_hops = int(self._advance().value)
                # else: *2.. means min=2, max=unlimited
            else:
                # *2 means exactly 2 hops
                max_hops = min_hops
        elif self._match(TokenType.DOTDOT):
            if self._peek().type == TokenType.INTEGER:
                max_hops = int(self._advance().value)
            # *.. means any length
        else:
            # bare * means any length (min=1 by convention)
            min_hops = 1

        return min_hops, max_hops

    def _parse_property_map(self) -> dict[str, CypherExpr]:
        self._expect(TokenType.LBRACE)
        props: dict[str, CypherExpr] = {}
        if self._peek().type != TokenType.RBRACE:
            key = self._expect(TokenType.IDENT).value
            self._expect(TokenType.COLON)
            val = self._parse_expression()
            props[key] = val
            while self._match(TokenType.COMMA):
                key = self._expect(TokenType.IDENT).value
                self._expect(TokenType.COLON)
                val = self._parse_expression()
                props[key] = val
        self._expect(TokenType.RBRACE)
        return props

    # -- Expressions (Pratt-style precedence) --------------------------

    def _parse_expression(self) -> CypherExpr:
        return self._parse_or()

    def _parse_or(self) -> CypherExpr:
        left = self._parse_xor()
        while self._at_keyword("OR"):
            self._advance()
            right = self._parse_xor()
            left = BinaryOp(op="OR", left=left, right=right)
        return left

    def _parse_xor(self) -> CypherExpr:
        left = self._parse_and()
        while self._at_keyword("XOR"):
            self._advance()
            right = self._parse_and()
            left = BinaryOp(op="XOR", left=left, right=right)
        return left

    def _parse_and(self) -> CypherExpr:
        left = self._parse_not()
        while self._at_keyword("AND"):
            self._advance()
            right = self._parse_not()
            left = BinaryOp(op="AND", left=left, right=right)
        return left

    def _parse_not(self) -> CypherExpr:
        if self._at_keyword("NOT"):
            self._advance()
            operand = self._parse_not()
            return UnaryOp(op="NOT", operand=operand)
        return self._parse_comparison()

    def _parse_comparison(self) -> CypherExpr:
        left = self._parse_addition()

        # IS NULL / IS NOT NULL
        if self._at_keyword("IS"):
            self._advance()
            if self._match_keyword("NOT"):
                self._expect_keyword("NULL")
                return IsNotNull(expr=left)
            self._expect_keyword("NULL")
            return IsNull(expr=left)

        # IN
        if self._at_keyword("IN"):
            self._advance()
            right = self._parse_addition()
            return InList(expr=left, list_expr=right)

        # STARTS WITH / ENDS WITH / CONTAINS
        if self._at_keyword("STARTS"):
            self._advance()
            self._expect_keyword("WITH")
            right = self._parse_addition()
            return BinaryOp(op="STARTS WITH", left=left, right=right)
        if self._at_keyword("ENDS"):
            self._advance()
            self._expect_keyword("WITH")
            right = self._parse_addition()
            return BinaryOp(op="ENDS WITH", left=left, right=right)
        if self._at_keyword("CONTAINS"):
            self._advance()
            right = self._parse_addition()
            return BinaryOp(op="CONTAINS", left=left, right=right)

        # Comparison operators
        comp_ops = {
            TokenType.EQ: "=",
            TokenType.NEQ: "<>",
            TokenType.LT: "<",
            TokenType.GT: ">",
            TokenType.LTE: "<=",
            TokenType.GTE: ">=",
        }
        if self._peek().type in comp_ops:
            tok = self._advance()
            right = self._parse_addition()
            return BinaryOp(op=comp_ops[tok.type], left=left, right=right)

        return left

    def _parse_addition(self) -> CypherExpr:
        left = self._parse_multiplication()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            right = self._parse_multiplication()
            left = BinaryOp(op=op_tok.value, left=left, right=right)
        return left

    def _parse_multiplication(self) -> CypherExpr:
        left = self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_tok = self._advance()
            right = self._parse_unary()
            left = BinaryOp(op=op_tok.value, left=left, right=right)
        return left

    def _parse_unary(self) -> CypherExpr:
        if self._peek().type == TokenType.MINUS:
            self._advance()
            operand = self._parse_unary()
            return UnaryOp(op="-", operand=operand)
        return self._parse_postfix()

    def _parse_postfix(self) -> CypherExpr:
        expr = self._parse_atom()
        while True:
            # Property access: expr.key
            if self._peek().type == TokenType.DOT:
                self._advance()
                key = self._expect(TokenType.IDENT).value
                if isinstance(expr, Variable):
                    expr = PropertyAccess(variable=expr.name, keys=(key,))
                elif isinstance(expr, PropertyAccess):
                    expr = PropertyAccess(
                        variable=expr.variable,
                        keys=(*expr.keys, key),
                    )
                else:
                    expr = BinaryOp(op=".", left=expr, right=Literal(key))
            # Index access: expr[index]
            elif self._peek().type == TokenType.LBRACKET:
                self._advance()
                from uqa.graph.cypher.ast import ListIndex

                idx = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                expr = ListIndex(expr=expr, index=idx)
            else:
                break
        return expr

    def _parse_atom(self) -> CypherExpr:
        tok = self._peek()

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        # List literal [...]
        if tok.type == TokenType.LBRACKET:
            return self._parse_list_literal()

        # Map literal { ... } (only in expression context, not pattern)
        # We need to distinguish from property maps in patterns.
        # In expression context, we parse { key: expr, ... }

        # Parameter $name
        if tok.type == TokenType.DOLLAR:
            self._advance()
            name = self._expect(TokenType.IDENT).value
            return Parameter(name=name)

        # Numeric literals
        if tok.type == TokenType.INTEGER:
            self._advance()
            return Literal(int(tok.value))

        if tok.type == TokenType.FLOAT:
            self._advance()
            return Literal(float(tok.value))

        # String literal
        if tok.type == TokenType.STRING:
            self._advance()
            return Literal(tok.value)

        # Keywords acting as literals
        if tok.type == TokenType.IDENT:
            upper = tok.value.upper()
            if upper == "TRUE":
                self._advance()
                return Literal(True)
            if upper == "FALSE":
                self._advance()
                return Literal(False)
            if upper == "NULL":
                self._advance()
                return Literal(None)

            # CASE expression
            if upper == "CASE":
                return self._parse_case()

            # Check for function call: name(...)
            if (
                self._pos + 1 < len(self._tokens)
                and self._tokens[self._pos + 1].type == TokenType.LPAREN
            ):
                return self._parse_function_call()

            # Plain variable
            self._advance()
            return Variable(tok.value)

        raise SyntaxError(f"Unexpected token {tok.value!r} at position {tok.pos}")

    def _parse_list_literal(self) -> ListLiteral:
        self._expect(TokenType.LBRACKET)
        elements: list[CypherExpr] = []
        if self._peek().type != TokenType.RBRACKET:
            elements.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                elements.append(self._parse_expression())
        self._expect(TokenType.RBRACKET)
        return ListLiteral(elements=tuple(elements))

    def _parse_function_call(self) -> FunctionCall:
        name = self._advance().value
        self._expect(TokenType.LPAREN)
        distinct = self._match_keyword("DISTINCT")
        args: list[CypherExpr] = []
        if self._peek().type != TokenType.RPAREN:
            # Handle * as argument (e.g. count(*))
            if self._peek().type == TokenType.STAR:
                self._advance()
                args.append(Variable("*"))
            else:
                args.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    args.append(self._parse_expression())
        self._expect(TokenType.RPAREN)
        return FunctionCall(name=name, args=tuple(args), distinct=distinct)

    def _parse_case(self) -> CaseExpr:
        self._expect_keyword("CASE")
        operand = None
        # Simple CASE: CASE expr WHEN ...
        if not self._at_keyword("WHEN"):
            operand = self._parse_expression()
        whens: list[tuple[CypherExpr, CypherExpr]] = []
        while self._match_keyword("WHEN"):
            cond = self._parse_expression()
            self._expect_keyword("THEN")
            result = self._parse_expression()
            whens.append((cond, result))
        else_expr = None
        if self._match_keyword("ELSE"):
            else_expr = self._parse_expression()
        self._expect_keyword("END")
        return CaseExpr(
            operand=operand,
            whens=tuple(whens),
            else_expr=else_expr,
        )


# A set of Cypher keywords that cannot be used as bare variable names
# in relationship patterns.
_KEYWORDS = frozenset(
    {
        "AND",
        "AS",
        "ASC",
        "BY",
        "CASE",
        "CONTAINS",
        "CREATE",
        "DELETE",
        "DESC",
        "DETACH",
        "DISTINCT",
        "ELSE",
        "END",
        "ENDS",
        "EXISTS",
        "FALSE",
        "IN",
        "IS",
        "LIMIT",
        "MATCH",
        "MERGE",
        "NODE",
        "NOT",
        "NULL",
        "ON",
        "OPTIONAL",
        "OR",
        "ORDER",
        "RELATIONSHIP",
        "REMOVE",
        "RETURN",
        "SET",
        "SKIP",
        "STARTS",
        "THEN",
        "TRUE",
        "UNWIND",
        "WHEN",
        "WHERE",
        "WITH",
        "XOR",
    }
)


def parse_cypher(source: str) -> CypherQuery:
    """Parse a Cypher query string into a CypherQuery AST."""
    return CypherParser(source).parse()
