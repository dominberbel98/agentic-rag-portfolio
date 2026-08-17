"""
Predictive model – La Liga end-of-season projections.

Uses:
  1. Linear pace projection (points/game * 38)
  2. Poisson-based Monte Carlo simulation (1 000 seasons)
  3. XGBoost multi-class classifier for zone probability
     (Champion / Champions League / Europa / Relegation)

Reads  : frontend/public/data/la_liga_data.json   (output of pipeline_laliga.py)
Writes : frontend/public/data/la_liga_predictions.json

Usage:
    pip install xgboost scikit-learn numpy
    python scripts/predict_laliga.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.laliga_transform import (  # noqa: E402
    SHRINKAGE_K,
    league_priors,
    shrink,
    zone_for_position,
)

try:
    import xgboost as xgb
    from sklearn.preprocessing import LabelEncoder

    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("[predict] xgboost not installed – using pace-only projections")

TOTAL_MATCHES = 38
N_SIMULATIONS = 1_000
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "data")
INPUT_FILE = os.path.join(DATA_DIR, "la_liga_data.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "la_liga_predictions.json")

np.random.seed(42)


def load_data():
    with open(INPUT_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── Feature engineering ─────────────────────────────────────────────
def engineer_features(teams):
    """Per-team feature vectors, with every rate shrunk toward the league prior.

    Without shrinkage this model was not a forecast. On matchday one of the
    2026-27 season it projected Espanyol and Alaves to 114 points with a combined
    100% title probability, and Real Madrid and Barcelona to zero points, purely
    because the first pair had played a match and the second pair had not.
    Multiplying a one-game sample by 38 is not a projection.

    Each rate is now blended toward the league average, weighted by matches
    played, so early in the season a team looks like an average team and only
    earns its own numbers as evidence accumulates. See laliga_transform.shrink.
    """
    priors = league_priors(teams)
    features = []
    for t in teams:
        played = t["playedGames"] or 0
        # Divisor for observed rates. `remaining` uses the true count: coercing
        # played to 1 before subtracting left 37 matches remaining at kickoff.
        divisor = played if played > 0 else 1
        observed = {
            "ppg": t["points"] / divisor,
            "winRate": t["won"] / divisor,
            "drawRate": t["draw"] / divisor,
            "lossRate": t["lost"] / divisor,
            "gfPerGame": t["goalsFor"] / divisor,
            "gaPerGame": t["goalsAgainst"] / divisor,
        }
        shrunk = {
            key: shrink(value, priors[key], played, SHRINKAGE_K)
            for key, value in observed.items()
        }
        features.append(
            {
                "teamName": t["teamName"],
                "teamShortName": t.get("teamShortName", t["teamName"]),
                "teamCrest": t.get("teamCrest", ""),
                "position": t["position"],
                "played": played,
                "remaining": TOTAL_MATCHES - played,
                "points": t["points"],
                "won": t["won"],
                "draw": t["draw"],
                "lost": t["lost"],
                "goalsFor": t["goalsFor"],
                "goalsAgainst": t["goalsAgainst"],
                "goalDifference": t["goalDifference"],
                # Shrunk rates drive the projection and the classifier.
                "ppg": shrunk["ppg"],
                "winRate": shrunk["winRate"],
                "drawRate": shrunk["drawRate"],
                "lossRate": shrunk["lossRate"],
                "gfPerGame": shrunk["gfPerGame"],
                "gaPerGame": shrunk["gaPerGame"],
                "gdPerGame": shrunk["gfPerGame"] - shrunk["gaPerGame"],
                # Raw rates kept for display, so the UI can show what actually
                # happened alongside what the model expects.
                "observed": observed,
            }
        )
    return features


# ── Monte Carlo simulation ──────────────────────────────────────────
def simulate_season(features):
    """
    Simulate remaining matches using Poisson-distributed goals.
    Returns per-team distributions of final points, GF, GA.
    """
    results = {f["teamName"]: {"points": [], "gf": [], "ga": []} for f in features}

    for _ in range(N_SIMULATIONS):
        for t in features:
            remaining = t["remaining"]
            if remaining <= 0:
                results[t["teamName"]]["points"].append(t["points"])
                results[t["teamName"]]["gf"].append(t["goalsFor"])
                results[t["teamName"]]["ga"].append(t["goalsAgainst"])
                continue

            sim_points = t["points"]
            sim_gf = t["goalsFor"]
            sim_ga = t["goalsAgainst"]

            lam_gf = max(t["gfPerGame"], 0.3)
            lam_ga = max(t["gaPerGame"], 0.3)

            for _ in range(remaining):
                gf = np.random.poisson(lam_gf)
                ga = np.random.poisson(lam_ga)
                if gf > ga:
                    sim_points += 3
                elif gf == ga:
                    sim_points += 1
                sim_gf += gf
                sim_ga += ga

            results[t["teamName"]]["points"].append(sim_points)
            results[t["teamName"]]["gf"].append(sim_gf)
            results[t["teamName"]]["ga"].append(sim_ga)

    return results


# ── XGBoost zone classifier ────────────────────────────────────────
def train_xgb_zone_model(features):
    """
    Train XGBoost to predict zone probabilities.
    Labels based on current position: 1-4=champion, 5-6=europa, 18-20=relegation, rest=mid.
    Even with 20 samples, it demonstrates the pipeline for the portfolio.
    """
    if not HAS_XGB:
        return None

    feature_cols = [
        "ppg", "winRate", "drawRate", "lossRate",
        "gfPerGame", "gaPerGame", "gdPerGame",
        "points", "goalDifference",
    ]

    X = np.array([[t[c] for c in feature_cols] for t in features])

    # Labels from current position
    # Shared zone definition, so the classifier knows about Conference League.
    labels = [zone_for_position(t["position"]) for t in features]

    le = LabelEncoder()
    y = le.fit_transform(labels)

    model = xgb.XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.3,
        objective="multi:softprob",
        num_class=len(le.classes_),
        eval_metric="mlogloss",
        use_label_encoder=False,
        verbosity=0,
    )
    model.fit(X, y)

    # Get probabilities
    probas = model.predict_proba(X)  # shape: (20, n_classes)

    zone_probas = {}
    for i, t in enumerate(features):
        zone_probas[t["teamName"]] = {
            cls: round(float(probas[i][j]) * 100, 1)
            for j, cls in enumerate(le.classes_)
        }

    # Feature importance
    importance = dict(zip(feature_cols, [round(float(v), 3) for v in model.feature_importances_]))

    return zone_probas, importance


# ── Build predictions JSON ──────────────────────────────────────────
def build_predictions(features, sim_results, xgb_results):
    predictions = []

    # Champion counts from simulation
    champion_counts = {}
    for sim_i in range(N_SIMULATIONS):
        max_pts = -1
        champion = None
        for t in features:
            pts = sim_results[t["teamName"]]["points"][sim_i]
            if pts > max_pts:
                max_pts = pts
                champion = t["teamName"]
        champion_counts[champion] = champion_counts.get(champion, 0) + 1

    # Most-goals / least-goals counts
    most_gf_counts = {}
    most_ga_counts = {}
    least_ga_counts = {}
    for sim_i in range(N_SIMULATIONS):
        max_gf, max_ga, min_ga_val = -1, -1, 999
        t_gf = t_ga = t_min_ga = None
        for t in features:
            gf = sim_results[t["teamName"]]["gf"][sim_i]
            ga = sim_results[t["teamName"]]["ga"][sim_i]
            if gf > max_gf:
                max_gf = gf
                t_gf = t["teamName"]
            if ga > max_ga:
                max_ga = ga
                t_ga = t["teamName"]
            if ga < min_ga_val:
                min_ga_val = ga
                t_min_ga = t["teamName"]
        most_gf_counts[t_gf] = most_gf_counts.get(t_gf, 0) + 1
        most_ga_counts[t_ga] = most_ga_counts.get(t_ga, 0) + 1
        least_ga_counts[t_min_ga] = least_ga_counts.get(t_min_ga, 0) + 1

    xgb_zone_probas, xgb_importance = xgb_results if xgb_results else ({}, {})

    for t in features:
        pts_arr = sim_results[t["teamName"]]["points"]
        gf_arr = sim_results[t["teamName"]]["gf"]
        ga_arr = sim_results[t["teamName"]]["ga"]

        zone_proba = xgb_zone_probas.get(t["teamName"], {})

        predictions.append(
            {
                "teamName": t["teamName"],
                "teamShortName": t["teamShortName"],
                "teamCrest": t["teamCrest"],
                "currentPosition": t["position"],
                "currentPoints": t["points"],
                "played": t["played"],
                "remaining": t["remaining"],
                # Pace projection
                "projectedPoints": round(t["ppg"] * TOTAL_MATCHES, 1),
                "projectedGF": round(t["gfPerGame"] * TOTAL_MATCHES, 1),
                "projectedGA": round(t["gaPerGame"] * TOTAL_MATCHES, 1),
                # Monte Carlo stats
                "mc": {
                    "pointsMean": round(float(np.mean(pts_arr)), 1),
                    "pointsStd": round(float(np.std(pts_arr)), 1),
                    "pointsMin": int(np.min(pts_arr)),
                    "pointsMax": int(np.max(pts_arr)),
                    "pointsP10": int(np.percentile(pts_arr, 10)),
                    "pointsP90": int(np.percentile(pts_arr, 90)),
                    "gfMean": round(float(np.mean(gf_arr)), 1),
                    "gaMean": round(float(np.mean(ga_arr)), 1),
                },
                # Probabilities
                "championProb": round(
                    champion_counts.get(t["teamName"], 0) / N_SIMULATIONS * 100, 1
                ),
                "mostGoalsProb": round(
                    most_gf_counts.get(t["teamName"], 0) / N_SIMULATIONS * 100, 1
                ),
                "mostConcededProb": round(
                    most_ga_counts.get(t["teamName"], 0) / N_SIMULATIONS * 100, 1
                ),
                "leastConcededProb": round(
                    least_ga_counts.get(t["teamName"], 0) / N_SIMULATIONS * 100, 1
                ),
                # XGBoost zone probabilities
                "xgbZone": zone_proba,
            }
        )

    # Sort by projected points desc
    predictions.sort(key=lambda x: x["mc"]["pointsMean"], reverse=True)

    return predictions, xgb_importance


def main():
    print("[predict] Loading standings data …")
    raw = load_data()
    standings = raw.get("standings", [])
    if not standings:
        print("[predict] ERROR: No standings data found")
        sys.exit(1)

    print(f"[predict] Engineering features for {len(standings)} teams …")
    features = engineer_features(standings)

    print(f"[predict] Running Monte Carlo simulation ({N_SIMULATIONS} seasons) …")
    sim_results = simulate_season(features)

    xgb_results = None
    if HAS_XGB:
        print("[predict] Training XGBoost zone classifier …")
        xgb_results = train_xgb_zone_model(features)

    print("[predict] Building predictions …")
    predictions, xgb_importance = build_predictions(features, sim_results, xgb_results)

    # Carried through so the UI can gate the projection honestly instead of
    # presenting an opening-weekend extrapolation as a forecast.
    state = raw.get("state") or {}
    max_played = max((f["played"] for f in features), default=0)

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "season": raw.get("season", ""),
        "matchday": raw.get("matchday", ""),
        "totalMatches": TOTAL_MATCHES,
        "nSimulations": N_SIMULATIONS,
        "shrinkageK": SHRINKAGE_K,
        "maxGamesPlayed": max_played,
        "lowConfidence": bool(state.get("lowConfidence", max_played < 5)),
        "model": "XGBoost + Monte Carlo Poisson" if HAS_XGB else "Monte Carlo Poisson",
        "xgbFeatureImportance": xgb_importance,
        "predictions": predictions,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Quick summary
    top = predictions[0]
    print(f"[predict] Champion favourite: {top['teamShortName']} ({top['championProb']}%)")
    print(f"[predict] Written {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
