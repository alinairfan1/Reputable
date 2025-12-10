"""Lightweight PyGithub test doubles — no network calls."""
from datetime import datetime, timedelta, timezone

from github import GithubException


class FakeContentItem:
    def __init__(self, name: str, item_type: str):
        self.name = name
        self.type = item_type


class FakeOwner:
    def __init__(self, login="octocat", avatar_url="https://example.com/a.png"):
        self.login = login
        self.avatar_url = avatar_url


class FakeRepo:
    """
    Minimal stand-in for a PyGithub Repository, configurable enough to drive
    every branch of feature_config.extract_features_from_pygithub.
    """

    def __init__(
        self,
        full_name="octocat/demo",
        root_items=None,
        workflows=None,
        workflows_raise=False,
        stars=100,
        forks=10,
        open_issues=2,
        size=500,
        has_wiki=True,
        has_pages=False,
        created_days_ago=365,
        updated_days_ago=1,
        language="Python",
    ):
        owner_login, name = full_name.split("/")
        self.owner = FakeOwner(login=owner_login)
        self.name = name
        self.full_name = full_name
        self.html_url = f"https://github.com/{full_name}"
        self.language = language
        self.stargazers_count = stars
        self.forks_count = forks
        self.open_issues_count = open_issues
        self.size = size
        self.has_wiki = has_wiki
        self.has_pages = has_pages
        self.description = "A demo repository"

        now = datetime.now(timezone.utc)
        self.created_at = now - timedelta(days=created_days_ago)
        self.updated_at = now - timedelta(days=updated_days_ago)

        self._root_items = root_items if root_items is not None else [
            FakeContentItem("README.md", "file"),
        ]
        self._workflows = workflows
        self._workflows_raise = workflows_raise

    def get_contents(self, path):
        if path == "":
            return self._root_items
        if path == ".github/workflows":
            if self._workflows_raise:
                raise GithubException(404, {"message": "Not Found"}, None)
            return self._workflows or []
        raise GithubException(404, {"message": "Not Found"}, None)
