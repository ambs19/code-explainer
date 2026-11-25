# Evaluation results

`python evaluate.py` · qwen3:8b via Ollama · 3 runs per case · 2026-11-24.
Raw traces: [traces/eval/](traces/eval). Summary: [traces/eval/summary.json](traces/eval/summary.json).

| Score | Check (read from the traces, not from the model's claims) |
|---|---|
| 3/3 | A: `average` → `none_found` |
| 3/3 | B: `discount_price`, no tests → `suspected` |
| 3/3 | S2: no tests → never `verified` |
| 3/3 | C: `discount_price`, with tests → `verified`, citing the real failing test and output |
| 3/3 | S3: after the test failure, the agent reads `apply_rate` |
| **0/3** | S3+: the cited `evidence_code` is the `* 100` line itself |
| 3/3 | D: missing function → honest "not found" |
| 3/3 | S1: misspelled `discount_prise` → answers about the real `discount_price` |
| 10/10 | S4: runs where Python rejected an `explain` and the agent recovered to an accepted one |

## Tool sequences the model chose

```
A_1  list_functions > read:average > run_tests > explain
A_2  list_functions > read:average > explain                      (chose not to run tests)
A_3  list_functions > read:average > run_tests > explain(REJECTED) > explain
B_*  list_functions > read:discount_price > run_tests ("No tests available")
       > explain(REJECTED: calls apply_rate, not read) > read:apply_rate > explain
C_*  list_functions > read:discount_price > run_tests (1 FAILED)
       > explain(REJECTED: calls apply_rate, not read) > read:apply_rate > explain
D_*  list_functions > explain (not found)                         (no reading, no tests)
S1_* same as C
```

## Honest reading of these numbers

- **The model decides, but its habits are strong.** It always starts with `list_functions`.
  It skips `run_tests` when it thinks it is unnecessary (A_2) and skips reading entirely when
  the function does not exist (D). The program never fixes this order.
- **S3 is driven by a Python check, not by the model alone.** In every B/C/S1 run the model first
  tried to explain `discount_price` without reading `apply_rate`. The callee check rejected it with
  the name of the unread function, and the model then read `apply_rate`. This is the agent using an
  observation (the rejection) to decide its next step. Without that check, an earlier version
  wrongly blamed `discount_price` itself.
- **S1 is easy for this model** because it always lists function names first, so it never actually
  hit the "unknown name" error. The recovery path exists (`read_function` returns the real names)
  but was not exercised in these runs.
- **S3+ fails (0/3).** The final answers name `apply_rate` and usually propose the right fix
  (`/ 100` instead of `* 100`), but the cited code line is `discount_price`'s
  `return round(price - discount, 2)`. Python can prove the line is real, but not that it is the
  root cause. That would need knowledge of where the bug is, which Python does not have.
- The free-text `issue` and `fix` are not checked by Python and are sometimes vague or partly wrong.
