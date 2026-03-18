#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Comprehensive SQL-level integration tests for all named graph features.

Every test exercises graph functionality exclusively through ``engine.sql()``,
covering named graph lifecycle, per-table graphs, traverse, RPQ, temporal
traverse, Cypher, centrality, message passing, graph embedding, graph
isolation, and graph algebra (union/intersect/difference).
"""

from __future__ import annotations

import pytest

from uqa.core.types import Edge, Vertex
from uqa.engine import Engine

# =====================================================================
# Helpers
# =====================================================================


def _make_named_graph_engine(graph_name: str = "social") -> Engine:
    """Create an engine with a named graph containing a small social network.

    Graph topology::

        1 --knows--> 2 --knows--> 3
        1 --follows--> 3
    """
    engine = Engine()
    engine.create_graph(graph_name)
    gs = engine.get_graph(graph_name)
    gs.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph=graph_name)
    gs.add_vertex(Vertex(2, "person", {"name": "Bob"}), graph=graph_name)
    gs.add_vertex(Vertex(3, "person", {"name": "Carol"}), graph=graph_name)
    gs.add_edge(Edge(1, 1, 2, "knows", {}), graph=graph_name)
    gs.add_edge(Edge(2, 2, 3, "knows", {}), graph=graph_name)
    gs.add_edge(Edge(3, 1, 3, "follows", {}), graph=graph_name)
    return engine


def _make_per_table_graph_engine() -> Engine:
    """Create an engine with a per-table graph on table 't'.

    Graph topology::

        1 --knows--> 2 --knows--> 3
        1 --follows--> 3
    """
    engine = Engine()
    engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, name TEXT)")
    engine.add_graph_vertex(Vertex(1, "person", {"name": "Alice"}), table="t")
    engine.add_graph_vertex(Vertex(2, "person", {"name": "Bob"}), table="t")
    engine.add_graph_vertex(Vertex(3, "person", {"name": "Carol"}), table="t")
    engine.add_graph_edge(Edge(1, 1, 2, "knows", {}), table="t")
    engine.add_graph_edge(Edge(2, 2, 3, "knows", {}), table="t")
    engine.add_graph_edge(Edge(3, 1, 3, "follows", {}), table="t")
    return engine


# =====================================================================
# 1. Named graph lifecycle via Engine API + SQL traverse
# =====================================================================


class TestNamedGraphLifecycle:
    """Test create_graph, add vertices/edges, query via SQL traverse."""

    def test_create_graph_and_traverse(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids, "1-hop 'knows' from vertex 1 should reach vertex 2"

    def test_traverse_two_hops(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 2, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids, "vertex 2 reachable in 1 hop"
        assert 3 in ids, "vertex 3 reachable in 2 hops via knows"

    def test_traverse_no_match(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM traverse(3, 'knows', 1, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        # vertex 3 has no outgoing 'knows' edges
        assert 1 not in ids
        assert 2 not in ids

    def test_create_graph_via_sql(self) -> None:
        engine = Engine()
        result = engine.sql("SELECT * FROM create_graph('mygraph')")
        assert len(result.rows) == 1
        assert engine.has_graph("mygraph")

    def test_drop_graph_via_sql(self) -> None:
        engine = Engine()
        engine.sql("SELECT * FROM create_graph('tmp')")
        assert engine.has_graph("tmp")
        engine.sql("SELECT * FROM drop_graph('tmp')")
        assert not engine.has_graph("tmp")

    def test_create_duplicate_graph_fails(self) -> None:
        engine = Engine()
        engine.sql("SELECT * FROM create_graph('g')")
        with pytest.raises(ValueError, match="already exists"):
            engine.sql("SELECT * FROM create_graph('g')")

    def test_drop_nonexistent_graph_fails(self) -> None:
        engine = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("SELECT * FROM drop_graph('nope')")


# =====================================================================
# 2. Named graph RPQ via SQL
# =====================================================================


class TestNamedGraphRPQ:
    """Test rpq() on named graphs."""

    def test_rpq_single_label(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM rpq('knows', 1, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        # Single label 'knows' matches exactly one hop from vertex 1
        assert 2 in ids

    def test_rpq_kleene_star(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM rpq('knows*', 1, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        # knows* from 1: reaches 2 (one hop) and 3 (two hops)
        assert 2 in ids
        assert 3 in ids

    def test_rpq_path_concatenation(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM rpq('knows/knows', 1, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        # 1 --knows--> 2 --knows--> 3
        assert 3 in ids

    def test_rpq_alternation(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM rpq('knows|follows', 1, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        # 'knows' from 1 reaches 2; 'follows' from 1 reaches 3
        assert 2 in ids
        assert 3 in ids


# =====================================================================
# 3. Per-table graph traverse via SQL
# =====================================================================


class TestPerTableGraphTraverse:
    """Test traverse() on per-table graphs."""

    def test_traverse_one_hop(self) -> None:
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 't')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids

    def test_traverse_two_hops(self) -> None:
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 2, 't')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids
        assert 3 in ids

    def test_traverse_different_label(self) -> None:
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT * FROM traverse(1, 'follows', 1, 't')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 3 in ids
        assert 2 not in ids

    def test_traverse_returns_scores(self) -> None:
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT _doc_id, _score FROM traverse(1, 'knows', 1, 't')")
        assert len(result.rows) > 0
        for row in result.rows:
            assert "_score" in row


# =====================================================================
# 4. Per-table graph RPQ via SQL
# =====================================================================


class TestPerTableGraphRPQ:
    """Test rpq() on per-table graphs."""

    def test_rpq_single_label(self) -> None:
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT * FROM rpq('knows', 1, 't')")
        ids = {row["_doc_id"] for row in result.rows}
        # Single label matches one hop: 1 --knows--> 2
        assert 2 in ids

    def test_rpq_kleene_star(self) -> None:
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT * FROM rpq('knows*', 1, 't')")
        ids = {row["_doc_id"] for row in result.rows}
        # knows* reaches 2 (one hop) and 3 (two hops)
        assert 2 in ids
        assert 3 in ids

    def test_rpq_path(self) -> None:
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT * FROM rpq('knows/knows', 1, 't')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 3 in ids

    def test_rpq_follows_then_knows(self) -> None:
        """follows from 1 reaches 3; knows from 3 has no outgoing edges."""
        engine = _make_per_table_graph_engine()
        result = engine.sql("SELECT * FROM rpq('follows/knows', 1, 't')")
        ids = {row["_doc_id"] for row in result.rows}
        # 1 --follows--> 3, but 3 has no outgoing 'knows' edges
        assert 2 not in ids


# =====================================================================
# 5. Named graph temporal traverse via SQL
# =====================================================================


class TestNamedGraphTemporalTraverse:
    """Test temporal_traverse() on named graphs with timestamped edges."""

    @staticmethod
    def _make_temporal_engine() -> Engine:
        engine = Engine()
        engine.create_graph("tnet")
        gs = engine.get_graph("tnet")
        gs.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph="tnet")
        gs.add_vertex(Vertex(2, "person", {"name": "Bob"}), graph="tnet")
        gs.add_vertex(Vertex(3, "person", {"name": "Carol"}), graph="tnet")
        gs.add_edge(
            Edge(1, 1, 2, "knows", {"valid_from": 100, "valid_to": 200}),
            graph="tnet",
        )
        gs.add_edge(
            Edge(2, 1, 3, "knows", {"valid_from": 300, "valid_to": 400}),
            graph="tnet",
        )
        gs.add_edge(
            Edge(3, 2, 3, "works_with", {"valid_from": 150, "valid_to": 350}),
            graph="tnet",
        )
        return engine

    def test_temporal_traverse_point_in_time(self) -> None:
        engine = self._make_temporal_engine()
        result = engine.sql(
            "SELECT * FROM temporal_traverse(1, 'knows', 2, 150, 'graph:tnet')"
        )
        ids = {row["_doc_id"] for row in result.rows}
        # At t=150, edge 1->2 (valid_from=100, valid_to=200) is active
        assert 2 in ids
        # Edge 1->3 (valid_from=300) is NOT active at t=150
        assert 3 not in ids

    def test_temporal_traverse_time_range(self) -> None:
        engine = self._make_temporal_engine()
        result = engine.sql(
            "SELECT * FROM temporal_traverse(1, 'knows', 2, 100, 400, 'graph:tnet')"
        )
        ids = {row["_doc_id"] for row in result.rows}
        # Range [100, 400] covers both edges from vertex 1
        assert 2 in ids
        assert 3 in ids

    def test_temporal_traverse_no_match(self) -> None:
        engine = self._make_temporal_engine()
        result = engine.sql(
            "SELECT * FROM temporal_traverse(1, 'knows', 1, 500, 'graph:tnet')"
        )
        ids = {row["_doc_id"] for row in result.rows}
        # t=500 is beyond all edge validity ranges
        assert 2 not in ids
        assert 3 not in ids

    def test_temporal_traverse_per_table(self) -> None:
        """Temporal traverse on a per-table graph."""
        engine = Engine()
        engine.sql("CREATE TABLE tt (id SERIAL PRIMARY KEY, name TEXT)")
        engine.add_graph_vertex(Vertex(1, "person", {"name": "Alice"}), table="tt")
        engine.add_graph_vertex(Vertex(2, "person", {"name": "Bob"}), table="tt")
        engine.add_graph_edge(
            Edge(1, 1, 2, "knows", {"valid_from": 10, "valid_to": 20}),
            table="tt",
        )
        result = engine.sql("SELECT * FROM temporal_traverse(1, 'knows', 1, 15, 'tt')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids


# =====================================================================
# 6. Named graph Cypher via SQL
# =====================================================================


class TestNamedGraphCypher:
    """Test cypher() SQL function on named graphs."""

    def test_cypher_create_and_match(self) -> None:
        engine = Engine()
        engine.sql("SELECT * FROM create_graph('cg')")
        engine.sql("""
            SELECT * FROM cypher('cg', $$
                CREATE (a:Person {name: 'Alice', age: 30})
            $$) AS (a agtype)
        """)
        engine.sql("""
            SELECT * FROM cypher('cg', $$
                CREATE (b:Person {name: 'Bob', age: 25})
            $$) AS (b agtype)
        """)
        result = engine.sql("""
            SELECT * FROM cypher('cg', $$
                MATCH (n:Person) RETURN n.name, n.age
            $$) AS (name agtype, age agtype)
        """)
        assert len(result.rows) == 2
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Bob"}

    def test_cypher_create_relationship_and_traverse(self) -> None:
        engine = Engine()
        engine.sql("SELECT * FROM create_graph('rg')")
        engine.sql("""
            SELECT * FROM cypher('rg', $$
                CREATE (a:Person {name: 'X'})-[:KNOWS]->(b:Person {name: 'Y'})
            $$) AS (a agtype, b agtype)
        """)
        result = engine.sql("""
            SELECT * FROM cypher('rg', $$
                MATCH (a)-[r:KNOWS]->(b) RETURN a.name, b.name
            $$) AS (src agtype, tgt agtype)
        """)
        assert len(result.rows) == 1
        assert result.rows[0]["src"] == "X"
        assert result.rows[0]["tgt"] == "Y"

    def test_cypher_match_where(self) -> None:
        engine = Engine()
        engine.sql("SELECT * FROM create_graph('wg')")
        for name, age in [("A", 20), ("B", 30), ("C", 40)]:
            engine.sql(f"""
                SELECT * FROM cypher('wg', $$
                    CREATE (:Person {{name: '{name}', age: {age}}})
                $$) AS (v agtype)
            """)
        result = engine.sql("""
            SELECT * FROM cypher('wg', $$
                MATCH (n:Person) WHERE n.age > 25 RETURN n.name
            $$) AS (name agtype)
        """)
        names = {r["name"] for r in result.rows}
        assert names == {"B", "C"}

    def test_cypher_sql_where_filter(self) -> None:
        """SQL WHERE on top of Cypher results."""
        engine = Engine()
        engine.sql("SELECT * FROM create_graph('fg')")
        for name, age in [("A", 20), ("B", 30), ("C", 40)]:
            engine.sql(f"""
                SELECT * FROM cypher('fg', $$
                    CREATE (:Person {{name: '{name}', age: {age}}})
                $$) AS (v agtype)
            """)
        result = engine.sql("""
            SELECT name FROM cypher('fg', $$
                MATCH (n:Person) RETURN n.name AS name, n.age AS age
            $$) AS (name agtype, age agtype)
            WHERE age > 25
        """)
        names = {r["name"] for r in result.rows}
        assert names == {"B", "C"}


# =====================================================================
# 7. Graph isolation via SQL
# =====================================================================


class TestGraphIsolation:
    """Verify that named graphs are isolated from each other."""

    def test_two_graphs_isolated_traverse(self) -> None:
        engine = Engine()

        # Graph g1: 1 --knows--> 2
        engine.create_graph("g1")
        gs = engine.get_graph("g1")
        gs.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph="g1")
        gs.add_vertex(Vertex(2, "person", {"name": "Bob"}), graph="g1")
        gs.add_edge(Edge(1, 1, 2, "knows", {}), graph="g1")

        # Graph g2: 1 --knows--> 3
        engine.create_graph("g2")
        gs2 = engine.get_graph("g2")
        gs2.add_vertex(Vertex(1, "person", {"name": "Alice"}), graph="g2")
        gs2.add_vertex(Vertex(3, "person", {"name": "Carol"}), graph="g2")
        gs2.add_edge(Edge(2, 1, 3, "knows", {}), graph="g2")

        # Traverse g1: should see 2, NOT 3
        r1 = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'graph:g1')")
        ids_g1 = {row["_doc_id"] for row in r1.rows}
        assert 2 in ids_g1
        assert 3 not in ids_g1

        # Traverse g2: should see 3, NOT 2
        r2 = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'graph:g2')")
        ids_g2 = {row["_doc_id"] for row in r2.rows}
        assert 3 in ids_g2
        assert 2 not in ids_g2

    def test_two_graphs_isolated_rpq(self) -> None:
        engine = Engine()

        engine.create_graph("rg1")
        gs = engine.get_graph("rg1")
        gs.add_vertex(Vertex(1, "p", {}), graph="rg1")
        gs.add_vertex(Vertex(2, "p", {}), graph="rg1")
        gs.add_edge(Edge(1, 1, 2, "link", {}), graph="rg1")

        engine.create_graph("rg2")
        gs2 = engine.get_graph("rg2")
        gs2.add_vertex(Vertex(1, "p", {}), graph="rg2")
        gs2.add_vertex(Vertex(3, "p", {}), graph="rg2")
        gs2.add_edge(Edge(2, 1, 3, "link", {}), graph="rg2")

        r1 = engine.sql("SELECT * FROM rpq('link', 1, 'graph:rg1')")
        ids1 = {row["_doc_id"] for row in r1.rows}
        assert 2 in ids1
        assert 3 not in ids1

        r2 = engine.sql("SELECT * FROM rpq('link', 1, 'graph:rg2')")
        ids2 = {row["_doc_id"] for row in r2.rows}
        assert 3 in ids2
        assert 2 not in ids2

    def test_per_table_graphs_isolated(self) -> None:
        engine = Engine()
        engine.sql("CREATE TABLE t1 (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("CREATE TABLE t2 (id SERIAL PRIMARY KEY, name TEXT)")
        engine.add_graph_vertex(Vertex(1, "p", {}), table="t1")
        engine.add_graph_vertex(Vertex(2, "p", {}), table="t1")
        engine.add_graph_edge(Edge(1, 1, 2, "knows", {}), table="t1")

        engine.add_graph_vertex(Vertex(1, "p", {}), table="t2")
        engine.add_graph_vertex(Vertex(3, "p", {}), table="t2")
        engine.add_graph_edge(Edge(2, 1, 3, "knows", {}), table="t2")

        r1 = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 't1')")
        ids1 = {row["_doc_id"] for row in r1.rows}
        assert 2 in ids1
        assert 3 not in ids1

        r2 = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 't2')")
        ids2 = {row["_doc_id"] for row in r2.rows}
        assert 3 in ids2
        assert 2 not in ids2


# =====================================================================
# 8. Graph algebra then SQL query
# =====================================================================


class TestGraphAlgebraSQL:
    """Test union/intersect/difference followed by SQL traverse."""

    def test_union_graphs_traverse(self) -> None:
        engine = Engine()

        # g1: 1 --knows--> 2
        engine.create_graph("ug1")
        gs = engine.get_graph("ug1")
        gs.add_vertex(Vertex(1, "p", {"name": "Alice"}), graph="ug1")
        gs.add_vertex(Vertex(2, "p", {"name": "Bob"}), graph="ug1")
        gs.add_edge(Edge(1, 1, 2, "knows", {}), graph="ug1")

        # g2: 1 --knows--> 3
        engine.create_graph("ug2")
        gs.add_vertex(Vertex(1, "p", {"name": "Alice"}), graph="ug2")
        gs.add_vertex(Vertex(3, "p", {"name": "Carol"}), graph="ug2")
        gs.add_edge(Edge(2, 1, 3, "knows", {}), graph="ug2")

        # Union
        engine.graph_store.union_graphs("ug1", "ug2", "merged")
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'graph:merged')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids, "vertex 2 from ug1 should be in merged"
        assert 3 in ids, "vertex 3 from ug2 should be in merged"

    def test_intersect_graphs_traverse(self) -> None:
        engine = Engine()

        # g1: 1 --knows--> 2, 1 --knows--> 3
        engine.create_graph("ig1")
        gs = engine.get_graph("ig1")
        gs.add_vertex(Vertex(1, "p", {}), graph="ig1")
        gs.add_vertex(Vertex(2, "p", {}), graph="ig1")
        gs.add_vertex(Vertex(3, "p", {}), graph="ig1")
        gs.add_edge(Edge(1, 1, 2, "knows", {}), graph="ig1")
        gs.add_edge(Edge(2, 1, 3, "knows", {}), graph="ig1")

        # g2: 1 --knows--> 2 (same edge id=1)
        engine.create_graph("ig2")
        gs.add_vertex(Vertex(1, "p", {}), graph="ig2")
        gs.add_vertex(Vertex(2, "p", {}), graph="ig2")
        gs.add_edge(Edge(1, 1, 2, "knows", {}), graph="ig2")

        engine.graph_store.intersect_graphs("ig1", "ig2", "common")
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'graph:common')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids, "vertex 2 is in both graphs"
        # vertex 3 and edge 2 are only in ig1, so not in intersection
        assert 3 not in ids

    def test_difference_graphs_traverse(self) -> None:
        engine = Engine()

        # g1: 1 --knows--> 2, 1 --knows--> 3
        engine.create_graph("dg1")
        gs = engine.get_graph("dg1")
        gs.add_vertex(Vertex(1, "p", {}), graph="dg1")
        gs.add_vertex(Vertex(2, "p", {}), graph="dg1")
        gs.add_vertex(Vertex(3, "p", {}), graph="dg1")
        gs.add_edge(Edge(1, 1, 2, "knows", {}), graph="dg1")
        gs.add_edge(Edge(2, 1, 3, "knows", {}), graph="dg1")

        # g2: has vertex 2, edge 1
        engine.create_graph("dg2")
        gs.add_vertex(Vertex(1, "p", {}), graph="dg2")
        gs.add_vertex(Vertex(2, "p", {}), graph="dg2")
        gs.add_edge(Edge(1, 1, 2, "knows", {}), graph="dg2")

        engine.graph_store.difference_graphs("dg1", "dg2", "diff")
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'graph:diff')")
        ids = {row["_doc_id"] for row in result.rows}
        # Only edge 2 (1->3) remains after removing dg2's edge 1
        assert 3 in ids
        assert 2 not in ids


# =====================================================================
# 9. Per-table graph centrality via SQL
# =====================================================================


class TestPerTableGraphCentrality:
    """Test pagerank(), hits(), betweenness() with per-table and named graphs."""

    @staticmethod
    def _make_centrality_engine() -> Engine:
        engine = Engine()
        engine.sql("CREATE TABLE net (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO net (name) VALUES ('A'), ('B'), ('C'), ('D')")
        for i in range(1, 5):
            engine.add_graph_vertex(
                Vertex(i, "node", {"name": chr(64 + i)}), table="net"
            )
        engine.add_graph_edge(Edge(1, 1, 2, "link", {}), table="net")
        engine.add_graph_edge(Edge(2, 2, 3, "link", {}), table="net")
        engine.add_graph_edge(Edge(3, 3, 4, "link", {}), table="net")
        engine.add_graph_edge(Edge(4, 2, 1, "link", {}), table="net")
        return engine

    def test_pagerank_from(self) -> None:
        engine = self._make_centrality_engine()
        result = engine.sql("SELECT _doc_id, _score FROM pagerank('net')")
        assert len(result.rows) > 0
        for row in result.rows:
            assert 0.0 <= row["_score"] <= 1.0

    def test_pagerank_custom_damping(self) -> None:
        engine = self._make_centrality_engine()
        result = engine.sql("SELECT _doc_id, _score FROM pagerank(0.95, 'net')")
        assert len(result.rows) > 0

    def test_hits_from(self) -> None:
        engine = self._make_centrality_engine()
        result = engine.sql("SELECT _doc_id, _score FROM hits('net')")
        assert len(result.rows) > 0

    def test_betweenness_from(self) -> None:
        engine = self._make_centrality_engine()
        result = engine.sql("SELECT _doc_id, _score FROM betweenness('net')")
        assert len(result.rows) > 0

    def test_pagerank_order_by(self) -> None:
        engine = self._make_centrality_engine()
        result = engine.sql(
            "SELECT _doc_id, _score FROM pagerank('net') ORDER BY _score DESC LIMIT 2"
        )
        assert len(result.rows) == 2
        assert result.rows[0]["_score"] >= result.rows[1]["_score"]

    def test_pagerank_count(self) -> None:
        engine = self._make_centrality_engine()
        result = engine.sql("SELECT COUNT(*) AS cnt FROM pagerank('net')")
        assert result.rows[0]["cnt"] == 4

    def test_centrality_named_graph(self) -> None:
        """pagerank on a named graph via 'graph:' prefix (backward compat)."""
        engine = Engine()
        engine.create_graph("cg")
        gs = engine.get_graph("cg")
        for i in range(1, 4):
            gs.add_vertex(Vertex(i, "node", {}), graph="cg")
        gs.add_edge(Edge(1, 1, 2, "link", {}), graph="cg")
        gs.add_edge(Edge(2, 2, 3, "link", {}), graph="cg")
        gs.add_edge(Edge(3, 3, 1, "link", {}), graph="cg")

        result = engine.sql("SELECT _doc_id, _score FROM pagerank('graph:cg')")
        assert len(result.rows) == 3
        for row in result.rows:
            assert row["_score"] > 0.0

    def test_hits_named_graph(self) -> None:
        engine = Engine()
        engine.create_graph("hg")
        gs = engine.get_graph("hg")
        for i in range(1, 4):
            gs.add_vertex(Vertex(i, "node", {}), graph="hg")
        gs.add_edge(Edge(1, 1, 2, "link", {}), graph="hg")
        gs.add_edge(Edge(2, 2, 3, "link", {}), graph="hg")

        result = engine.sql("SELECT _doc_id, _score FROM hits('graph:hg')")
        assert len(result.rows) > 0

    def test_betweenness_named_graph(self) -> None:
        engine = Engine()
        engine.create_graph("bg")
        gs = engine.get_graph("bg")
        for i in range(1, 4):
            gs.add_vertex(Vertex(i, "node", {}), graph="bg")
        gs.add_edge(Edge(1, 1, 2, "link", {}), graph="bg")
        gs.add_edge(Edge(2, 2, 3, "link", {}), graph="bg")

        result = engine.sql("SELECT _doc_id, _score FROM betweenness('graph:bg')")
        assert len(result.rows) > 0


# =====================================================================
# 10. Per-table message passing and graph embedding via SQL
# =====================================================================


class TestPerTableMessagePassing:
    """Test message_passing() and graph_embedding() via SQL WHERE clause."""

    @staticmethod
    def _make_gnn_engine() -> Engine:
        engine = Engine()
        engine.sql("CREATE TABLE g (id SERIAL PRIMARY KEY, name TEXT)")
        gs = engine._tables["g"].graph_store
        gs.add_vertex(Vertex(1, "person", {"score": 0.8}), graph="g")
        gs.add_vertex(Vertex(2, "person", {"score": 0.6}), graph="g")
        gs.add_vertex(Vertex(3, "person", {"score": 0.4}), graph="g")
        gs.add_edge(Edge(1, 1, 2, "knows", {}), graph="g")
        gs.add_edge(Edge(2, 2, 3, "knows", {}), graph="g")
        return engine

    def test_message_passing_sql(self) -> None:
        engine = self._make_gnn_engine()
        result = engine.sql("SELECT * FROM g WHERE message_passing(2, 'mean', 'score')")
        assert result is not None
        assert len(result.rows) > 0

    def test_graph_embedding_sql(self) -> None:
        engine = self._make_gnn_engine()
        result = engine.sql("SELECT * FROM g WHERE graph_embedding(16, 2)")
        assert result is not None
        assert len(result.rows) > 0


# =====================================================================
# 11. Graph vertex/edge management via SQL functions
# =====================================================================


class TestGraphManagementSQL:
    """Test graph_add_vertex() and graph_add_edge() SQL functions."""

    def test_add_vertex_via_sql(self) -> None:
        engine = Engine()
        engine.sql("CREATE TABLE m (id SERIAL PRIMARY KEY, name TEXT)")
        result = engine.sql(
            "SELECT * FROM graph_add_vertex(1, 'person', 'm', 'name=Alice')"
        )
        assert len(result.rows) == 1
        gs = engine._tables["m"].graph_store
        v = gs.get_vertex(1)
        assert v is not None
        assert v.label == "person"
        assert v.properties.get("name") == "Alice"

    def test_add_edge_via_sql(self) -> None:
        engine = Engine()
        engine.sql("CREATE TABLE m (id SERIAL PRIMARY KEY, name TEXT)")
        engine.add_graph_vertex(Vertex(1, "p", {}), table="m")
        engine.add_graph_vertex(Vertex(2, "p", {}), table="m")
        result = engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'knows', 'm')")
        assert len(result.rows) == 1
        # Now traverse should work
        tr = engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'm')")
        ids = {row["_doc_id"] for row in tr.rows}
        assert 2 in ids

    def test_add_vertex_and_edge_then_rpq(self) -> None:
        engine = Engine()
        engine.sql("CREATE TABLE m (id SERIAL PRIMARY KEY)")
        engine.sql("SELECT * FROM graph_add_vertex(1, 'p', 'm')")
        engine.sql("SELECT * FROM graph_add_vertex(2, 'p', 'm')")
        engine.sql("SELECT * FROM graph_add_vertex(3, 'p', 'm')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'link', 'm')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'link', 'm')")
        result = engine.sql("SELECT * FROM rpq('link/link', 1, 'm')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 3 in ids


# =====================================================================
# 12. Combined: traverse with aggregation and ordering
# =====================================================================


class TestTraverseWithSQL:
    """Test graph traverse results combined with SQL features."""

    @staticmethod
    def _make_employee_engine() -> Engine:
        engine = Engine()
        engine.sql(
            "CREATE TABLE employees "
            "(id SERIAL PRIMARY KEY, name TEXT, salary REAL, role TEXT)"
        )
        engine.sql(
            "INSERT INTO employees (name, salary, role) "
            "VALUES ('Alice', 100000, 'manager')"
        )
        engine.sql(
            "INSERT INTO employees (name, salary, role) "
            "VALUES ('Bob', 80000, 'engineer')"
        )
        engine.sql(
            "INSERT INTO employees (name, salary, role) "
            "VALUES ('Carol', 90000, 'engineer')"
        )
        engine.sql(
            "INSERT INTO employees (name, salary, role) "
            "VALUES ('Dave', 70000, 'intern')"
        )
        for i in range(1, 5):
            engine.add_graph_vertex(Vertex(i, "employee", {}), table="employees")
        # Alice manages Bob and Carol; Bob manages Dave
        engine.add_graph_edge(Edge(1, 1, 2, "manages", {}), table="employees")
        engine.add_graph_edge(Edge(2, 1, 3, "manages", {}), table="employees")
        engine.add_graph_edge(Edge(3, 2, 4, "manages", {}), table="employees")
        return engine

    def test_count_from_traverse(self) -> None:
        engine = self._make_employee_engine()
        result = engine.sql(
            "SELECT COUNT(*) AS cnt FROM traverse(1, 'manages', 2, 'employees')"
        )
        # Start vertex (1) + 1->2, 1->3 (hop 1) + 2->4 (hop 2) = 4
        assert result.rows[0]["cnt"] == 4

    def test_sum_from_traverse(self) -> None:
        engine = self._make_employee_engine()
        result = engine.sql(
            "SELECT SUM(salary) AS total FROM traverse(1, 'manages', 1, 'employees')"
        )
        # Start vertex Alice (100000) + Bob (80000) + Carol (90000)
        assert result.rows[0]["total"] == 270000

    def test_order_by_from_traverse(self) -> None:
        engine = self._make_employee_engine()
        result = engine.sql(
            "SELECT name, salary FROM traverse(1, 'manages', 1, 'employees') "
            "ORDER BY salary DESC"
        )
        # Start vertex (Alice) + 2 direct reports = 3 rows
        assert len(result.rows) == 3
        assert result.rows[0]["salary"] >= result.rows[1]["salary"]
        assert result.rows[1]["salary"] >= result.rows[2]["salary"]

    def test_select_star_from_traverse(self) -> None:
        engine = self._make_employee_engine()
        result = engine.sql("SELECT * FROM traverse(1, 'manages', 1, 'employees')")
        # Start vertex (Alice) + 2 direct reports (Bob, Carol) = 3 rows
        assert len(result.rows) == 3
        names = {r["name"] for r in result.rows}
        assert names == {"Alice", "Bob", "Carol"}


# =====================================================================
# 13. Edge cases
# =====================================================================


class TestEdgeCases:
    """Edge cases for graph SQL functions."""

    def test_traverse_nonexistent_label(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql(
            "SELECT * FROM traverse(1, 'nonexistent', 1, 'graph:social')"
        )
        ids = {row["_doc_id"] for row in result.rows}
        # Only the start vertex is returned; no neighbors via 'nonexistent'
        assert ids == {1}

    def test_rpq_nonexistent_label(self) -> None:
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM rpq('nonexistent', 1, 'graph:social')")
        assert len(result.rows) == 0

    def test_traverse_from_isolated_vertex(self) -> None:
        engine = Engine()
        engine.create_graph("iso")
        gs = engine.get_graph("iso")
        gs.add_vertex(Vertex(99, "lonely", {}), graph="iso")
        result = engine.sql("SELECT * FROM traverse(99, 'any', 1, 'graph:iso')")
        ids = {row["_doc_id"] for row in result.rows}
        # Only the start vertex itself; no neighbors
        assert ids == {99}

    def test_rpq_from_isolated_vertex(self) -> None:
        engine = Engine()
        engine.create_graph("iso2")
        gs = engine.get_graph("iso2")
        gs.add_vertex(Vertex(99, "lonely", {}), graph="iso2")
        result = engine.sql("SELECT * FROM rpq('any', 99, 'graph:iso2')")
        assert len(result.rows) == 0

    def test_traverse_nonexistent_table_fails(self) -> None:
        engine = Engine()
        with pytest.raises(ValueError, match="is not a table or named graph"):
            engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'no_such_table')")


# =====================================================================
# 14. Direct graph name (no 'graph:' prefix)
# =====================================================================


class TestDirectGraphName:
    """Verify that graph functions accept graph names directly without
    the legacy ``'graph:'`` prefix."""

    def test_traverse_named_graph_without_prefix(self) -> None:
        """traverse() should work with direct graph name (no 'graph:' prefix)."""
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 2, 'social')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids
        assert 3 in ids

    def test_rpq_named_graph_without_prefix(self) -> None:
        """rpq() should work with direct graph name (no 'graph:' prefix)."""
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM rpq('knows', 1, 'social')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids

    def test_temporal_traverse_named_graph_without_prefix(self) -> None:
        """temporal_traverse() should work with direct graph name."""
        engine = Engine()
        engine.create_graph("tg")
        gs = engine.get_graph("tg")
        gs.add_vertex(Vertex(1, "p", {"name": "A"}), graph="tg")
        gs.add_vertex(Vertex(2, "p", {"name": "B"}), graph="tg")
        gs.add_edge(
            Edge(1, 1, 2, "knows", {"valid_from": 10, "valid_to": 20}),
            graph="tg",
        )
        result = engine.sql("SELECT * FROM temporal_traverse(1, 'knows', 1, 15, 'tg')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids

    def test_pagerank_named_graph_without_prefix(self) -> None:
        """pagerank() should work with direct graph name."""
        engine = Engine()
        engine.create_graph("pg")
        gs = engine.get_graph("pg")
        for i in range(1, 4):
            gs.add_vertex(Vertex(i, "node", {}), graph="pg")
        gs.add_edge(Edge(1, 1, 2, "link", {}), graph="pg")
        gs.add_edge(Edge(2, 2, 3, "link", {}), graph="pg")
        gs.add_edge(Edge(3, 3, 1, "link", {}), graph="pg")
        result = engine.sql("SELECT _doc_id, _score FROM pagerank('pg')")
        assert len(result.rows) == 3

    def test_hits_named_graph_without_prefix(self) -> None:
        """hits() should work with direct graph name."""
        engine = Engine()
        engine.create_graph("hg2")
        gs = engine.get_graph("hg2")
        for i in range(1, 4):
            gs.add_vertex(Vertex(i, "node", {}), graph="hg2")
        gs.add_edge(Edge(1, 1, 2, "link", {}), graph="hg2")
        gs.add_edge(Edge(2, 2, 3, "link", {}), graph="hg2")
        result = engine.sql("SELECT _doc_id, _score FROM hits('hg2')")
        assert len(result.rows) > 0

    def test_betweenness_named_graph_without_prefix(self) -> None:
        """betweenness() should work with direct graph name."""
        engine = Engine()
        engine.create_graph("bg2")
        gs = engine.get_graph("bg2")
        for i in range(1, 4):
            gs.add_vertex(Vertex(i, "node", {}), graph="bg2")
        gs.add_edge(Edge(1, 1, 2, "link", {}), graph="bg2")
        gs.add_edge(Edge(2, 2, 3, "link", {}), graph="bg2")
        result = engine.sql("SELECT _doc_id, _score FROM betweenness('bg2')")
        assert len(result.rows) > 0

    def test_traverse_with_prefix_still_works(self) -> None:
        """Backward compat: 'graph:' prefix should still work."""
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM traverse(1, 'knows', 2, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids
        assert 3 in ids

    def test_rpq_with_prefix_still_works(self) -> None:
        """Backward compat: 'graph:' prefix should still work for rpq."""
        engine = _make_named_graph_engine("social")
        result = engine.sql("SELECT * FROM rpq('knows', 1, 'graph:social')")
        ids = {row["_doc_id"] for row in result.rows}
        assert 2 in ids

    def test_pagerank_signal_named_graph(self) -> None:
        """pagerank() in WHERE clause should accept a named graph argument."""
        engine = Engine()
        engine.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO docs (name) VALUES ('A'), ('B'), ('C')")
        for i in range(1, 4):
            engine.sql(f"SELECT * FROM graph_add_vertex({i}, 'node', 'docs')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'link', 'docs')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'link', 'docs')")
        engine.sql("SELECT * FROM graph_add_edge(3, 3, 1, 'link', 'docs')")
        result = engine.sql("SELECT name, _score FROM docs WHERE pagerank('docs')")
        assert len(result.rows) == 3
        for row in result.rows:
            assert 0.0 <= row["_score"] <= 1.0

    def test_pagerank_signal_named_graph_with_params(self) -> None:
        """pagerank(damping, max_iter, tol, 'graph') in WHERE clause."""
        engine = Engine()
        engine.sql("CREATE TABLE docs2 (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO docs2 (name) VALUES ('X'), ('Y'), ('Z')")
        for i in range(1, 4):
            engine.sql(f"SELECT * FROM graph_add_vertex({i}, 'node', 'docs2')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'link', 'docs2')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'link', 'docs2')")
        result = engine.sql(
            "SELECT name, _score FROM docs2 WHERE pagerank(0.90, 50, 1e-5, 'docs2')"
        )
        assert len(result.rows) > 0

    def test_hits_signal_named_graph(self) -> None:
        """hits() in WHERE clause should accept a named graph argument."""
        engine = Engine()
        engine.sql("CREATE TABLE hdocs (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO hdocs (name) VALUES ('A'), ('B'), ('C')")
        for i in range(1, 4):
            engine.sql(f"SELECT * FROM graph_add_vertex({i}, 'node', 'hdocs')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'link', 'hdocs')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'link', 'hdocs')")
        result = engine.sql("SELECT name, _score FROM hdocs WHERE hits('hdocs')")
        assert len(result.rows) > 0

    def test_betweenness_signal_named_graph(self) -> None:
        """betweenness() in WHERE clause should accept a named graph argument."""
        engine = Engine()
        engine.sql("CREATE TABLE bdocs (id SERIAL PRIMARY KEY, name TEXT)")
        engine.sql("INSERT INTO bdocs (name) VALUES ('A'), ('B'), ('C')")
        for i in range(1, 4):
            engine.sql(f"SELECT * FROM graph_add_vertex({i}, 'node', 'bdocs')")
        engine.sql("SELECT * FROM graph_add_edge(1, 1, 2, 'link', 'bdocs')")
        engine.sql("SELECT * FROM graph_add_edge(2, 2, 3, 'link', 'bdocs')")
        result = engine.sql("SELECT name, _score FROM bdocs WHERE betweenness('bdocs')")
        assert len(result.rows) > 0

    def test_nonexistent_graph_without_prefix_fails(self) -> None:
        """Error for names that are neither table nor named graph."""
        engine = Engine()
        with pytest.raises(ValueError, match="is not a table or named graph"):
            engine.sql("SELECT * FROM traverse(1, 'knows', 1, 'nonexistent')")
