#!/usr/bin/env python3
#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Advanced analytics: aggregates, window functions, JSON, and date/time.

Demonstrates:
  - COUNT(DISTINCT), STRING_AGG, ARRAY_AGG, BOOL_AND, BOOL_OR
  - STDDEV, VARIANCE, PERCENTILE_CONT, PERCENTILE_DISC, MODE
  - Aggregate FILTER (WHERE ...) and ORDER BY within aggregate
  - Window functions: ROWS BETWEEN, RANGE BETWEEN, named windows
  - PERCENT_RANK, CUME_DIST, NTH_VALUE
  - JSON/JSONB: operators (->>, #>>), containment (@>), functions
  - Date/time: EXTRACT, DATE_TRUNC, AGE, interval arithmetic
  - GREATEST, LEAST, NULLIF, COALESCE
  - CASE with aggregates
"""

from uqa.engine import Engine

engine = Engine()


def show(label, result):
    print(f"\n--- {label} ---")
    if not result.rows:
        print("  (no rows)")
        return
    header = "  " + " | ".join(f"{c:<18}" for c in result.columns)
    print(header)
    print("  " + "-" * len(header.strip()))
    for row in result.rows:
        vals = []
        for c in result.columns:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<18.4f}")
            else:
                vals.append(str(v)[:18].ljust(18))
        print("  " + " | ".join(vals))


print("=" * 70)
print("Advanced Analytics Examples")
print("=" * 70)


# ==================================================================
# Setup: sales data
# ==================================================================
engine.sql("""
    CREATE TABLE sales (
        id SERIAL PRIMARY KEY,
        rep TEXT NOT NULL,
        region TEXT NOT NULL,
        product TEXT NOT NULL,
        amount REAL NOT NULL,
        quantity INTEGER NOT NULL,
        sale_date DATE NOT NULL,
        returned BOOLEAN DEFAULT FALSE
    )
""")
engine.sql("""INSERT INTO sales (rep, region, product, amount, quantity, sale_date, returned) VALUES
    ('Alice', 'East',  'Widget',  1200.00, 10, '2024-01-15', FALSE),
    ('Alice', 'East',  'Gadget',  800.00,  5,  '2024-02-10', FALSE),
    ('Bob',   'West',  'Widget',  1500.00, 12, '2024-01-20', FALSE),
    ('Bob',   'West',  'Gadget',  600.00,  3,  '2024-03-05', TRUE),
    ('Carol', 'East',  'Widget',  900.00,  8,  '2024-02-28', FALSE),
    ('Carol', 'East',  'Gizmo',   2100.00, 7,  '2024-03-15', FALSE),
    ('Diana', 'West',  'Gizmo',   1800.00, 6,  '2024-01-10', FALSE),
    ('Diana', 'West',  'Widget',  1100.00, 9,  '2024-04-01', FALSE),
    ('Alice', 'East',  'Gizmo',   1400.00, 4,  '2024-04-15', FALSE),
    ('Bob',   'West',  'Gizmo',   2200.00, 8,  '2024-04-20', TRUE),
    ('Carol', 'East',  'Gadget',  750.00,  6,  '2024-05-01', FALSE),
    ('Diana', 'West',  'Gadget',  950.00,  7,  '2024-05-10', FALSE)
""")

print("\n  Table created: sales (12 rows)")


# ==================================================================
# 1. COUNT(DISTINCT)
# ==================================================================
show(
    "1. COUNT(DISTINCT product) by region",
    engine.sql("""
    SELECT region,
           COUNT(*) AS total_sales,
           COUNT(DISTINCT product) AS unique_products,
           COUNT(DISTINCT rep) AS unique_reps
    FROM sales
    GROUP BY region
    ORDER BY region
"""),
)


# ==================================================================
# 2. STRING_AGG
# ==================================================================
show(
    "2. STRING_AGG: product list per rep",
    engine.sql("""
    SELECT rep,
           STRING_AGG(DISTINCT product, ', ') AS products
    FROM sales
    GROUP BY rep
    ORDER BY rep
"""),
)


# ==================================================================
# 3. ARRAY_AGG
# ==================================================================
show(
    "3. ARRAY_AGG: quantities per region",
    engine.sql("""
    SELECT region,
           ARRAY_AGG(quantity) AS quantities
    FROM sales
    WHERE returned = FALSE
    GROUP BY region
    ORDER BY region
"""),
)


# ==================================================================
# 4. BOOL_AND / BOOL_OR
# ==================================================================
show(
    "4. BOOL_AND / BOOL_OR: return status by rep",
    engine.sql("""
    SELECT rep,
           BOOL_AND(returned) AS all_returned,
           BOOL_OR(returned) AS any_returned
    FROM sales
    GROUP BY rep
    ORDER BY rep
"""),
)


# ==================================================================
# 5. Aggregate with FILTER clause
# ==================================================================
show(
    "5. FILTER: conditional aggregates in one query",
    engine.sql("""
    SELECT region,
           SUM(amount) AS total,
           SUM(amount) FILTER (WHERE returned = FALSE) AS net_revenue,
           COUNT(*) FILTER (WHERE returned = TRUE) AS return_count
    FROM sales
    GROUP BY region
    ORDER BY region
"""),
)


# ==================================================================
# 6. Aggregate with ORDER BY within aggregate
# ==================================================================
show(
    "6. STRING_AGG with ORDER BY",
    engine.sql("""
    SELECT region,
           STRING_AGG(rep, ', ' ORDER BY rep) AS reps_sorted
    FROM sales
    GROUP BY region
    ORDER BY region
"""),
)


# ==================================================================
# 7. STDDEV / VARIANCE
# ==================================================================
show(
    "7. STDDEV and VARIANCE of sale amounts",
    engine.sql("""
    SELECT region,
           AVG(amount) AS avg_amount,
           STDDEV(amount) AS stddev_amount,
           VARIANCE(amount) AS var_amount
    FROM sales
    WHERE returned = FALSE
    GROUP BY region
    ORDER BY region
"""),
)


# ==================================================================
# 8. PERCENTILE_CONT / PERCENTILE_DISC
# ==================================================================
show(
    "8. Percentile: median and P90 sale amount",
    engine.sql("""
    SELECT
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) AS median,
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) AS p90,
        PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY amount) AS median_disc
    FROM sales
    WHERE returned = FALSE
