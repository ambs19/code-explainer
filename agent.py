"""The agent loop.

Model proposes one JSON action -> Python parses and validates it
-> the tool runs -> the observation goes back to the model -> repeat,
until an `explain` passes checks.py, the step limit is hit, or the model is stuck.
"""

import json
import time
from pathlib import Path

import requests

from checks import check_explain
from prompts import SYSTEM_PROMPT
from tools import TOOLS, AgentState

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"
MAX_STEPS = 15
STUCK_REPEATS = 3          # same rejected action proposed this many times -> stuck
MAX_SHOWN_CHARS = 600      # how much of each observation to print on screen

VALID_TOOLS = list(TOOLS) + ["explain"]
NO_ARG_TOOLS = ["list_functions", "run_tests"]


def call_model(messages):
    body = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }
    response = requests.post(OLLAMA_URL, json=body, timeout=180)
    response.raise_for_status()
    return response.json()["message"]["content"]


def validate_action(raw_reply):
    """Return (action, None) if valid, or (None, error message naming the valid options)."""
    try:
        action = json.loads(raw_reply)
    except json.JSONDecodeError:
        return None, (
            'REJECTED: reply was not valid JSON. Reply with one object like '
            '{"thought": "...", "tool": "read_function", "args": {"name": "..."}}.'
        )
    if not isinstance(action, dict):
        return None, "REJECTED: reply must be a JSON object with keys thought, tool, args."

    tool = action.get("tool")
    args = action.get("args", {})
    if tool not in VALID_TOOLS:
        return None, f"REJECTED: unknown tool '{tool}'. Valid tools: {VALID_TOOLS}."
    if not isinstance(args, dict):
        return None, "REJECTED: args must be a JSON object, for example {} or {\"name\": \"...\"}."
    if tool == "read_function" and not isinstance(args.get("name"), str):
        return None, 'REJECTED: read_function needs args {"name": "<function name>"}.'
    if tool in NO_ARG_TOOLS and args:
        return None, f"REJECTED: {tool} takes no arguments. Use args {{}}."
    return action, None


def show(label, text):
    text = str(text)
    if len(text) > MAX_SHOWN_CHARS:
        text = text[:MAX_SHOWN_CHARS] + " ...[cut]"
    print(f"  {label}: {text}")


def run_agent(question, project_dir, trace_path=None, verbose=True):
    """Run one episode. Returns a result dict with status, final answer, and full trace."""
    state = AgentState(project_dir)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    trace = []
    status = "max_steps"
    final = None
    outcome = None
    rejected_counts = {}   # rejected action -> how many times it was proposed

    if verbose:
        print(f"\nQUESTION: {question}\nPROJECT:  {project_dir}\n")

    for step in range(1, MAX_STEPS + 1):
        raw = call_model(messages)
        messages.append({"role": "assistant", "content": raw})
        action, error = validate_action(raw)
        record = {"step": step, "raw_reply": raw}

        if action is not None:
            record["thought"] = action.get("thought", "")
            record["tool"] = action["tool"]
            record["args"] = action.get("args", {})

        if verbose:
            print(f"--- step {step} ---")
            if action is None:
                show("model reply", raw)
            else:
                show("thought", record["thought"])
                show("tool call", f"{record['tool']} {json.dumps(record['args'])}")

        accepted = False
        if error:
            observation = error
        elif action["tool"] == "explain":
            accepted, observation, outcome = check_explain(action.get("args", {}), state)
        else:
            observation = TOOLS[action["tool"]](state, action.get("args", {}))
            accepted = True

        record["observation"] = observation
        record["rejected"] = observation.startswith("REJECTED")
        trace.append(record)
        if verbose:
            show("result", observation)

        if action is not None and action["tool"] == "explain" and accepted:
            status = "done"
            final = action["args"]
            break

        # Stuck detection: the same rejected action keeps coming back.
        if record["rejected"]:
            key = json.dumps(record.get("args"), sort_keys=True) if action else raw.strip()
            key = f"{record.get('tool')}:{key}"
            rejected_counts[key] = rejected_counts.get(key, 0) + 1
            if rejected_counts[key] >= STUCK_REPEATS:
                status = "stuck"
                break

        messages.append({"role": "user", "content": "OBSERVATION:\n" + observation})

    result = {
        "question": question,
        "project_dir": str(project_dir),
        "model": MODEL_NAME,
        "status": status,
        "outcome": outcome,
        "steps": len(trace),
        "final": final,
        "trace": trace,
    }
    if trace_path:
        Path(trace_path).parent.mkdir(parents=True, exist_ok=True)
        Path(trace_path).write_text(json.dumps(result, indent=2))
    if verbose:
        print_result(result)
    return result


def print_result(result):
    print("\n================ RESULT ================")
    print(f"status: {result['status']}   steps: {result['steps']}")
    final = result["final"]
    if not final:
        print("The agent did not produce an accepted explanation.")
        return
    if result["outcome"] == "not_found":
        print(f"Function '{final['function']}' was not found in the project.")
        print(f"Agent says: {final['summary']}")
        return
    print(f"function:      {final['function']}")
    print(f"issue level:   {final['issue_level']}")
    print(f"explanation:   {final['summary']}")
    print(f"code cited:    {final['evidence_code']}")
    if final["issue"]:
        print(f"issue:         {final['issue']}")
    if final["evidence_test"]:
        print(f"failing test:  {final['evidence_test']}")
        print(f"test output:   {final['evidence_output']}")
    if final["fix"]:
        print(f"possible fix:  {final['fix']}  (not verified)")
    print("(every citation above was checked by Python against real tool output)")
