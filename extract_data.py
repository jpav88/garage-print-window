#!/usr/bin/env python3
"""Extract a portable garage-readings snapshot from the ruuvi SQLite DB.

Pivots the tall `readings` table (ts, device, metric, value) into wide rows of
minute-bucketed (ts, temp_f, humidity) for the garage tag, and writes a CSV the
Shiny app / Quarto report can read anywhere (no live DB needed to deploy).

Usage: python3 extract_data.py [path/to/ruuvi.db]
"""
import csv
import os
import sqlite3
import sys

DEFAULT_DB = os.path.expanduser("~/Programming-pavdog/ruuvi/data/ruuvi.db")
OUT = os.path.join(os.path.dirname(__file__), "data", "garage_readings.csv")

QUERY = """
WITH t AS (
    SELECT strftime('%Y-%m-%d %H:%M', ts, 'localtime') AS m, AVG(value) AS temp_f
    FROM readings WHERE metric = 'garage_temp_f' GROUP BY m
),
h AS (
    SELECT strftime('%Y-%m-%d %H:%M', ts, 'localtime') AS m, AVG(value) AS humidity
    FROM readings WHERE metric = 'garage_humidity' GROUP BY m
)
SELECT t.m AS ts, ROUND(t.temp_f, 2) AS temp_f, ROUND(h.humidity, 2) AS humidity
FROM t JOIN h ON t.m = h.m
ORDER BY t.m;
"""


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    con = sqlite3.connect(db)
    rows = con.execute(QUERY).fetchall()
    con.close()
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "temp_f", "humidity"])
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")
    if rows:
        print(f"Range: {rows[0][0]} -> {rows[-1][0]}")


if __name__ == "__main__":
    main()
