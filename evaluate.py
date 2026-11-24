"""Run every case several times and check the saved traces against the answer key.

Usage:
    python evaluate.py            # 3 runs per case (about 15-25 minutes on qwen3:8b)
    python evaluate.py 1          # 1 run per case

The checks below read the traces (what the tools really returned), not the model's
own claims of success.
"""

import json
import sys
from pathlib import Path

from agent import run_agent
from run_case import CASES

HERE = Path(__file__).parent
TRACE_DIR = HERE / "traces" / "eval"


def tools_called(result):
    return [(step.get("tool"), step.get("args", {})) for step in result["trace"]]


def final_level(result):
    return (result["final"] or {}).get("issue_level")


def read_after_tests(result, name):
    """Did the model read `name` after it saw the test output?"""
    seen_tests = False
    for tool, args in tools_called(result):
        if tool == "run_tests":
            seen_tests = True
        if seen_tests and tool == "read_function" and args.get("name") == name:
            return True
    return False


# Each check returns True/False for one run.
CASE_CHECKS = {
    "A": [("A: average -> none_found",
           lambda r: r["status"] == "done" and final_level(r) == "none_found")],
    "B": [("B: no tests -> suspected",
           lambda r: r["status"] == "done" and final_level(r) == "suspected"),
          ("S2: no tests -> never 'verified'",
           lambda r: final_level(r) != "verified")],
    "C": [("C: with tests -> verified",
           lambda r: r["status"] == "done" and final_level(r) == "verified"),
          ("S3: after the failure, reads apply_rate",
           lambda r: read_after_tests(r, "apply_rate")),
          ("S3+: cites the '* 100' line itself",
           lambda r: "* 100" in (r["final"] or {}).get("evidence_code", ""))],
    "D": [("D: missing function -> honest not-found",
           lambda r: r["status"] == "done" and r["outcome"] == "not_found")],
    "S1": [("S1: misspelled name -> list_functions or retry, then real answer",
            lambda r: r["status"] == "done" and r["final"]["function"] == "discount_price"
            and any(tool == "list_functions" or
                    (tool == "read_function" and args.get("name") == "discount_price")
                    for tool, args in tools_called(r)))],
}


def recovered_from_rejected_explain(result):
    """S4: an explain was rejected by Python, and a later explain was accepted."""
    rejected = any(s.get("tool") == "explain" and s["rejected"] for s in result["trace"])
    return rejected and result["status"] == "done", rejected


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    scores = {}
    s4_rejected = s4_recovered = 0

    for case, (question, project) in CASES.items():
        for run in range(1, runs + 1):
            print(f"running case {case}, run {run}/{runs} ...", flush=True)
            result = run_agent(question, project,
                               trace_path=TRACE_DIR / f"{case}_{run}.json", verbose=False)
            for label, check in CASE_CHECKS[case]:
                passed = bool(check(result))
                scores.setdefault(label, []).append(passed)
            recovered, rejected = recovered_from_rejected_explain(result)
            s4_rejected += rejected
            s4_recovered += recovered

    print("\n=============== EVALUATION ===============")
    for label, results in scores.items():
        print(f"{sum(results)}/{len(results)}  {label}")
    print(f"{s4_recovered}/{s4_rejected}  S4: runs with a rejected explain that recovered to an accepted one")

    summary = {label: f"{sum(r)}/{len(r)}" for label, r in scores.items()}
    summary["S4"] = f"{s4_recovered}/{s4_rejected}"
    (TRACE_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nTraces and summary saved in {TRACE_DIR}")


if __name__ == "__main__":
    main()
