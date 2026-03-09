#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for remaining PostgreSQL 17 P2 features:
UPDATE FROM, DELETE USING, LATERAL, TEMP TABLE, FOREIGN KEY, and edge cases.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from uqa.engine import Engine


# ==================================================================
# 1. UPDATE ... FROM ... (multi-table UPDATE)
# ==================================================================


class TestUpdateFrom:
    @pytest.fixture
    def engine(self):
        e = Engine()
        e.sql(
            "CREATE TABLE employees "
            "(id INT PRIMARY KEY, name TEXT, dept_id INT, salary INT)"
        )
        e.sql(
            "CREATE TABLE departments "
            "(id INT PRIMARY KEY, name TEXT, budget INT)"
        )
        e.sql("INSERT INTO departments VALUES (1, 'Engineering', 100000)")
        e.sql("INSERT INTO departments VALUES (2, 'Sales', 50000)")
        e.sql("INSERT INTO employees VALUES (1, 'Alice', 1, 50000)")
        e.sql("INSERT INTO employees VALUES (2, 'Bob', 2, 40000)")
        e.sql("INSERT INTO employees VALUES (3, 'Charlie', 1, 60000)")
        yield e

    def test_basic_update_from(self, engine):
        engine.sql(
            "UPDATE employees SET salary = departments.budget / 2 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Engineering'"
        )
        r = engine.sql(
            "SELECT id, name, dept_id, salary "
            "FROM employees ORDER BY id"
        )
        # Alice: Engineering budget 100000 / 2 = 50000
        assert r.rows[0]["salary"] == 50000
        # Bob: Sales, not updated
        assert r.rows[1]["salary"] == 40000
        # Charlie: Engineering budget 100000 / 2 = 50000
        assert r.rows[2]["salary"] == 50000

    def test_update_from_returning(self, engine):
        r = engine.sql(
            "UPDATE employees SET salary = 99999 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Sales' "
            "RETURNING employees.id, employees.salary"
        )
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 2
        assert r.rows[0]["salary"] == 99999

    def test_update_from_no_match(self, engine):
        r = engine.sql(
            "UPDATE employees SET salary = 0 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Marketing'"
        )
        assert r.rows[0]["updated"] == 0

    def test_update_from_multiple_matches(self, engine):
        """UPDATE FROM updates both Engineering employees."""
        engine.sql(
            "UPDATE employees SET salary = salary + 1000 "
            "FROM departments "
            "WHERE employees.dept_id = departments.id "
            "AND departments.name = 'Engineering'"
        )
        r = engine.sql(
            "SELECT id, salary FROM employees ORDER BY id"
        )
        assert r.rows[0]["salary"] == 51000  # Alice
        assert r.rows[1]["salary"] == 40000  # Bob unchanged
        assert r.rows[2]["salary"] == 61000  # Charlie


# ==================================================================
# 2. DELETE ... USING ... (multi-table DELETE)
# ==================================================================


class TestDeleteUsing:
    @pytest.fixture
    def engine(self):
        e = Engine()
        e.sql(
            "CREATE TABLE orders "
            "(id INT PRIMARY KEY, customer_id INT, total INT)"
        )
        e.sql("CREATE TABLE blacklist (customer_id INT PRIMARY KEY)")
        e.sql("INSERT INTO orders VALUES (1, 10, 100)")
        e.sql("INSERT INTO orders VALUES (2, 20, 200)")
        e.sql("INSERT INTO orders VALUES (3, 10, 300)")
        e.sql("INSERT INTO blacklist VALUES (10)")
        yield e

    def test_basic_delete_using(self, engine):
        engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id"
        )
        r = engine.sql("SELECT id, customer_id, total FROM orders ORDER BY id")
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 2

    def test_delete_using_returning(self, engine):
        r = engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id "
            "RETURNING orders.id"
        )
        assert len(r.rows) == 2
        ids = {row["id"] for row in r.rows}
        assert ids == {1, 3}

    def test_delete_using_no_match(self, engine):
        engine.sql("DELETE FROM blacklist WHERE customer_id = 10")
        r = engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id"
        )
        assert r.rows[0]["deleted"] == 0

    def test_delete_using_preserves_unmatched(self, engine):
        """Rows not matching the USING condition remain intact."""
        engine.sql(
            "DELETE FROM orders USING blacklist "
            "WHERE orders.customer_id = blacklist.customer_id"
        )
        r = engine.sql("SELECT id, customer_id, total FROM orders")
        assert len(r.rows) == 1
        assert r.rows[0]["customer_id"] == 20
        assert r.rows[0]["total"] == 200


