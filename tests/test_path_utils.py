from pathlib import Path

from codereview.path_utils import normalize_repo_path, resolve_repo_path


def test_normalize_repo_path_from_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = Path("sample.py")
    file_path.write_text("print('ok')\n", encoding="utf-8")

    normalized = normalize_repo_path(str(file_path.resolve()))
    assert normalized == "sample.py"
    assert resolve_repo_path(normalized) == str(file_path.resolve())


def test_normalize_repo_path_from_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = Path("dir") / "sample.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("print('ok')\n", encoding="utf-8")

    normalized = normalize_repo_path(str(file_path))
    assert normalized == "dir/sample.py"
