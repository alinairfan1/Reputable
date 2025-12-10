"""
main.py — Reputable (GitHub Repo Quality Predictor) API
--------------------------------------------
FastAPI backend that loads a trained RandomForest .pkl model and
exposes a POST /analyze endpoint.

ANTI Train-Serving Skew: feature extraction logic is imported from
feature_config.py — the same module used during data collection and
model training. Never duplicate the extraction logic here.

Supabase: All analysis results are persisted to PostgreSQL via Supabase.
Caching: Same repo analyzed within 24h returns cached DB result instantly.
"""
import os
import re
import joblib
import shap
import pandas as pd
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from github import Github, Auth, GithubException
from github.GithubException import UnknownObjectException
from supabase import create_client, Client

# ── SINGLE SOURCE OF TRUTH: import feature config from the shared module ──
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from feature_config import FEATURE_ORDER, extract_features_from_pygithub

# ── Startup ───────────────────────────────────────────────────────────────
# Load .env from THIS file's directory (backend/) explicitly
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path, override=True)
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN")
SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")
print(f"[ENV] SUPABASE_URL = {SUPABASE_URL}")

# ── Load ML Model ─────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), "github_quality_rf_model.pkl")
model = None
explainer = None
try:
    model = joblib.load(MODEL_PATH)
    print(f"[SUCCESS] Model loaded from '{MODEL_PATH}'")
    print(f"   Classes: {list(model.classes_)}")
    explainer = shap.TreeExplainer(model)
    print("[SUCCESS] SHAP TreeExplainer ready")
except FileNotFoundError:
    print(f"[WARNING]  '{MODEL_PATH}' not found.")
except Exception as e:
    print(f"[WARNING] SHAP explainer init failed: {e}")

# ── Supabase Client ───────────────────────────────────────────────────────
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[SUCCESS] Supabase connected: {SUPABASE_URL}")
    except Exception as e:
        print(f"[WARNING] Supabase connection failed: {e}")
else:
    print("[WARNING] SUPABASE_URL / SUPABASE_KEY not set — DB persistence disabled.")

