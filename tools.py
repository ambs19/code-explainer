"""The four read-only tools the model can choose from.

Every tool returns plain text (the observation the model sees) and records
what it saw in `state`, so checks.py can later compare the model's claims
against real evidence.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

TEST_TIMEOUT_SECONDS = 30
MAX_TEST_OUTPUT_CHARS = 3000


class AgentState:
    """Everything the tools have actually observed during one run."""

    def __init__(self, project_dir):
        self.project_dir = Path(project_dir)
        self.read_sources = {}      # function name -> source text that was shown
        self.saw_name_list = False  # did the model ever see the real function names?
        self.tests_ran = False
        self.test_output = ""
        self.test_results = {}      # test name -> "PASSED" / "FAILED"


def _source_files(project_dir):
    """Python files in the project that are not test files."""
    return sorted(
        path for path in Path(project_dir).glob("*.py")
        if not path.name.startswith("test_")
    )


def _all_functions(project_dir):
    """Return {name: (file_name, first_line, source_text)} for top-level functions."""
    functions = {}
    for path in _source_files(project_dir):
        text = path.read_text()
        tree = ast.parse(text)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                source = ast.get_source_segment(text, node)
                functions[node.name] = (path.name, node.lineno, source)
    return functions


def function_names(project_dir):
    return sorted(_all_functions(project_dir))


def project_functions_called_by(project_dir, name):
    """Names of other project functions that `name` calls directly (found with ast)."""
    functions = _all_functions(project_dir)
    if name not in functions:
        return []
    tree = ast.parse(functions[name][2])
    called = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    return sorted(called & set(functions) - {name})


def list_functions(state, args):
    names = function_names(state.project_dir)
    state.saw_name_list = True
    return "Functions in this project: " + ", ".join(names)


def read_function(state, args):
    name = args.get("name", "")
    functions = _all_functions(state.project_dir)
    if name not in functions:
        state.saw_name_list = True
        return (
            f"ERROR: no function named '{name}'. "
            f"Available functions: {', '.join(sorted(functions))}"
        )

    file_name, first_line, source = functions[name]
    state.read_sources[name] = source
    numbered = [
        f"{first_line + offset:>4} | {line}"
        for offset, line in enumerate(source.splitlines())
    ]
    return f"Source of {name} in {file_name}:\n" + "\n".join(numbered)


def _parse_test_results(output):
    """Read the pytest -rA short summary lines, e.g. 'FAILED test_x.py::test_y - ...'."""
    results = {}
    for match in re.finditer(r"^(PASSED|FAILED|ERROR) \S+::(\w+)", output, re.MULTILINE):
        status, test_name = match.groups()
        results[test_name] = status
    return results


def run_tests(state, args):
    if not list(state.project_dir.glob("test_*.py")):
        state.tests_ran = False
        return "No tests available in this project."

    command = [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider"]
    try:
        completed = subprocess.run(
            command,
            cwd=state.project_dir,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: tests did not finish within {TEST_TIMEOUT_SECONDS} seconds."

    output = completed.stdout + completed.stderr
    state.tests_ran = True
    state.test_output = output
    state.test_results = _parse_test_results(output)

    if len(output) > MAX_TEST_OUTPUT_CHARS:
        output = output[-MAX_TEST_OUTPUT_CHARS:]
    return "pytest output:\n" + output


# `explain` is handled by checks.py, because it is the final answer, not a lookup.
TOOLS = {
    "list_functions": list_functions,
    "read_function": read_function,
    "run_tests": run_tests,
}
