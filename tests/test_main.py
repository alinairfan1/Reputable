import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from github.GithubException import UnknownObjectException

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
import main
from feature_config import FEATURE_ORDER
from tests.fakes import FakeRepo

client = TestClient(main.app)


# ── Helpers / fixtures ───────────────────────────────────────────────────

class FakeGithubClient:
    """Stands in for `Github(...)` — configurable get_repo() result."""

    def __init__(self, repo=None, raise_exc=None):
        self._repo = repo
        self._raise_exc = raise_exc

    def __call__(self, *args, **kwargs):
        return self

    def get_repo(self, full_name):
        if self._raise_exc:
            raise self._raise_exc
        return self._repo


@pytest.fixture(autouse=True)
def no_supabase(monkeypatch):
    """Isolate every test from the real Supabase instance by default."""
    monkeypatch.setattr(main, "supabase", None)


# ── Health ────────────────────────────────────────────────────────────────

def test_root_health():
    res = client.get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db_connected"] is False


# ── parse_github_url ─────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/octocat/Hello-World", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World/", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
    ("github.com/octocat/Hello-World", ("octocat", "Hello-World")),
])
def test_parse_github_url_valid(url, expected):
    assert main.parse_github_url(url) == expected


def test_parse_github_url_invalid():
    with pytest.raises(HTTPException) as exc_info:
        main.parse_github_url("https://example.com/not-a-repo")
    assert exc_info.value.status_code == 400


# ── compute_quality_score ────────────────────────────────────────────────

def test_compute_quality_score_all_beginner():
    assert main.compute_quality_score({"Beginner": 100.0, "Intermediate": 0.0, "Production Ready": 0.0}) == 0


def test_compute_quality_score_all_production_ready():
    assert main.compute_quality_score({"Beginner": 0.0, "Intermediate": 0.0, "Production Ready": 100.0}) == 100


def test_compute_quality_score_all_intermediate():
    assert main.compute_quality_score({"Beginner": 0.0, "Intermediate": 100.0, "Production Ready": 0.0}) == 50


# ── build_suggestions ────────────────────────────────────────────────────

def test_build_suggestions_flags_every_missing_practice():
    features = {"has_readme": 0, "has_tests": 0, "has_cicd": 0, "has_docker": 0}
    suggestions = main.build_suggestions(features)
    assert len(suggestions) == 4


def test_build_suggestions_empty_when_all_present():
    features = {"has_readme": 1, "has_tests": 1, "has_cicd": 1, "has_docker": 1}
    suggestions = main.build_suggestions(features)
    assert len(suggestions) == 1
    assert "Excellent" in suggestions[0]


# ── build_explanation (uses the real bundled model + SHAP explainer) ────

def test_build_explanation_top_n_and_shape():
    sample = {
        "stars": 500, "forks": 50, "open_issues": 10, "size_kb": 2000,
        "has_wiki": 1, "has_pages": 0, "has_readme": 1, "has_docker": 1,
        "has_cicd": 1, "has_tests": 1, "repo_age_days": 900,
        "days_since_last_update": 3,
    }
    input_df = pd.DataFrame([sample])[FEATURE_ORDER]
    prediction = main.model.predict(input_df)[0]

    explanation = main.build_explanation(input_df, prediction, top_n=3)

    assert len(explanation) == 3
    impacts = [abs(row["impact"]) for row in explanation]
    assert impacts == sorted(impacts, reverse=True)
    for row in explanation:
        assert row["feature"] in FEATURE_ORDER


def test_build_explanation_from_row_reconstructs_from_cached_columns():
    # Simulates a Supabase row: no days_since_last_update column (it isn't
    # persisted), everything else present as it would be from a real insert.
    row = {
        "stars": 41757, "forks": 2825, "open_issues": 291, "size_kb": 8332,
        "has_wiki": True, "has_pages": False, "has_readme": True,
        "has_docker": True, "has_cicd": True, "has_tests": True,
        "repo_age_days": 3000, "label": "Production Ready",
    }
    explanation = main.build_explanation_from_row(row)
    assert len(explanation) > 0
    assert all(row["feature"] in FEATURE_ORDER for row in explanation)


def test_format_analysis_row_includes_explanation():
    row = {
        "label": "Production Ready", "quality_score": 96,
        "repo_full_name": "psf/black", "repo_url": "https://github.com/psf/black",
        "stars": 41757, "forks": 2825, "open_issues": 291, "size_kb": 8332,
        "has_wiki": True, "has_pages": False, "has_readme": True,
        "has_docker": True, "has_cicd": True, "has_tests": True,
        "repo_age_days": 3000,
    }
    formatted = main.format_analysis_row(row)
    assert formatted["cached"] is True
    assert len(formatted["explanation"]) > 0


# ── /analyze ──────────────────────────────────────────────────────────────

def test_analyze_rejects_invalid_url():
    res = client.post("/analyze", json={"url": "not-a-github-url"})
    assert res.status_code == 400


def test_analyze_repo_not_found(monkeypatch):
    monkeypatch.setattr(main, "Github", FakeGithubClient(raise_exc=UnknownObjectException(404, {}, None)))
    res = client.post("/analyze", json={"url": "https://github.com/octocat/does-not-exist"})
    assert res.status_code == 404


def test_analyze_success_fresh_returns_explanation(monkeypatch):
    repo = FakeRepo(full_name="octocat/demo", stars=5000, forks=500, has_wiki=True)
    monkeypatch.setattr(main, "Github", FakeGithubClient(repo=repo))

    res = client.post("/analyze", json={"url": "https://github.com/octocat/demo"})
    assert res.status_code == 200

    body = res.json()
    assert body["cached"] is False
    assert body["label"] in ["Beginner", "Intermediate", "Production Ready"]
    assert 0 <= body["quality_score"] <= 100
    assert body["repo_meta"]["full_name"] == "octocat/demo"
    assert isinstance(body["explanation"], list)
    assert len(body["explanation"]) > 0
    assert set(FEATURE_ORDER) == set(body["features"].keys())


# ── /badge ────────────────────────────────────────────────────────────────

def test_badge_unknown_without_cache_or_github(monkeypatch):
    # No supabase (autoused fixture) and GitHub lookup fails -> "unknown" badge.
    monkeypatch.setattr(main, "Github", FakeGithubClient(raise_exc=UnknownObjectException(404, {}, None)))
    res = client.get("/badge/octocat/does-not-exist")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/svg+xml")
    assert "unknown" in res.text


def test_badge_renders_svg_via_lazy_analyze(monkeypatch):
    repo = FakeRepo(full_name="octocat/demo", stars=9000, forks=900)
    monkeypatch.setattr(main, "Github", FakeGithubClient(repo=repo))
    res = client.get("/badge/octocat/demo")
    assert res.status_code == 200
    assert res.text.startswith("<svg")
    assert "repo quality" in res.text
    assert res.headers["cache-control"] == "public, max-age=3600"


# ── /history and /stats without a DB connection ──────────────────────────

def test_history_without_db_returns_503():
    res = client.get("/history")
    assert res.status_code == 503


def test_stats_without_db_returns_503():
    res = client.get("/stats")
    assert res.status_code == 503
