"""
Product Recommendation Engine (portfolio export)
================================================
Content-Based recommender with TF-IDF + categorical + numerical features
plus Maximal Marginal Relevance (MMR) re-ranking for diversity.

Pipeline:
    1. Curated synthetic catalog (32 products, 4 categories, rich tags)
    2. Feature engineering:
         - TF-IDF (1-2 grams) on description+tags
         - One-hot category
         - MinMax-scaled price + rating
    3. Cosine similarity user-item scoring
    4. MMR re-ranking (λ trade-off relevance/diversity)
    5. Persona evaluations (coverage, intra-list diversity, novelty)
    6. JSON export with the full feature matrix so the same
       cosine-similarity computation runs in the browser.

Reads  : nothing
Writes : frontend/public/data/product_recommendations.json

Usage:
    python scripts/recommendation_engine.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder


# ---------------------------------------------------------------------------
# 1. Catalog
# ---------------------------------------------------------------------------

CATALOG = [
    # electronics
    {"id": 1,  "name": "Pro Laptop 15\"",          "category": "electronics", "price": 1299, "rating": 4.7, "icon": "laptop_mac",
     "description": "high performance laptop professional productivity portable computing developer workstation"},
    {"id": 2,  "name": "Wireless Headphones",      "category": "electronics", "price": 249,  "rating": 4.5, "icon": "headphones",
     "description": "premium noise canceling headphones wireless audio bluetooth lifestyle music travel"},
    {"id": 3,  "name": "Smart Watch",              "category": "electronics", "price": 399,  "rating": 4.6, "icon": "watch",
     "description": "smartwatch fitness health tracking tech lifestyle wearable notifications heart-rate"},
    {"id": 4,  "name": "Tablet 11\"",              "category": "electronics", "price": 699,  "rating": 4.4, "icon": "tablet_mac",
     "description": "tablet portable productivity tech touchscreen lightweight reading drawing stylus"},
    {"id": 5,  "name": "Mirrorless Camera",        "category": "electronics", "price": 899,  "rating": 4.8, "icon": "photo_camera",
     "description": "professional mirrorless camera creative photography lifestyle tech video 4k"},
    {"id": 6,  "name": "Mechanical Keyboard",      "category": "electronics", "price": 149,  "rating": 4.6, "icon": "keyboard",
     "description": "mechanical keyboard tactile productivity typing tech desktop programming gamer"},
    {"id": 7,  "name": "Studio Monitors",          "category": "electronics", "price": 329,  "rating": 4.7, "icon": "speaker",
     "description": "studio monitor speakers audio creative music production lifestyle premium"},
    {"id": 8,  "name": "Curved 4K Monitor",        "category": "electronics", "price": 549,  "rating": 4.5, "icon": "monitor",
     "description": "curved 4k monitor productivity tech desktop developer workstation gaming"},

    # books
    {"id": 9,  "name": "Python Data Science",      "category": "books",       "price": 45,   "rating": 4.8, "icon": "menu_book",
     "description": "python programming data science learning tutorial analytics pandas numpy"},
    {"id": 10, "name": "Machine Learning",         "category": "books",       "price": 55,   "rating": 4.7, "icon": "menu_book",
     "description": "machine learning algorithms ai tech learning hands-on scikit sklearn"},
    {"id": 11, "name": "Data Science Handbook",    "category": "books",       "price": 60,   "rating": 4.6, "icon": "menu_book",
     "description": "data science reference learning analytics productivity tech statistics"},
    {"id": 12, "name": "Clean Code",               "category": "books",       "price": 40,   "rating": 4.9, "icon": "menu_book",
     "description": "clean code software programming best practices productivity learning craftsmanship"},
    {"id": 13, "name": "Deep Learning",            "category": "books",       "price": 65,   "rating": 4.8, "icon": "menu_book",
     "description": "deep learning neural networks ai tech learning advanced pytorch tensorflow"},
    {"id": 14, "name": "Business Analytics",       "category": "books",       "price": 55,   "rating": 4.4, "icon": "menu_book",
     "description": "business analytics data strategy learning professional kpis dashboards"},
    {"id": 15, "name": "Designing Data Systems",   "category": "books",       "price": 58,   "rating": 4.9, "icon": "menu_book",
     "description": "data engineering distributed systems learning architecture tech database scalable"},
    {"id": 16, "name": "Pragmatic Programmer",     "category": "books",       "price": 38,   "rating": 4.8, "icon": "menu_book",
     "description": "software programming productivity craftsmanship best practices learning developer"},

    # sports
    {"id": 17, "name": "Running Shoes Pro",        "category": "sports",      "price": 180,  "rating": 4.7, "icon": "directions_run",
     "description": "running shoes fitness outdoor performance lifestyle sports cushion lightweight"},
    {"id": 18, "name": "Yoga Mat Premium",         "category": "sports",      "price": 65,   "rating": 4.6, "icon": "self_improvement",
     "description": "yoga mat fitness wellness lifestyle non-slip premium meditation pilates"},
    {"id": 19, "name": "Resistance Bands Set",     "category": "sports",      "price": 35,   "rating": 4.5, "icon": "fitness_center",
     "description": "resistance bands fitness training strength home gym workout"},
    {"id": 20, "name": "Whey Protein 2kg",         "category": "sports",      "price": 55,   "rating": 4.6, "icon": "nutrition",
     "description": "whey protein fitness nutrition wellness supplement muscle recovery"},
    {"id": 21, "name": "Smart Fitness Tracker",    "category": "sports",      "price": 120,  "rating": 4.5, "icon": "watch_check",
     "description": "fitness tracker wearable tech health lifestyle sports steps sleep"},
    {"id": 22, "name": "Insulated Water Bottle",   "category": "sports",      "price": 40,   "rating": 4.8, "icon": "water_drop",
     "description": "water bottle fitness outdoor lifestyle hydration sports stainless"},
    {"id": 23, "name": "Adjustable Dumbbells",     "category": "sports",      "price": 299,  "rating": 4.7, "icon": "exercise",
     "description": "adjustable dumbbells fitness strength gym home weights workout"},
    {"id": 24, "name": "Trail Running Backpack",   "category": "sports",      "price": 89,   "rating": 4.6, "icon": "backpack",
     "description": "running backpack outdoor sports lifestyle hydration trail hiking lightweight"},

    # home
    {"id": 25, "name": "Espresso Machine",         "category": "home",        "price": 299,  "rating": 4.7, "icon": "coffee_maker",
     "description": "espresso machine coffee home lifestyle wellness kitchen barista"},
    {"id": 26, "name": "Air Purifier",             "category": "home",        "price": 199,  "rating": 4.6, "icon": "air",
     "description": "air purifier home wellness lifestyle hepa filtration allergy quiet"},
    {"id": 27, "name": "LED Desk Lamp",            "category": "home",        "price": 79,   "rating": 4.5, "icon": "lightbulb",
     "description": "desk lamp led home productivity lifestyle workspace eye-care"},
    {"id": 28, "name": "High-Speed Blender",       "category": "home",        "price": 149,  "rating": 4.7, "icon": "blender",
     "description": "blender home nutrition lifestyle kitchen smoothie wellness powerful"},
    {"id": 29, "name": "Wireless Charger",         "category": "home",        "price": 45,   "rating": 4.4, "icon": "battery_charging_full",
     "description": "wireless charger home tech lifestyle charging pad qi"},
    {"id": 30, "name": "Standing Desk Converter",  "category": "home",        "price": 189,  "rating": 4.5, "icon": "desk",
     "description": "standing desk home productivity wellness ergonomic workspace adjustable"},
    {"id": 31, "name": "Aromatherapy Diffuser",    "category": "home",        "price": 49,   "rating": 4.6, "icon": "humidity_indoor",
     "description": "diffuser home wellness lifestyle aromatherapy essential oils relaxation"},
    {"id": 32, "name": "Robot Vacuum",             "category": "home",        "price": 379,  "rating": 4.5, "icon": "smart_outlet",
     "description": "robot vacuum home tech lifestyle automation cleaning lidar productivity"},
]


# ---------------------------------------------------------------------------
# 2. Personas (used for evaluation only)
# ---------------------------------------------------------------------------

PERSONAS = {
    "Tech Enthusiast":   [1, 2, 6, 8, 3],
    "Data Scientist":    [9, 10, 11, 13, 15],
    "Fitness Fan":       [17, 18, 19, 20, 21],
    "Home Professional": [25, 27, 26, 30, 28],
}


# ---------------------------------------------------------------------------
# 3. Recommender
# ---------------------------------------------------------------------------

class ContentBasedRecommender:
    def __init__(self, max_features: int = 120, top_n: int = 6, mmr_lambda: float = 0.7):
        self.top_n = top_n
        self.mmr_lambda = mmr_lambda
        self.tfidf = TfidfVectorizer(max_features=max_features, ngram_range=(1, 2),
                                     stop_words="english")
        self.scaler = MinMaxScaler()
        self.encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")

        self.products: pd.DataFrame | None = None
        self.feature_matrix: np.ndarray | None = None
        self.feature_breakdown: dict | None = None
        self.tfidf_vocab: list[str] | None = None

    def fit(self, products: pd.DataFrame) -> "ContentBasedRecommender":
        self.products = products.reset_index(drop=True)
        tfidf_feats = self.tfidf.fit_transform(self.products["description"]).toarray()
        cat_feats = self.encoder.fit_transform(self.products[["category"]])
        num_feats = self.scaler.fit_transform(self.products[["price", "rating"]])

        # Soft-weight numeric/category vs text so they don't drown the TF-IDF signal
        cat_feats = cat_feats * 0.6
        num_feats = num_feats * 0.4

        self.feature_matrix = np.hstack([tfidf_feats, cat_feats, num_feats]).astype(np.float32)
        self.tfidf_vocab = self.tfidf.get_feature_names_out().tolist()
        self.feature_breakdown = {
            "tfidf_dims": int(tfidf_feats.shape[1]),
            "category_dims": int(cat_feats.shape[1]),
            "numerical_dims": int(num_feats.shape[1]),
        }
        return self

    # ------- core ops -------

    def _user_profile(self, item_ids: list[int]) -> np.ndarray:
        idx = self.products.index[self.products["id"].isin(item_ids)].tolist()
        if not idx:
            raise ValueError(f"No items found in catalog for: {item_ids}")
        return self.feature_matrix[idx].mean(axis=0, keepdims=True)

    def recommend(self, history: list[int], use_mmr: bool = True) -> pd.DataFrame:
        user_vec = self._user_profile(history)
        sims = cosine_similarity(user_vec, self.feature_matrix)[0]
        seen = set(history)

        candidates = [(i, sims[i]) for i in range(len(self.products))
                      if int(self.products.iloc[i]["id"]) not in seen]

        if use_mmr:
            picked = self._mmr(candidates, k=self.top_n)
        else:
            candidates.sort(key=lambda t: t[1], reverse=True)
            picked = candidates[: self.top_n]

        rows = []
        for rank, (i, score) in enumerate(picked):
            row = self.products.iloc[i].to_dict()
            row["similarity"] = round(float(score), 4)
            row["rank"] = rank + 1
            rows.append(row)
        return pd.DataFrame(rows)

    def _mmr(self, candidates: list[tuple[int, float]], k: int) -> list[tuple[int, float]]:
        """Maximal Marginal Relevance — relevance vs diversity trade-off."""
        if not candidates:
            return []
        candidates = sorted(candidates, key=lambda t: t[1], reverse=True)
        selected: list[tuple[int, float]] = []
        remaining = candidates.copy()

        # always start with the most relevant
        selected.append(remaining.pop(0))

        while remaining and len(selected) < k:
            best_idx, best_score = -1, -np.inf
            for j, (idx, rel) in enumerate(remaining):
                max_div = max(
                    cosine_similarity(
                        self.feature_matrix[idx:idx + 1],
                        self.feature_matrix[s[0]:s[0] + 1],
                    )[0, 0]
                    for s in selected
                )
                mmr = self.mmr_lambda * rel - (1 - self.mmr_lambda) * max_div
                if mmr > best_score:
                    best_score, best_idx = mmr, j
            selected.append(remaining.pop(best_idx))
        return selected


# ---------------------------------------------------------------------------
# 4. Evaluation
# ---------------------------------------------------------------------------

def intra_list_diversity(rec_indices: list[int], feature_matrix: np.ndarray) -> float:
    if len(rec_indices) < 2:
        return 0.0
    sub = feature_matrix[rec_indices]
    sim = cosine_similarity(sub)
    n = len(rec_indices)
    return float(1 - sim[np.triu_indices(n, k=1)].mean())


def catalog_coverage(all_recs: list[list[int]], catalog_size: int) -> float:
    return len({i for recs in all_recs for i in recs}) / catalog_size


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    out_path = os.path.join(repo_root, "frontend", "public", "data", "product_recommendations.json")

    print("=" * 60)
    print("  Product Recommendation Engine (export)")
    print("=" * 60)

    products = pd.DataFrame(CATALOG)
    rec = ContentBasedRecommender(max_features=120, top_n=6, mmr_lambda=0.7).fit(products)
    print(f"  Catalog: {len(products)} products / {products['category'].nunique()} categories")
    print(f"  Feature matrix: {rec.feature_matrix.shape}  ({rec.feature_breakdown})")

    persona_results = []
    all_rec_idx = []
    for persona, history in PERSONAS.items():
        df_recs = rec.recommend(history, use_mmr=True)
        rec_idx = products.index[products["id"].isin(df_recs["id"])].tolist()
        diversity = intra_list_diversity(rec_idx, rec.feature_matrix)
        all_rec_idx.append(rec_idx)
        persona_results.append({
            "persona": persona,
            "history": history,
            "recommendations": [
                {
                    "id": int(r["id"]),
                    "name": r["name"],
                    "category": r["category"],
                    "price": float(r["price"]),
                    "rating": float(r["rating"]),
                    "icon": r["icon"],
                    "similarity": float(r["similarity"]),
                    "rank": int(r["rank"]),
                }
                for _, r in df_recs.iterrows()
            ],
            "diversity": round(diversity, 4),
        })
        print(f"  · {persona:<20} diversity={diversity:.3f}")

    coverage = catalog_coverage(all_rec_idx, len(products))
    print(f"  Catalog coverage (across personas): {coverage:.1%}")

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalog": [
            {
                "id": int(row["id"]),
                "name": row["name"],
                "category": row["category"],
                "price": float(row["price"]),
                "rating": float(row["rating"]),
                "icon": row["icon"],
                "description": row["description"],
            }
            for _, row in products.iterrows()
        ],
        "categories": sorted(products["category"].unique().tolist()),
        "featureBreakdown": rec.feature_breakdown,
        "featureMatrix": rec.feature_matrix.round(5).tolist(),
        "tfidfVocab": rec.tfidf_vocab,
        "personas": persona_results,
        "metrics": {
            "catalogCoverage": round(coverage, 4),
            "avgDiversity": round(float(np.mean([p["diversity"] for p in persona_results])), 4),
            "topN": rec.top_n,
            "mmrLambda": rec.mmr_lambda,
        },
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    kb = os.path.getsize(out_path) / 1024
    print(f"\n  Wrote {out_path} ({kb:.1f} KB)")


if __name__ == "__main__":
    main()