"""),
)


# ==================================================================
# 9. MODE
# ==================================================================
show(
    "9. MODE: most frequent product",
    engine.sql("""
    SELECT MODE() WITHIN GROUP (ORDER BY product) AS most_common
    FROM sales
"""),
)


# ==================================================================
# 10. Window: ROW_NUMBER + running total
# ==================================================================
show(
    "10. Window: running total by date",
    engine.sql("""
    SELECT rep, sale_date, amount,
           SUM(amount) OVER (ORDER BY sale_date
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
    FROM sales
    WHERE returned = FALSE
    ORDER BY sale_date
    LIMIT 8
"""),
)


# ==================================================================
# 11. Window: ROWS BETWEEN for moving average
# ==================================================================
show(
    "11. Window: 3-row moving average",
    engine.sql("""
    SELECT rep, sale_date, amount,
           AVG(amount) OVER (ORDER BY sale_date
               ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) AS moving_avg
    FROM sales
    WHERE returned = FALSE
    ORDER BY sale_date
    LIMIT 8
"""),
)


# ==================================================================
# 12. Window: PERCENT_RANK and CUME_DIST
# ==================================================================
show(
    "12. PERCENT_RANK and CUME_DIST",
    engine.sql("""
    SELECT rep, amount,
           PERCENT_RANK() OVER (ORDER BY amount) AS pct_rank,
           CUME_DIST() OVER (ORDER BY amount) AS cume_dist
    FROM sales
    WHERE returned = FALSE
    ORDER BY amount DESC
    LIMIT 6
"""),
)


# ==================================================================
# 13. Window: NTH_VALUE
# ==================================================================
show(
    "13. NTH_VALUE: 2nd highest sale per region",
    engine.sql("""
    SELECT rep, region, amount,
           NTH_VALUE(amount, 2) OVER (
               PARTITION BY region ORDER BY amount DESC
               ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
           ) AS second_highest
    FROM sales
    WHERE returned = FALSE
    ORDER BY region, amount DESC
"""),
)


# ==================================================================
# 14. Named window
# ==================================================================
show(
    "14. Named window: multiple functions sharing window",
    engine.sql("""
    SELECT rep, amount,
           ROW_NUMBER() OVER w AS rn,
           RANK() OVER w AS rnk,
           LAG(amount) OVER w AS prev_amount
    FROM sales
    WHERE returned = FALSE
    WINDOW w AS (ORDER BY amount DESC)
    ORDER BY amount DESC
    LIMIT 6
"""),
)


# ==================================================================
# 15. Date functions: EXTRACT, DATE_TRUNC
# ==================================================================
show(
    "15. EXTRACT and DATE_TRUNC",
    engine.sql("""
    SELECT sale_date,
           EXTRACT(YEAR FROM sale_date) AS yr,
           EXTRACT(MONTH FROM sale_date) AS mo,
           DATE_TRUNC('month', sale_date) AS month_start
    FROM sales
    ORDER BY sale_date
    LIMIT 6
"""),
)


# ==================================================================
# 16. Date grouping: monthly revenue
# ==================================================================
show(
    "16. Monthly revenue summary",
    engine.sql("""
    SELECT DATE_TRUNC('month', sale_date) AS month,
           COUNT(*) AS num_sales,
           SUM(amount) AS revenue
    FROM sales
    WHERE returned = FALSE
    GROUP BY DATE_TRUNC('month', sale_date)
    ORDER BY month
"""),
)


# ==================================================================
# 17. GREATEST, LEAST, NULLIF
# ==================================================================
show(
    "17. GREATEST / LEAST / NULLIF",
    engine.sql("""
    SELECT rep, amount, quantity,
           GREATEST(amount, quantity * 100) AS higher_metric,
           LEAST(amount, 1000) AS capped_amount,
           NULLIF(returned, FALSE) AS returned_or_null
    FROM sales
    ORDER BY amount DESC
    LIMIT 6
"""),
)


# ==================================================================
# 18. CASE with aggregates: pivot-style query
# ==================================================================
show(
    "18. CASE pivot: revenue by product",
    engine.sql("""
    SELECT rep,
           SUM(CASE WHEN product = 'Widget' THEN amount ELSE 0 END) AS widget_rev,
           SUM(CASE WHEN product = 'Gadget' THEN amount ELSE 0 END) AS gadget_rev,
           SUM(CASE WHEN product = 'Gizmo' THEN amount ELSE 0 END) AS gizmo_rev,
           SUM(amount) AS total
    FROM sales
    WHERE returned = FALSE
    GROUP BY rep
    ORDER BY total DESC
"""),
)


# ==================================================================
# 19. JSON: create and query JSON data
# ==================================================================
engine.sql("""
    CREATE TABLE events (
        id SERIAL PRIMARY KEY,
        event_type TEXT NOT NULL,
        payload JSONB NOT NULL,
        created_at TIMESTAMP NOT NULL
    )
""")
engine.sql("""INSERT INTO events (event_type, payload, created_at) VALUES
    ('login',    '{"user": "alice", "ip": "10.0.0.1", "device": "mobile"}'::jsonb,
     '2024-03-01 09:00:00'),
    ('purchase', '{"user": "alice", "item": "widget", "price": 29.99}'::jsonb,
     '2024-03-01 09:15:00'),
    ('login',    '{"user": "bob", "ip": "10.0.0.2", "device": "desktop"}'::jsonb,
     '2024-03-01 10:00:00'),
    ('purchase', '{"user": "bob", "item": "gadget", "price": 49.99}'::jsonb,
     '2024-03-01 10:30:00'),
    ('logout',   '{"user": "alice", "session_duration": 1800}'::jsonb,
     '2024-03-01 11:00:00')
""")

show(
    "19a. JSON ->> operator: extract fields",
    engine.sql("""
    SELECT event_type,
           payload->>'user' AS username,
           created_at
    FROM events
    ORDER BY created_at
"""),
)

show(
    "19b. JSON containment @>",
    engine.sql("""
    SELECT event_type, payload->>'user' AS username
    FROM events
    WHERE payload @> '{"device": "mobile"}'::jsonb
"""),
)


# ==================================================================
# 20. String functions: POSITION, SPLIT_PART, LPAD
# ==================================================================
show(
    "20. String functions",
    engine.sql("""
    SELECT rep,
           POSITION('o' IN rep) AS o_pos,
           LPAD(rep, 8, '.') AS padded,
           REVERSE(rep) AS reversed
    FROM sales
    GROUP BY rep
    ORDER BY rep
"""),
)


# ==================================================================
# 21. Math functions: POWER, SQRT, LOG
# ==================================================================
show(
    "21. Math functions on amounts",
    engine.sql("""
    SELECT rep, amount,
           ROUND(SQRT(amount), 2) AS sqrt_amt,
           ROUND(LN(amount), 2) AS ln_amt,
           ROUND(POWER(amount / 1000.0, 2), 4) AS scaled_sq
    FROM sales
    WHERE returned = FALSE
    ORDER BY amount DESC
    LIMIT 5
"""),
)


# ==================================================================
# 22. Complex CTE: running rank with threshold
# ==================================================================
show(
    "22. CTE: top performers (above median)",
    engine.sql("""
    WITH rep_totals AS (
        SELECT rep, SUM(amount) AS total_revenue
        FROM sales
        WHERE returned = FALSE
        GROUP BY rep
    ),
    median_calc AS (
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_revenue) AS median_rev
        FROM rep_totals
    )
    SELECT rt.rep, rt.total_revenue
    FROM rep_totals rt, median_calc mc
    WHERE rt.total_revenue >= mc.median_rev
    ORDER BY rt.total_revenue DESC