# ==================================================================
# 3. LATERAL subquery
# ==================================================================


class TestLateral:
    @pytest.fixture
    def engine(self):
        e = Engine()
        e.sql("CREATE TABLE depts (id INT PRIMARY KEY, dept_name TEXT)")
        e.sql(
            "CREATE TABLE emps "
            "(id INT PRIMARY KEY, emp_name TEXT, dept_id INT, salary INT)"
        )
        e.sql("INSERT INTO depts VALUES (1, 'Engineering')")
        e.sql("INSERT INTO depts VALUES (2, 'Sales')")
        e.sql("INSERT INTO emps VALUES (1, 'Alice', 1, 90000)")
        e.sql("INSERT INTO emps VALUES (2, 'Bob', 1, 80000)")
        e.sql("INSERT INTO emps VALUES (3, 'Charlie', 2, 70000)")
        e.sql("INSERT INTO emps VALUES (4, 'Diana', 2, 75000)")
        yield e

    def test_lateral_subquery_with_aggregate(self, engine):
        r = engine.sql(
            "SELECT d.dept_name, sub.top_salary "
            "FROM depts d, "
            "LATERAL (SELECT MAX(salary) AS top_salary "
            "FROM emps WHERE emps.dept_id = d.id) sub "
            "ORDER BY d.dept_name"
        )
        assert len(r.rows) == 2
        assert r.rows[0]["dept_name"] == "Engineering"
        assert r.rows[0]["top_salary"] == 90000
        assert r.rows[1]["dept_name"] == "Sales"
        assert r.rows[1]["top_salary"] == 75000

    def test_lateral_with_limit(self, engine):
        """LATERAL with ORDER BY + LIMIT, selecting the sort column."""
        r = engine.sql(
            "SELECT d.dept_name, sub.top_emp, sub.top_sal "
            "FROM depts d, "
            "LATERAL (SELECT emp_name AS top_emp, salary AS top_sal "
            "FROM emps WHERE emps.dept_id = d.id "
            "ORDER BY salary DESC LIMIT 1) sub "
            "ORDER BY d.dept_name"
        )
        assert len(r.rows) == 2
        # Top earner in Engineering: Alice (90000)
        assert r.rows[0]["top_emp"] == "Alice"
        assert r.rows[0]["top_sal"] == 90000
        # Top earner in Sales: Diana (75000)
        assert r.rows[1]["top_emp"] == "Diana"
        assert r.rows[1]["top_sal"] == 75000

    def test_lateral_with_count(self, engine):
        """LATERAL subquery returning a count per department."""
        r = engine.sql(
            "SELECT d.dept_name, sub.emp_count "
            "FROM depts d, "
            "LATERAL (SELECT COUNT(*) AS emp_count "
            "FROM emps WHERE emps.dept_id = d.id) sub "
            "ORDER BY d.dept_name"
        )
        assert r.rows[0]["dept_name"] == "Engineering"
        assert r.rows[0]["emp_count"] == 2
        assert r.rows[1]["dept_name"] == "Sales"
        assert r.rows[1]["emp_count"] == 2


# ==================================================================
# 4. CREATE TEMPORARY TABLE
# ==================================================================


