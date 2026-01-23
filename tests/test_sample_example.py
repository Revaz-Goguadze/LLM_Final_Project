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
