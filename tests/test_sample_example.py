import importlib.util
from pathlib import Path


def _load_example_module():
    path = Path(__file__).resolve().parent.parent / "sample" / "example.py"
    spec = importlib.util.spec_from_file_location("sample_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_total_with_discount_percent_contract():
    example = _load_example_module()
    total = example.total_with_discount([100.0, 50.0], 10.0)
    assert total == 135.0


def test_sort_scores_mutates_and_returns_same_list():
    example = _load_example_module()
    scores = [3, 1, 2]
    result = example.sort_scores(scores)
    assert result is scores
    assert scores == [3, 2, 1]


def test_read_file_unbounded_rejects_traversal():
    example = _load_example_module()
    try:
        example.read_file_unbounded("../../etc/passwd")
    except ValueError:
        return
    assert False, "Traversal should be rejected"


def test_api_login_requires_secret(monkeypatch):
    example = _load_example_module()
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("ADMIN_USER", "admin")
    assert example.api_login("admin", "secret") is False


def test_api_login_rejects_wrong_password(monkeypatch):
    example = _load_example_module()
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("ADMIN_USER", "admin")
    assert example.api_login("admin", "wrong") is False


def test_api_login_accepts_admin(monkeypatch):
    example = _load_example_module()
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("ADMIN_USER", "admin")
    assert example.api_login("admin", "secret") is True


def test_api_login_rejects_non_admin(monkeypatch):
    example = _load_example_module()
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("ADMIN_USER", "admin")
    assert example.api_login("user", "secret") is False
