#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for SQL sequences (CREATE SEQUENCE, nextval, currval, setval)."""

from __future__ import annotations

import pytest

from uqa.engine import Engine


@pytest.fixture
def engine():
    return Engine()


class TestSequence:
    def test_create_and_nextval(self, engine):
        engine.sql("CREATE SEQUENCE myseq START 1")
        result = engine.sql("SELECT nextval('myseq') AS v")
        assert result.rows[0]["v"] == 1
        result = engine.sql("SELECT nextval('myseq') AS v")
        assert result.rows[0]["v"] == 2

    def test_currval(self, engine):
        engine.sql("CREATE SEQUENCE s2 START 10")
        engine.sql("SELECT nextval('s2') AS v")
        result = engine.sql("SELECT currval('s2') AS v")
        assert result.rows[0]["v"] == 10

    def test_setval(self, engine):
        engine.sql("CREATE SEQUENCE s3 START 1")
        engine.sql("SELECT nextval('s3') AS v")
        engine.sql("SELECT setval('s3', 100) AS v")
        result = engine.sql("SELECT currval('s3') AS v")
        assert result.rows[0]["v"] == 100

    def test_increment(self, engine):
        engine.sql("CREATE SEQUENCE s4 START 1 INCREMENT 5")
        result = engine.sql("SELECT nextval('s4') AS v")
        assert result.rows[0]["v"] == 1
        result = engine.sql("SELECT nextval('s4') AS v")
        assert result.rows[0]["v"] == 6
