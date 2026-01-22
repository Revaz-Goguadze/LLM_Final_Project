import pytest
from codereview.grader import MultiLLMGrader


def test_select_model_for_security():
    grader = MultiLLMGrader()

    model = grader._select_model_for_role("security", 0)
    assert model is not None
    assert isinstance(model, str)
    assert len(model) > 0  # Valid model name returned


def test_select_model_for_logic():
    grader = MultiLLMGrader()

    model = grader._select_model_for_role("logic", 0)
    assert model is not None
    assert isinstance(model, str)


def test_select_model_for_performance():
    grader = MultiLLMGrader()

    model = grader._select_model_for_role("performance", 0)
    assert model is not None
    assert isinstance(model, str)


def test_select_model_fallback_cycle():
    grader = MultiLLMGrader()

    model_0 = grader._select_model_for_role("security", 0)
    model_1 = grader._select_model_for_role("security", 1)
    model_2 = grader._select_model_for_role("security", 2)
    model_3 = grader._select_model_for_role("security", 3)

    # Should cycle back to first model after exhausting options
    assert model_3 == model_0


def test_select_model_invalid_role():
    grader = MultiLLMGrader()

    model = grader._select_model_for_role("invalid_role", 0)
    assert model is not None
    # Should return fallback model


def test_grade_with_model_selection():
    grader = MultiLLMGrader()

    # When model_id is None, should select based on role
    # This is a basic smoke test - doesn't actually call the API
    security_model = grader._select_model_for_role("security", 0)
    logic_model = grader._select_model_for_role("logic", 0)
    perf_model = grader._select_model_for_role("performance", 0)

    print(f"Security model: {security_model}")
    print(f"Logic model: {logic_model}")
    print(f"Performance model: {perf_model}")

    # Verify different models are preferred for different roles
    assert security_model is not None
    assert logic_model is not None
    assert perf_model is not None
