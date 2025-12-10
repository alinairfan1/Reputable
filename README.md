# Reputable - GitHub Repo Quality Predictor

Paste any public GitHub URL and get back an ML-driven quality assessment:
a `Beginner` / `Intermediate` / `Production Ready` label, a 0-100 score,
a per-repo SHAP explanation of *why* the model predicted what it did, and
concrete suggestions for improvement. Results are cached in Postgres
(via Supabase) and re-used for 24h.

## Architecture

```
collect_data.py ──► raw_github_data.csv ──► auto_labeler.py (K-Means) ──► labeled_github_data.csv
                                                                                  │
                                                                          train_model.py
                                                                                  │
                                                                     github_quality_rf_model.pkl
                                                                                  │
                          ┌───────────────────────────────────────────────────────┘
                          ▼
                  backend/main.py (FastAPI)
                  ├─ /analyze   → predicts label + score + SHAP explanation
                  ├─ /badge     → embeddable SVG badge
                  ├─ /history   → recent analyses (Supabase)
                  └─ /stats     → aggregate stats (Supabase)
                          │
                          ▼
                  frontend/ (React + Vite + Tailwind)
```

`feature_config.py` is the single source of truth for feature extraction —
both `collect_data.py` (training) and `backend/main.py` (live inference)
import from it, so training and serving can never drift apart.

## How the model works

1. **Collection** — `collect_data.py` pulls ~1000 public repos via PyGithub
   across Python/JS/TS.
2. **Labeling** — since there's no ground-truth "quality" label, `auto_labeler.py`
   runs K-Means (k=3) on normalized repo features and maps the resulting
   clusters to `Beginner` / `Intermediate` / `Production Ready` by cluster
   maturity score. This is a semi-supervised bootstrap, not hand-labeled data.
   The four core practice flags (`has_readme`, `has_tests`, `has_cicd`,
   `has_docker`) are collapsed into one composite `practice_score` (0-4)
   before clustering and up-weighted (`PRACTICE_WEIGHT` in `auto_labeler.py`)
   — without this, K-Means naturally clusters almost entirely on popularity
   (stars/forks) and CI/CD presence, leaving `has_tests`/`has_docker` with
   <1% influence on the final labels even though they're well-balanced,
   informative features on their own. Weighting the four flags individually
   was tried first and was unstable (a near-constant flag like `has_readme`,
   98.7% true, gets isolated into a tiny outlier cluster instead of forming
   a gradient; weighting `has_docker` without `has_cicd` let them pull in
   conflicting directions). A single composite axis is more robust.
3. **Training** — `train_model.py` fits a `RandomForestClassifier` on the
   K-Means labels.
4. **Serving** — `backend/main.py` loads the trained model and, for each
   request, derives the 0-100 `quality_score` directly from the model's own
   `predict_proba` output (weighted by class maturity) — so the score and
   the label can never disagree — and computes a SHAP `TreeExplainer`
   explanation of the top features driving that specific prediction.

**Current holdout performance** (from the last `train_model.py` run,
80/20 stratified split, 5-fold CV): **96.0% test accuracy**, **96.4% ± 1.0%
CV accuracy**. Top features by importance: `has_tests` (23.6%), `forks`
(21.1%), `stars` (17.9%), `open_issues` (10.7%), `has_docker` (8.6%),
`has_cicd` (7.5%) — practice signals now carry real, non-trivial weight
instead of being drowned out by popularity alone. Re-run
`python auto_labeler.py && python train_model.py` to reproduce (and copy
the resulting `.pkl` to `backend/`).

## Project layout

- `feature_config.py` — canonical feature extraction (shared by training & serving)
- `collect_data.py`, `auto_labeler.py`, `train_model.py` — offline ML pipeline
- `backend/` — FastAPI service (`main.py`) + tests live under `tests/` at repo root
- `frontend/` — React/Vite/Tailwind UI
- `tests/` — pytest suite for `feature_config.py` and `backend/main.py`, hermetic (no live GitHub/Supabase calls)

## Running locally

```bash
# Backend
pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env   # fill in GITHUB_TOKEN, SUPABASE_URL, SUPABASE_KEY
uvicorn main:app --reload --app-dir backend

# Frontend
cd frontend
npm install
cp .env.example .env                   # fill in VITE_API_URL, VITE_SUPABASE_* 
npm run dev
```

Or via Docker:

```bash
docker compose up --build
```

(`docker-compose.yml` needs `backend/.env` to exist locally — same as above.)

## Testing

```bash
pip install -r backend/requirements-dev.txt
pytest tests/ -v
```

Tests mock GitHub/Supabase so they run without any credentials or network
access — see `tests/fakes.py`.

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR: backend pytest suite,
frontend lint + build, and a Docker build validation for both images.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for deploying the backend (Render) and
frontend (Vercel).

## Embeddable badge

Once deployed, drop this in any repo's README:

```md
![repo quality](https://your-backend-url/badge/OWNER/REPO)
```
