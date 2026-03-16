#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""NYC Taxi analytics via FDW full query pushdown.

Queries the NYC TLC Yellow Taxi trip data from S3 Parquet files using
DuckDB's httpfs extension -- no download required.  DuckDB reads
Parquet metadata and column chunks via HTTP Range requests, and UQA's
full query pushdown delegates the entire SQL to DuckDB.

Data source:
    s3://cognica-database/nyc-taxi/yellow/

Demonstrates:
  - S3 Parquet via httpfs extension
  - Full query pushdown (aggregates, GROUP BY, ORDER BY, LIMIT)
  - Window functions on foreign tables
  - Subqueries on foreign tables
  - Mixed foreign-local JOINs (local dimension table shipped to DuckDB)
  - R*Tree spatial index with foreign-local JOIN
"""

from uqa.engine import Engine

S3_BUCKET = "s3://cognica-database/nyc-taxi/yellow"

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
                vals.append(f"{v:<20.2f}")
            else:
                vals.append(str(v)[:20].ljust(20))
        print("  " + " | ".join(vals))


print("=" * 70)
print("NYC Taxi Analytics -- FDW Full Query Pushdown")
print("=" * 70)


# ==================================================================
# 1. Setup: remote Parquet via httpfs
# ==================================================================
print("\n--- 1. Setup: CREATE SERVER with httpfs + S3 region ---")

engine.sql("""
    CREATE SERVER taxi_s3 FOREIGN DATA WRAPPER duckdb_fdw
    OPTIONS (extensions 'httpfs', s3_region 'ap-northeast-2')
""")

# January 2024 -- single month for fast examples
engine.sql(f"""
    CREATE FOREIGN TABLE yellow_trips (
        "VendorID" INTEGER,
        tpep_pickup_datetime TIMESTAMP,
        tpep_dropoff_datetime TIMESTAMP,
        passenger_count BIGINT,
        trip_distance DOUBLE PRECISION,
        "RatecodeID" BIGINT,
        store_and_fwd_flag TEXT,
        "PULocationID" INTEGER,
        "DOLocationID" INTEGER,
        payment_type BIGINT,
        fare_amount DOUBLE PRECISION,
        extra DOUBLE PRECISION,
        mta_tax DOUBLE PRECISION,
        tip_amount DOUBLE PRECISION,
        tolls_amount DOUBLE PRECISION,
        improvement_surcharge DOUBLE PRECISION,
        total_amount DOUBLE PRECISION,
        congestion_surcharge DOUBLE PRECISION,
        "Airport_fee" DOUBLE PRECISION
    ) SERVER taxi_s3
    OPTIONS (source '{S3_BUCKET}/yellow_tripdata_2024-01.parquet')
""")
print("  Server and foreign table created (S3 Parquet).")


# ==================================================================
# 2. Basic count -- full pushdown to DuckDB
# ==================================================================
show(
    "2. Total trips in January 2024",
    engine.sql("SELECT COUNT(*) AS total_trips FROM yellow_trips"),
)


# ==================================================================
# 3. Aggregate statistics
# ==================================================================
show(
    "3. Trip statistics",
    engine.sql("""
        SELECT COUNT(*) AS trips,
               AVG(trip_distance) AS avg_distance,
               AVG(fare_amount) AS avg_fare,
               AVG(tip_amount) AS avg_tip,
               AVG(total_amount) AS avg_total,
               MAX(total_amount) AS max_total
        FROM yellow_trips
        WHERE fare_amount > 0
    """),
)


# ==================================================================
# 4. GROUP BY: payment type breakdown
# ==================================================================
show(
    "4. Trips by payment type",
    engine.sql("""
        SELECT payment_type,
               COUNT(*) AS trips,
               AVG(fare_amount) AS avg_fare,
               AVG(tip_amount) AS avg_tip
        FROM yellow_trips
        GROUP BY payment_type
        ORDER BY trips DESC
    """),
)


# ==================================================================
# 5. Top pickup locations
# ==================================================================
show(
    "5. Top 10 pickup locations",
    engine.sql("""
        SELECT "PULocationID" AS location,
               COUNT(*) AS pickups,
               AVG(total_amount) AS avg_total
        FROM yellow_trips
        GROUP BY "PULocationID"
        ORDER BY pickups DESC
        LIMIT 10
    """),
)


# ==================================================================
# 6. Hourly trip distribution
# ==================================================================
show(
    "6. Trips by hour of day",
    engine.sql("""
        SELECT HOUR(tpep_pickup_datetime) AS hour,
               COUNT(*) AS trips,
               AVG(trip_distance) AS avg_dist
        FROM yellow_trips
        GROUP BY HOUR(tpep_pickup_datetime)
        ORDER BY hour
    """),
)


# ==================================================================
# 7. Window function: running average fare by day
# ==================================================================
show(
    "7. Daily running average fare (window function)",
    engine.sql("""
        SELECT day, daily_avg_fare,
               AVG(daily_avg_fare) OVER (
                   ORDER BY day
                   ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
               ) AS moving_avg_3d
        FROM (
            SELECT DATE_TRUNC('day', tpep_pickup_datetime) AS day,
                   AVG(fare_amount) AS daily_avg_fare
            FROM yellow_trips
            WHERE fare_amount > 0
            GROUP BY DATE_TRUNC('day', tpep_pickup_datetime)
        ) daily
        ORDER BY day
        LIMIT 10
    """),
)


# ==================================================================
# 8. Subquery: above-average trips
# ==================================================================
show(
    "8. Trips with above-average fare (subquery)",
    engine.sql("""
        SELECT COUNT(*) AS above_avg_trips,
               AVG(total_amount) AS avg_total_of_above
        FROM yellow_trips
        WHERE fare_amount > (
            SELECT AVG(fare_amount) FROM yellow_trips WHERE fare_amount > 0
        )
    """),
)


# ==================================================================
# 9. Top earners by day of week
# ==================================================================
show(
    "9. Revenue by day of week",
    engine.sql("""
        SELECT DAYOFWEEK(tpep_pickup_datetime) AS dow,
               COUNT(*) AS trips,
               SUM(total_amount) AS total_revenue,
               AVG(total_amount) AS avg_total
        FROM yellow_trips
        GROUP BY DAYOFWEEK(tpep_pickup_datetime)
        ORDER BY dow
    """),
)


# ==================================================================
# 10. Mixed foreign-local JOIN: zone lookup
# ==================================================================
print("\n--- 10. Mixed foreign-local JOIN ---")
print("  Creating local zone lookup table...")

engine.sql("""
    CREATE TABLE zone_names (
        location_id INTEGER PRIMARY KEY,
        zone TEXT NOT NULL,
        borough TEXT NOT NULL
    )
