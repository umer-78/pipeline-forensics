"""Backward analysis: where did a bad output come from?

Walk the spans back from the final output. The origin is the earliest step whose own check
failed: everything after it is a symptom. When every step's check passed and the output is
still wrong, the fault is in content the checks can't judge; it is blamed on the model step
(and its confidence, if it gave one, is reported).
"""
from collections import Counter


def blame(trace, model_step="generate"):
    """(step, problem) for a failed trace; None if the trace succeeded."""
    if trace.status == "success":
        return None
    for span in trace.spans:
        if not span.ok:
            return span.step, span.problem or span.error
    s = next((s for s in trace.spans if s.step == model_step), None)
    note = f" (model confidence {s.confidence})" if s is not None and s.confidence is not None else ""
    return model_step, "every check passed, but the answer is wrong" + note


def summary(traces):
    """Blamed step and problem across failed traces, most common first."""
    return Counter(b for b in map(blame, traces) if b).most_common()


def flag(trace, note, path):
    """Human feedback: add a bad trace to the growing evaluation set (JSON lines)."""
    import json
    first, last = trace.spans[0], trace.spans[-1]
    step, problem = blame(trace) or ("", "")
    with open(path, "a") as f:
        f.write(json.dumps({"trace": trace.id, "input": first.input, "bad_output": last.output, "blamed_step": step,
                            "problem": problem, "note": note, **trace.meta}, default=str) + "\n")
