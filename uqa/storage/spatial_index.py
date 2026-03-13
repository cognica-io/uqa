#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""R*Tree-backed spatial index for POINT columns.

Uses SQLite's built-in R*Tree virtual table module for O(log N) spatial
queries.  Each point is stored as a degenerate bounding box (min == max)
in the R*Tree.  Range queries use a two-pass approach:

1. **Coarse filter**: R*Tree bounding box query (fast, conservative).
2. **Fine filter**: Haversine great-circle distance (exact).

The bounding box is computed by converting the search radius (meters)
to approximate degree deltas.
"""

from __future__ import annotations

import math
import sqlite3
from typing import TYPE_CHECKING

from uqa.core.posting_list import PostingList
from uqa.core.types import DocId, Payload, PostingEntry

if TYPE_CHECKING:
    from uqa.storage.managed_connection import SQLiteConnection

# Earth radius in meters (WGS-84 mean radius).
_EARTH_RADIUS_M = 6_371_000.0

# Meters per degree of latitude (approximate, constant).
_METERS_PER_DEG_LAT = 111_320.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points in meters.

    Uses the Haversine formula.  Inputs are in decimal degrees.
    """
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


class SpatialIndex:
    """R*Tree spatial index for 2-D point data.

    Coordinates are stored as (x, y) which, for geographic data,
    correspond to (longitude, latitude).  Search distances are in
    meters and use Haversine for the fine-filter pass.

    When *conn* is ``None`` a private in-memory SQLite connection is
    created so that the R*Tree module is still available for in-memory
    engines.
    """

    def __init__(
        self,
        table_name: str,
        field_name: str,
        conn: SQLiteConnection | None = None,
    ) -> None:
        self._table_name = table_name
        self._field_name = field_name
        self._owns_conn = conn is None
        self._conn = (
            conn
            if conn is not None
            else sqlite3.connect(":memory:", check_same_thread=False)
        )
        self._rtree_name = f"_rtree_{table_name}_{field_name}"
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            f'CREATE VIRTUAL TABLE IF NOT EXISTS "{self._rtree_name}" '
            f"USING rtree(id, min_x, max_x, min_y, max_y)"
        )
        self._conn.commit()

    # -- Mutations ---------------------------------------------------------

    def add(self, doc_id: DocId, x: float, y: float) -> None:
        """Insert or replace a point in the R*Tree."""
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{self._rtree_name}" '
            f"(id, min_x, max_x, min_y, max_y) VALUES (?, ?, ?, ?, ?)",
            (doc_id, x, x, y, y),
        )
        self._conn.commit()

    def delete(self, doc_id: DocId) -> None:
        """Remove a point from the R*Tree."""
        self._conn.execute(f'DELETE FROM "{self._rtree_name}" WHERE id = ?', (doc_id,))
        self._conn.commit()

    def clear(self) -> None:
        """Remove all entries from the R*Tree."""
        self._conn.execute(f'DELETE FROM "{self._rtree_name}"')
        self._conn.commit()

    # -- Search ------------------------------------------------------------

    def search_within(self, cx: float, cy: float, distance_m: float) -> PostingList:
        """Return all points within *distance_m* meters of (*cx*, *cy*).

        *cx* is longitude, *cy* is latitude (decimal degrees).
        Returns a PostingList sorted by doc_id with scores proportional
        to proximity: ``score = 1.0 - (dist / distance_m)``.
        """
        if distance_m <= 0.0:
            return PostingList()

        # Convert radius to approximate degree deltas for the bounding box.
        # For latitude: straightforward conversion.
        # For longitude: use the angular distance formula for a more
        # accurate bounding box, especially at large radii.
        delta_lat = distance_m / _METERS_PER_DEG_LAT

        # Angular distance in radians on the sphere.
        angular_dist = distance_m / _EARTH_RADIUS_M
        cos_lat = math.cos(math.radians(cy))
        if cos_lat < 1e-10 or angular_dist >= math.pi:
            delta_lon = 180.0
        else:
            # Maximum longitude offset at any latitude within the circle.
            # From the spherical law of cosines:
            # cos(angular_dist) = sin(lat1)*sin(lat2) + cos(lat1)*cos(lat2)*cos(dlon)
            # Solving for dlon when lat2 = lat1 (worst case for lon spread):
            sin_ratio = math.sin(angular_dist) / cos_lat
            if sin_ratio >= 1.0:
                delta_lon = 180.0
            else:
                delta_lon = math.degrees(math.asin(sin_ratio))

        min_x = cx - delta_lon
        max_x = cx + delta_lon
        min_y = cy - delta_lat
        max_y = cy + delta_lat

        rows = self._conn.execute(
            f'SELECT id, min_x, min_y FROM "{self._rtree_name}" '
            f"WHERE max_x >= ? AND min_x <= ? "
            f"AND max_y >= ? AND min_y <= ?",
            (min_x, max_x, min_y, max_y),
        ).fetchall()

        entries: list[PostingEntry] = []
        for doc_id, px, py in rows:
            dist = haversine_distance(cy, cx, py, px)
            if dist <= distance_m:
                score = 1.0 - (dist / distance_m)
                entries.append(PostingEntry(doc_id, Payload(score=score)))

        entries.sort(key=lambda e: e.doc_id)
        return PostingList.from_sorted(entries)

    # -- Metadata ----------------------------------------------------------

    def count(self) -> int:
        """Return the number of points in the index."""
        row = self._conn.execute(
            f'SELECT COUNT(*) FROM "{self._rtree_name}"'
        ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        """Close the private connection if we own it."""
        if self._owns_conn:
            self._conn.close()