"""),
)


# ==================================================================
# 23. UPSERT: INSERT ... ON CONFLICT DO UPDATE
# ==================================================================
engine.sql("""
    CREATE TABLE rep_quotas (
        rep TEXT PRIMARY KEY,
        quota INTEGER NOT NULL,
        achieved INTEGER DEFAULT 0
    )
""")
engine.sql("""INSERT INTO rep_quotas (rep, quota) VALUES
    ('Alice', 3000), ('Bob', 3500), ('Carol', 2500), ('Diana', 3000)
""")

# Update achieved from actual sales
engine.sql("""
    INSERT INTO rep_quotas (rep, quota, achieved)
    SELECT rep, 0, SUM(amount)
    FROM sales WHERE returned = FALSE GROUP BY rep
    ON CONFLICT (rep) DO UPDATE SET achieved = EXCLUDED.achieved
""")

show(
    "23. UPSERT: quota vs achieved",
    engine.sql("""
    SELECT rep, quota, achieved,
           CASE WHEN achieved >= quota THEN 'MET' ELSE 'MISS' END AS status
    FROM rep_quotas
    ORDER BY rep
"""),
)


# ==================================================================
# 24. DELETE ... RETURNING
# ==================================================================
show(
    "24. DELETE RETURNING: remove returned sales",
    engine.sql("""
    DELETE FROM sales
    WHERE returned = TRUE
    RETURNING id, rep, product, amount
"""),
)

show("    Remaining sales count", engine.sql("SELECT COUNT(*) AS remaining FROM sales"))


print("\n" + "=" * 70)
print("All analytics examples completed successfully.")
print("=" * 70)
