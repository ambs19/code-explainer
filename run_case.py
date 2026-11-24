"""Run one demo case and save its trace.

Usage:
    python run_case.py C          # one case
    python run_case.py all        # cases A-D and S1
"""

import sys
from pathlib import Path

from agent import run_agent

HERE = Path(__file__).parent
WITH_TESTS = HERE / "sample_project"
NO_TESTS = HERE / "sample_project_no_tests"

CASES = {
    "A": ("Explain what the function average does and whether it has a bug.", WITH_TESTS),
    "B": ("Explain what the function discount_price does and whether it has a bug.", NO_TESTS),
    "C": ("Explain what the function discount_price does and whether it has a bug.", WITH_TESTS),
    "D": ("Explain what the function calculate_tax does and whether it has a bug.", WITH_TESTS),
    "S1": ("Explain what the function discount_prise does and whether it has a bug.", WITH_TESTS),
}


def main():
    if len(sys.argv) != 2 or (sys.argv[1] not in CASES and sys.argv[1] != "all"):
        print(f"Usage: python run_case.py <{'|'.join(CASES)}|all>")
        sys.exit(1)
    names = list(CASES) if sys.argv[1] == "all" else [sys.argv[1]]
    for name in names:
        question, project = CASES[name]
        print(f"\n######## CASE {name} ########")
        run_agent(question, project, trace_path=HERE / "traces" / f"case_{name}.json")


if __name__ == "__main__":
    main()
