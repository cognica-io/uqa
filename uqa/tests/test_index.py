#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for Phase 2: Index Infrastructure.

Covers CREATE INDEX, DROP INDEX, index scans, optimizer integration,
EXPLAIN output, persistence across engine restart, and error handling.
"""

from __future__ import annotations

import pytest

from uqa.engine import Engine

# -- Helpers ---------------------------------------------------------------


def _make_engine(db_path: str) -> Engine:
    """Create a persistent engine at the given path."""
    return Engine(db_path=db_path)


def _setup_employees(engine: Engine) -> None:
    """Create and populate an employees table."""
    engine.sql(
        "CREATE TABLE employees (id SERIAL PRIMARY KEY, name TEXT NOT NULL, age INTEGER, salary REAL)"
    )
    engine.sql(
        "INSERT INTO employees (name, age, salary) VALUES ('Alice', 30, 70000.0)"
    )
    engine.sql("INSERT INTO employees (name, age, salary) VALUES ('Bob', 25, 55000.0)")
    engine.sql(
        "INSERT INTO employees (name, age, salary) VALUES ('Charlie', 35, 90000.0)"
    )
    engine.sql(
        "INSERT INTO employees (name, age, salary) VALUES ('Diana', 28, 65000.0)"
    )
    engine.sql("INSERT INTO employees (name, age, salary) VALUES ('Eve', 40, 95000.0)")


# -- CREATE INDEX / DROP INDEX ---------------------------------------------


class TestCreateDropIndex:
    def test_create_index_on_existing_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            assert engine._index_manager.has_index("idx_age")

    def test_create_index_on_nonexistent_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        with (
            _make_engine(db) as engine,
            pytest.raises(ValueError, match="does not exist"),
        ):
            engine.sql("CREATE INDEX idx_foo ON nonexistent (col)")

    def test_create_index_on_nonexistent_column(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            with pytest.raises(ValueError, match="does not exist"):
                engine.sql("CREATE INDEX idx_bad ON employees (nonexistent)")

    def test_create_duplicate_index(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            with pytest.raises(ValueError, match="already exists"):
                engine.sql("CREATE INDEX idx_age ON employees (age)")

    def test_drop_index(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            assert engine._index_manager.has_index("idx_age")
            engine.sql("DROP INDEX idx_age")
            assert not engine._index_manager.has_index("idx_age")

    def test_drop_index_nonexistent(self, tmp_path):
        db = str(tmp_path / "test.db")
        with (
            _make_engine(db) as engine,
            pytest.raises(ValueError, match="does not exist"),
        ):
            engine.sql("DROP INDEX idx_none")

    def test_drop_index_if_exists(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            # Should not raise
            engine.sql("DROP INDEX IF EXISTS idx_none")

    def test_drop_table_cascades_indexes(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            engine.sql("CREATE INDEX idx_salary ON employees (salary)")
            assert engine._index_manager.has_index("idx_age")
            assert engine._index_manager.has_index("idx_salary")
            engine.sql("DROP TABLE employees")
            assert not engine._index_manager.has_index("idx_age")
            assert not engine._index_manager.has_index("idx_salary")

    def test_multi_column_index(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age_salary ON employees (age, salary)")
            assert engine._index_manager.has_index("idx_age_salary")
            idx = engine._index_manager._indexes["idx_age_salary"]
            assert idx.index_def.columns == ("age", "salary")


# -- Index scan correctness -----------------------------------------------


class TestIndexScan:
    def test_equality_scan(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            # With index
            result = engine.sql("SELECT name FROM employees WHERE age = 30")
            names = [r["name"] for r in result]
            assert names == ["Alice"]

    def test_range_scan_greater_than(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            result = engine.sql("SELECT name FROM employees WHERE age > 30")
            names = sorted(r["name"] for r in result)
            assert names == ["Charlie", "Eve"]

    def test_range_scan_less_than(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            result = engine.sql("SELECT name FROM employees WHERE age < 30")
            names = sorted(r["name"] for r in result)
            assert names == ["Bob", "Diana"]

    def test_between_scan(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            result = engine.sql(
                "SELECT name FROM employees WHERE age BETWEEN 28 AND 35"
            )
            names = sorted(r["name"] for r in result)
            assert names == ["Alice", "Charlie", "Diana"]

    def test_in_scan(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            result = engine.sql("SELECT name FROM employees WHERE age IN (25, 40)")
            names = sorted(r["name"] for r in result)
            assert names == ["Bob", "Eve"]

    def test_index_scan_matches_full_scan(self, tmp_path):
        """Index scan produces same results as full scan."""
        db1 = str(tmp_path / "with_index.db")
        db2 = str(tmp_path / "without_index.db")

        # With index
        with _make_engine(db1) as e1:
            _setup_employees(e1)
            e1.sql("CREATE INDEX idx_age ON employees (age)")
            r1 = e1.sql("SELECT name, age FROM employees WHERE age >= 30 ORDER BY age")

        # Without index
        with _make_engine(db2) as e2:
            _setup_employees(e2)
            r2 = e2.sql("SELECT name, age FROM employees WHERE age >= 30 ORDER BY age")

        assert r1.rows == r2.rows


# -- Optimizer integration ------------------------------------------------


class TestOptimizerIntegration:
    def test_explain_shows_index_scan(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            # Need ANALYZE so stats.total_docs > 0 for the optimizer
            engine.sql("ANALYZE employees")
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            result = engine.sql("EXPLAIN SELECT name FROM employees WHERE age = 30")
            plan_text = "\n".join(r["plan"] for r in result)
            assert "IndexScanOp" in plan_text

    def test_explain_without_index_shows_filter(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("ANALYZE employees")

            result = engine.sql("EXPLAIN SELECT name FROM employees WHERE age = 30")
            plan_text = "\n".join(r["plan"] for r in result)
            assert "FilterOp" in plan_text

    def test_multiple_indexes_optimizer_picks_best(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("ANALYZE employees")
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            engine.sql("CREATE INDEX idx_salary ON employees (salary)")

            # Query on age should use idx_age
            result = engine.sql("EXPLAIN SELECT name FROM employees WHERE age = 30")
            plan_text = "\n".join(r["plan"] for r in result)
            assert "idx_age" in plan_text

            # Query on salary should use idx_salary
            result = engine.sql(
                "EXPLAIN SELECT name FROM employees WHERE salary > 80000"
            )
            plan_text = "\n".join(r["plan"] for r in result)
            assert "idx_salary" in plan_text

    def test_and_filter_with_index(self, tmp_path):
        """WHERE with AND: one indexed column, one not."""
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("ANALYZE employees")
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            result = engine.sql(
                "SELECT name FROM employees WHERE age > 28 AND salary > 70000"
            )
            names = sorted(r["name"] for r in result)
            assert names == ["Charlie", "Eve"]


# -- Persistence -----------------------------------------------------------


class TestIndexPersistence:
    def test_index_survives_restart(self, tmp_path):
        db = str(tmp_path / "test.db")

        # Create engine, table, index, and close
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")

        # Reopen and verify index is restored
        with _make_engine(db) as engine:
            assert engine._index_manager.has_index("idx_age")

            # Index still works
            result = engine.sql("SELECT name FROM employees WHERE age = 30")
            names = [r["name"] for r in result]
            assert names == ["Alice"]

    def test_dropped_index_stays_dropped_after_restart(self, tmp_path):
        db = str(tmp_path / "test.db")

        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            engine.sql("DROP INDEX idx_age")

        with _make_engine(db) as engine:
            assert not engine._index_manager.has_index("idx_age")

    def test_index_data_after_insert_and_restart(self, tmp_path):
        db = str(tmp_path / "test.db")

        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")

            # Insert after index creation
            engine.sql(
                "INSERT INTO employees (name, age, salary) VALUES ('Frank', 33, 72000.0)"
            )

        with _make_engine(db) as engine:
            result = engine.sql("SELECT name FROM employees WHERE age = 33")
            names = [r["name"] for r in result]
            assert names == ["Frank"]


# -- In-memory engine (no db_path) -----------------------------------------


class TestInMemoryEngine:
    def test_in_memory_engine_no_index_manager(self):
        """In-memory engine (no db_path) has no index manager."""
        engine = Engine()
        assert engine._index_manager is None

    def test_in_memory_engine_queries_work(self):
        """In-memory engine queries work without index infrastructure."""
        engine = Engine()
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
        engine.sql("INSERT INTO t (val) VALUES (42)")
        result = engine.sql("SELECT val FROM t WHERE val = 42")
        assert len(result) == 1
        assert result.rows[0]["val"] == 42

    def test_create_index_fails_without_db_path(self):
        """CREATE INDEX on in-memory engine raises error."""
        engine = Engine()
        engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
        with pytest.raises(ValueError, match="persistent engine"):
            engine.sql("CREATE INDEX idx ON t (val)")


# -- Index types -----------------------------------------------------------


class TestIndexTypes:
    def test_index_def_frozen(self):
        from uqa.storage.index_types import IndexDef, IndexType

        idef = IndexDef(
            name="idx",
            index_type=IndexType.BTREE,
            table_name="t",
            columns=("a", "b"),
        )
        assert idef.columns == ("a", "b")
        with pytest.raises(AttributeError):
            idef.name = "other"

    def test_index_type_values(self):
        from uqa.storage.index_types import IndexType

        assert IndexType.BTREE.value == "btree"
        assert IndexType.INVERTED.value == "inverted"
        assert IndexType.HNSW.value == "hnsw"
        assert IndexType.GRAPH.value == "graph"


# -- BTreeIndex unit tests ------------------------------------------------


class TestBTreeIndex:
    def test_scan_cost_empty_table(self, tmp_path):
        from uqa.core.types import Equals
        from uqa.storage.btree_index import BTreeIndex
        from uqa.storage.index_types import IndexDef, IndexType

        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
            idef = IndexDef("idx", IndexType.BTREE, "t", ("val",))
            idx = BTreeIndex(idef, engine._catalog.conn)
            idx.build()
            assert idx.scan_cost(Equals(42)) == 0.0

    def test_estimate_cardinality(self, tmp_path):
        from uqa.core.types import Equals
        from uqa.storage.btree_index import BTreeIndex
        from uqa.storage.index_types import IndexDef, IndexType

        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            engine.sql("CREATE TABLE t (id SERIAL PRIMARY KEY, val INTEGER)")
            engine.sql("INSERT INTO t (val) VALUES (1)")
            engine.sql("INSERT INTO t (val) VALUES (2)")
            engine.sql("INSERT INTO t (val) VALUES (1)")

            idef = IndexDef("idx", IndexType.BTREE, "t", ("val",))
            idx = BTreeIndex(idef, engine._catalog.conn)
            idx.build()

            assert idx.estimate_cardinality(Equals(1)) == 2
            assert idx.estimate_cardinality(Equals(2)) == 1
            assert idx.estimate_cardinality(Equals(999)) == 0


# -- Catalog index CRUD ---------------------------------------------------


class TestCatalogIndexes:
    def test_save_and_load_indexes(self, tmp_path):
        from uqa.storage.catalog import Catalog
        from uqa.storage.index_types import IndexDef, IndexType

        db = str(tmp_path / "test.db")
        catalog = Catalog(db)

        idef = IndexDef("idx_age", IndexType.BTREE, "employees", ("age",))
        catalog.save_index(idef)

        loaded = catalog.load_indexes()
        assert len(loaded) == 1
        name, idx_type, tbl, cols, _params = loaded[0]
        assert name == "idx_age"
        assert idx_type == "btree"
        assert tbl == "employees"
        assert cols == ["age"]
        catalog.close()

    def test_drop_index_from_catalog(self, tmp_path):
        from uqa.storage.catalog import Catalog
        from uqa.storage.index_types import IndexDef, IndexType

        db = str(tmp_path / "test.db")
        catalog = Catalog(db)

        idef = IndexDef("idx_age", IndexType.BTREE, "employees", ("age",))
        catalog.save_index(idef)
        catalog.drop_index("idx_age")

        loaded = catalog.load_indexes()
        assert len(loaded) == 0
        catalog.close()

    def test_load_indexes_for_table(self, tmp_path):
        from uqa.storage.catalog import Catalog
        from uqa.storage.index_types import IndexDef, IndexType

        db = str(tmp_path / "test.db")
        catalog = Catalog(db)

        catalog.save_index(IndexDef("idx1", IndexType.BTREE, "t1", ("a",)))
        catalog.save_index(IndexDef("idx2", IndexType.BTREE, "t2", ("b",)))
        catalog.save_index(IndexDef("idx3", IndexType.BTREE, "t1", ("c",)))

        t1_indexes = catalog.load_indexes_for_table("t1")
        assert len(t1_indexes) == 2

        t2_indexes = catalog.load_indexes_for_table("t2")
        assert len(t2_indexes) == 1
        catalog.close()

    def test_drop_table_cascades_catalog_indexes(self, tmp_path):
        from uqa.storage.catalog import Catalog
        from uqa.storage.index_types import IndexDef, IndexType

        db = str(tmp_path / "test.db")
        catalog = Catalog(db)

        # Simulate having a table schema
        catalog.save_table_schema(
            "emp",
            [
                {
                    "name": "id",
                    "type_name": "integer",
                    "primary_key": True,
                    "not_null": True,
                    "auto_increment": False,
                    "default": None,
                }
            ],
        )
        catalog.save_index(IndexDef("idx1", IndexType.BTREE, "emp", ("id",)))

        catalog.drop_table_schema("emp")
        loaded = catalog.load_indexes()
        assert len(loaded) == 0
        catalog.close()


# -- IndexManager unit tests -----------------------------------------------


class TestIndexManager:
    def test_find_covering_index(self, tmp_path):
        from uqa.core.types import Equals

        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            engine.sql("CREATE INDEX idx_salary ON employees (salary)")

            idx = engine._index_manager.find_covering_index(
                "employees", "age", Equals(30)
            )
            assert idx is not None
            assert idx.index_def.name == "idx_age"

            idx = engine._index_manager.find_covering_index(
                "employees", "name", Equals("Alice")
            )
            assert idx is None  # No index on name

    def test_get_indexes_for_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        with _make_engine(db) as engine:
            _setup_employees(engine)
            engine.sql("CREATE TABLE other (id SERIAL PRIMARY KEY, val INTEGER)")
            engine.sql("CREATE INDEX idx_age ON employees (age)")
            engine.sql("CREATE INDEX idx_val ON other (val)")

            emp_indexes = engine._index_manager.get_indexes_for_table("employees")
            assert len(emp_indexes) == 1
            assert emp_indexes[0].index_def.name == "idx_age"

            other_indexes = engine._index_manager.get_indexes_for_table("other")
            assert len(other_indexes) == 1
