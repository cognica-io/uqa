#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Tests for geospatial type support (POINT, R*Tree, spatial functions)."""

from __future__ import annotations

import os
import tempfile

import pytest

from uqa.engine import Engine
from uqa.storage.spatial_index import SpatialIndex, haversine_distance

# -- Known distances -------------------------------------------------------
# NYC:    (40.7128, -74.0060)  -- (lat, lon) -> POINT(-74.0060, 40.7128)
# LA:     (34.0522, -118.2437) -> POINT(-118.2437, 34.0522)
# London: (51.5074, -0.1278)   -> POINT(-0.1278, 51.5074)
# Tokyo:  (35.6762, 139.6503)  -> POINT(139.6503, 35.6762)

NYC_LON, NYC_LAT = -74.0060, 40.7128
LA_LON, LA_LAT = -118.2437, 34.0522
LONDON_LON, LONDON_LAT = -0.1278, 51.5074
TOKYO_LON, TOKYO_LAT = 139.6503, 35.6762


# ==========================================================================
# Unit tests: Haversine distance
# ==========================================================================


class TestHaversine:
    def test_same_point(self):
        assert haversine_distance(NYC_LAT, NYC_LON, NYC_LAT, NYC_LON) == 0.0

    def test_nyc_to_la(self):
        dist = haversine_distance(NYC_LAT, NYC_LON, LA_LAT, LA_LON)
        # Known distance: ~3940 km
        assert 3900_000 < dist < 4000_000

    def test_nyc_to_london(self):
        dist = haversine_distance(NYC_LAT, NYC_LON, LONDON_LAT, LONDON_LON)
        # Known distance: ~5570 km
        assert 5500_000 < dist < 5650_000

    def test_symmetric(self):
        d1 = haversine_distance(NYC_LAT, NYC_LON, TOKYO_LAT, TOKYO_LON)
        d2 = haversine_distance(TOKYO_LAT, TOKYO_LON, NYC_LAT, NYC_LON)
        assert abs(d1 - d2) < 0.01


# ==========================================================================
# Unit tests: SpatialIndex
# ==========================================================================


class TestSpatialIndex:
    def test_add_and_search(self):
        idx = SpatialIndex("test", "loc")
        idx.add(1, NYC_LON, NYC_LAT)
        idx.add(2, LA_LON, LA_LAT)
        idx.add(3, LONDON_LON, LONDON_LAT)

        # Search within 100km of NYC -- should only find NYC
        pl = idx.search_within(NYC_LON, NYC_LAT, 100_000)
        ids = [e.doc_id for e in pl.entries]
        assert ids == [1]
        assert pl.entries[0].payload.score > 0.999

    def test_search_large_radius(self):
        idx = SpatialIndex("test", "loc")
        idx.add(1, NYC_LON, NYC_LAT)
        idx.add(2, LA_LON, LA_LAT)
        idx.add(3, LONDON_LON, LONDON_LAT)
        idx.add(4, TOKYO_LON, TOKYO_LAT)

        # 6000km radius from NYC -- NYC (~0km), LA (~3940km), London (~5570km)
        # all within range.  Tokyo (~10800km) is NOT.
        pl = idx.search_within(NYC_LON, NYC_LAT, 6_000_000)
        ids = sorted(e.doc_id for e in pl.entries)
        assert 1 in ids  # NYC
        assert 2 in ids  # LA
        assert 3 in ids  # London
        assert 4 not in ids  # Tokyo

    def test_empty_index(self):
        idx = SpatialIndex("test", "loc")
        pl = idx.search_within(0, 0, 1000)
        assert len(pl.entries) == 0

    def test_zero_distance(self):
        idx = SpatialIndex("test", "loc")
        idx.add(1, NYC_LON, NYC_LAT)
        pl = idx.search_within(NYC_LON, NYC_LAT, 0)
        assert len(pl.entries) == 0

    def test_delete(self):
        idx = SpatialIndex("test", "loc")
        idx.add(1, NYC_LON, NYC_LAT)
        idx.add(2, NYC_LON + 0.001, NYC_LAT + 0.001)
        assert idx.count() == 2

        idx.delete(1)
        assert idx.count() == 1

        pl = idx.search_within(NYC_LON, NYC_LAT, 1_000_000)
        ids = [e.doc_id for e in pl.entries]
        assert 1 not in ids
        assert 2 in ids

    def test_clear(self):
        idx = SpatialIndex("test", "loc")
        idx.add(1, NYC_LON, NYC_LAT)
        idx.add(2, LA_LON, LA_LAT)
        assert idx.count() == 2

        idx.clear()
        assert idx.count() == 0

    def test_proximity_score(self):
        idx = SpatialIndex("test", "loc")
        # Two points: one close, one far
        idx.add(1, NYC_LON, NYC_LAT)
        idx.add(2, NYC_LON + 0.01, NYC_LAT + 0.01)  # ~1.4km away

        pl = idx.search_within(NYC_LON, NYC_LAT, 100_000)
        scores = {e.doc_id: e.payload.score for e in pl.entries}
        # doc_id=1 is at the center, should have score very close to 1.0
        assert scores[1] > 0.999
        # doc_id=2 is farther, should have lower score
        assert scores[2] < scores[1]
        assert scores[2] > 0.0


