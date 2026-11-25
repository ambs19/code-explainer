"""Python checks on the model's final `explain` answer.

The model's answer is accepted only if every claim matches evidence that
the tools really produced in this run. Each error message says what is
wrong and what would be valid, so the model can fix it and resubmit.
"""

import re

from tools import function_names, project_functions_called_by

ISSUE_LEVELS = ["verified", "suspected", "none_found"]
REQUIRED_FIELDS = [
    "function", "summary", "evidence_code", "issue_level",
    "issue", "evidence_test", "evidence_output", "fix",
]

LINE_NUMBER_PREFIX = re.compile(r"^\s*\d+\s*\|\s?")


def _clean_code(code):
    """Allow the model to copy lines with their '  20 | ' prefixes."""
    lines = [LINE_NUMBER_PREFIX.sub("", line) for line in code.strip().splitlines()]
    return "\n".join(line.rstrip() for line in lines).strip()


def _unmatched_code_line(code, state):
    """Return the first cited line not found in any source read so far, '' if all match.

    Each cited line must equal (ignoring indentation) a real line that read_function showed.
    Returns None when nothing was cited at all.
    """
    cited = [line.strip() for line in _clean_code(code).splitlines() if line.strip()]
    if not cited:
        return None
    shown = {
        line.strip()
        for source in state.read_sources.values()
        for line in source.splitlines()
    }
    for line in cited:
        if line not in shown:
            return line
    return ""


def _squash_spaces(text):
    """Compare pytest text ignoring how many spaces separate the words."""
    return " ".join(text.split())


def _failed_tests_for(function, state):
    return [
        name for name, status in state.test_results.items()
        if status == "FAILED" and function in name
    ]


def check_explain(args, state):
    """Return (accepted, message, outcome). outcome is 'explained' or 'not_found'."""
    missing = [field for field in REQUIRED_FIELDS if field not in args]
    if missing:
        return False, (
            f"REJECTED: explain is missing fields {missing}. "
            f"Required fields: {REQUIRED_FIELDS}. Use \"\" for fields that do not apply."
        ), None
    if not all(isinstance(args[field], str) for field in REQUIRED_FIELDS):
        return False, "REJECTED: every explain field must be a string. Use \"\" if not applicable.", None

    level = args["issue_level"]
    if level not in ISSUE_LEVELS:
        return False, f"REJECTED: issue_level '{level}' is not valid. Valid levels: {ISSUE_LEVELS}.", None

    function = args["function"]
    names = function_names(state.project_dir)

    # Honest "not found" answer.
    if function not in names:
        if not state.saw_name_list:
            return False, (
                f"REJECTED: '{function}' is not a confirmed function name. "
                "Check the real names first with list_functions or read_function."
            ), None
        if level != "none_found":
            return False, (
                f"REJECTED: '{function}' does not exist, so there is nothing to diagnose. "
                f"Use issue_level 'none_found' and say it was not found. Real functions: {names}."
            ), None
        return True, f"ACCEPTED: '{function}' does not exist in this project.", "not_found"

    if function not in state.read_sources:
        return False, (
            f"REJECTED: you have not read '{function}' yet. "
            f"Call read_function with name '{function}' before explaining it."
        ), None

    unread_callees = [
        name for name in project_functions_called_by(state.project_dir, function)
        if name not in state.read_sources
    ]
    if unread_callees:
        return False, (
            f"REJECTED: '{function}' calls {unread_callees}, which you have not read. "
            "What the code actually does depends on them. Read them before explaining."
        ), None

    if not args["summary"].strip():
        return False, "REJECTED: summary is empty. Explain in plain English what the code does.", None

    bad_line = _unmatched_code_line(args["evidence_code"], state)
    if bad_line is None:
        return False, "REJECTED: evidence_code is empty. Copy 1-3 real code lines from read_function.", None
    if bad_line:
        return False, (
            f"REJECTED: this evidence_code line does not appear in any source you read: {bad_line!r}. "
            "Copy 1-3 short lines exactly as read_function showed them "
            f"(functions read so far: {sorted(state.read_sources)})."
        ), None

    failed = _failed_tests_for(function, state)


    if level == "verified":
        if not state.tests_ran:
            return False, (
                "REJECTED: 'verified' needs a failing test, but no tests have run. "
                "Call run_tests, or use 'suspected' if no tests are available."
            ), None
        status = state.test_results.get(args["evidence_test"])
        if status != "FAILED":
            failed_all = [n for n, s in state.test_results.items() if s == "FAILED"]
            return False, (
                f"REJECTED: evidence_test '{args['evidence_test']}' is not a FAILED test. "
                f"FAILED tests in the output: {failed_all or 'none'}."
            ), None
        output = _squash_spaces(args["evidence_output"])
        if not output or output not in _squash_spaces(state.test_output):
            return False, (
                "REJECTED: evidence_output must be copied exactly from the pytest output, "
                "for example the line starting with 'E       assert'."
            ), None

    cited_test = args["evidence_test"].strip()
    if cited_test and state.test_results.get(cited_test) != "FAILED":
        failed_all = [n for n, s in state.test_results.items() if s == "FAILED"]
        return False, (
            f"REJECTED: evidence_test '{cited_test}' is not a FAILED test in the pytest output. "
            f"Use \"\" or one of the FAILED tests: {failed_all or 'none'}."
        ), None

    if level == "none_found" and failed:
        return False, (
            f"REJECTED: tests {failed} FAILED for '{function}', so 'none_found' contradicts the evidence."
        ), None

    if level in ("verified", "suspected"):
        if not args["issue"].strip() or not args["fix"].strip():
            return False, f"REJECTED: issue_level '{level}' needs a non-empty issue and fix.", None

    return True, f"ACCEPTED: explanation of '{function}' with issue_level '{level}'.", "explained"
