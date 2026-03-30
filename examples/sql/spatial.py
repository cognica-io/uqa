#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Geospatial SQL examples using the engine.sql() API.

Demonstrates:
  - POINT column type and R*Tree spatial index
  - spatial_within(): range query in WHERE clause
  - ST_Distance(): scalar Haversine distance
  - ST_DWithin(): scalar distance predicate
  - POINT() constructor in SELECT and INSERT
  - Spatial + text combined queries
  - Spatial + fusion (fuse_log_odds with spatial signal)
  - Spatial ORDER BY distance
  - Parameter binding for POINT and distance
"""

import numpy as np

from uqa.engine import Engine

engine = Engine()


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<20}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<20.4f}")
            elif isinstance(v, list):
                vals.append(str(v)[:20].ljust(20))
            else:
                vals.append(str(v)[:20].ljust(20))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Geospatial SQL Examples")
print("=" * 70)


# ==================================================================
# DDL: CREATE TABLE with POINT column
# ==================================================================
engine.sql("""
    CREATE TABLE restaurants (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        cuisine TEXT NOT NULL,
        rating REAL,
        description TEXT,
        location POINT,
        embedding VECTOR(8)
    )
""")

# ==================================================================
# CREATE INDEX: GIN index for text search on description
# ==================================================================
engine.sql("CREATE INDEX idx_restaurants_gin ON restaurants USING gin (description)")

# ==================================================================
# CREATE INDEX: R*Tree spatial index
# ==================================================================
engine.sql("CREATE INDEX idx_location ON restaurants USING rtree (location)")

# ==================================================================
# INSERT: POINT(longitude, latitude)
# ==================================================================
rng = np.random.RandomState(42)

restaurants = [
    # name, cuisine, rating, description, (lon, lat)
    (
        "Joes Pizza",
        "italian",
        4.5,
        "classic new york slice pizza and pasta",
        -73.9969,
        40.7306,
    ),  # Greenwich Village, NYC
    (
        "Sushi Nakazawa",
        "japanese",
        4.8,
        "omakase sushi from jiro apprentice",
        -74.0021,
        40.7339,
    ),  # West Village, NYC
    (
        "Xian Famous",
        "chinese",
        4.3,
        "hand pulled noodles and spicy lamb",
        -73.9936,
        40.7426,
    ),  # Midtown, NYC
    (
        "Le Bernardin",
        "french",
        4.9,
        "fine dining seafood and french cuisine",
        -73.9817,
        40.7614,
    ),  # Midtown West, NYC
    (
        "Katzs Deli",
        "american",
        4.6,
        "legendary pastrami sandwich since 1888",
        -73.9874,
        40.7223,
    ),  # Lower East Side, NYC
    (
        "Ippudo",
        "japanese",
        4.4,
        "authentic japanese ramen and gyoza",
        -73.9901,
        40.7310,
    ),  # East Village, NYC
    (
        "Lombardis",
        "italian",
        4.2,
        "first pizzeria in america coal oven pizza",
        -73.9956,
        40.7216,
    ),  # Little Italy, NYC
    (
        "Blue Ribbon Sushi",
        "japanese",
        4.5,
        "fresh sushi and sashimi late night spot",
        -73.9981,
        40.7268,
    ),  # SoHo, NYC
    (
        "LArtusi",
        "italian",
        4.6,
        "modern italian pasta and wine bar",
        -74.0014,
        40.7332,
    ),  # West Village, NYC
    (
        "Bouley at Home",
        "french",
        4.7,
        "french bistro tasting menu downtown",
        -74.0084,
        40.7174,
    ),  # Tribeca, NYC
    (
        "Santa Monica Pier",
        "american",
        3.8,
        "beachside burgers and seafood shack",
        -118.4965,
        34.0094,
    ),  # Santa Monica, LA
    (
        "Nobu Malibu",
        "japanese",
        4.7,
        "oceanfront japanese cuisine and sushi",
        -118.6798,
        34.0367,
    ),  # Malibu, LA
]

for name, cuisine, rating, desc, lon, lat in restaurants:
    vec = rng.randn(8).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    arr = "ARRAY[" + ",".join(str(float(v)) for v in vec) + "]"
    engine.sql(
        f"INSERT INTO restaurants (name, cuisine, rating, description, "
        f"location, embedding) "
        f"VALUES ('{name}', '{cuisine}', {rating}, '{desc}', "
        f"POINT({lon}, {lat}), {arr})"
    )


# ==================================================================
# 1. Basic: SELECT all restaurants
# ==================================================================
show(
    "1. All restaurants",
    engine.sql("SELECT name, cuisine, rating, location FROM restaurants ORDER BY name"),
)


# ==================================================================
# 2. spatial_within: restaurants within 2km of Washington Square Park
# ==================================================================
WSP_LON, WSP_LAT = -73.9973, 40.7308  # Washington Square Park

show(
    "2. Within 2km of Washington Square Park",
    engine.sql(f"""
    SELECT name, cuisine, rating
    FROM restaurants
    WHERE spatial_within(location, POINT({WSP_LON}, {WSP_LAT}), 2000)
    ORDER BY rating DESC
