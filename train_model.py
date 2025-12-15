"""
train_model.py — Random Forest Training Pipeline
--------------------------------------------------
Loads labeled_github_data.csv, trains a RandomForestClassifier on the
canonical feature set defined in feature_config.py, evaluates it, and
saves the final model as github_quality_rf_model.pkl.

Place the resulting .pkl inside backend/ so FastAPI can load it.

Usage:
    python train_model.py
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from feature_config import FEATURE_ORDER  # canonical feature list — same as inference

# ── Config ────────────────────────────────────────────────────────────────
INPUT_FILE  = "labeled_github_data.csv"
OUTPUT_FILE = "github_quality_rf_model.pkl"

# RandomForest hyper-parameters
RF_PARAMS = {
    "n_estimators":      300,    # more trees → better generalisation
    "max_depth":         None,   # let trees grow fully (RF handles overfitting via bagging)
    "min_samples_split": 5,
    "min_samples_leaf":  2,
    "class_weight":      "balanced",  # handles class imbalance automatically
    "random_state":      42,
    "n_jobs":            -1,     # use all CPU cores
}

TEST_SIZE   = 0.20
RANDOM_SEED = 42
CV_FOLDS    = 5


def load_data(path: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load CSV and return (X, y) with only canonical features."""
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from '{path}'")

    # Validate columns
    missing = [f for f in FEATURE_ORDER if f not in df.columns]
    if missing:
        raise ValueError(
            f"Missing feature columns: {missing}\n"
            "Run collect_data.py → auto_labeler.py first."
        )
    if "quality_label" not in df.columns:
        raise ValueError("'quality_label' column not found. Run auto_labeler.py first.")

    X = df[FEATURE_ORDER].fillna(0)
    y = df["quality_label"]

    print(f"\nFeatures used ({len(FEATURE_ORDER)}): {FEATURE_ORDER}")
    print(f"\nLabel distribution:\n{y.value_counts().to_string()}\n")
    return X, y


def train_and_evaluate(X: pd.DataFrame, y: pd.Series):
    """
    1. Stratified 80/20 train-test split.
    2. Fit RandomForestClassifier.
    3. Evaluate on hold-out test set.
    4. 5-fold Cross-Validation for a more robust accuracy estimate.
    """
    # ── Split ─────────────────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y,  # preserve label proportions in both sets
    )
    print(f"Train size: {len(X_train)}  |  Test size: {len(X_test)}\n")

    # ── Train ─────────────────────────────────────────────────────────────
    print("Training Random Forest...")
    model = RandomForestClassifier(**RF_PARAMS)
    model.fit(X_train, y_train)

    # ── Evaluate on hold-out ──────────────────────────────────────────────
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print("=" * 55)
    print(f"  Hold-out Test Accuracy : {acc * 100:.2f}%")
    print("=" * 55)

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    print("Confusion Matrix (rows=actual, cols=predicted):")
    labels = sorted(y.unique())
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    cm_df = pd.DataFrame(cm, index=labels, columns=labels)
    print(cm_df.to_string())

    # ── Cross-Validation ──────────────────────────────────────────────────
    print(f"\nRunning {CV_FOLDS}-Fold Stratified Cross-Validation...")
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy", n_jobs=-1)
    print(f"  CV Accuracy: {cv_scores.mean() * 100:.2f}% ± {cv_scores.std() * 100:.2f}%")
    print(f"  Per-fold:    {[f'{s*100:.1f}%' for s in cv_scores]}")

    # ── Feature importance ────────────────────────────────────────────────
    importance_df = pd.DataFrame({
        "feature":   FEATURE_ORDER,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    print("\nTop Feature Importances:")
    print(importance_df.to_string(index=False))

    return model


def save_model(model, path: str):
    joblib.dump(model, path)
    print(f"\n[DONE] Model saved to '{path}'")
    print(f"   -> Copy this file to backend/ so FastAPI can load it.")


def main():
    # 1. Load labeled data
    X, y = load_data(INPUT_FILE)

    # 2. Train + evaluate
    model = train_and_evaluate(X, y)

    # 3. Retrain on FULL dataset before saving (maximise training data)
    print("\nRetraining on the full dataset before saving...")
    final_model = RandomForestClassifier(**RF_PARAMS)
    final_model.fit(X, y)
    print("  Done.")

    # 4. Save
    save_model(final_model, OUTPUT_FILE)


if __name__ == "__main__":
    main()