""")

# Top Manhattan zones
zones = [
    (132, "JFK Airport", "Queens"),
    (138, "LaGuardia Airport", "Queens"),
    (161, "Midtown Center", "Manhattan"),
    (162, "Midtown East", "Manhattan"),
    (163, "Midtown North", "Manhattan"),
    (170, "Murray Hill", "Manhattan"),
    (186, "Penn Station/Madison Sq West", "Manhattan"),
    (230, "Times Sq/Theatre District", "Manhattan"),
    (236, "Upper East Side North", "Manhattan"),
    (237, "Upper East Side South", "Manhattan"),
]
for lid, zone, borough in zones:
    zone_escaped = zone.replace("'", "''")
    engine.sql(
        f"INSERT INTO zone_names (location_id, zone, borough) "
        f"VALUES ({lid}, '{zone_escaped}', '{borough}')"
    )

show(
    "10. Pickups by zone (foreign-local JOIN)",
    engine.sql("""
        SELECT z.zone, z.borough,
               COUNT(*) AS pickups,
               AVG(t.total_amount) AS avg_total
        FROM yellow_trips t
        JOIN zone_names z ON t."PULocationID" = z.location_id
        GROUP BY z.zone, z.borough
        ORDER BY pickups DESC
    """),
)


# ==================================================================
# 11. Airport trip analysis
# ==================================================================
show(
    "11. Airport vs Manhattan comparison",
    engine.sql("""
        SELECT z.borough,
               COUNT(*) AS trips,
               AVG(t.trip_distance) AS avg_dist,
               AVG(t.fare_amount) AS avg_fare,
               AVG(t.tip_amount) AS avg_tip
        FROM yellow_trips t
        JOIN zone_names z ON t."PULocationID" = z.location_id
        GROUP BY z.borough
        ORDER BY trips DESC
    """),
)


# ==================================================================
# 12. Spatial query: R*Tree index on local zones
# ==================================================================
print("\n--- 12. Spatial R*Tree index + foreign-local JOIN ---")

engine.sql("""
    CREATE TABLE zone_locations (
        location_id INTEGER PRIMARY KEY,
        zone TEXT NOT NULL,
        location POINT
    )
""")

# Approximate centroids for selected zones (lon, lat)
spatial_zones = [
    (132, "JFK Airport", -73.7781, 40.6413),
    (138, "LaGuardia Airport", -73.8740, 40.7769),
    (161, "Midtown Center", -73.9819, 40.7549),
    (162, "Midtown East", -73.9685, 40.7587),
    (163, "Midtown North", -73.9817, 40.7648),
    (170, "Murray Hill", -73.9780, 40.7478),
    (186, "Penn Station/Madison Sq West", -73.9928, 40.7491),
    (230, "Times Sq/Theatre District", -73.9862, 40.7580),
    (236, "Upper East Side North", -73.9548, 40.7749),
    (237, "Upper East Side South", -73.9623, 40.7680),
]
for lid, zone, lon, lat in spatial_zones:
    zone_escaped = zone.replace("'", "''")
    engine.sql(
        f"INSERT INTO zone_locations (location_id, zone, location) "
        f"VALUES ({lid}, '{zone_escaped}', POINT({lon}, {lat}))"
    )

engine.sql("CREATE INDEX idx_zone_loc ON zone_locations USING rtree (location)")

# Find zones within 2km of Times Square
result = engine.sql("""
    SELECT zone,
           ROUND(ST_Distance(location, POINT(-73.9857, 40.7580)), 0) AS dist_m
    FROM zone_locations
    WHERE spatial_within(location, POINT(-73.9857, 40.7580), 2000)
    ORDER BY dist_m
""")
show("12a. Zones within 2km of Times Square (R*Tree)", result)

# Get zone IDs from spatial query, then aggregate taxi trips
zone_ids = [
    r["location_id"]
    for r in engine.sql("""
        SELECT location_id FROM zone_locations
        WHERE spatial_within(location, POINT(-73.9857, 40.7580), 2000)
    """).rows
]
id_list = ", ".join(str(z) for z in zone_ids)

show(
    "12b. Trip volume for zones near Times Square",
    engine.sql(f"""
        SELECT z.zone,
               COUNT(*) AS pickups,
               AVG(t.total_amount) AS avg_total
        FROM yellow_trips t
        JOIN zone_names z ON t."PULocationID" = z.location_id
        WHERE z.location_id IN ({id_list})
        GROUP BY z.zone
        ORDER BY pickups DESC
    """),
)


# ==================================================================
# Cleanup
# ==================================================================
engine.sql("DROP FOREIGN TABLE yellow_trips")
engine.sql("DROP SERVER taxi_s3")
engine.close()


print("\n" + "=" * 70)
print("All NYC Taxi examples completed successfully.")
print("=" * 70)