class TestCreateTemporaryTable:
    def test_basic_temp_table(self):
        e = Engine()
        e.sql("CREATE TEMPORARY TABLE tmp (id INT PRIMARY KEY, val TEXT)")
        e.sql("INSERT INTO tmp VALUES (1, 'hello')")
        r = e.sql("SELECT id, val FROM tmp")
        assert len(r.rows) == 1
        assert r.rows[0]["val"] == "hello"

    def test_temp_table_dropped_on_close(self):
        e = Engine()
        e.sql("CREATE TEMP TABLE tmp (id INT, val TEXT)")
        e.sql("INSERT INTO tmp VALUES (1, 'test')")
        assert "tmp" in e._tables
        e.close()
        assert "tmp" not in e._tables

    def test_temp_table_not_persisted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            e = Engine(db_path=db_path)
            e.sql("CREATE TABLE perm (id INT PRIMARY KEY)")
            e.sql("CREATE TEMP TABLE tmp (id INT PRIMARY KEY)")
            e.sql("INSERT INTO perm VALUES (1)")
            e.sql("INSERT INTO tmp VALUES (1)")
            e.close()

            # Re-open: permanent table should exist, temp should not
            e2 = Engine(db_path=db_path)
            r = e2.sql("SELECT id FROM perm")
            assert len(r.rows) == 1
            with pytest.raises(ValueError, match="does not exist"):
                e2.sql("SELECT id FROM tmp")
            e2.close()

    def test_temp_table_create_as_select(self):
        e = Engine()
        e.sql("CREATE TABLE src (id INT PRIMARY KEY, val INT)")
        e.sql("INSERT INTO src VALUES (1, 10)")
        e.sql("INSERT INTO src VALUES (2, 20)")
        e.sql(
            "CREATE TEMP TABLE tmp AS "
            "SELECT id, val FROM src WHERE val > 10"
        )
        r = e.sql("SELECT id, val FROM tmp")
        assert len(r.rows) == 1
        assert r.rows[0]["val"] == 20

    def test_temp_table_insert_and_query(self):
        """Temp tables support normal DML operations."""
        e = Engine()
        e.sql(
            "CREATE TEMPORARY TABLE staging "
            "(id INT PRIMARY KEY, status TEXT)"
        )
        e.sql("INSERT INTO staging VALUES (1, 'pending')")
        e.sql("INSERT INTO staging VALUES (2, 'done')")
        e.sql("UPDATE staging SET status = 'done' WHERE id = 1")
        r = e.sql(
            "SELECT id, status FROM staging ORDER BY id"
        )
        assert r.rows[0]["status"] == "done"
        assert r.rows[1]["status"] == "done"


# ==================================================================
# 5. FOREIGN KEY constraint
# ==================================================================


