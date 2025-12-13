"""
collect_data.py — Production-Grade Data Collection
----------------------------------------------------
Uses PyGithub to fetch GitHub repository data.
Feature extraction is delegated to feature_config.py so that
training data and live inference share IDENTICAL logic.

Usage:
    python collect_data.py
"""
import os
import time
import pandas as pd
from dotenv import load_dotenv
from github import Github, Auth, GithubException
from github.GithubException import RateLimitExceededException

# Import the SINGLE SOURCE OF TRUTH for feature extraction
from feature_config import extract_features_from_pygithub

# ── Auth ──────────────────────────────────────────────────────────────────
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found. Add it to your .env file.")

OUTPUT_FILE = "raw_github_data.csv"
CHECKPOINT_EVERY = 100   # save progress every N repos


def get_client() -> Github:
    return Github(auth=Auth.Token(GITHUB_TOKEN), per_page=100)


def search_language(g: Github, language: str, target: int) -> list:
    """
    Return up to `target` Repository objects for a given language.
    Stars > 10 keeps a natural mix of beginner → production-grade repos.
    """
    collected = []
    query = f"language:{language} stars:>10"
    print(f"\n[SEARCH] '{query}' — targeting {target} repos")

    try:
        results = g.search_repositories(query=query, sort="updated", order="desc")
        for repo in results:
            collected.append(repo)
            if len(collected) >= target:
                break
            # Search API: 30 requests/min → sleep between items when close to limit
            if len(collected) % 100 == 0:
                print(f"  -> {len(collected)} repos buffered...")
                time.sleep(2)
    except RateLimitExceededException:
        wait = 65
        print(f"[RATE LIMIT] Sleeping {wait}s...")
        time.sleep(wait)
    except GithubException as e:
        print(f"[ERROR] Search failed: {e}")

    print(f"  -> Collected {len(collected)} '{language}' repos")
    return collected[:target]


def main():
    g = get_client()

    # ── Collect repo objects ───────────────────────────────────────────────
    py_repos = search_language(g, "python",     500)
    js_repos = search_language(g, "javascript", 250)
    ts_repos = search_language(g, "typescript", 250)

    all_repos = py_repos + js_repos + ts_repos
    print(f"\nTotal repositories to process: {len(all_repos)}")

    # ── Resume from checkpoint ─────────────────────────────────────────────
    dataset: list[dict] = []
    processed: set[str] = set()

    if os.path.exists(OUTPUT_FILE):
        try:
            existing = pd.read_csv(OUTPUT_FILE)
            if not existing.empty:
                dataset = existing.to_dict("records")
                processed = set(existing["full_name"].tolist())
                print(f"[RESUME] {len(dataset)} repos already processed — skipping.")
        except Exception as e:
            print(f"[WARN] Could not load checkpoint: {e}. Starting fresh.")

    # ── Extract features for each repo ────────────────────────────────────
    for i, repo in enumerate(all_repos):
        if repo.full_name in processed:
            continue

        print(f"[{i+1:>4}/{len(all_repos)}] {repo.full_name}")

        try:
            # Core extraction — same logic as backend inference
            features = extract_features_from_pygithub(repo)
            dataset.append(features)
            processed.add(repo.full_name)
        except RateLimitExceededException:
            wait = 65
            print(f"  [RATE LIMIT] Sleeping {wait}s...")
            time.sleep(wait)
            # Retry the same repo after sleeping
            try:
                features = extract_features_from_pygithub(repo)
                dataset.append(features)
                processed.add(repo.full_name)
            except Exception as retry_err:
                print(f"  [SKIP] {repo.full_name} after retry: {retry_err}")
        except Exception as e:
            print(f"  [SKIP] {repo.full_name}: {e}")

        # Polite delay to stay within core API rate limits (5000/hr ≈ 1.4/s)
        time.sleep(0.5)

        # Save checkpoint
        if len(dataset) % CHECKPOINT_EVERY == 0 and len(dataset) > 0:
            pd.DataFrame(dataset).to_csv(OUTPUT_FILE, index=False)
            print(f"  [CHECKPOINT] {len(dataset)} repos saved.")

    # ── Final save ────────────────────────────────────────────────────────
    df = pd.DataFrame(dataset)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[DONE] {len(df)} repositories saved to '{OUTPUT_FILE}'")
    print(df[["full_name", "stars", "has_readme", "has_docker", "has_cicd", "has_tests",
              "repo_age_days", "days_since_last_update"]].head(10).to_string())


if __name__ == "__main__":
    main()
