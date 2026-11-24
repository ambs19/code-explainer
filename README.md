# Code Explainer and Bug Finder

CSYE 7374 Agentic AI mini project · Huizhen Zheng (individual project)

## Problem

People who cannot read code are often handed code that someone else, or an AI, wrote.
They want to know two things: **what is this code meant to do, and does it actually do that?**
Asking a chatbot directly is risky: it can invent code lines, or claim "there is a bug" or
"it works" without any evidence.

This agent investigates a small Python project with **read-only** tools, then explains one
function in plain English. **Every claim is checked by Python against real tool output**:
cited code must really exist, cited test failures must really have happened.

Each answer gets one of three levels:

| Level | Meaning | Required evidence |
|---|---|---|
| `verified` | There is a bug | A test that really FAILED, plus its failure output |
| `suspected` | Looks wrong | The code disagrees with its description, but no failing test proves it |
| `none_found` | No problem found | No failing test for this function |

If the function does not exist, the agent must say so honestly instead of inventing an explanation.

## How it works

```
question ─► model proposes ONE JSON action ─► Python validates it
                 ▲                               │
                 │                ┌──────────────┴──────────────┐
                 │            invalid                         valid
                 │       (error names the                 run the tool
                 │        valid options)                       │
                 └──────────── observation ◄───────────────────┘
stop when: an `explain` passes checks.py (done) · 15 steps (max_steps) · same rejected action 3 times (stuck)
```

- Model: `qwen3:8b` through Ollama (local), JSON output, temperature 0.2.
- The system prompt describes the tools and rules but **does not fix an order**. The model decides
  which tool to use next based on what it has seen.

### Tools the model chooses between

| Tool | What it does |
|---|---|
| `list_functions {}` | Names of the functions in the project |
| `read_function {"name"}` | Source of one function with line numbers (uses `ast`). Unknown name → returns the real names |
| `run_tests {}` | Fixed command `pytest -q -rA`, 30 s timeout. No test files → "No tests available" |
| `explain {...}` | Final answer: `function, summary, evidence_code, issue_level, issue, evidence_test, evidence_output, fix` |

### Python checks on `explain` ([checks.py](checks.py))

1. The function must have been read. If it does not exist, the model must first have seen the real name list.
2. Every project function it calls must also have been read (what code does depends on what it calls).
3. Every line of `evidence_code` must match a line that `read_function` really returned.
4. `verified` requires that `run_tests` ran, `evidence_test` is a test that FAILED, and
   `evidence_output` appears in the real pytest output.
5. A cited `evidence_test` must be a FAILED test (a PASSED test is not evidence of anything).
6. `none_found` is rejected when a test for this function FAILED.
7. With no tests, the highest possible level is `suspected`.

A rejected answer goes back to the model with the exact reason, so it can gather more evidence and resubmit.

## Sample project (fictional)

[sample_project/pricing.py](sample_project/pricing.py) plays the role of AI-generated shop code:

- `average()`: correct.
- `discount_price()`: correct by itself, but calls `apply_rate()`.
- `apply_rate()`: **bug**: `price * percent * 100` instead of `/ 100`.

[sample_project/test_pricing.py](sample_project/test_pricing.py) is the answer key.
[sample_project_no_tests/](sample_project_no_tests) is the same code without tests.

## Demo cases

| Case | Question | Expected |
|---|---|---|
| A | Explain `average` | `none_found` |
| B | Explain `discount_price`, no tests | `suspected` |
| C | Explain `discount_price`, with tests | `verified`, citing the failing test |
| D | Explain `calculate_tax` (does not exist) | honest "not found" |
| S1 | Explain `discount_prise` (misspelled) | agent finds the real name and answers |

Adaptive scenarios checked by [evaluate.py](evaluate.py) from the saved traces:
S1 misspelled name → recovery; S2 no tests → never `verified`;
S3 after the test failure → the agent reads `apply_rate`; S4 a rejected `explain` → fixed and accepted.

## How to run

Requirements: Python 3.10+ and [Ollama](https://ollama.com).

```bash
ollama pull qwen3:8b
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run one case (prints every step: the model's thought, tool call, tool result, and the final answer):

```bash
python run_case.py C
```

Other options: `A`, `B`, `C`, `D`, `S1`, or `all`. Traces are saved to `traces/case_<name>.json`.

Run the evaluation (each case 3 times, about 20 minutes on a laptop):

```bash
python evaluate.py
```

Run the unit tests for the Python checks (no model needed):

```bash
python -m pytest harness_tests -q
```

## Results

See [RESULTS.md](RESULTS.md) for the latest `evaluate.py` numbers.

## Files

| File | Purpose |
|---|---|
| [agent.py](agent.py) | Agent loop, action validation, step limit, stuck detection, trace |
| [tools.py](tools.py) | The read-only tools and the state of what they observed |
| [checks.py](checks.py) | Python checks on the final `explain` |
| [prompts.py](prompts.py) | System prompt |
| [run_case.py](run_case.py) | Run a demo case |
| [evaluate.py](evaluate.py) | Run all cases several times and score the traces |
| [harness_tests/](harness_tests) | Unit tests for the checks |

## Limitations

- The suggested `fix` is not verified (the agent never edits or runs changed code).
- `suspected` relies on the model reading the docstring correctly and can be wrong.
- Tests are assumed to be correct.
- Only a single small folder of top-level functions is analyzed.
- With an 8B local model, the cited line is not always the root-cause line (see RESULTS.md).