# ==========================================================================
# SQL integration tests
# ==========================================================================


class TestSpatialSQL:
    @pytest.fixture()
    def engine(self):
        e = Engine()
        e.sql("""
            CREATE TABLE places (
                id SERIAL PRIMARY KEY,
                name TEXT,
                location POINT
            )
        """)
        return e

    def test_create_table_with_point(self, engine):
        result = engine.sql("SELECT * FROM places")
        assert result.columns == ["id", "name", "location"]
        assert result.rows == []

    def test_insert_and_select(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        result = engine.sql("SELECT name, location FROM places ORDER BY name")
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "LA"
        assert result.rows[0]["location"] == pytest.approx([-118.2437, 34.0522])
        assert result.rows[1]["name"] == "NYC"
        assert result.rows[1]["location"] == pytest.approx([-74.0060, 40.7128])

    def test_spatial_within_without_index(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('London', POINT(-0.1278, 51.5074))"
        )
        # 100km radius around NYC -- brute-force scan (no index)
        result = engine.sql(
            "SELECT name FROM places "
            "WHERE spatial_within(location, POINT(-74.0060, 40.7128), 100000)"
        )
        names = [r["name"] for r in result.rows]
        assert "NYC" in names
        assert "LA" not in names
        assert "London" not in names

    def test_create_rtree_index(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        # Create R*Tree index
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")
        table = engine._tables["places"]
        assert "location" in table.spatial_indexes
        assert table.spatial_indexes["location"].count() == 2

    def test_spatial_within_with_index(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('London', POINT(-0.1278, 51.5074))"
        )
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")

        # 100km from NYC
        result = engine.sql(
            "SELECT name FROM places "
            "WHERE spatial_within(location, POINT(-74.0060, 40.7128), 100000)"
        )
        names = [r["name"] for r in result.rows]
        assert "NYC" in names
        assert "LA" not in names

    def test_spatial_within_large_radius(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('London', POINT(-0.1278, 51.5074))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('Tokyo', POINT(139.6503, 35.6762))"
        )
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")

        # 6000km from NYC -- NYC, LA, London all within range
        result = engine.sql(
            "SELECT name FROM places "
            "WHERE spatial_within(location, POINT(-74.0060, 40.7128), 6000000)"
        )
        names = [r["name"] for r in result.rows]
        assert "NYC" in names
        assert "LA" in names
        assert "London" in names
        assert "Tokyo" not in names  # ~10,800 km

    def test_st_distance_scalar(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        result = engine.sql(
            "SELECT name, ST_Distance(location, POINT(-118.2437, 34.0522)) "
            "AS dist FROM places"
        )
        assert len(result.rows) == 1
        dist = result.rows[0]["dist"]
        # NYC to LA: ~3940km
        assert 3900_000 < dist < 4000_000

    def test_st_within_scalar(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        result = engine.sql(
            "SELECT name FROM places "
            "WHERE ST_DWithin(location, POINT(-74.0060, 40.7128), 100000)"
        )
        names = [r["name"] for r in result.rows]
        assert "NYC" in names
        assert "LA" not in names

    def test_point_constructor_in_select(self, engine):
        result = engine.sql("SELECT POINT(1.0, 2.0) AS pt")
        assert result.rows[0]["pt"] == [1.0, 2.0]

    def test_spatial_with_order_by_distance(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('London', POINT(-0.1278, 51.5074))"
        )
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")

        result = engine.sql(
            "SELECT name, "
            "ST_Distance(location, POINT(-74.0060, 40.7128)) AS dist "
            "FROM places "
            "WHERE spatial_within(location, POINT(-74.0060, 40.7128), 6000000) "
            "ORDER BY dist"
        )
        names = [r["name"] for r in result.rows]
        # NYC closest, then London (~5570km), LA might or might not be in range
        assert names[0] == "NYC"

    def test_delete_updates_spatial_index(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('LA', POINT(-118.2437, 34.0522))"
        )
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")
        assert engine._tables["places"].spatial_indexes["location"].count() == 2

        engine.sql("DELETE FROM places WHERE name = 'NYC'")
        assert engine._tables["places"].spatial_indexes["location"].count() == 1

        result = engine.sql(
            "SELECT name FROM places "
            "WHERE spatial_within(location, POINT(-74.0060, 40.7128), 100000)"
        )
        assert len(result.rows) == 0

    def test_truncate_clears_spatial_index(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")
        assert engine._tables["places"].spatial_indexes["location"].count() == 1

        engine.sql("TRUNCATE places")
        assert engine._tables["places"].spatial_indexes["location"].count() == 0

    def test_update_point_column(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")

        # Move NYC to LA's position
        engine.sql(
            "UPDATE places SET location = POINT(-118.2437, 34.0522) WHERE name = 'NYC'"
        )

        # Should no longer be found near NYC
        result = engine.sql(
            "SELECT name FROM places "
            "WHERE spatial_within(location, POINT(-74.0060, 40.7128), 100000)"
        )
        assert len(result.rows) == 0

        # Should be found near LA
        result = engine.sql(
            "SELECT name FROM places "
            "WHERE spatial_within(location, POINT(-118.2437, 34.0522), 100000)"
        )
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "NYC"

    def test_spatial_within_with_params(self, engine):
        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")

        result = engine.sql(
            "SELECT name FROM places WHERE spatial_within(location, $1, $2)",
            params=[[-74.0060, 40.7128], 100000],
        )
        names = [r["name"] for r in result.rows]
        assert "NYC" in names

    def test_insert_auto_updates_index(self, engine):
        engine.sql("CREATE INDEX idx_loc ON places USING rtree (location)")
        assert engine._tables["places"].spatial_indexes["location"].count() == 0

        engine.sql(
            "INSERT INTO places (name, location) "
            "VALUES ('NYC', POINT(-74.0060, 40.7128))"
        )
        assert engine._tables["places"].spatial_indexes["location"].count() == 1

    def test_rtree_index_on_non_point_column_fails(self, engine):
        with pytest.raises(ValueError, match="not a POINT column"):
            engine.sql("CREATE INDEX idx_name ON places USING rtree (name)")

    def test_spatial_and_text_search(self):
        e = Engine()
        e.sql("""
            CREATE TABLE restaurants (
                id SERIAL PRIMARY KEY,
                name TEXT,
                cuisine TEXT,
                location POINT
            )
        """)
        e.sql(
            "INSERT INTO restaurants (name, cuisine, location) "
            "VALUES ('Pizza Place', 'italian', POINT(-74.0060, 40.7128))"
        )
        e.sql(
            "INSERT INTO restaurants (name, cuisine, location) "
            "VALUES ('Sushi Bar', 'japanese', POINT(-74.0050, 40.7130))"
        )
        e.sql(
            "INSERT INTO restaurants (name, cuisine, location) "
            "VALUES ('Far Pizza', 'italian', POINT(-118.2437, 34.0522))"
        )
        e.sql("CREATE INDEX idx_rloc ON restaurants USING rtree (location)")

        # Find italian restaurants within 10km of NYC
        result = e.sql(
            "SELECT name FROM restaurants "
            "WHERE spatial_within(location, POINT(-74.0060, 40.7128), 10000) "
            "AND cuisine = 'italian'"
        )
        names = [r["name"] for r in result.rows]
        assert "Pizza Place" in names
        assert "Far Pizza" not in names
        assert "Sushi Bar" not in names


class TestSpatialPersistence:
    def test_data_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # First session: create table, insert data, create index
            with Engine(db_path=db_path) as e:
                e.sql("""
                    CREATE TABLE places (
                        id SERIAL PRIMARY KEY,
                        name TEXT,
                        location POINT
                    )
                """)
                e.sql(
                    "INSERT INTO places (name, location) "
                    "VALUES ('NYC', POINT(-74.0060, 40.7128))"
                )
                e.sql(
                    "INSERT INTO places (name, location) "
                    "VALUES ('LA', POINT(-118.2437, 34.0522))"
                )
                e.sql("CREATE INDEX idx_loc ON places USING rtree (location)")

            # Second session: verify data and index persist
            with Engine(db_path=db_path) as e:
                result = e.sql("SELECT name FROM places ORDER BY name")
                names = [r["name"] for r in result.rows]
                assert names == ["LA", "NYC"]

                # Verify spatial index was restored
                table = e._tables["places"]
                assert "location" in table.spatial_indexes
                assert table.spatial_indexes["location"].count() == 2

                # Verify spatial query works
                result = e.sql(
                    "SELECT name FROM places "
                    "WHERE spatial_within(location, "
                    "POINT(-74.0060, 40.7128), 100000)"
                )
                names = [r["name"] for r in result.rows]
                assert "NYC" in names
                assert "LA" not in names

    def test_insert_after_restart_updates_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            with Engine(db_path=db_path) as e:
                e.sql("""
                    CREATE TABLE places (
                        id SERIAL PRIMARY KEY,
                        name TEXT,
                        location POINT
                    )
                """)
                e.sql("CREATE INDEX idx_loc ON places USING rtree (location)")
                e.sql(
                    "INSERT INTO places (name, location) "
                    "VALUES ('NYC', POINT(-74.0060, 40.7128))"
                )

            with Engine(db_path=db_path) as e:
                e.sql(
                    "INSERT INTO places (name, location) "
                    "VALUES ('LA', POINT(-118.2437, 34.0522))"
                )
                assert e._tables["places"].spatial_indexes["location"].count() == 2

                result = e.sql(
                    "SELECT name FROM places "
                    "WHERE spatial_within(location, "
                    "POINT(-118.2437, 34.0522), 100000)"
                )
                names = [r["name"] for r in result.rows]
                assert "LA" in names


class TestSpatialFusion:
    def test_spatial_in_fuse_log_odds(self):
        e = Engine()
        e.sql("""
            CREATE TABLE restaurants (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                location POINT
            )
        """)
        e.sql(
            "INSERT INTO restaurants (name, description, location) "
            "VALUES ('Pizza Place', 'authentic italian pizza pasta', "
            "POINT(-74.0060, 40.7128))"
        )
        e.sql(
            "INSERT INTO restaurants (name, description, location) "
            "VALUES ('Sushi Bar', 'fresh japanese sushi rolls', "
            "POINT(-74.0050, 40.7130))"
        )
        e.sql(
            "INSERT INTO restaurants (name, description, location) "
            "VALUES ('Far Pizza', 'great italian pizza', "
            "POINT(-118.2437, 34.0522))"
        )
        e.sql("CREATE INDEX idx_rloc ON restaurants USING rtree (location)")
        e.sql("CREATE INDEX idx_rdesc_gin ON restaurants USING gin (description)")

        # Fuse text + spatial signals
        result = e.sql(
            "SELECT name FROM restaurants "
            "WHERE fuse_log_odds("
            "  text_match(description, 'italian pizza'), "
            "  spatial_within(location, POINT(-74.0060, 40.7128), 10000)"
            ") ORDER BY score DESC"
        )
        names = [r["name"] for r in result.rows]
        # Pizza Place matches both text and spatial
        assert names[0] == "Pizza Place"