# ── App setup ─────────────────────────────────────────────────────────────
app = FastAPI(title="Reputable — GitHub Repo Quality Predictor", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request schema ────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    url: str


# ── Helpers ───────────────────────────────────────────────────────────────
def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from any GitHub URL."""
    pattern = r"github\.com/([^/]+)/([^/?\s#]+)"
    match = re.search(pattern, url.strip().rstrip("/"))
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub URL. Expected: https://github.com/owner/repo",
        )
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    return owner, repo


# Maturity weight for each class label, used to turn the model's own
# predict_proba output into a single 0-100 score. Keeps the score and the
# label prediction as two views of the SAME model output instead of two
# independently-computed numbers that can disagree.
LABEL_MATURITY = {
    "Beginner":         0,
    "Intermediate":     50,
    "Production Ready": 100,
}


def compute_quality_score(probabilities: dict) -> int:
    """Blend class probabilities into a single 0-100 score via LABEL_MATURITY."""
    weighted = sum(
        (prob / 100) * LABEL_MATURITY.get(label, 50)
        for label, prob in probabilities.items()
    )
    return round(weighted)


def build_suggestions(features: dict) -> list[str]:
    suggestions = []
    if not features["has_readme"]: suggestions.append("Add a README file to explain your project")
    if not features["has_tests"]:  suggestions.append("Add unit/integration tests (pytest, Jest, etc.)")
    if not features["has_cicd"]:   suggestions.append("Set up CI/CD pipelines via GitHub Actions / Travis CI")
    if not features["has_docker"]: suggestions.append("Containerise your app with a Dockerfile or docker-compose")
    if not suggestions:
        suggestions.append("Excellent work! Keep documentation and tests up to date as the project grows.")
    return suggestions


def build_explanation(input_df: pd.DataFrame, predicted_class: str, top_n: int = 5) -> list[dict]:
    """
    Explain WHY the model predicted `predicted_class` for this repo, using
    SHAP TreeExplainer contributions for that specific class. Returns the
    top_n features ranked by |impact|, each signed: positive pushes the
    prediction toward predicted_class, negative pushes away from it.
    """
    if explainer is None:
        return []

    class_idx = list(model.classes_).index(predicted_class)
    shap_values = explainer.shap_values(input_df)  # shape: (1, n_features, n_classes)
    contributions = shap_values[0, :, class_idx]

    rows = [
        {
            "feature": feature,
            "value": input_df.iloc[0][feature].item(),
            "impact": round(float(contribution), 4),
        }
        for feature, contribution in zip(FEATURE_ORDER, contributions)
    ]
    rows.sort(key=lambda r: abs(r["impact"]), reverse=True)
    return rows[:top_n]


def build_explanation_from_row(row: dict) -> list[dict]:
    """
    Recompute the SHAP explanation for a cached DB row. `days_since_last_update`
    isn't persisted to the DB, so it defaults to 0 here — safe, since it's by
    far the least important feature in the trained model (importance ~0.00003,
    see README), so this has negligible effect on the result.
    """
    if explainer is None:
        return []

    features = {
        "stars":                  row.get("stars", 0),
        "forks":                  row.get("forks", 0),
        "open_issues":            row.get("open_issues", 0),
        "size_kb":                row.get("size_kb", 0),
        "has_wiki":               int(row.get("has_wiki", False)),
        "has_pages":              int(row.get("has_pages", False)),
        "has_readme":             int(row.get("has_readme", False)),
        "has_docker":             int(row.get("has_docker", False)),
        "has_cicd":               int(row.get("has_cicd", False)),
        "has_tests":              int(row.get("has_tests", False)),
        "repo_age_days":          row.get("repo_age_days", 0),
        "days_since_last_update": 0,
    }
    input_df = pd.DataFrame([features])[FEATURE_ORDER]
    return build_explanation(input_df, row["label"])


def format_analysis_row(row: dict) -> dict:
    """Convert a Supabase DB row back into the API response format."""
    return {
        "label":         row["label"],
        "quality_score": row["quality_score"],
        "probabilities": {
            "Beginner":          float(row.get("prob_beginner", 0)),
            "Intermediate":      float(row.get("prob_intermediate", 0)),
            "Production Ready":  float(row.get("prob_production_ready", 0)),
        },
        "features": {
            "stars":       row.get("stars", 0),
            "forks":       row.get("forks", 0),
            "open_issues": row.get("open_issues", 0),
            "size_kb":     row.get("size_kb", 0),
            "has_readme":  int(row.get("has_readme", False)),
            "has_tests":   int(row.get("has_tests", False)),
            "has_cicd":    int(row.get("has_cicd", False)),
            "has_docker":  int(row.get("has_docker", False)),
            "has_wiki":    int(row.get("has_wiki", False)),
            "has_pages":   int(row.get("has_pages", False)),
        },
        "suggestions": row.get("suggestions", []),
        "explanation": build_explanation_from_row(row),
        "repo_meta": {
            "name":        row["repo_full_name"].split("/")[-1],
            "full_name":   row["repo_full_name"],
            "description": row.get("repo_description", ""),
            "language":    row.get("repo_language", "Unknown"),
            "url":         row["repo_url"],
            "avatar_url":  row.get("avatar_url", ""),
        },
        "cached": True,
        "analyzed_at": row.get("analyzed_at"),
    }


# ── Routes ────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "message": "Reputable — GitHub Repo Quality Predictor API v3",
        "db_connected": supabase is not None,
    }


@app.post("/analyze", tags=["Prediction"])
def analyze(request: AnalyzeRequest):
    """
    Accept a GitHub URL, check cache (24h), else fetch from GitHub,
    run ML model, persist to Supabase, and return the result.
    """
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Place 'github_quality_rf_model.pkl' in backend/ and restart.",
        )

    owner, repo_name = parse_github_url(request.url)
    repo_full_name   = f"{owner}/{repo_name}"

    # ── Cache check (24h) ─────────────────────────────────────────────────
    if supabase:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            cached = (
                supabase.table("analyses")
                .select("*")
                .eq("repo_full_name", repo_full_name)
                .gte("analyzed_at", cutoff)
                .order("analyzed_at", desc=True)
                .limit(1)
                .execute()
            )
            if cached.data:
                print(f"[CACHE HIT] {repo_full_name}")
                return format_analysis_row(cached.data[0])
        except Exception as e:
            print(f"[WARN] Cache check failed: {e}")

    # ── Connect to GitHub ─────────────────────────────────────────────────
    try:
        g    = Github(auth=Auth.Token(GITHUB_TOKEN)) if GITHUB_TOKEN else Github()
        repo = g.get_repo(repo_full_name)
    except UnknownObjectException:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repo_full_name}' not found or is private.",
        )
    except GithubException as exc:
        status = 429 if exc.status == 403 else 500
        msg = exc.data.get("message", str(exc)) if hasattr(exc, "data") and exc.data else str(exc)
        raise HTTPException(status_code=status, detail=f"GitHub API error: {msg}")

    # ── Extract features ──────────────────────────────────────────────────
    all_features  = extract_features_from_pygithub(repo)
    model_features = {k: all_features[k] for k in FEATURE_ORDER}

    # ── Predict ───────────────────────────────────────────────────────────
    input_df    = pd.DataFrame([model_features])[FEATURE_ORDER]
    prediction  = model.predict(input_df)[0]
    raw_probs   = model.predict_proba(input_df)[0].tolist()
    class_labels = list(model.classes_)
    probabilities = {
        label: round(prob * 100, 1)
        for label, prob in zip(class_labels, raw_probs)
    }

    quality_score = compute_quality_score(probabilities)
    suggestions   = build_suggestions(model_features)
    explanation   = build_explanation(input_df, prediction)

    # ── Persist to Supabase ───────────────────────────────────────────────
    if supabase:
        try:
            row = {
                "repo_full_name":       repo_full_name,
                "repo_url":             repo.html_url,
                "repo_description":     repo.description or "",
                "repo_language":        repo.language or "Unknown",
                "avatar_url":           repo.owner.avatar_url,
                "label":                prediction,
                "quality_score":        quality_score,
                "stars":                model_features["stars"],
                "forks":                model_features["forks"],
                "open_issues":          model_features["open_issues"],
                "size_kb":              model_features["size_kb"],
                "has_readme":           bool(model_features["has_readme"]),
                "has_tests":            bool(model_features["has_tests"]),
                "has_cicd":             bool(model_features["has_cicd"]),
                "has_docker":           bool(model_features["has_docker"]),
                "has_wiki":             bool(model_features["has_wiki"]),
                "has_pages":            bool(model_features["has_pages"]),
                "repo_age_days":        model_features["repo_age_days"],
                "prob_beginner":        probabilities.get("Beginner", 0),
                "prob_intermediate":    probabilities.get("Intermediate", 0),
                "prob_production_ready": probabilities.get("Production Ready", 0),
                "suggestions":          suggestions,
            }
            supabase.table("analyses").insert(row).execute()
        except Exception as e:
            print(f"[WARN] Failed to save to Supabase: {e}")
        else:
            # Kept outside the try so a console-encoding hiccup in this log
            # line can never be misreported as a failed DB save.
            print(f"[DB SAVED] {repo_full_name} -> {prediction} ({quality_score}/100)")

    return {
        "label":         prediction,
        "quality_score": quality_score,
        "probabilities": probabilities,
        "features":      model_features,
        "suggestions":   suggestions,
        "explanation":   explanation,
        "cached":        False,
        "repo_meta": {
            "name":        repo.name,
            "full_name":   repo.full_name,
            "description": repo.description or "",
            "language":    repo.language or "Unknown",
            "url":         repo.html_url,
            "avatar_url":  repo.owner.avatar_url,
        },
    }


@app.get("/history", tags=["History"])
def get_history(limit: int = 10):
    """Return the most recent unique repo analyses from Supabase."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        response = (
            supabase.table("analyses")
            .select(
                "id, repo_full_name, repo_url, repo_description, repo_language, "
                "avatar_url, label, quality_score, analyzed_at, "
                "has_readme, has_tests, has_cicd, has_docker"
            )
            .order("analyzed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"history": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB query failed: {e}")


@app.get("/stats", tags=["Stats"])
def get_stats():
    """Return aggregate stats: total analyses, label breakdown, top repos."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        total_res = supabase.table("analyses").select("id", count="exact").execute()
        label_res = supabase.table("analyses").select("label").execute()

        label_counts = {}
        for row in label_res.data:
            lbl = row["label"]
            label_counts[lbl] = label_counts.get(lbl, 0) + 1

        top_res = (
            supabase.table("analyses")
            .select("repo_full_name, avatar_url, repo_language, quality_score, label")
            .order("quality_score", desc=True)
            .limit(5)
            .execute()
        )
        return {
            "total_analyses": total_res.count,
            "label_breakdown": label_counts,
            "top_repos": top_res.data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB query failed: {e}")


# ── Embeddable badge ─────────────────────────────────────────────────────
BADGE_COLORS = {
    "Production Ready": "#2E7D32",  # green
    "Intermediate":      "#F9A825", # amber
    "Beginner":           "#9E9E9E", # gray
    "unknown":            "#9E9E9E",
}


def render_badge_svg(label: str, message: str, color: str) -> str:
    """Render a flat, shields.io-style two-segment SVG badge."""
    char_w = 6.5
    label_w   = int(len(label) * char_w) + 20
    message_w = int(len(message) * char_w) + 20
    total_w   = label_w + message_w
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img" aria-label="{label}: {message}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_w}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{message_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_w / 2}" y="14">{label}</text>
    <text x="{label_w + message_w / 2}" y="14">{message}</text>
  </g>
</svg>'''


@app.get("/badge/{owner}/{repo}", tags=["Badge"])
def get_badge(owner: str, repo: str):
    """
    Embeddable SVG badge, e.g. in a README:
    ![repo quality](https://your-api/badge/owner/repo)

    Serves the most recent cached analysis if one exists. If the repo has
    NEVER been analyzed, runs one lazily (via the same /analyze logic) so
    the badge still resolves on first request. Falls back to a neutral
    "unknown" badge on any failure so a broken repo never breaks a README.
    """
    repo_full_name = f"{owner}/{repo}"
    row = None

    if supabase:
        try:
            cached = (
                supabase.table("analyses")
                .select("label, quality_score")
                .eq("repo_full_name", repo_full_name)
                .order("analyzed_at", desc=True)
                .limit(1)
                .execute()
            )
            if cached.data:
                row = cached.data[0]
        except Exception as e:
            print(f"[WARN] Badge cache lookup failed: {e}")

    if row is None and model is not None:
        try:
            # Use the live result directly rather than re-querying Supabase —
            # this also works when persistence is disabled (supabase is None).
            result = analyze(AnalyzeRequest(url=f"https://github.com/{repo_full_name}"))
            row = {"label": result["label"], "quality_score": result["quality_score"]}
        except HTTPException:
            row = None  # invalid/missing repo — render "unknown" below
        except Exception as e:
            print(f"[WARN] Badge lazy-analyze failed: {e}")

    if row is None:
        svg = render_badge_svg("repo quality", "unknown", BADGE_COLORS["unknown"])
    else:
        svg = render_badge_svg(
            "repo quality",
            f'{row["quality_score"]}/100',
            BADGE_COLORS.get(row["label"], BADGE_COLORS["unknown"]),
        )

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
