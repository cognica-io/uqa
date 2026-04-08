#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""SQL-level tests for standalone property graph functions.

Tests graph_create_node, graph_create_edge, graph_nodes, graph_neighbors,
graph_delete_node, and graph_delete_edge -- all operating on named graphs
through ``engine.sql()``.
"""

from __future__ import annotations

import json

import pytest

from uqa.engine import Engine

# =====================================================================
# Helpers
# =====================================================================


def _engine_with_graph(name: str = "social") -> Engine:
    """Create an engine with an empty named graph."""
    engine = Engine()
    engine.sql(f"SELECT * FROM create_graph('{name}')")
    return engine


def _engine_with_social_graph() -> Engine:
    """Create an engine with a small social graph built via SQL functions.

    Graph topology::

        Alice(1) --KNOWS--> Bob(2) --KNOWS--> Carol(3)
        Alice(1) --FOLLOWS--> Carol(3)
    """
    engine = _engine_with_graph("social")
    engine.sql(
        "SELECT * FROM graph_create_node('social', 'Person', "
        '\'{"name":"Alice","age":30}\')'
    )
    engine.sql(
        "SELECT * FROM graph_create_node('social', 'Person', "
        '\'{"name":"Bob","age":25}\')'
    )
    engine.sql(
        "SELECT * FROM graph_create_node('social', 'Person', "
        '\'{"name":"Carol","age":35}\')'
    )
    engine.sql("SELECT * FROM graph_create_edge('social', 'KNOWS', 1, 2, '{}')")
    engine.sql("SELECT * FROM graph_create_edge('social', 'KNOWS', 2, 3, '{}')")
    engine.sql("SELECT * FROM graph_create_edge('social', 'FOLLOWS', 1, 3, '{}')")
    return engine


# =====================================================================
# graph_create_node
# =====================================================================


class TestGraphCreateNode:
    def test_basic_creation(self) -> None:
        engine = _engine_with_graph()
        result = engine.sql(
            "SELECT * FROM graph_create_node('social', 'Person', "
            '\'{"name":"Alice"}\')'
        )
        assert len(result.rows) == 1
        node_id = result.rows[0]["id"]
        assert node_id == "social:Person:1"

    def test_auto_increment_id(self) -> None:
        engine = _engine_with_graph()
        r1 = engine.sql("SELECT * FROM graph_create_node('social', 'A', '{}')")
        r2 = engine.sql("SELECT * FROM graph_create_node('social', 'B', '{}')")
        assert r1.rows[0]["id"] == "social:A:1"
        assert r2.rows[0]["id"] == "social:B:2"

    def test_no_properties(self) -> None:
        engine = _engine_with_graph()
        result = engine.sql("SELECT * FROM graph_create_node('social', 'Tag')")
        assert result.rows[0]["id"] == "social:Tag:1"

    def test_complex_properties(self) -> None:
        engine = _engine_with_graph()
        props = json.dumps({"name": "Alice", "scores": [1, 2, 3], "active": True})
        engine.sql(f"SELECT * FROM graph_create_node('social', 'User', '{props}')")
        rows = engine.sql("SELECT * FROM graph_nodes('social', 'User')").rows
        assert len(rows) == 1
        stored = json.loads(rows[0]["properties"])
        assert stored["scores"] == [1, 2, 3]
        assert stored["active"] is True

    def test_nonexistent_graph_raises(self) -> None:
        engine = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("SELECT * FROM graph_create_node('nope', 'X', '{}')")

    def test_missing_label_raises(self) -> None:
        engine = _engine_with_graph()
        with pytest.raises(ValueError):
            engine.sql("SELECT * FROM graph_create_node('social')")


# =====================================================================
# graph_create_edge
# =====================================================================


class TestGraphCreateEdge:
    def test_basic_creation(self) -> None:
        engine = _engine_with_graph()
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        result = engine.sql(
            "SELECT * FROM graph_create_edge('social', 'KNOWS', 1, 2, '{}')"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == "social:KNOWS:1"

    def test_auto_increment_edge_id(self) -> None:
        engine = _engine_with_graph()
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        r1 = engine.sql("SELECT * FROM graph_create_edge('social', 'A', 1, 2, '{}')")
        r2 = engine.sql("SELECT * FROM graph_create_edge('social', 'B', 2, 3, '{}')")
        assert r1.rows[0]["id"] == "social:A:1"
        assert r2.rows[0]["id"] == "social:B:2"

    def test_edge_with_properties(self) -> None:
        engine = _engine_with_graph()
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql(
            "SELECT * FROM graph_create_edge('social', 'KNOWS', 1, 2, "
            '\'{"since":2020,"weight":0.9}\')'
        )
        # Verify edge exists by traversing
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 1
        assert rows[0]["id"] == 2

    def test_no_properties(self) -> None:
        engine = _engine_with_graph()
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        result = engine.sql("SELECT * FROM graph_create_edge('social', 'LINK', 1, 2)")
        assert result.rows[0]["id"] == "social:LINK:1"

    def test_missing_args_raises(self) -> None:
        engine = _engine_with_graph()
        with pytest.raises(ValueError):
            engine.sql("SELECT * FROM graph_create_edge('social', 'KNOWS', 1)")


# =====================================================================
# graph_nodes
# =====================================================================


class TestGraphNodes:
    def test_all_nodes(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT * FROM graph_nodes('social')").rows
        assert len(rows) == 3
        ids = {row["id"] for row in rows}
        assert ids == {1, 2, 3}

    def test_filter_by_label(self) -> None:
        engine = _engine_with_graph()
        engine.sql(
            "SELECT * FROM graph_create_node('social', 'Person', "
            '\'{"name":"Alice"}\')'
        )
        engine.sql(
            "SELECT * FROM graph_create_node('social', 'Company', "
            '\'{"name":"Cognica"}\')'
        )
        rows = engine.sql("SELECT * FROM graph_nodes('social', 'Person')").rows
        assert len(rows) == 1
        assert rows[0]["label"] == "Person"

    def test_filter_by_properties(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_nodes('social', 'Person', '{\"name\":\"Bob\"}')"
        ).rows
        assert len(rows) == 1
        props = json.loads(rows[0]["properties"])
        assert props["name"] == "Bob"
        assert props["age"] == 25

    def test_filter_no_match(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_nodes('social', 'Person', '{\"name\":\"Nobody\"}')"
        ).rows
        assert len(rows) == 0

    def test_properties_column_is_json(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT * FROM graph_nodes('social', 'Person')").rows
        for row in rows:
            props = json.loads(row["properties"])
            assert "name" in props

    def test_empty_graph(self) -> None:
        engine = _engine_with_graph()
        rows = engine.sql("SELECT * FROM graph_nodes('social')").rows
        assert len(rows) == 0

    def test_nonexistent_graph_raises(self) -> None:
        engine = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("SELECT * FROM graph_nodes('nope')")


# =====================================================================
# graph_neighbors
# =====================================================================


class TestGraphNeighbors:
    def test_one_hop_outgoing(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 1
        assert rows[0]["id"] == 2
        assert rows[0]["depth"] == 1

    def test_two_hop_outgoing(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 2)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_incoming_direction(self) -> None:
        engine = _engine_with_social_graph()
        # Carol (3) has incoming KNOWS from Bob (2) and FOLLOWS from Alice (1)
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 3, 'KNOWS', 'incoming', 1)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2}

    def test_both_directions(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 2, 'KNOWS', 'both', 1)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {1, 3}

    def test_no_edge_label_filter(self) -> None:
        engine = _engine_with_social_graph()
        # All outgoing from Alice: KNOWS->Bob, FOLLOWS->Carol
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, '', 'outgoing', 1)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_depth_path(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 2)"
        ).rows
        depth_map = {row["id"]: row["depth"] for row in rows}
        assert depth_map[2] == 1
        assert depth_map[3] == 2

        # Verify path
        for row in rows:
            path = json.loads(row["path"])
            assert path[0] == 1  # starts from source
            assert path[-1] == row["id"]  # ends at target

    def test_no_neighbors(self) -> None:
        engine = _engine_with_social_graph()
        # Carol has no outgoing KNOWS edges
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 3, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 0

    def test_default_direction_and_depth(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT * FROM graph_neighbors('social', 1, 'KNOWS')").rows
        # Default: outgoing, depth 1
        assert len(rows) == 1
        assert rows[0]["id"] == 2

    def test_properties_and_label_returned(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert rows[0]["label"] == "Person"
        props = json.loads(rows[0]["properties"])
        assert props["name"] == "Bob"


# =====================================================================
# graph_delete_node
# =====================================================================


class TestGraphDeleteNode:
    def test_delete_node(self) -> None:
        engine = _engine_with_social_graph()
        engine.sql("SELECT * FROM graph_delete_node('social', 2)")
        rows = engine.sql("SELECT * FROM graph_nodes('social')").rows
        ids = {row["id"] for row in rows}
        assert 2 not in ids
        assert ids == {1, 3}

    def test_delete_removes_incident_edges(self) -> None:
        engine = _engine_with_social_graph()
        # Bob (2) has KNOWS edges: 1->2, 2->3
        engine.sql("SELECT * FROM graph_delete_node('social', 2)")
        # Alice should have no KNOWS neighbors anymore
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 0

    def test_delete_nonexistent_node_is_no_op(self) -> None:
        engine = _engine_with_social_graph()
        # Deleting a non-existent vertex is silently ignored (no error).
        result = engine.sql("SELECT * FROM graph_delete_node('social', 999)")
        assert "deleted" in result.rows[0]["result"]
        # Existing nodes remain intact.
        rows = engine.sql("SELECT * FROM graph_nodes('social')").rows
        assert len(rows) == 3

    def test_delete_returns_confirmation(self) -> None:
        engine = _engine_with_social_graph()
        result = engine.sql("SELECT * FROM graph_delete_node('social', 1)")
        assert "deleted" in result.rows[0]["result"]


# =====================================================================
# graph_delete_edge
# =====================================================================


class TestGraphDeleteEdge:
    def test_delete_edge(self) -> None:
        engine = _engine_with_social_graph()
        # Edge 1 is KNOWS from Alice to Bob
        engine.sql("SELECT * FROM graph_delete_edge('social', 1)")
        # Alice should no longer know Bob via edge 1
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 0

    def test_delete_edge_keeps_nodes(self) -> None:
        engine = _engine_with_social_graph()
        engine.sql("SELECT * FROM graph_delete_edge('social', 1)")
        # Both Alice and Bob should still exist
        rows = engine.sql("SELECT * FROM graph_nodes('social')").rows
        ids = {row["id"] for row in rows}
        assert {1, 2, 3} == ids

    def test_delete_nonexistent_edge_is_no_op(self) -> None:
        engine = _engine_with_social_graph()
        # Deleting a non-existent edge is silently ignored (no error).
        result = engine.sql("SELECT * FROM graph_delete_edge('social', 999)")
        assert "deleted" in result.rows[0]["result"]
        # Existing edges remain intact.
        rows = engine.sql(
            "SELECT * FROM graph_neighbors('social', 1, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 1

    def test_delete_returns_confirmation(self) -> None:
        engine = _engine_with_social_graph()
        result = engine.sql("SELECT * FROM graph_delete_edge('social', 1)")
        assert "deleted" in result.rows[0]["result"]


# =====================================================================
# graph_traverse
# =====================================================================


class TestGraphEdges:
    def test_all_edges(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT * FROM graph_edges('social')").rows
        assert len(rows) == 3
        labels = {row["label"] for row in rows}
        assert labels == {"KNOWS", "FOLLOWS"}

    def test_filter_by_type(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT * FROM graph_edges('social', 'KNOWS')").rows
        assert len(rows) == 2
        assert all(row["label"] == "KNOWS" for row in rows)

    def test_filter_by_properties(self) -> None:
        engine = _engine_with_graph()
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql("SELECT * FROM graph_create_node('social', 'P', '{}')")
        engine.sql(
            "SELECT * FROM graph_create_edge('social', 'KNOWS', 1, 2, "
            "'{\"since\":2020}')"
        )
        engine.sql(
            "SELECT * FROM graph_create_edge('social', 'KNOWS', 2, 1, "
            "'{\"since\":2021}')"
        )
        rows = engine.sql(
            "SELECT * FROM graph_edges('social', 'KNOWS', '{\"since\":2020}')"
        ).rows
        assert len(rows) == 1
        assert rows[0]["source_id"] == 1
        assert rows[0]["target_id"] == 2

    def test_columns(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT * FROM graph_edges('social', 'FOLLOWS')").rows
        assert len(rows) == 1
        row = rows[0]
        assert row["source_id"] == 1
        assert row["target_id"] == 3
        assert row["label"] == "FOLLOWS"
        props = json.loads(row["properties"])
        assert isinstance(props, dict)

    def test_empty_graph(self) -> None:
        engine = _engine_with_graph()
        rows = engine.sql("SELECT * FROM graph_edges('social')").rows
        assert len(rows) == 0

    def test_count_edges(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT COUNT(*) AS cnt FROM graph_edges('social')").rows
        assert rows[0]["cnt"] == 3

    def test_nonexistent_graph_raises(self) -> None:
        engine = Engine()
        with pytest.raises(ValueError, match="does not exist"):
            engine.sql("SELECT * FROM graph_edges('nope')")


class TestGraphEdgesPerVertex:
    def test_per_vertex_outgoing(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_edges('social', 1, NULL, 'outgoing')"
        ).rows
        # Alice (1) has outgoing: KNOWS->Bob, FOLLOWS->Carol
        assert len(rows) == 2
        labels = {row["label"] for row in rows}
        assert labels == {"KNOWS", "FOLLOWS"}

    def test_per_vertex_incoming(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_edges('social', 3, NULL, 'incoming')"
        ).rows
        # Carol (3) has incoming: KNOWS from Bob, FOLLOWS from Alice
        assert len(rows) == 2

    def test_per_vertex_with_type(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_edges('social', 1, 'KNOWS', 'outgoing')"
        ).rows
        assert len(rows) == 1
        assert rows[0]["label"] == "KNOWS"
        assert rows[0]["target_id"] == 2

    def test_per_vertex_both(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql("SELECT * FROM graph_edges('social', 2, NULL, 'both')").rows
        # Bob (2): incoming KNOWS from Alice, outgoing KNOWS to Carol
        assert len(rows) == 2

    def test_per_vertex_no_edges(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_edges('social', 3, NULL, 'outgoing')"
        ).rows
        assert len(rows) == 0


class TestGraphTraverseArray:
    def test_array_literal_edge_types(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, ARRAY['KNOWS','FOLLOWS'], "
            "'outgoing', 1, 'bfs')"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_null_edge_types(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, NULL, 'outgoing', 1)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}


class TestGraphTraverse:
    def test_bfs_single_type(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, 'KNOWS', 'outgoing', 2, 'bfs')"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_dfs_single_type(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, 'KNOWS', 'outgoing', 2, 'dfs')"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_multiple_edge_types(self) -> None:
        engine = _engine_with_social_graph()
        # KNOWS and FOLLOWS from Alice (1)
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, 'KNOWS,FOLLOWS', "
            "'outgoing', 1, 'bfs')"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_empty_types_means_all(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, '', 'outgoing', 1)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_incoming_direction(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 3, 'KNOWS,FOLLOWS', "
            "'incoming', 1, 'bfs')"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {1, 2}

    def test_both_directions(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 2, 'KNOWS', 'both', 1)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {1, 3}

    def test_depth_and_path(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, 'KNOWS', 'outgoing', 2, 'bfs')"
        ).rows
        depth_map = {row["id"]: row["depth"] for row in rows}
        assert depth_map[2] == 1
        assert depth_map[3] == 2
        for row in rows:
            path = json.loads(row["path"])
            assert path[0] == 1
            assert path[-1] == row["id"]

    def test_default_strategy_is_bfs(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, 'KNOWS', 'outgoing', 2)"
        ).rows
        ids = {row["id"] for row in rows}
        assert ids == {2, 3}

    def test_no_results(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 3, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 0

    def test_properties_returned(self) -> None:
        engine = _engine_with_social_graph()
        rows = engine.sql(
            "SELECT * FROM graph_traverse('social', 1, 'KNOWS', 'outgoing', 1)"
        ).rows
        assert len(rows) == 1
        assert rows[0]["label"] == "Person"
        props = json.loads(rows[0]["properties"])
        assert props["name"] == "Bob"


# =====================================================================
# End-to-end workflow
# =====================================================================


class TestEndToEndWorkflow:
    def test_full_lifecycle(self) -> None:
        """Create graph -> add nodes -> add edges -> query -> delete."""
        engine = Engine()

        # Create graph
        engine.sql("SELECT * FROM create_graph('code')")

        # Add nodes
        r1 = engine.sql(
            "SELECT * FROM graph_create_node('code', 'Function', "
            '\'{"name":"main","lines":42}\')'
        )
        r2 = engine.sql(
            "SELECT * FROM graph_create_node('code', 'Function', "
            '\'{"name":"helper","lines":10}\')'
        )
        r3 = engine.sql(
            "SELECT * FROM graph_create_node('code', 'Module', '{\"name\":\"utils\"}')"
        )
        assert r1.rows[0]["id"] == "code:Function:1"
        assert r2.rows[0]["id"] == "code:Function:2"
        assert r3.rows[0]["id"] == "code:Module:3"

        # Add edges
        engine.sql("SELECT * FROM graph_create_edge('code', 'CALLS', 1, 2, '{}')")
        engine.sql("SELECT * FROM graph_create_edge('code', 'BELONGS_TO', 1, 3, '{}')")

        # Query: all Function nodes
        funcs = engine.sql("SELECT * FROM graph_nodes('code', 'Function')").rows
        assert len(funcs) == 2

        # Query: neighbors of main
        neighbors = engine.sql(
            "SELECT * FROM graph_neighbors('code', 1, 'CALLS', 'outgoing', 1)"
        ).rows
        assert len(neighbors) == 1
        assert json.loads(neighbors[0]["properties"])["name"] == "helper"

        # Delete edge
        engine.sql("SELECT * FROM graph_delete_edge('code', 1)")

        # Verify edge gone
        neighbors = engine.sql(
            "SELECT * FROM graph_neighbors('code', 1, 'CALLS', 'outgoing', 1)"
        ).rows
        assert len(neighbors) == 0

        # Delete node
        engine.sql("SELECT * FROM graph_delete_node('code', 2)")
        nodes = engine.sql("SELECT * FROM graph_nodes('code')").rows
        assert len(nodes) == 2

        # Drop graph
        engine.sql("SELECT * FROM drop_graph('code')")
        with pytest.raises(ValueError):
            engine.sql("SELECT * FROM graph_nodes('code')")

    def test_multi_graph_isolation(self) -> None:
        """Nodes in different graphs are isolated."""
        engine = Engine()
        engine.sql("SELECT * FROM create_graph('g1')")
        engine.sql("SELECT * FROM create_graph('g2')")

        engine.sql("SELECT * FROM graph_create_node('g1', 'X', '{\"val\":1}')")
        engine.sql("SELECT * FROM graph_create_node('g2', 'X', '{\"val\":2}')")

        g1_nodes = engine.sql("SELECT * FROM graph_nodes('g1')").rows
        g2_nodes = engine.sql("SELECT * FROM graph_nodes('g2')").rows
        assert len(g1_nodes) == 1
        assert len(g2_nodes) == 1
        assert json.loads(g1_nodes[0]["properties"])["val"] == 1
        assert json.loads(g2_nodes[0]["properties"])["val"] == 2
