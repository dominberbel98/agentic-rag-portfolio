"""
Banking Credit Scoring Pipeline (portfolio export)
==================================================
Improved binary credit-risk classification pipeline.

Pipeline:
    1. Synthetic credit dataset (5 000 applicants, ~15% default rate)
    2. Feature engineering (numerical + categorical, derived ratios)
    3. Two models:
         - Logistic Regression (interpretable, exportable to JS)
         - Gradient Boosting Classifier (best AUC reference)
    4. Stratified 5-fold cross-validation + held-out test set
    5. Sigmoid calibration of GBM probabilities
    6. Metrics: AUC, KS, Avg Precision, F1, Precision@k, Recall, Brier
    7. Permutation feature importance
    8. PDO scorecard (300-850)
    9. JSON export for in-browser interactive demo:
         - LR coefficients + scaler params + OHE levels (full client inference)
         - Pre-computed metrics, ROC curve, score histogram, sample applicants

Reads  : nothing (synthetic data)
Writes : frontend/public/data/credit_scoring.json

Usage:
    python scripts/credit_scoring_pipeline.py
"""

from __future__ import annotations

import json
import os
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(42)
np.random.seed(42)


# ---------------------------------------------------------------------------
# 1. Synthetic dataset
# ---------------------------------------------------------------------------

NUMERICAL_FEATURES = [
    "age", "annual_income", "employment_years", "loan_amount",
    "payment_history_pct", "credit_utilization", "credit_age_years",
    "num_credit_accounts", "recent_inquiries", "derogatory_marks",
    "debt_to_income", "loan_to_income",
]
CATEGORICAL_FEATURES = ["loan_purpose", "home_ownership"]
TARGET = "default"

LOAN_PURPOSES = ["personal", "auto", "mortgage", "education", "business"]
HOME_OWNERSHIPS = ["rent", "own", "mortgage"]


def generate_credit_dataset(n: int = 5000) -> pd.DataFrame:
    """Realistic synthetic credit dataset with ~15% default rate."""
    age = RNG.integers(21, 70, n)
    annual_income = RNG.lognormal(mean=10.8, sigma=0.6, size=n).clip(15_000, 300_000)
    employment_years = RNG.exponential(scale=6, size=n).clip(0, 40).astype(int)
    loan_amount = RNG.lognormal(mean=9.5, sigma=0.7, size=n).clip(1_000, 100_000)

    payment_history_pct = RNG.beta(a=8, b=2, size=n) * 100
    credit_utilization = RNG.beta(a=2, b=4, size=n) * 100
    credit_age_years = RNG.exponential(scale=7, size=n).clip(0, 35)
    num_credit_accounts = RNG.poisson(lam=4, size=n).clip(1, 15)
    recent_inquiries = RNG.poisson(lam=2, size=n).clip(0, 10)
    derogatory_marks = RNG.poisson(lam=0.3, size=n).clip(0, 5)

    debt_to_income = (loan_amount * 0.05) / (annual_income / 12)
    loan_to_income = loan_amount / annual_income

    loan_purpose = RNG.choice(LOAN_PURPOSES, n, p=[0.30, 0.25, 0.20, 0.15, 0.10])
    home_ownership = RNG.choice(HOME_OWNERSHIPS, n, p=[0.40, 0.25, 0.35])

    log_odds = (
        0.4
        + (-0.04) * payment_history_pct
        +   0.025 * credit_utilization
        + (-0.07) * credit_age_years
        +   0.18  * recent_inquiries
        +   0.55  * derogatory_marks
        +   1.20  * debt_to_income
        + (-0.012) * (annual_income / 10_000)
        + (-0.03) * employment_years
        + np.where(home_ownership == "own", -0.30, 0.0)
        + np.where(loan_purpose == "business", 0.25, 0.0)
    )
    prob = 1 / (1 + np.exp(-log_odds))
    default = (RNG.random(n) < prob).astype(int)

    return pd.DataFrame({
        "age": age,
        "annual_income": annual_income.astype(int),
        "employment_years": employment_years,
        "loan_amount": loan_amount.astype(int),
        "payment_history_pct": payment_history_pct.round(2),
        "credit_utilization": credit_utilization.round(2),
        "credit_age_years": credit_age_years.round(1),
        "num_credit_accounts": num_credit_accounts,
        "recent_inquiries": recent_inquiries,
        "derogatory_marks": derogatory_marks,
        "debt_to_income": debt_to_income.round(3),
        "loan_to_income": loan_to_income.round(3),
        "loan_purpose": loan_purpose,
        "home_ownership": home_ownership,
        TARGET: default,
    })