"""),
)


# ==================================================================
# 3. ST_Distance: compute distance from a point
# ==================================================================
show(
    "3. Distance from Times Square",
    engine.sql("""
    SELECT name,
           ROUND(ST_Distance(location, POINT(-73.9855, 40.7580)), 0) AS dist_m
    FROM restaurants
    WHERE spatial_within(location, POINT(-73.9855, 40.7580), 5000)
    ORDER BY dist_m
"""),
)


# ==================================================================
# 4. ST_DWithin in WHERE: scalar distance predicate
# ==================================================================
show(
    "4. ST_DWithin: restaurants within 1.5km of Union Square",
    engine.sql("""
    SELECT name, cuisine
    FROM restaurants
    WHERE ST_DWithin(location, POINT(-73.9903, 40.7359), 1500)
    ORDER BY name
"""),
)


# ==================================================================
# 5. Spatial + text: Japanese restaurants near SoHo
# ==================================================================
show(
    "5. Japanese restaurants within 3km of SoHo",
    engine.sql("""
    SELECT name, rating
    FROM restaurants
    WHERE spatial_within(location, POINT(-73.9990, 40.7233), 3000)
      AND cuisine = 'japanese'
    ORDER BY rating DESC
"""),
)


# ==================================================================
# 6. Spatial + ORDER BY distance
# ==================================================================
show(
    "6. Nearest restaurants to Empire State Building",
    engine.sql("""
    SELECT name, cuisine,
           ROUND(ST_Distance(location, POINT(-73.9857, 40.7484)), 0) AS dist_m
    FROM restaurants
    WHERE spatial_within(location, POINT(-73.9857, 40.7484), 5000)
    ORDER BY dist_m
    LIMIT 5
"""),
)


# ==================================================================
# 7. POINT constructor in SELECT
# ==================================================================
show(
    "7. POINT constructor in SELECT",
    engine.sql("""
    SELECT name, POINT(-73.9857, 40.7484) AS empire_state
    FROM restaurants
    LIMIT 3
"""),
)


# ==================================================================
# 8. Spatial + fusion: text relevance + proximity
# ==================================================================
show(
    "8. fuse_log_odds: text + spatial (pizza near Greenwich Village)",
    engine.sql("""
    SELECT name, _score
    FROM restaurants
    WHERE fuse_log_odds(
        text_match(description, 'pizza'),
        spatial_within(location, POINT(-73.9969, 40.7306), 3000)
    )
    ORDER BY _score DESC
"""),
)


# ==================================================================
# 9. Spatial + fusion: 3 signals (text + spatial + vector)
# ==================================================================
query_vec = rng.randn(8).astype(np.float32)
query_vec = query_vec / np.linalg.norm(query_vec)

show(
    "9. fuse_log_odds: text + spatial + vector",
    engine.sql(
        """
    SELECT name, _score
    FROM restaurants
    WHERE fuse_log_odds(
        text_match(description, 'sushi japanese'),
        spatial_within(location, POINT(-73.9973, 40.7308), 5000),
        knn_match(embedding, $1, 5)
    )
    ORDER BY _score DESC
""",
        params=[query_vec],
    ),
)


# ==================================================================
# 10. Aggregation with spatial filter
# ==================================================================
show(
    "10. Average rating by cuisine (NYC only, within 10km of Midtown)",
    engine.sql("""
    SELECT cuisine, COUNT(*) AS cnt, ROUND(AVG(rating), 2) AS avg_rating
    FROM restaurants
    WHERE spatial_within(location, POINT(-73.9857, 40.7484), 10000)
    GROUP BY cuisine
    ORDER BY avg_rating DESC
"""),
)


# ==================================================================
# 11. Parameter binding for spatial queries
# ==================================================================
show(
    "11. Parameter binding: $1=center, $2=radius",
    engine.sql(
        "SELECT name, cuisine FROM restaurants "
        "WHERE spatial_within(location, $1, $2) "
        "ORDER BY name",
        params=[[-73.9973, 40.7308], 2000],
    ),
)


# ==================================================================
# 12. UPDATE with POINT
# ==================================================================
engine.sql("""
    UPDATE restaurants
    SET location = POINT(-73.9950, 40.7280)
    WHERE name = 'Katzs Deli'
""")
show(
    "12. After UPDATE location",
    engine.sql("""
    SELECT name, location FROM restaurants WHERE name = 'Katzs Deli'
"""),
)


# ==================================================================
# 13. DELETE + spatial index maintenance
# ==================================================================
engine.sql("DELETE FROM restaurants WHERE name = 'Santa Monica Pier'")
show(
    "13. After DELETE (LA restaurants removed)",
    engine.sql("""
    SELECT name FROM restaurants
    WHERE spatial_within(location, POINT(-118.4965, 34.0094), 100000)
"""),
)


# ==================================================================
# 14. EXPLAIN spatial query
# ==================================================================
result = engine.sql("""
    EXPLAIN SELECT name FROM restaurants
    WHERE spatial_within(location, POINT(-73.9973, 40.7308), 2000)
""")
print("\n--- 14. EXPLAIN spatial query ---")
for row in result.rows:
    print(f"  {row['plan']}")


print("\n" + "=" * 70)
print("All geospatial SQL examples completed successfully.")
print("=" * 70)
