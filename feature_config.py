"""
feature_config.py — SINGLE SOURCE OF TRUTH
-------------------------------------------
All feature names, detection patterns, and extraction logic live here.
Both collect_data.py (training) and backend/main.py (inference) MUST
import from this file. This is the primary defence against Train-Serving Skew.
"""
from datetime import datetime, timezone

# ── The canonical feature list (order matters for the model) ──────────────
FEATURE_ORDER = [
    "stars",
    "forks",
    "open_issues",
    "size_kb",
    "has_wiki",
    "has_pages",
    "has_readme",
    "has_docker",
    "has_cicd",
    "has_tests",
    "repo_age_days",
    "days_since_last_update",
]

# ── Detection patterns ────────────────────────────────────────────────────
# Files/dirs that count as "has docker support"
DOCKER_FILES = {"dockerfile", "docker-compose.yml", "docker-compose.yaml"}

# Root-level files that indicate CI/CD
CICD_ROOT_FILES = {
    ".travis.yml",
    ".gitlab-ci.yml",
    "jenkinsfile",       # case-insensitive match applied in extractor
    "appveyor.yml",
}

# Directories whose PRESENCE (not contents) indicates CI/CD
CICD_DIRS = {".circleci"}

# Directories that contain workflows (contents must be non-empty)
CICD_WORKFLOW_DIRS = {".github/workflows"}

# Directories that count as "has tests"
TEST_DIRS = {"test", "tests", "__tests__", "spec", "vitest"}

# Root-level config files that imply a test suite exists
TEST_CONFIG_FILES = {
    "pytest.ini",
    "tox.ini",
    "jest.config.js",
    "jest.config.ts",
    "vitest.config.js",
    "vitest.config.ts",
    "vitest.config.mts",
    ".noserc",
    "setup.cfg",         # often contains [tool:pytest] section
    ".coveragerc",       # Python coverage config
    "codecov.yml",       # Codecov testing CI
    ".codecov.yml",      # Codecov alternate
    "pyproject.toml",    # Modern Python package config (contains pytest/test settings)
}

# File suffixes that indicate test files in the root
TEST_SUFFIXES = (
    ".test.js", ".spec.js",
    ".test.ts", ".spec.ts",
    "_test.py",
)


# ── Shared extraction function ────────────────────────────────────────────
def extract_features_from_pygithub(repo) -> dict:
    """
    Extract the full feature dict from a PyGithub Repository object.
    Call this from BOTH collect_data.py and backend/main.py to guarantee
    that training and serving use identical logic.

    Returns a dict with exactly the keys in FEATURE_ORDER plus metadata
    keys (owner, name, full_name, html_url, language) for bookkeeping.
    """
    from github import GithubException

    now = datetime.now(timezone.utc)

    # ── Time features ────────────────────────────────────────────────────
    # Ensure timezone-aware datetimes before subtracting
    created = repo.created_at
    updated = repo.updated_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    features = {
        # Metadata (not fed to model, used for bookkeeping / display)
        "owner":     repo.owner.login,
        "name":      repo.name,
        "full_name": repo.full_name,
        "html_url":  repo.html_url,
        "language":  repo.language or "Unknown",

        # Numeric features
        "stars":                  repo.stargazers_count,
        "forks":                  repo.forks_count,
        "open_issues":            repo.open_issues_count,
        "size_kb":                repo.size,
        "has_wiki":               int(repo.has_wiki),
        "has_pages":              int(repo.has_pages),
        "repo_age_days":          (now - created).days,
        "days_since_last_update": (now - updated).days,

        # Boolean features (set below)
        "has_readme": 0,
        "has_docker": 0,
        "has_cicd":   0,
        "has_tests":  0,
    }

    # ── Root tree scan ───────────────────────────────────────────────────
    try:
        contents = repo.get_contents("")
        # Build {lowercase_name: item_type} for O(1) lookups
        root = {item.name.lower(): item.type for item in contents}

        # has_readme: any root file whose name starts with "readme"
        if any(name.startswith("readme") for name in root):
            features["has_readme"] = 1

        # has_docker: dockerfile / docker-compose variants
        if DOCKER_FILES & root.keys():
            features["has_docker"] = 1

        # has_tests: test dirs OR test config files OR test-suffixed root files
        if any(name in TEST_DIRS and root[name] == "dir" for name in root):
            features["has_tests"] = 1
        if TEST_CONFIG_FILES & root.keys():
            features["has_tests"] = 1
        if any(name.endswith(TEST_SUFFIXES) for name in root):
            features["has_tests"] = 1

        # has_cicd: root-level CI files (case-insensitive)
        if CICD_ROOT_FILES & root.keys():
            features["has_cicd"] = 1
        # Jenkinsfile can be any case
        if any("jenkinsfile" in name for name in root):
            features["has_cicd"] = 1
        # .circleci directory
        if CICD_DIRS & root.keys():
            features["has_cicd"] = 1
        # .github/workflows — must contain at least one file
        if ".github" in root and root[".github"] == "dir":
            try:
                workflows = repo.get_contents(".github/workflows")
                if isinstance(workflows, list) and len(workflows) > 0:
                    features["has_cicd"] = 1
            except GithubException:
                pass

    except GithubException as exc:
        # Empty repo or permission error — leave binary features as 0
        print(f"[WARN] Could not read root for {repo.full_name}: {exc}")

    return features
