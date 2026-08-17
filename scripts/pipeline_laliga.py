"""PySpark pipeline — fetches La Liga data, transforms it, and writes the single
JSON the frontend consumes.

    python scripts/pipeline_laliga.py             # fetch, transform, write
    python scripts/pipeline_laliga.py --dry-run   # fetch and report, write nothing
    python scripts/pipeline_laliga.py --verify    # assert the written file is sane

GitHub Actions runs this on a 30-minute cron.

Spark handles the standings aggregation, which is the part worth demonstrating.
The pure transforms live in `laliga_transform.py` so the season boundaries are
testable without a JVM — both faults that took this down for two days were
arithmetic on a calendar edge.

Note on match history: the upstream scores endpoint exposes only a rolling window
of recent matches, so no single run can see enough to compute a five-match form
string. This script therefore reads its own previous output and folds new results
into it. The committed JSON is the store.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.laliga_transform import (  # noqa: E402
    add_rates,
    assign_ranks,
    build_team_aliases,
    derive_form,
    extract_fixtures,
    extract_results,
    merge_results,
    season_state,
    zone_for_position,
)

BASE_URL = "https://api.sportsrc.org/"
OUTPUT_DIR = ROOT_DIR / "frontend" / "public" / "data"
OUTPUT_FILE = OUTPUT_DIR / "la_liga_data.json"
TIMEOUT = 30


# ── Fetch ───────────────────────────────────────────────────────────────────


def _get(params: dict) -> dict:
    response = requests.get(BASE_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def fetch_standings() -> dict:
    return _get({"data": "results", "category": "tables", "league": "PD"})


def fetch_scores() -> dict:
    """Finished and live La Liga matches — the source for results and form."""
    return _get({"data": "results", "category": "scores", "league": "PD"})


def fetch_upcoming() -> dict:
    """Global football fixtures. Filtered to La Liga by team name, because this
    feed carries no league field."""
    return _get({"data": "matches", "category": "football"})


# ── Standings extraction ────────────────────────────────────────────────────


def extract_table(standings_raw: dict) -> tuple[list[dict], dict]:
    """Navigate the nested response to a flat table plus season metadata."""
    if isinstance(standings_raw.get("table"), list):
        return standings_raw["table"], {}

    data = standings_raw.get("data", standings_raw)
    season = data.get("season") or {}
    standings = data.get("standings") or []
    if not standings:
        return [], {}

    flat: list[dict] = []
    for row in standings[0].get("table", []):
        entry = {k: v for k, v in row.items() if k != "team"}
        team = row.get("team") or {}
        entry["teamId"] = team.get("id")
        entry["teamName"] = team.get("name", "")
        entry["teamShortName"] = team.get("shortName") or entry["teamName"]
        entry["teamCrest"] = team.get("crest", "")
        flat.append(entry)

    meta = {
        "season": (season.get("startDate") or "")[:4],
        "matchday": season.get("currentMatchday", ""),
        "seasonStart": season.get("startDate"),
        "seasonEnd": season.get("endDate"),
    }
    return flat, meta


# ── Spark transform ─────────────────────────────────────────────────────────


def transform_with_spark(table: list[dict]) -> list[dict]:
    """Rank, classify and rate the standings in Spark.

    The rank is recomputed rather than trusted: upstream returns a rank with ties
    (twelve teams shared position 6 on the opening matchday), which collapsed the
    zone split and gave the frontend duplicate row keys.
    """
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
    )
    from pyspark.sql.window import Window

    spark = SparkSession.builder.master("local[*]").appName("LaLiga").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    try:
        for row in table:
            if row.get("form") is None:
                row["form"] = ""

        schema = StructType(
            [
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
            ]
        )
        df = spark.createDataFrame(table, schema=schema)

        league_order = Window.orderBy(
            F.col("points").desc(),
            F.col("goalDifference").desc(),
            F.col("goalsFor").desc(),
            F.col("teamName").asc(),
        )
        df = df.withColumn("apiPosition", F.col("position"))
        df = df.withColumn("position", F.row_number().over(league_order))

        # Zone boundaries come from laliga_transform so the pipeline, the model
        # and the frontend cannot drift apart — that drift is how the Conference
        # League zone stayed missing.
        zone = F.when(F.col("position") <= 4, "champions")
        zone = zone.when(F.col("position") <= 6, "europa")
        zone = zone.when(F.col("position") <= 7, "conference")
        zone = zone.when(F.col("position") >= 18, "relegation")
        df = df.withColumn("zone", zone.otherwise("mid"))

        # Clamp the divisor: on the opening matchday every team is on zero games,
        # and Spark under ANSI mode raises DIVIDE_BY_ZERO rather than returning
        # null. The numerators are zero there too, so every rate lands on 0.0.
        safe_played = F.when(F.col("playedGames") > 0, F.col("playedGames")).otherwise(F.lit(1))
        for name, source in (("winRate", "won"), ("drawRate", "draw"), ("lossRate", "lost")):
            df = df.withColumn(name, F.round(F.col(source) / safe_played * 100, 1))

        return [row.asDict() for row in df.collect()]
    finally:
        spark.stop()


def transform_plain(table: list[dict]) -> list[dict]:
    """Pure-Python equivalent of the Spark path. Must agree with it exactly."""
    ranked = assign_ranks(table)
    for row in ranked:
        row["zone"] = zone_for_position(row["position"])
    return add_rates(ranked)


# ── Assemble ────────────────────────────────────────────────────────────────


def load_previous(path: Path) -> dict:
    """Previous output, for accumulating match history. Missing is not an error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build_payload(
    standings_raw: dict,
    scores_raw: dict,
    upcoming_raw: dict,
    previous: dict,
    use_spark: bool = True,
) -> dict:
    table, meta = extract_table(standings_raw)
    if not table:
        raise SystemExit("error: upstream returned no standings")

    standings = transform_with_spark(table) if use_spark else transform_plain(table)
    standings.sort(key=lambda row: row["position"])

    results = merge_results(previous.get("results") or [], extract_results(scores_raw))
    derive_form(standings, results)

    aliases = build_team_aliases(standings)
    fixtures = extract_fixtures(upcoming_raw, aliases)

    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "season": meta.get("season", ""),
        "matchday": meta.get("matchday", ""),
        "seasonStart": meta.get("seasonStart"),
        "seasonEnd": meta.get("seasonEnd"),
        "state": season_state(standings, meta.get("matchday")),
        "standings": standings,
        "results": results,
        "fixtures": fixtures,
    }