# ---------------------------------------------------------------------------
# 2. Pipelines
# ---------------------------------------------------------------------------

def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(transformers=[
        ("num", StandardScaler(), NUMERICAL_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
    ])


def build_logistic() -> Pipeline:
    return Pipeline([
        ("preprocessor", build_preprocessor()),
        ("classifier", LogisticRegression(
            C=0.5, max_iter=2000, class_weight="balanced",
            solver="lbfgs", random_state=42,
        )),
    ])


def build_gbm() -> Pipeline:
    base = Pipeline([
        ("preprocessor", build_preprocessor()),
        ("classifier", GradientBoostingClassifier(
            n_estimators=300, learning_rate=0.04, max_depth=4,
            subsample=0.8, min_samples_leaf=20, random_state=42,
        )),
    ])
    return base


# ---------------------------------------------------------------------------
# 3. Metrics
# ---------------------------------------------------------------------------

def ks_statistic(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    return float(np.max(tpr - fpr))


def gini(auc: float) -> float:
    return 2 * auc - 1


def cv_metrics(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series) -> dict:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    auc_scores = cross_val_score(pipeline, X, y, cv=cv, scoring="roc_auc", n_jobs=-1)
    ap_scores  = cross_val_score(pipeline, X, y, cv=cv, scoring="average_precision", n_jobs=-1)
    f1_scores  = cross_val_score(pipeline, X, y, cv=cv, scoring="f1", n_jobs=-1)
    return {
        "auc_mean": float(auc_scores.mean()), "auc_std": float(auc_scores.std()),
        "ap_mean":  float(ap_scores.mean()),  "ap_std":  float(ap_scores.std()),
        "f1_mean":  float(f1_scores.mean()),  "f1_std":  float(f1_scores.std()),
    }


def test_metrics(pipeline: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    probs = pipeline.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)
    auc = roc_auc_score(y_test, probs)
    return {
        "auc": float(auc),
        "gini": float(gini(auc)),
        "ks": ks_statistic(y_test.values, probs),
        "average_precision": float(average_precision_score(y_test, probs)),
        "f1": float(f1_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds)),
        "brier": float(brier_score_loss(y_test, probs)),
    }


def roc_curve_points(pipeline: Pipeline, X_test: pd.DataFrame, y_test: pd.Series, n: int = 60) -> list:
    probs = pipeline.predict_proba(X_test)[:, 1]
    fpr, tpr, _ = roc_curve(y_test.values, probs)
    if len(fpr) > n:
        idx = np.linspace(0, len(fpr) - 1, n).astype(int)
        fpr, tpr = fpr[idx], tpr[idx]
    return [{"fpr": round(float(a), 4), "tpr": round(float(b), 4)} for a, b in zip(fpr, tpr)]


def pr_curve_points(pipeline: Pipeline, X_test: pd.DataFrame, y_test: pd.Series, n: int = 60) -> list:
    probs = pipeline.predict_proba(X_test)[:, 1]
    precision, recall, _ = precision_recall_curve(y_test.values, probs)
    if len(precision) > n:
        idx = np.linspace(0, len(precision) - 1, n).astype(int)
        precision, recall = precision[idx], recall[idx]
    return [{"precision": round(float(p), 4), "recall": round(float(r), 4)} for p, r in zip(precision, recall)]


# ---------------------------------------------------------------------------
# 4. Scorecard
# ---------------------------------------------------------------------------

def population_odds(default_rate: float) -> float:
    """Good:bad odds of the portfolio the scorecard is being built for."""
    return (1.0 - default_rate) / max(default_rate, 1e-9)


def prob_to_score(prob_default: np.ndarray, base_odds: float, pdo: int = 50,
                  base_score: int = 600) -> np.ndarray:
    """Map a default probability onto the 300-850 scale.

    `base_odds` is the anchor: it declares what odds the base score means, and it
    has to be the odds of the population being scored. It used to be hardcoded at
    50.0, which asserts that 600 points is a 1.96% chance of default — while this
    portfolio defaults at 17%, odds of roughly 4.8:1. Every applicant therefore
    landed about 168 points below where they belonged, and the scorecard reported
    4,995 of 5,000 as Poor with nobody at all reaching Good. A scale on which the
    entire population occupies the bottom band ranks correctly and communicates
    nothing, which is the opposite of what a scorecard is for.

    Anchoring on the real rate puts the average applicant at the base score and
    spreads the rest around it, so a band finally carries meaning.
    """
    factor = pdo / np.log(2)
    offset = base_score - factor * np.log(base_odds)
    odds = (1 - prob_default) / np.maximum(prob_default, 1e-9)
    score = offset + factor * np.log(odds)
    return np.clip(score, 300, 850).round().astype(int)


def score_band(score: int) -> str:
    if score < 580: return "Poor"
    if score < 670: return "Fair"
    if score < 740: return "Good"
    if score < 800: return "Very Good"
    return "Exceptional"


# ---------------------------------------------------------------------------
# 5. Browser-friendly LR export
# ---------------------------------------------------------------------------

def export_logistic_for_browser(pipeline: Pipeline) -> dict:
    """
    Extract scaler stats, OHE levels, LR coefficients & intercept so that
    the same prediction can be reproduced in the browser as a pure dot
    product + sigmoid.
    """
    pre: ColumnTransformer = pipeline.named_steps["preprocessor"]
    clf: LogisticRegression = pipeline.named_steps["classifier"]

    scaler: StandardScaler = pre.named_transformers_["num"]
    encoder: OneHotEncoder = pre.named_transformers_["cat"]

    # Coefficients are already aligned with the transformer column order:
    #   [num_features..., cat_ohe_columns...]
    coefs = clf.coef_[0].tolist()
    intercept = float(clf.intercept_[0])

    n_num = len(NUMERICAL_FEATURES)
    num_coefs = coefs[:n_num]
    cat_coefs = coefs[n_num:]

    # Map OHE columns back to (feature, level)
    ohe_columns = []
    cur = 0
    for feat, levels in zip(CATEGORICAL_FEATURES, encoder.categories_):
        for lvl in levels:
            ohe_columns.append({"feature": feat, "level": str(lvl), "coef": float(cat_coefs[cur])})
            cur += 1

    return {
        "intercept": intercept,
        "numerical": [
            {
                "feature": f,
                "coef": float(num_coefs[i]),
                "mean": float(scaler.mean_[i]),
                "std":  float(scaler.scale_[i]),
            }
            for i, f in enumerate(NUMERICAL_FEATURES)
        ],
        "categorical": ohe_columns,
        "categorical_features": CATEGORICAL_FEATURES,
        "categorical_levels": {
            f: [str(x) for x in levels]
            for f, levels in zip(CATEGORICAL_FEATURES, encoder.categories_)
        },
    }


# ---------------------------------------------------------------------------
# 6. Permutation importance (model-agnostic, on raw features)
# ---------------------------------------------------------------------------

def feature_importance_table(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series) -> list:
    result = permutation_importance(
        pipeline, X, y, n_repeats=8, scoring="roc_auc",
        random_state=42, n_jobs=-1,
    )
    rows = []
    for f, mean, std in zip(
        NUMERICAL_FEATURES + CATEGORICAL_FEATURES,
        result.importances_mean,
        result.importances_std,
    ):
        rows.append({
            "feature": f,
            "importance": round(float(mean), 5),
            "std": round(float(std), 5),
        })
    rows.sort(key=lambda r: r["importance"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 7. Score distribution helpers
# ---------------------------------------------------------------------------

def score_histogram(scores: np.ndarray, n_bins: int = 22) -> list:
    edges = np.linspace(300, 850, n_bins + 1)
    counts, _ = np.histogram(scores, bins=edges)
    return [
        {
            "bin": int(round((edges[i] + edges[i + 1]) / 2)),
            "from": int(round(edges[i])),
            "to": int(round(edges[i + 1])),
            "count": int(counts[i]),
        }
        for i in range(n_bins)
    ]


def band_distribution(scores: np.ndarray) -> list:
    bands = ["Poor", "Fair", "Good", "Very Good", "Exceptional"]
    counts = {b: 0 for b in bands}
    for s in scores:
        counts[score_band(int(s))] += 1
    return [{"band": b, "count": counts[b]} for b in bands]


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    out_path = os.path.join(repo_root, "frontend", "public", "data", "credit_scoring.json")

    print("=" * 60)
    print("  Banking Credit Scoring Pipeline (export)")
    print("=" * 60)

    df = generate_credit_dataset(n=5000)
    X = df.drop(columns=[TARGET])
    y = df[TARGET]
    print(f"  Dataset:       {len(df):,} applicants")
    print(f"  Default rate:  {y.mean():.1%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=42,
    )

    # --- Logistic Regression (used for browser inference) ---
    lr = build_logistic()
    lr_cv = cv_metrics(lr, X_train, y_train)
    lr.fit(X_train, y_train)
    lr_test = test_metrics(lr, X_test, y_test)
    lr_export = export_logistic_for_browser(lr)
    print(f"  LR  AUC (CV):  {lr_cv['auc_mean']:.4f} ± {lr_cv['auc_std']:.4f}")
    print(f"  LR  AUC (test): {lr_test['auc']:.4f}  KS: {lr_test['ks']:.4f}")

    # --- Gradient Boosting (calibrated) ---
    gbm = build_gbm()
    gbm_cv = cv_metrics(gbm, X_train, y_train)
    cal_gbm = CalibratedClassifierCV(gbm, method="sigmoid", cv=3)
    cal_gbm.fit(X_train, y_train)
    gbm_test = test_metrics(cal_gbm, X_test, y_test)
    print(f"  GBM AUC (CV):  {gbm_cv['auc_mean']:.4f} ± {gbm_cv['auc_std']:.4f}")
    print(f"  GBM AUC (test, calibrated): {gbm_test['auc']:.4f}  KS: {gbm_test['ks']:.4f}")

    # --- ROC / PR curves on the GBM (best model) ---
    roc = roc_curve_points(cal_gbm, X_test, y_test)
    pr  = pr_curve_points(cal_gbm, X_test, y_test)

    # --- Permutation importance (GBM) ---
    gbm.fit(X_train, y_train)
    importance = feature_importance_table(gbm, X_test, y_test)
    print("  Top features:")
    for row in importance[:5]:
        print(f"    {row['feature']:<22} {row['importance']:.4f}")

    # --- Score distribution (using GBM probabilities on full dataset) ---
    # The anchor comes from the portfolio's own default rate, so the base score
    # describes the average applicant rather than an arbitrary 50:1.
    base_odds = population_odds(float(y.mean()))
    full_probs = cal_gbm.predict_proba(X)[:, 1]
    scores = prob_to_score(full_probs, base_odds)
    histogram = score_histogram(scores)
    bands = band_distribution(scores)

    # --- Sample applicants (real rows, scored by both models) ---
    sample = X_test.sample(8, random_state=7).copy()
    s_probs_lr  = lr.predict_proba(sample)[:, 1]
    s_probs_gbm = cal_gbm.predict_proba(sample)[:, 1]
    s_scores    = prob_to_score(s_probs_gbm, base_odds)
    sample_records = []
    for (_, row), p_lr, p_gbm, sc in zip(sample.iterrows(), s_probs_lr, s_probs_gbm, s_scores):
        rec = {k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v)
               for k, v in row.items()}
        rec["prob_default_lr"] = round(float(p_lr), 4)
        rec["prob_default_gbm"] = round(float(p_gbm), 4)
        rec["score"] = int(sc)
        rec["band"] = score_band(int(sc))
        sample_records.append(rec)

    # --- Build payload ---
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "n": int(len(df)),
            "defaultRate": round(float(y.mean()), 4),
            "trainSize": int(len(X_train)),
            "testSize": int(len(X_test)),
            "numericalFeatures": NUMERICAL_FEATURES,
            "categoricalFeatures": CATEGORICAL_FEATURES,
        },
        "models": {
            "logistic": {
                "name": "Logistic Regression",
                "cv": lr_cv,
                "test": lr_test,
                "weights": lr_export,
            },
            "gbm": {
                "name": "Gradient Boosting (sigmoid-calibrated)",
                "cv": gbm_cv,
                "test": gbm_test,
            },
        },
        "rocCurve": roc,
        "prCurve":  pr,
        "featureImportance": importance,
        "scoreHistogram": histogram,
        "bandDistribution": bands,
        "sampleApplicants": sample_records,
        # Exported so the browser scores with the same anchor. It used to be
        # hardcoded in both places, which is how they could disagree.
        "scorecard": {"pdo": 50, "baseScore": 600, "baseOdds": round(base_odds, 4),
                      "minScore": 300, "maxScore": 850},
        "thresholds": {"poor": 580, "fair": 670, "good": 740, "veryGood": 800},
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    kb = os.path.getsize(out_path) / 1024
    print(f"\n  Wrote {out_path} ({kb:.1f} KB)")


if __name__ == "__main__":
    main()
