"""
auto_labeler.py — Unsupervised K-Means Labeling
-------------------------------------------------
Loads raw_github_data.csv, drops non-numeric/metadata columns,
applies K-Means (k=3), and maps clusters to quality labels
('Beginner', 'Intermediate', 'Production Ready') based on
the cluster centroids' feature intensity.

Saves the final labeled dataset to labeled_github_data.csv.

Usage:
    python auto_labeler.py
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler, StandardScaler

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from feature_config import FEATURE_ORDER  # canonical feature list


# ── Config ────────────────────────────────────────────────────────────────
INPUT_FILE  = "raw_github_data.csv"
OUTPUT_FILE = "labeled_github_data.csv"
N_CLUSTERS  = 3
RANDOM_SEED = 42

# Weight applied to the composite practice-score dimension (see preprocess())
# after standard-scaling, before K-Means. Weighting the four individual
# practice booleans separately was tried and was too unstable: has_readme is
# 98.7% true (near-constant, so up-weighting it just isolates a tiny outlier
# cluster), and boosting has_docker/has_cicd independently let them pull in
# different directions — large, CI-tested-but-Dockerless projects (e.g.
# language toolchains) ended up ranked inconsistently against smaller
# Dockerized ones, producing non-monotonic clusters (e.g. "Intermediate"
# with fewer stars than "Beginner"). A single composite score of "how many
# core practices does this repo follow" is a more robust clustering axis
# than four separately-weighted, mutually-correlated booleans.
PRACTICE_WEIGHT = 1.6

# Metadata columns to keep for the final CSV but NOT feed into clustering
METADATA_COLS = ["owner", "name", "full_name", "html_url", "language"]


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from '{path}'")
    print(f"Columns: {df.columns.tolist()}\n")
    return df


def preprocess(df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """
    1. Keep only the canonical FEATURE_ORDER columns.
    2. Fill any NaNs with 0 (safety net for partial API failures).
    3. Log-transform skewed numeric features (stars, forks, etc.).
    4. Collapse the four core practice booleans into one composite
       practice_score (0-4) — a single coherent "engineering maturity" axis,
       instead of four separately-weighted, mutually-correlated booleans
       that can pull K-Means in conflicting directions (see PRACTICE_WEIGHT
       comment above for what went wrong when they were weighted directly).
    5. Standard-scale everything, then up-weight practice_score so K-Means
       can't bury it under the popularity signal.
    Returns (scaled_array, feature_df).
    """
    # Validate that all expected features exist
    missing = [f for f in FEATURE_ORDER if f not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}. Re-run collect_data.py.")

    feat_df = df[FEATURE_ORDER].copy().fillna(0)

    # Log-transform right-skewed numeric columns
    skewed_cols = ["stars", "forks", "open_issues", "size_kb",
                   "repo_age_days", "days_since_last_update"]
    for col in skewed_cols:
        feat_df[f"{col}_log"] = np.log1p(feat_df[col])

    # Composite "how many core practices does this repo follow" (0-4).
    # has_wiki/has_pages are deliberately excluded — they're community
    # extras, not engineering practices (same grouping used elsewhere in
    # the app, e.g. suggestions only ever mention readme/tests/cicd/docker).
    feat_df["practice_score"] = (
        feat_df["has_readme"] + feat_df["has_tests"]
        + feat_df["has_cicd"] + feat_df["has_docker"]
    )

    # Build the final column list for clustering: log-transformed skewed
    # cols + community-extra booleans + the composite practice score.
    log_cols = [f"{c}_log" for c in skewed_cols]
    cluster_cols = log_cols + ["has_wiki", "has_pages", "practice_score"]

    scaler = StandardScaler()
    scaled = scaler.fit_transform(feat_df[cluster_cols])

    weights = np.array([PRACTICE_WEIGHT if col == "practice_score" else 1.0 for col in cluster_cols])
    scaled = scaled * weights

    return scaled, feat_df


def run_kmeans(scaled: np.ndarray) -> np.ndarray:
    print(f"Running K-Means (k={N_CLUSTERS}, seed={RANDOM_SEED})...")
    km = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_SEED, n_init=15)
    labels = km.fit_predict(scaled)
    print(f"Cluster sizes: {dict(zip(*np.unique(labels, return_counts=True)))}\n")
    return labels


def map_clusters_to_labels(df: pd.DataFrame, cluster_col: str = "cluster") -> dict:
    """
    Score each cluster by the mean of its normalised features.
    Higher score → 'Production Ready', mid → 'Intermediate', lowest → 'Beginner'.
    This is ML-driven, not hand-crafted rules.
    """
    # Features that reflect repository maturity
    scoring_features = ["stars", "forks", "has_readme",
                        "has_docker", "has_cicd", "has_tests",
                        "repo_age_days"]

    cluster_means = df.groupby(cluster_col)[scoring_features].mean()

    # Normalise to 0-1 so all features contribute equally to the score
    scaler = MinMaxScaler()
    normalised = scaler.fit_transform(cluster_means)
    scores = normalised.sum(axis=1)  # higher sum → more mature cluster

    sorted_clusters = np.argsort(scores)   # ascending
    label_map = {
        int(sorted_clusters[0]): "Beginner",
        int(sorted_clusters[1]): "Intermediate",
        int(sorted_clusters[2]): "Production Ready",
    }

    print("Cluster -> Label mapping (based on feature intensity):")
    for cluster_id, label in sorted(label_map.items()):
        print(f"  Cluster {cluster_id}: {label}  (score={scores[cluster_id]:.3f})")

    return label_map


def compute_quality_score(row: pd.Series) -> int:
    """
    Bootstrap heuristic 0-100 score, used ONLY here to sanity-check clusters
    before a model exists. 50 pts for engineering best practices, 50 pts for
    community popularity. The live app (backend/main.py) does NOT use this
    heuristic — it derives quality_score from the trained model's own
    predict_proba output (see LABEL_MATURITY in backend/main.py) so the score
    and the predicted label are always consistent with each other.
    """
    import math
    practice = (
        row["has_readme"] * 10 +
        row["has_tests"]  * 15 +
        row["has_cicd"]   * 15 +
        row["has_docker"] * 10
    )
    popularity = (
        (math.log1p(row["stars"]) / 9.2) * 25 +
        (math.log1p(row["forks"])  / 7.0) * 25
    )
    return min(int(practice + popularity), 100)


def build_suggestions(row: pd.Series) -> str:
    suggestions = []
    if not row["has_readme"]: suggestions.append("Add a README file")
    if not row["has_tests"]:  suggestions.append("Add unit/integration tests")
    if not row["has_cicd"]:   suggestions.append("Set up CI/CD workflows")
    if not row["has_docker"]: suggestions.append("Add Docker support")
    return ", ".join(suggestions) if suggestions else "Great job! Keep it up."


def main():
    # 1. Load
    df = load_data(INPUT_FILE)

    # 2. Preprocess
    scaled, feat_df = preprocess(df)

    # 3. Cluster
    df["cluster"] = run_kmeans(scaled)

    # 4. Map clusters → labels
    label_map = map_clusters_to_labels(df)
    df["quality_label"] = df["cluster"].map(label_map)

    # 5. Quality score & suggestions
    df["quality_score"] = df.apply(compute_quality_score, axis=1)
    df["improvement_suggestions"] = df.apply(build_suggestions, axis=1)

    # 6. Save — keep metadata cols + model features + labels
    keep = METADATA_COLS + FEATURE_ORDER + \
           ["quality_label", "quality_score", "improvement_suggestions"]
    # Only keep columns that actually exist in df
    keep = [c for c in keep if c in df.columns]
    out_df = df[keep]

    out_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[DONE] Labeled dataset saved to '{OUTPUT_FILE}'")

    print("\nLabel distribution:")
    print(df["quality_label"].value_counts().to_string())

    print("\nMean features per label:")
    print(df.groupby("quality_label")[FEATURE_ORDER].mean().round(2).to_string())


if __name__ == "__main__":
    main()