# ── Verification ────────────────────────────────────────────────────────────


def verify(payload: dict) -> list[str]:
    """Assertions that must hold before this is published.

    The workflow used to commit and deploy whatever the transform produced, so a
    wrong-but-not-raising result reached the site. It published a finished
    season's final table as the current standings for several days.
    """
    problems: list[str] = []
    standings = payload.get("standings") or []

    if len(standings) != 20:
        problems.append(f"expected 20 teams, got {len(standings)}")

    positions = sorted(row.get("position") for row in standings)
    if positions != list(range(1, len(standings) + 1)):
        problems.append(f"positions are not a unique 1-N rank: {positions}")

    for row in standings:
        for key in ("winRate", "drawRate", "lossRate"):
            value = row.get(key)
            if value is None or not 0.0 <= value <= 100.0:
                problems.append(f"{row.get('teamShortName')}.{key} = {value!r}")
        played = row.get("playedGames")
        if played is None or not 0 <= played <= 38:
            problems.append(f"{row.get('teamShortName')}.playedGames = {played!r}")
        if row.get("zone") not in {"champions", "europa", "conference", "mid", "relegation"}:
            problems.append(f"{row.get('teamShortName')}.zone = {row.get('zone')!r}")

    state = payload.get("state") or {}
    if state.get("phase") not in {"preseason", "in_progress", "finished"}:
        problems.append(f"state.phase = {state.get('phase')!r}")

    return problems


# ── Main ────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="do not write the output file")
    parser.add_argument("--no-spark", action="store_true", help="use the plain-Python transform")
    parser.add_argument("--verify", action="store_true", help="verify the existing output and exit")
    args = parser.parse_args(argv)

    if args.verify:
        problems = verify(load_previous(OUTPUT_FILE))
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("verification failed" if problems else "verification passed")
        return 1 if problems else 0

    print("[pipeline] fetching …")
    standings_raw = fetch_standings()
    scores_raw = fetch_scores()
    upcoming_raw = fetch_upcoming()

    print(f"[pipeline] transforming ({'PySpark' if not args.no_spark else 'plain Python'}) …")
    payload = build_payload(
        standings_raw,
        scores_raw,
        upcoming_raw,
        load_previous(OUTPUT_FILE),
        use_spark=not args.no_spark,
    )

    problems = verify(payload)
    if problems:
        print("[pipeline] refusing to publish — output failed verification:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    state = payload["state"]
    print(
        f"[pipeline] season {payload['season']} matchday {payload['matchday']} "
        f"({state['phase']}, {state['matchesPlayed']} matches played)"
    )
    print(
        f"[pipeline] {len(payload['standings'])} teams, "
        f"{len(payload['results'])} results in history, "
        f"{len(payload['fixtures'])} upcoming fixtures"
    )

    if args.dry_run:
        print("[pipeline] dry run — nothing written")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, OUTPUT_FILE)
    print(f"[pipeline] wrote {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
