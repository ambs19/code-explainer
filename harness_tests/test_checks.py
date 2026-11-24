"""Tests for the Python checks. These do not call the model.

Run with:  python -m pytest harness_tests -q
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import check_explain                       # noqa: E402
from tools import AgentState, read_function, run_tests  # noqa: E402

WITH_TESTS = ROOT / "sample_project"
NO_TESTS = ROOT / "sample_project_no_tests"


def answer(**overrides):
    base = {
        "function": "discount_price",
        "summary": "Takes a percentage off a price.",
        "evidence_code": "return price * percent * 100",
        "issue_level": "verified",
        "issue": "apply_rate multiplies by 100 instead of dividing.",
        "evidence_test": "test_discount_price_ten_percent",
        "evidence_output": "assert -99900 == 90",
        "fix": "Use price * percent / 100 in apply_rate.",
    }
    base.update(overrides)
    return base


def state_after(project, names, tests=True):
    state = AgentState(project)
    for name in names:
        read_function(state, {"name": name})
    if tests:
        run_tests(state, {})
    return state


def test_good_verified_answer_is_accepted():
    state = state_after(WITH_TESTS, ["discount_price", "apply_rate"])
    accepted, message, _ = check_explain(answer(), state)
    assert accepted, message


def test_must_read_called_functions_first():
    state = state_after(WITH_TESTS, ["discount_price"])
    accepted, message, _ = check_explain(answer(), state)
    assert not accepted and "apply_rate" in message


def test_invented_code_is_rejected():
    state = state_after(WITH_TESTS, ["discount_price", "apply_rate"])
    accepted, message, _ = check_explain(answer(evidence_code="return price / 0"), state)
    assert not accepted and "does not appear" in message


def test_invented_test_output_is_rejected():
    state = state_after(WITH_TESTS, ["discount_price", "apply_rate"])
    accepted, _, _ = check_explain(answer(evidence_output="assert 5 == 90"), state)
    assert not accepted


def test_verified_without_tests_is_rejected():
    state = state_after(NO_TESTS, ["discount_price", "apply_rate"])
    accepted, message, _ = check_explain(answer(), state)
    assert not accepted and "suspected" in message


def test_none_found_with_failing_test_is_rejected():
    state = state_after(WITH_TESTS, ["discount_price", "apply_rate"])
    accepted, _, _ = check_explain(
        answer(issue_level="none_found", issue="", fix="", evidence_test="", evidence_output=""), state)
    assert not accepted


def test_passed_test_cannot_be_cited_as_evidence():
    state = state_after(WITH_TESTS, ["average"])
    accepted, _, _ = check_explain(answer(
        function="average", evidence_code="return sum(numbers) / len(numbers)",
        issue_level="none_found", issue="", fix="",
        evidence_test="test_average_of_three_numbers", evidence_output=""), state)
    assert not accepted


def test_missing_function_needs_real_name_list_first():
    state = AgentState(WITH_TESTS)
    not_found = answer(function="calculate_tax", issue_level="none_found", evidence_code="",
                       issue="", fix="", evidence_test="", evidence_output="")
    accepted, _, _ = check_explain(not_found, state)
    assert not accepted
    read_function(state, {"name": "calculate_tax"})  # returns the real names
    accepted, _, outcome = check_explain(not_found, state)
    assert accepted and outcome == "not_found"