class TestForeignKey:
    @pytest.fixture
    def engine(self):
        e = Engine()
        e.sql("CREATE TABLE parents (id INT PRIMARY KEY, name TEXT)")
        e.sql("INSERT INTO parents VALUES (1, 'Parent1')")
        e.sql("INSERT INTO parents VALUES (2, 'Parent2')")
        yield e

    def test_basic_fk_insert(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        r = engine.sql("SELECT id, parent_id, val FROM children")
        assert len(r.rows) == 1
        assert r.rows[0]["parent_id"] == 1

    def test_fk_insert_violation(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        with pytest.raises(
            ValueError, match="FOREIGN KEY constraint violated"
        ):
            engine.sql("INSERT INTO children VALUES (1, 999, 'bad')")

    def test_fk_null_allowed(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        # NULL FK should be allowed
        engine.sql("INSERT INTO children VALUES (1, NULL, 'orphan')")
        r = engine.sql("SELECT id, parent_id, val FROM children")
        assert len(r.rows) == 1
        assert r.rows[0]["parent_id"] is None

    def test_fk_delete_violation(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        with pytest.raises(
            ValueError, match="FOREIGN KEY constraint violated"
        ):
            engine.sql("DELETE FROM parents WHERE id = 1")

    def test_fk_delete_unreferenced(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        # Deleting parent 2 (not referenced) should work
        engine.sql("DELETE FROM parents WHERE id = 2")
        r = engine.sql("SELECT id, name FROM parents")
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 1

    def test_fk_update_violation(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        with pytest.raises(
            ValueError, match="FOREIGN KEY constraint violated"
        ):
            engine.sql("UPDATE children SET parent_id = 999 WHERE id = 1")

    def test_fk_update_valid(self, engine):
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        engine.sql("UPDATE children SET parent_id = 2 WHERE id = 1")
        r = engine.sql("SELECT parent_id FROM children WHERE id = 1")
        assert r.rows[0]["parent_id"] == 2

    def test_fk_update_parent_pk_violation(self, engine):
        """Updating a referenced parent PK should be rejected."""
        engine.sql(
            "CREATE TABLE children "
            "(id INT PRIMARY KEY, parent_id INT REFERENCES parents(id), "
            "val TEXT)"
        )
        engine.sql("INSERT INTO children VALUES (1, 1, 'child1')")
        with pytest.raises(
            ValueError, match="FOREIGN KEY constraint violated"
        ):
            engine.sql("UPDATE parents SET id = 99 WHERE id = 1")


# ==================================================================
# 6. Additional edge case tests
# ==================================================================


class TestJSONArrayElementsTableFunction:
    """Test JSON table functions."""

    def test_array_elements_from_literal(self):
        e = Engine()
        r = e.sql(
            "SELECT value FROM "
            "json_array_elements('[\"python\", \"sql\", \"rust\"]')"
        )
        assert len(r.rows) == 3
        values = [row["value"] for row in r.rows]
        assert "python" in values
        assert "sql" in values
        assert "rust" in values

    def test_array_elements_integers(self):
        e = Engine()
        r = e.sql(
            "SELECT value FROM json_array_elements('[1, 2, 3]')"
        )
        assert len(r.rows) == 3


class TestValuesInInsert:
    """Ensure standalone VALUES does not break INSERT INTO ... VALUES."""

    def test_insert_still_works(self):
        e = Engine()
        e.sql("CREATE TABLE t (id INT, val TEXT)")
        e.sql("INSERT INTO t VALUES (1, 'a'), (2, 'b')")
        r = e.sql("SELECT id, val FROM t ORDER BY id")
        assert len(r.rows) == 2
        assert r.rows[0]["id"] == 1
        assert r.rows[0]["val"] == "a"
        assert r.rows[1]["id"] == 2
        assert r.rows[1]["val"] == "b"

    def test_insert_single_row(self):
        e = Engine()
        e.sql("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
        e.sql("INSERT INTO t VALUES (42, 'answer')")
        r = e.sql("SELECT id, val FROM t")
        assert len(r.rows) == 1
        assert r.rows[0]["id"] == 42


class TestWindowFilterEdgeCases:
    """Additional window FILTER tests."""

    def test_avg_filter(self):
        e = Engine()
        e.sql(
            "CREATE TABLE scores "
            "(id INT PRIMARY KEY, subject TEXT, score INT)"
        )
        e.sql("INSERT INTO scores VALUES (1, 'math', 90)")
        e.sql("INSERT INTO scores VALUES (2, 'math', 60)")
        e.sql("INSERT INTO scores VALUES (3, 'sci', 80)")
        e.sql("INSERT INTO scores VALUES (4, 'sci', 40)")
        r = e.sql(
            "SELECT subject, score, "
            "AVG(score) FILTER (WHERE score >= 70) "
            "OVER (PARTITION BY subject) AS high_avg "
            "FROM scores ORDER BY id"
        )
        # math: only 90 qualifies -> avg = 90.0
        assert r.rows[0]["high_avg"] == 90.0
        assert r.rows[1]["high_avg"] == 90.0
        # sci: only 80 qualifies -> avg = 80.0
        assert r.rows[2]["high_avg"] == 80.0
        assert r.rows[3]["high_avg"] == 80.0

    def test_sum_filter(self):
        e = Engine()
        e.sql(
            "CREATE TABLE vals "
            "(id INT PRIMARY KEY, grp TEXT, amount INT)"
        )
        e.sql("INSERT INTO vals VALUES (1, 'a', 10)")
        e.sql("INSERT INTO vals VALUES (2, 'a', 20)")
        e.sql("INSERT INTO vals VALUES (3, 'a', 30)")
        r = e.sql(
            "SELECT id, "
            "SUM(amount) FILTER (WHERE amount > 10) "
            "OVER (PARTITION BY grp) AS filtered_sum "
            "FROM vals ORDER BY id"
        )
        # Only 20 and 30 qualify -> sum = 50
        assert r.rows[0]["filtered_sum"] == 50
        assert r.rows[1]["filtered_sum"] == 50
        assert r.rows[2]["filtered_sum"] == 50

    def test_count_filter(self):
        e = Engine()
        e.sql(
            "CREATE TABLE items "
            "(id INT PRIMARY KEY, category TEXT, price INT)"
        )
        e.sql("INSERT INTO items VALUES (1, 'food', 5)")
        e.sql("INSERT INTO items VALUES (2, 'food', 15)")
        e.sql("INSERT INTO items VALUES (3, 'food', 25)")
        r = e.sql(
            "SELECT id, "
            "COUNT(*) FILTER (WHERE price >= 10) "
            "OVER (PARTITION BY category) AS expensive_count "
            "FROM items ORDER BY id"
        )
        # 15 and 25 qualify -> count = 2
        assert r.rows[0]["expensive_count"] == 2
        assert r.rows[1]["expensive_count"] == 2
        assert r.rows[2]["expensive_count"] == 2
