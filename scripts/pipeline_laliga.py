"""
PySpark pipeline – fetches La Liga data from SportsRC API,
transforms it, and writes a single JSON consumed by the frontend.

Usage (local):
    pip install pyspark requests
    python scripts/pipeline_laliga.py

GitHub Actions runs this on a 30-min cron.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

# ---------- PySpark ----------
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

BASE_URL = "https://api.sportsrc.org/"
OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "public", "data"
)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "la_liga_data.json")


# ── Fetch helpers ──────────────────────────────────────────────────
def fetch_standings():
    """La Liga table: 20 teams with stats."""
    r = requests.get(
        BASE_URL, params={"data": "results", "category": "tables", "league": "PD"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_matches():
    """Upcoming football matches (global – we filter La Liga client-side)."""
    r = requests.get(
        BASE_URL, params={"data": "matches", "category": "football"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_scores():
    """Live / finished scores."""
    r = requests.get(
        BASE_URL, params={"data": "results", "category": "scores", "league": "PD"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── PySpark transform ─────────────────────────────────────────────
def transform_with_spark(standings_raw, matches_raw, scores_raw):
    spark = SparkSession.builder.master("local[*]").appName("LaLiga").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    # --- Standings ---
    table, _ = _extract_table(standings_raw)
    if not table:
        spark.stop()
        return _transform_plain_inner(table, matches_raw, scores_raw)

    # Clean None values that break schema inference
    for row in table:
        if row.get("form") is None:
            row["form"] = ""

    from pyspark.sql.types import (
        StructType, StructField, IntegerType, StringType, LongType,
    )
    schema = StructType([
        StructField("position", IntegerType()),
        StructField("playedGames", IntegerType()),
        StructField("form", StringType()),
        StructField("won", IntegerType()),
        StructField("draw", IntegerType()),
        StructField("lost", IntegerType()),
        StructField("points", IntegerType()),
        StructField("goalsFor", IntegerType()),
        StructField("goalsAgainst", IntegerType()),
        StructField("goalDifference", IntegerType()),
        StructField("teamId", LongType()),
        StructField("teamName", StringType()),
        StructField("teamShortName", StringType()),
        StructField("teamCrest", StringType()),
    ])

    df = spark.createDataFrame(table, schema=schema)

    # The upstream `position` is a rank *with ties* — on matchday 1 twelve teams all
    # come back as position 6, which collapses the zone split and gives the frontend
    # duplicate row keys. Recompute a unique 1-20 rank on the league tiebreak
    # (points, goal difference, goals for; name last so the order is deterministic).
    from pyspark.sql.window import Window

    league_order = Window.orderBy(
        F.col("points").desc(),
        F.col("goalDifference").desc(),
        F.col("goalsFor").desc(),
        F.col("teamName").asc(),
    )
    df = df.withColumn("apiPosition", F.col("position"))
    df = df.withColumn("position", F.row_number().over(league_order))

    # Zone classification
    df = df.withColumn(
        "zone",
        F.when(F.col("position") <= 4, "champions")
        .when(F.col("position") <= 6, "europa")
        .when(F.col("position") >= 18, "relegation")
        .otherwise("mid"),
    )

    # Win / draw / loss rates.
    # On the opening matchday every team still sits at playedGames = 0, and Spark
    # under ANSI mode raises DIVIDE_BY_ZERO rather than returning null. Clamp the
    # divisor to 1 — won/draw/lost are 0 there too, so every rate lands on 0.0,
    # matching _transform_plain_inner.
    safe_played = F.when(F.col("playedGames") > 0, F.col("playedGames")).otherwise(F.lit(1))
    df = df.withColumn("winRate", F.round(F.col("won") / safe_played * 100, 1))
    df = df.withColumn("drawRate", F.round(F.col("draw") / safe_played * 100, 1))
    df = df.withColumn("lossRate", F.round(F.col("lost") / safe_played * 100, 1))

    standings_out = [row.asDict() for row in df.collect()]
    spark.stop()

    # --- Matches & scores (keep light – no Spark needed) ---
    matches_out = _filter_laliga_matches(matches_raw)
    scores_out = scores_raw

    return standings_out, matches_out, scores_out


# ── Plain-Python fallback ─────────────────────────────────────────
def _extract_table(standings_raw):
    """Navigate nested SportsRC response to the table list."""
    # Direct key
    if "table" in standings_raw and isinstance(standings_raw["table"], list):
        return standings_raw["table"], standings_raw
    # Nested: data -> standings[0] -> table
    data = standings_raw.get("data", standings_raw)
    season_info = data.get("season", {})
    standings_list = data.get("standings", [])
    if standings_list:
        table = standings_list[0].get("table", [])
        # Flatten team object into each row
        flat = []
        for row in table:
            entry = {k: v for k, v in row.items() if k != "team"}
            team = row.get("team", {})
            entry["teamId"] = team.get("id")
            entry["teamName"] = team.get("name", "")
            entry["teamShortName"] = team.get("shortName", entry["teamName"])
            entry["teamCrest"] = team.get("crest", "")
            flat.append(entry)
        return flat, {
            "season": season_info.get("startDate", "")[:4] if season_info else "",
            "matchday": season_info.get("currentMatchday", ""),
        }
    return [], standings_raw


def _league_sort_key(row):
    """La Liga tiebreak order, minus head-to-head (absent from this feed)."""
    return (
        -(row.get("points") or 0),
        -(row.get("goalDifference") or 0),
        -(row.get("goalsFor") or 0),
        row.get("teamName") or "",
    )


def _assign_ranks(table):
    """Replace the upstream tied `position` with a unique 1-N rank.

    Keeps the original value as `apiPosition`. Mirrors the Spark window in
    transform_with_spark — both paths must agree on the ordering.
    """
    ordered = sorted(table, key=_league_sort_key)
    for rank, row in enumerate(ordered, start=1):
        row["apiPosition"] = row.get("position")
        row["position"] = rank
    return ordered


def transform_plain(standings_raw, matches_raw, scores_raw):
    table, _ = _extract_table(standings_raw)
    return _transform_plain_inner(table, matches_raw, scores_raw)


def _transform_plain_inner(table, matches_raw, scores_raw):
    table = _assign_ranks(table)
    for t in table:
        pos = t.get("position", 0)
        if pos <= 4:
            t["zone"] = "champions"
        elif pos <= 6:
            t["zone"] = "europa"
        elif pos >= 18:
            t["zone"] = "relegation"
        else:
            t["zone"] = "mid"

        played = t.get("playedGames", 1) or 1
        t["winRate"] = round(t.get("won", 0) / played * 100, 1)
        t["drawRate"] = round(t.get("draw", 0) / played * 100, 1)
        t["lossRate"] = round(t.get("lost", 0) / played * 100, 1)

    matches_out = _filter_laliga_matches(matches_raw)
    return table, matches_out, scores_raw


def _filter_laliga_matches(matches_raw):
    """Best-effort filter for La Liga matches from the global feed."""
    la_liga_keywords = {"la liga", "laliga", "primera division", "pd"}
    out = []
    items = matches_raw if isinstance(matches_raw, list) else matches_raw.get("matches", [])
    for m in items:
        league = (m.get("league") or m.get("competition") or "").lower()
        if any(k in league for k in la_liga_keywords):
            out.append(m)
    # If nothing matched, return first 10 as generic upcoming
    return out if out else items[:10]


# ── Main ───────────────────────────────────────────────────────────
def main():
    print("[pipeline] Fetching SportsRC data …")
    standings_raw = fetch_standings()
    matches_raw = fetch_matches()
    scores_raw = fetch_scores()

    print("[pipeline] Transforming with PySpark …")
    standings, matches, scores = transform_with_spark(
        standings_raw, matches_raw, scores_raw
    )

    _, meta = _extract_table(standings_raw)
    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "season": meta.get("season", ""),
        "matchday": meta.get("matchday", ""),
        "standings": standings,
        "matches": matches,
        "scores": scores,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[pipeline] Written {OUTPUT_FILE}  ({len(standings)} teams)")


if __name__ == "__main__":
    main()
