import pytest

from feature_config import FEATURE_ORDER, extract_features_from_pygithub
from tests.fakes import FakeContentItem, FakeRepo


def test_feature_order_keys_present_in_extraction():
    repo = FakeRepo()
    features = extract_features_from_pygithub(repo)
    for key in FEATURE_ORDER:
        assert key in features


def test_bare_repo_has_no_practice_features():
    repo = FakeRepo(root_items=[])
    features = extract_features_from_pygithub(repo)
    assert features["has_readme"] == 0
    assert features["has_docker"] == 0
    assert features["has_cicd"] == 0
    assert features["has_tests"] == 0


def test_readme_detected_case_insensitively():
    repo = FakeRepo(root_items=[FakeContentItem("Readme.rst", "file")])
    features = extract_features_from_pygithub(repo)
    assert features["has_readme"] == 1


@pytest.mark.parametrize("filename", ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"])
def test_docker_detected(filename):
    repo = FakeRepo(root_items=[FakeContentItem(filename, "file")])
    features = extract_features_from_pygithub(repo)
    assert features["has_docker"] == 1


@pytest.mark.parametrize("dirname", ["test", "tests", "__tests__", "spec"])
def test_test_dir_detected(dirname):
    repo = FakeRepo(root_items=[FakeContentItem(dirname, "dir")])
    features = extract_features_from_pygithub(repo)
    assert features["has_tests"] == 1


def test_test_suffix_file_detected():
    repo = FakeRepo(root_items=[FakeContentItem("foo.test.js", "file")])
    features = extract_features_from_pygithub(repo)
    assert features["has_tests"] == 1


def test_cicd_root_file_detected():
    repo = FakeRepo(root_items=[FakeContentItem(".travis.yml", "file")])
    features = extract_features_from_pygithub(repo)
    assert features["has_cicd"] == 1


def test_cicd_circleci_dir_detected():
    repo = FakeRepo(root_items=[FakeContentItem(".circleci", "dir")])
    features = extract_features_from_pygithub(repo)
    assert features["has_cicd"] == 1


def test_cicd_workflows_dir_with_files_detected():
    repo = FakeRepo(
        root_items=[FakeContentItem(".github", "dir")],
        workflows=[FakeContentItem("ci.yml", "file")],
    )
    features = extract_features_from_pygithub(repo)
    assert features["has_cicd"] == 1


def test_cicd_empty_workflows_dir_not_detected():
    repo = FakeRepo(
        root_items=[FakeContentItem(".github", "dir")],
        workflows=[],
    )
    features = extract_features_from_pygithub(repo)
    assert features["has_cicd"] == 0


def test_cicd_workflows_lookup_failure_does_not_crash():
    repo = FakeRepo(
        root_items=[FakeContentItem(".github", "dir")],
        workflows_raise=True,
    )
    features = extract_features_from_pygithub(repo)
    assert features["has_cicd"] == 0


def test_time_features_are_non_negative_ints():
    repo = FakeRepo(created_days_ago=400, updated_days_ago=5)
    features = extract_features_from_pygithub(repo)
    assert features["repo_age_days"] >= 400
    assert features["days_since_last_update"] >= 5
