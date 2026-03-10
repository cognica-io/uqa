#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Apache AGE compatible Cypher graph query support.

Tests are organized by feature area:
  - Lexer and parser
  - Pattern matching (MATCH)
  - Graph mutations (CREATE, SET, DELETE, MERGE)
  - Projection (RETURN, WITH, UNWIND)
  - SQL integration (cypher(), create_graph, drop_graph)
  - Posting list integration
  - Persistence
"""

from __future__ import annotations

import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine
from uqa.graph.cypher.ast import (
    BinaryOp,
    CreateClause,
    CypherQuery,
    DeleteClause,
    Literal,
    MatchClause,
    MergeClause,
    NodePattern,
    PathPattern,
    PropertyAccess,
    RelPattern,
    ReturnClause,
    ReturnItem,
    SetClause,
    SetItem,
    Variable,
    WithClause,
)
from uqa.graph.cypher.compiler import CypherCompiler
from uqa.graph.cypher.lexer import Token, TokenType, is_keyword, tokenize
from uqa.graph.cypher.parser import parse_cypher
from uqa.graph.posting_list import GraphPostingList
from uqa.graph.store import GraphStore


# -- Fixtures --------------------------------------------------------------


def _make_social_graph() -> GraphStore:
    """Create a social network graph for testing.

    Vertices: Alice, Bob, Charlie, Diana (label=Person)
              NYC, SF (label=City)
    Edges: KNOWS, LIVES_IN
    """
    g = GraphStore()
    g.add_vertex(Vertex(1, "Person", {"name": "Alice", "age": 30}))
    g.add_vertex(Vertex(2, "Person", {"name": "Bob", "age": 25}))
    g.add_vertex(Vertex(3, "Person", {"name": "Charlie", "age": 35}))
    g.add_vertex(Vertex(4, "Person", {"name": "Diana", "age": 28}))
    g.add_vertex(Vertex(10, "City", {"name": "NYC"}))
    g.add_vertex(Vertex(11, "City", {"name": "SF"}))

    g.add_edge(Edge(101, 1, 2, "KNOWS", {"since": 2020}))
    g.add_edge(Edge(102, 1, 3, "KNOWS", {"since": 2019}))
    g.add_edge(Edge(103, 2, 4, "KNOWS", {"since": 2021}))
    g.add_edge(Edge(104, 3, 4, "KNOWS", {"since": 2018}))
    g.add_edge(Edge(105, 1, 10, "LIVES_IN", {}))
    g.add_edge(Edge(106, 2, 11, "LIVES_IN", {}))
    g.add_edge(Edge(107, 3, 10, "LIVES_IN", {}))
    g.add_edge(Edge(108, 4, 11, "LIVES_IN", {}))
    return g


# =====================================================================
# Lexer Tests
# =====================================================================


class TestCypherLexer:
    def test_basic_tokens(self):
        tokens = tokenize("MATCH (n) RETURN n")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.IDENT,    # MATCH
            TokenType.LPAREN,
            TokenType.IDENT,    # n
            TokenType.RPAREN,
            TokenType.IDENT,    # RETURN
            TokenType.IDENT,    # n
        ]

    def test_string_literal(self):
        tokens = tokenize("'hello world'")
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_double_quoted_string(self):
        tokens = tokenize('"hello"')
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello"

    def test_integer_literal(self):
        tokens = tokenize("42")
        assert tokens[0].type == TokenType.INTEGER
        assert tokens[0].value == "42"

    def test_float_literal(self):
        tokens = tokenize("3.14")
        assert tokens[0].type == TokenType.FLOAT
        assert tokens[0].value == "3.14"

    def test_arrows(self):
        tokens = tokenize("->")
        assert tokens[0].type == TokenType.ARROW_RIGHT
        tokens = tokenize("<-")
        assert tokens[0].type == TokenType.ARROW_LEFT

    def test_comparison_operators(self):
        tokens = tokenize("<> <= >= =")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.NEQ,
            TokenType.LTE,
            TokenType.GTE,
            TokenType.EQ,
        ]

    def test_dotdot(self):
        tokens = tokenize("1..5")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [TokenType.INTEGER, TokenType.DOTDOT, TokenType.INTEGER]

    def test_is_keyword(self):
        tok = Token(TokenType.IDENT, "MATCH", 0)
        assert is_keyword(tok, "MATCH")
        assert not is_keyword(tok, "RETURN")

    def test_case_insensitive_keyword(self):
        tok = Token(TokenType.IDENT, "match", 0)
        assert is_keyword(tok, "MATCH")

    def test_backtick_identifier(self):
        tokens = tokenize("`my var`")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "my var"

    def test_single_line_comment(self):
        tokens = tokenize("MATCH // comment\n(n)")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.IDENT in types

    def test_block_comment(self):
        tokens = tokenize("MATCH /* comment */ (n)")
        ident_tokens = [t for t in tokens if t.type == TokenType.IDENT]
        assert len(ident_tokens) == 2

    def test_escaped_string(self):
        tokens = tokenize("'it\\'s'")
        assert tokens[0].value == "it's"

    def test_dollar_parameter(self):
        tokens = tokenize("$param")
        assert tokens[0].type == TokenType.DOLLAR
        assert tokens[1].type == TokenType.IDENT
        assert tokens[1].value == "param"


# =====================================================================
# Parser Tests
# =====================================================================


class TestCypherParser:
    def test_simple_match_return(self):
        q = parse_cypher("MATCH (n) RETURN n")
        assert len(q.clauses) == 2
        assert isinstance(q.clauses[0], MatchClause)
        assert isinstance(q.clauses[1], ReturnClause)

    def test_labeled_node(self):
        q = parse_cypher("MATCH (n:Person) RETURN n")
        match = q.clauses[0]
        assert isinstance(match, MatchClause)
        node = match.patterns[0].elements[0]
        assert isinstance(node, NodePattern)
        assert node.variable == "n"
        assert node.labels == ("Person",)

    def test_node_with_properties(self):
        q = parse_cypher("MATCH (n:Person {name: 'Alice'}) RETURN n")
        match = q.clauses[0]
        node = match.patterns[0].elements[0]
        assert isinstance(node, NodePattern)
        assert "name" in node.properties
        prop_val = node.properties["name"]
        assert isinstance(prop_val, Literal)
        assert prop_val.value == "Alice"

    def test_relationship_pattern(self):
        q = parse_cypher("MATCH (a)-[r:KNOWS]->(b) RETURN a, b")
        match = q.clauses[0]
        elements = match.patterns[0].elements
        assert len(elements) == 3
        assert isinstance(elements[0], NodePattern)
        assert isinstance(elements[1], RelPattern)
        assert isinstance(elements[2], NodePattern)
        rel = elements[1]
        assert rel.variable == "r"
        assert rel.types == ("KNOWS",)
        assert rel.direction == "right"

    def test_left_directed_relationship(self):
        q = parse_cypher("MATCH (a)<-[r:KNOWS]-(b) RETURN a")
        rel = q.clauses[0].patterns[0].elements[1]
        assert rel.direction == "left"

    def test_undirected_relationship(self):
        q = parse_cypher("MATCH (a)-[r:KNOWS]-(b) RETURN a")
        rel = q.clauses[0].patterns[0].elements[1]
        assert rel.direction == "both"

    def test_variable_length_path(self):
        q = parse_cypher("MATCH (a)-[r:KNOWS*2..5]->(b) RETURN b")
        rel = q.clauses[0].patterns[0].elements[1]
        assert rel.min_hops == 2
        assert rel.max_hops == 5

    def test_variable_length_star_only(self):
        q = parse_cypher("MATCH (a)-[*]->(b) RETURN b")
        rel = q.clauses[0].patterns[0].elements[1]
        assert rel.min_hops == 1
        assert rel.max_hops is None

    def test_where_clause(self):
        q = parse_cypher("MATCH (n:Person) WHERE n.age > 25 RETURN n")
        match = q.clauses[0]
        assert match.where is not None
        assert isinstance(match.where, BinaryOp)
        assert match.where.op == ">"

    def test_optional_match(self):
        q = parse_cypher("MATCH (a) OPTIONAL MATCH (a)-[r]->(b) RETURN a, b")
        assert len(q.clauses) == 3
        assert isinstance(q.clauses[1], MatchClause)
        assert q.clauses[1].optional

    def test_create_clause(self):
        q = parse_cypher("CREATE (n:Person {name: 'Eve', age: 22})")
        assert isinstance(q.clauses[0], CreateClause)
        node = q.clauses[0].patterns[0].elements[0]
        assert node.labels == ("Person",)
        assert "name" in node.properties

    def test_create_with_relationship(self):
        q = parse_cypher(
            "CREATE (a:Person {name: 'X'})-[:KNOWS]->(b:Person {name: 'Y'})"
        )
        elements = q.clauses[0].patterns[0].elements
        assert len(elements) == 3

    def test_set_clause(self):
        q = parse_cypher("MATCH (n:Person {name: 'Alice'}) SET n.age = 31 RETURN n")
        assert isinstance(q.clauses[1], SetClause)
        item = q.clauses[1].items[0]
        assert isinstance(item.target, PropertyAccess)
        assert item.operator == "="

    def test_delete_clause(self):
        q = parse_cypher("MATCH (n:Person {name: 'Alice'}) DETACH DELETE n")
        assert isinstance(q.clauses[1], DeleteClause)
        assert q.clauses[1].detach

    def test_merge_clause(self):
        q = parse_cypher(
            "MERGE (n:Person {name: 'Alice'}) "
            "ON CREATE SET n.created = true "
            "ON MATCH SET n.accessed = true "
            "RETURN n"
        )
        assert isinstance(q.clauses[0], MergeClause)
        assert q.clauses[0].on_create_set is not None
        assert q.clauses[0].on_match_set is not None

    def test_with_clause(self):
        q = parse_cypher(
            "MATCH (n:Person) WITH n.name AS name, n.age AS age "
            "WHERE age > 25 RETURN name"
        )
        assert isinstance(q.clauses[1], WithClause)
        assert q.clauses[1].where is not None

    def test_return_order_by_limit(self):
        q = parse_cypher(
            "MATCH (n:Person) RETURN n.name ORDER BY n.age DESC LIMIT 2"
        )
        ret = q.clauses[1]
        assert isinstance(ret, ReturnClause)
        assert ret.order_by is not None
        assert ret.order_by[0].ascending is False
        assert ret.limit is not None

    def test_return_distinct(self):
        q = parse_cypher("MATCH (n:Person) RETURN DISTINCT n.name")
        ret = q.clauses[1]
        assert ret.distinct

    def test_return_star(self):
        q = parse_cypher("MATCH (n) RETURN *")
        ret = q.clauses[1]
        assert isinstance(ret.items[0].expr, Variable)
        assert ret.items[0].expr.name == "*"

    def test_multiple_relationship_types(self):
        q = parse_cypher("MATCH (a)-[r:KNOWS|FOLLOWS]->(b) RETURN b")
        rel = q.clauses[0].patterns[0].elements[1]
        assert rel.types == ("KNOWS", "FOLLOWS")

    def test_function_call_expression(self):
        q = parse_cypher("MATCH (n) RETURN id(n), labels(n)")
        ret = q.clauses[1]
        assert len(ret.items) == 2

    def test_unwind(self):
        q = parse_cypher("UNWIND [1, 2, 3] AS x RETURN x")
        assert len(q.clauses) == 2


# =====================================================================
# Compiler Tests -- Pattern Matching
# =====================================================================


class TestCypherMatch:
    def test_match_all_vertices(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n) RETURN n")
        rows = c.execute(q)
        assert len(rows) == 6  # 4 Person + 2 City

    def test_match_by_label(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person) RETURN n")
        rows = c.execute(q)
        assert len(rows) == 4

    def test_match_by_label_city(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:City) RETURN n")
        rows = c.execute(q)
        assert len(rows) == 2

    def test_match_by_property(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person {name: 'Alice'}) RETURN n")
        rows = c.execute(q)
        assert len(rows) == 1
        assert rows[0]["n"]["properties"]["name"] == "Alice"

    def test_match_where_comparison(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person) WHERE n.age > 28 RETURN n.name")
        rows = c.execute(q)
        names = {r["n.name"] for r in rows}
        assert names == {"Alice", "Charlie"}

    def test_match_relationship(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (a:Person)-[r:KNOWS]->(b:Person) RETURN a.name, b.name"
        )
        rows = c.execute(q)
        assert len(rows) == 4  # 4 KNOWS edges
        pairs = {(r["a.name"], r["b.name"]) for r in rows}
        assert ("Alice", "Bob") in pairs
        assert ("Alice", "Charlie") in pairs

    def test_match_where_edge_property(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (a:Person)-[r:KNOWS]->(b:Person) "
            "WHERE r.since >= 2020 RETURN a.name, b.name"
        )
        rows = c.execute(q)
        pairs = {(r["a.name"], r["b.name"]) for r in rows}
        assert ("Alice", "Bob") in pairs
        assert ("Bob", "Diana") in pairs
        assert ("Alice", "Charlie") not in pairs

    def test_match_chain(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(c:Person) "
            "RETURN a.name, c.name"
        )
        rows = c.execute(q)
        pairs = {(r["a.name"], r["c.name"]) for r in rows}
        assert ("Alice", "Diana") in pairs

    def test_match_variable_length(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (a:Person {name: 'Alice'})-[:KNOWS*1..2]->(b:Person) "
            "RETURN b.name"
        )
        rows = c.execute(q)
        names = {r["b.name"] for r in rows}
        # 1 hop: Bob, Charlie. 2 hops: Diana (via Bob or Charlie)
        assert "Bob" in names
        assert "Charlie" in names
        assert "Diana" in names

    def test_match_left_directed(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (b:Person)<-[:KNOWS]-(a:Person {name: 'Alice'}) "
            "RETURN b.name"
        )
        rows = c.execute(q)
        names = {r["b.name"] for r in rows}
        assert names == {"Bob", "Charlie"}

    def test_match_cross_label_pattern(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (p:Person)-[:LIVES_IN]->(c:City) "
            "RETURN p.name, c.name"
        )
        rows = c.execute(q)
        assert len(rows) == 4
        city_map = {r["p.name"]: r["c.name"] for r in rows}
        assert city_map["Alice"] == "NYC"
        assert city_map["Bob"] == "SF"

    def test_optional_match(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (c:City) "
            "OPTIONAL MATCH (c)<-[:LIVES_IN]-(p:Person) "
            "RETURN c.name, p.name"
        )
        rows = c.execute(q)
        # Each city has 2 residents
        assert len(rows) == 4

    def test_match_and_or_where(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) WHERE n.age >= 28 AND n.age <= 30 RETURN n.name"
        )
        rows = c.execute(q)
        names = {r["n.name"] for r in rows}
        assert names == {"Alice", "Diana"}


# =====================================================================
# Compiler Tests -- Mutations
# =====================================================================


class TestCypherCreate:
    def test_create_node(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher("CREATE (n:Person {name: 'Eve', age: 22}) RETURN n")
        rows = c.execute(q)
        assert len(rows) == 1
        assert rows[0]["n"]["label"] == "Person"
        assert rows[0]["n"]["properties"]["name"] == "Eve"
        assert len(g.vertices) == 1

    def test_create_node_and_relationship(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher(
            "CREATE (a:Person {name: 'X'})-[:KNOWS {since: 2024}]->"
            "(b:Person {name: 'Y'}) RETURN a, b"
        )
        rows = c.execute(q)
        assert len(rows) == 1
        assert len(g.vertices) == 2
        assert len(g.edges) == 1
        edge = list(g.edges.values())[0]
        assert edge.label == "KNOWS"
        assert edge.properties["since"] == 2024

    def test_create_multiple_nodes(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher(
            "CREATE (a:Person {name: 'A'}), (b:Person {name: 'B'}) RETURN a, b"
        )
        rows = c.execute(q)
        assert len(g.vertices) == 2

    def test_create_with_existing_binding(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (a:Person {name: 'Alice'}) "
            "CREATE (a)-[:FRIEND]->(b:Person {name: 'NewFriend'}) "
            "RETURN b.name"
        )
        rows = c.execute(q)
        assert len(rows) == 1
        assert rows[0]["b.name"] == "NewFriend"
        # Edge should connect Alice to the new vertex
        new_edges = [
            e for e in g.edges.values() if e.label == "FRIEND"
        ]
        assert len(new_edges) == 1
        assert new_edges[0].source_id == 1  # Alice's ID


class TestCypherSet:
    def test_set_property(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person {name: 'Alice'}) SET n.age = 31 RETURN n.age"
        )
        rows = c.execute(q)
        assert rows[0]["n.age"] == 31
        assert g.get_vertex(1).properties["age"] == 31

    def test_set_new_property(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person {name: 'Bob'}) SET n.email = 'bob@test.com' "
            "RETURN n.email"
        )
        rows = c.execute(q)
        assert rows[0]["n.email"] == "bob@test.com"


class TestCypherDelete:
    def test_detach_delete_vertex(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        initial_count = len(g.vertices)
        q = parse_cypher(
            "MATCH (n:Person {name: 'Diana'}) DETACH DELETE n"
        )
        c.execute(q)
        assert len(g.vertices) == initial_count - 1
        assert g.get_vertex(4) is None

    def test_delete_without_detach_fails(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person {name: 'Alice'}) DELETE n"
        )
        with pytest.raises(ValueError, match="incident edges"):
            c.execute(q)

    def test_delete_edge(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        initial_edges = len(g.edges)
        q = parse_cypher(
            "MATCH (a:Person {name: 'Alice'})-[r:KNOWS]->(b:Person {name: 'Bob'}) "
            "DELETE r"
        )
        c.execute(q)
        assert len(g.edges) == initial_edges - 1


class TestCypherMerge:
    def test_merge_creates_when_missing(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MERGE (n:Person {name: 'Alice'}) RETURN n"
        )
        rows = c.execute(q)
        assert len(rows) == 1
        assert len(g.vertices) == 1

    def test_merge_matches_when_exists(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        initial_count = len(g.vertices)
        q = parse_cypher(
            "MERGE (n:Person {name: 'Alice'}) RETURN n"
        )
        rows = c.execute(q)
        assert len(rows) == 1
        assert len(g.vertices) == initial_count  # No new vertex

    def test_merge_on_create_set(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MERGE (n:Person {name: 'New'}) "
            "ON CREATE SET n.created = true "
            "RETURN n.created"
        )
        rows = c.execute(q)
        assert rows[0]["n.created"] is True


# =====================================================================
# Compiler Tests -- Projection
# =====================================================================


class TestCypherReturn:
    def test_return_property_access(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person) RETURN n.name, n.age")
        rows = c.execute(q)
        assert len(rows) == 4
        names = {r["n.name"] for r in rows}
        assert "Alice" in names

    def test_return_alias(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person) RETURN n.name AS person_name")
        rows = c.execute(q)
        assert "person_name" in rows[0]

    def test_return_order_by(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) RETURN n.name ORDER BY n.age"
        )
        rows = c.execute(q)
        ages = [r["n.name"] for r in rows]
        assert ages[0] == "Bob"  # youngest (25)

    def test_return_order_by_desc(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) RETURN n.name ORDER BY n.age DESC"
        )
        rows = c.execute(q)
        assert rows[0]["n.name"] == "Charlie"  # oldest (35)

    def test_return_limit(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) RETURN n.name ORDER BY n.age LIMIT 2"
        )
        rows = c.execute(q)
        assert len(rows) == 2

    def test_return_skip(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) RETURN n.name ORDER BY n.age SKIP 2"
        )
        rows = c.execute(q)
        assert len(rows) == 2

    def test_return_distinct(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person)-[:LIVES_IN]->(c:City) "
            "RETURN DISTINCT c.name"
        )
        rows = c.execute(q)
        assert len(rows) == 2

    def test_return_expression(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) RETURN n.name, n.age + 1 AS next_age"
        )
        rows = c.execute(q)
        alice = next(r for r in rows if r["n.name"] == "Alice")
        assert alice["next_age"] == 31


class TestCypherWith:
    def test_with_projection(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) "
            "WITH n.name AS name, n.age AS age "
            "WHERE age > 28 "
            "RETURN name"
        )
        rows = c.execute(q)
        names = {r["name"] for r in rows}
        assert names == {"Alice", "Charlie"}

    def test_with_order_by_limit(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person) "
            "WITH n ORDER BY n.age DESC LIMIT 2 "
            "RETURN n.name"
        )
        rows = c.execute(q)
        assert len(rows) == 2


class TestCypherUnwind:
    def test_unwind_list(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher("UNWIND [1, 2, 3] AS x RETURN x")
        rows = c.execute(q)
        assert [r["x"] for r in rows] == [1, 2, 3]

    def test_unwind_with_match(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "UNWIND ['Alice', 'Bob'] AS name "
            "MATCH (n:Person {name: name}) "
            "RETURN n.age"
        )
        rows = c.execute(q)
        ages = {r["n.age"] for r in rows}
        assert ages == {30, 25}


# =====================================================================
# Compiler Tests -- Functions
# =====================================================================


class TestCypherFunctions:
    def test_id_function(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person {name: 'Alice'}) RETURN id(n)")
        rows = c.execute(q)
        assert rows[0]["id"] == 1

    def test_labels_function(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person {name: 'Alice'}) RETURN labels(n)")
        rows = c.execute(q)
        assert rows[0]["labels"] == ["Person"]

    def test_type_function(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (:Person {name: 'Alice'})-[r]->(:Person) RETURN type(r)"
        )
        rows = c.execute(q)
        types = {r["type"] for r in rows}
        assert "KNOWS" in types

    def test_properties_function(self):
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (n:Person {name: 'Alice'}) RETURN properties(n) AS props"
        )
        rows = c.execute(q)
        assert rows[0]["props"]["name"] == "Alice"

    def test_size_function(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher("RETURN size('hello') AS s")
        rows = c.execute(q)
        assert rows[0]["s"] == 5

    def test_coalesce_function(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher("RETURN coalesce(null, 42) AS val")
        rows = c.execute(q)
        assert rows[0]["val"] == 42

    def test_string_functions(self):
        g = GraphStore()
        c = CypherCompiler(g)
        q = parse_cypher("RETURN toLower('HELLO') AS low, toUpper('hello') AS up")
        rows = c.execute(q)
        assert rows[0]["low"] == "hello"
        assert rows[0]["up"] == "HELLO"


# =====================================================================
# Posting List Integration Tests
# =====================================================================


class TestCypherPostingList:
    def test_match_produces_graph_posting_list(self):
        """Verify that MATCH internally produces a GraphPostingList."""
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person) RETURN n")

        # Execute the match clause directly to inspect the posting list
        match_clause = q.clauses[0]
        assert isinstance(match_clause, MatchClause)
        gpl = c._exec_match(match_clause, c._empty_binding())

        assert isinstance(gpl, GraphPostingList)
        assert len(gpl) == 4

        # Each entry should have 'n' in its fields (vertex ID)
        for entry in gpl:
            assert "n" in entry.payload.fields
            vid = entry.payload.fields["n"]
            assert isinstance(vid, int)
            vtx = g.get_vertex(vid)
            assert vtx is not None
            assert vtx.label == "Person"

    def test_match_with_rel_has_graph_payload(self):
        """Verify graph payloads track matched vertices and edges."""
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (a:Person)-[r:KNOWS]->(b:Person) RETURN a, b"
        )
        match_clause = q.clauses[0]
        gpl = c._exec_match(match_clause, c._empty_binding())

        assert isinstance(gpl, GraphPostingList)
        for entry in gpl:
            gp = gpl.get_graph_payload(entry.doc_id)
            assert gp is not None
            # Should have matched vertex IDs in subgraph_vertices
            assert len(gp.subgraph_vertices) > 0

    def test_posting_list_isomorphism(self):
        """Verify Phi: L_G -> L and Phi^-1: L -> L_G roundtrip."""
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher("MATCH (n:Person) RETURN n")
        match_clause = q.clauses[0]
        gpl = c._exec_match(match_clause, c._empty_binding())

        # Convert to standard PostingList and back
        pl = gpl.to_posting_list()
        from uqa.core.posting_list import PostingList
        assert isinstance(pl, PostingList)

        gpl2 = GraphPostingList.from_posting_list(pl)
        assert isinstance(gpl2, GraphPostingList)
        assert len(gpl2) == len(gpl)

    def test_binding_fields_carry_vertex_ids(self):
        """Fields store vertex/edge IDs (int), not objects."""
        g = _make_social_graph()
        c = CypherCompiler(g)
        q = parse_cypher(
            "MATCH (a:Person)-[r:KNOWS]->(b:Person) RETURN a, r, b"
        )
        match_clause = q.clauses[0]
        gpl = c._exec_match(match_clause, c._empty_binding())

        for entry in gpl:
            fields = entry.payload.fields
            # a and b are vertex IDs (int)
            assert isinstance(fields["a"], int)
            assert isinstance(fields["b"], int)
            # r is an edge ID (int)
            assert isinstance(fields["r"], int)


# =====================================================================
# SQL Integration Tests
# =====================================================================


class TestCypherSQLIntegration:
    def test_create_and_drop_graph(self):
        e = Engine()
        result = e.sql("SELECT * FROM create_graph('test_graph')")
        assert len(result.rows) == 1
        assert e.has_graph("test_graph")

        result = e.sql("SELECT * FROM drop_graph('test_graph')")
        assert len(result.rows) == 1
        assert not e.has_graph("test_graph")

    def test_create_graph_duplicate_fails(self):
        e = Engine()
        e.sql("SELECT * FROM create_graph('g')")
        with pytest.raises(ValueError, match="already exists"):
            e.sql("SELECT * FROM create_graph('g')")

    def test_drop_graph_nonexistent_fails(self):
        e = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            e.sql("SELECT * FROM drop_graph('nonexistent')")

    def test_cypher_create_and_query(self):
        e = Engine()
        e.sql("SELECT * FROM create_graph('social')")

        # Create vertices
        e.sql("""
            SELECT * FROM cypher('social', $$
                CREATE (a:Person {name: 'Alice', age: 30})
            $$) AS (a agtype)
        """)
        e.sql("""
            SELECT * FROM cypher('social', $$
                CREATE (b:Person {name: 'Bob', age: 25})
            $$) AS (b agtype)
        """)

        # Query
        result = e.sql("""
            SELECT * FROM cypher('social', $$
                MATCH (n:Person) RETURN n.name, n.age
            $$) AS (name agtype, age agtype)
        """)
        assert len(result.rows) == 2
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Bob"}

    def test_cypher_create_relationship(self):
        e = Engine()
        e.sql("SELECT * FROM create_graph('g')")
        e.sql("""
            SELECT * FROM cypher('g', $$
                CREATE (a:Person {name: 'X'})-[:KNOWS]->(b:Person {name: 'Y'})
            $$) AS (a agtype, b agtype)
        """)
        result = e.sql("""
            SELECT * FROM cypher('g', $$
                MATCH (a)-[r:KNOWS]->(b) RETURN a.name, b.name
            $$) AS (src agtype, tgt agtype)
        """)
        assert len(result.rows) == 1
        assert result.rows[0]["src"] == "X"
        assert result.rows[0]["tgt"] == "Y"

    def test_cypher_match_where(self):
        e = Engine()
        e.sql("SELECT * FROM create_graph('g')")
        for name, age in [("A", 20), ("B", 30), ("C", 40)]:
            e.sql(f"""
                SELECT * FROM cypher('g', $$
                    CREATE (:Person {{name: '{name}', age: {age}}})
                $$) AS (v agtype)
            """)
        result = e.sql("""
            SELECT * FROM cypher('g', $$
                MATCH (n:Person) WHERE n.age > 25 RETURN n.name
            $$) AS (name agtype)
        """)
        names = {r["name"] for r in result.rows}
        assert names == {"B", "C"}

    def test_cypher_with_sql_where(self):
        """Cypher results can be filtered by SQL WHERE on the outer query."""
        e = Engine()
        e.sql("SELECT * FROM create_graph('g')")
        for name, age in [("A", 20), ("B", 30), ("C", 40)]:
            e.sql(f"""
                SELECT * FROM cypher('g', $$
                    CREATE (:Person {{name: '{name}', age: {age}}})
                $$) AS (v agtype)
            """)
        result = e.sql("""
            SELECT name FROM cypher('g', $$
                MATCH (n:Person) RETURN n.name AS name, n.age AS age
            $$) AS (name agtype, age agtype)
            WHERE age > 25
        """)
        names = {r["name"] for r in result.rows}
        assert names == {"B", "C"}


# =====================================================================
# Named Graph + Vertex Label Tests
# =====================================================================


class TestNamedGraphs:
    def test_engine_create_get_graph(self):
        e = Engine()
        g = e.create_graph("test")
        assert e.has_graph("test")
        assert e.get_graph("test") is g

    def test_engine_drop_graph(self):
        e = Engine()
        e.create_graph("test")
        e.drop_graph("test")
        assert not e.has_graph("test")

    def test_named_graphs_are_isolated(self):
        e = Engine()
        g1 = e.create_graph("g1")
        g2 = e.create_graph("g2")
        g1.add_vertex(Vertex(1, "Person", {"name": "Alice"}))
        g2.add_vertex(Vertex(1, "Animal", {"name": "Rex"}))
        assert g1.get_vertex(1).label == "Person"
        assert g2.get_vertex(1).label == "Animal"


class TestVertexLabels:
    def test_vertex_has_label(self):
        v = Vertex(1, "Person", {"name": "Alice"})
        assert v.label == "Person"

    def test_vertices_by_label(self):
        g = GraphStore()
        g.add_vertex(Vertex(1, "Person", {"name": "Alice"}))
        g.add_vertex(Vertex(2, "Person", {"name": "Bob"}))
        g.add_vertex(Vertex(3, "City", {"name": "NYC"}))

        persons = g.vertices_by_label("Person")
        assert len(persons) == 2
        cities = g.vertices_by_label("City")
        assert len(cities) == 1

    def test_remove_vertex(self):
        g = GraphStore()
        g.add_vertex(Vertex(1, "Person", {"name": "Alice"}))
        g.add_vertex(Vertex(2, "Person", {"name": "Bob"}))
        g.add_edge(Edge(1, 1, 2, "KNOWS", {}))

        g.remove_vertex(1)
        assert g.get_vertex(1) is None
        assert len(g.edges) == 0  # incident edge also removed

    def test_remove_edge(self):
        g = GraphStore()
        g.add_vertex(Vertex(1, "Person", {}))
        g.add_vertex(Vertex(2, "Person", {}))
        g.add_edge(Edge(1, 1, 2, "KNOWS", {}))

        g.remove_edge(1)
        assert g.get_edge(1) is None
        assert len(g.neighbors(1)) == 0

    def test_next_vertex_id(self):
        g = GraphStore()
        g.add_vertex(Vertex(5, "X", {}))
        assert g.next_vertex_id() == 6
        assert g.next_vertex_id() == 7

    def test_next_edge_id(self):
        g = GraphStore()
        g.add_edge(Edge(10, 1, 2, "X", {}))
        assert g.next_edge_id() == 11
