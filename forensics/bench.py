"""Forensics on every model version's GSM8K failures, on the regression Gemini 1.5 Flash 002
shipped with, and an injection test of the analyzer itself."""
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

from . import gsm
from .analyze import blame

RESULTS = Path(__file__).resolve().parent.parent / "results"
KINDS = ["stopped before stating an answer", "hit the token limit", "extracted the wrong number",
         "wrong answer (every check passed)", "prompt lost the question"]


def kind(b):
    step, problem = b
    if step == "prompt":
        return "prompt lost the question"
    if problem.startswith("cut off at the token limit"):
        return "hit the token limit"
    if problem.startswith("stopped before"):
        return "stopped before stating an answer"
    if step == "extract":
        return "extracted the wrong number"
    return "wrong answer (every check passed)"


def per_version():
    rows = []
    for v in gsm.versions():
        recs = gsm.records(v)
        fails = [t for t in map(gsm.trace, recs) if t.status == "failure"]
        rows.append({"version": v, "accuracy": float(np.mean([r["correct"] for r in recs])), "failures": len(fails),
                     "stop": recs[0]["stop"], "blame": dict(Counter(kind(blame(t)) for t in fails))})
    return rows


def regression(base="gemini-1.5-flash-001", candidate="gemini-1.5-flash-002"):
    b = {r["id"]: r for r in gsm.records(base)}
    broke = [r for r in gsm.records(candidate) if r["id"] in b and b[r["id"]]["correct"] and not r["correct"]]
    counts = Counter(kind(blame(gsm.trace(r))) for r in broke)
    examples = [{"answer": r["answer"], "then": b[r["id"]]["answer"][-120:]} for r in broke[:3]]
    return {"base": base, "candidate": candidate, "broke": len(broke), "blame": dict(counts), "examples": examples,
            "stop": {"base": next(iter(b.values()))["stop"], "candidate": broke[0]["stop"] if broke else None}}


def injection(version="gpt-4o-2024-08-06", n=200, seed=0):
    """Break one step of a correct trace in a known way; does the analyzer point at it?"""
    recs = [r for r in gsm.records(version) if r["correct"] and gsm.stated(r["answer"]) is not None]
    recs = [recs[i] for i in np.random.default_rng(seed).permutation(len(recs))[:n]]
    wrong = lambda r: {"text": r["answer"] + f" So the answer is {int(float(r['gold'])) + 7}.", "tokens": r["output_tokens"]}
    first_number = lambda a: (gsm.NUMBER.findall(a["text"]) or [None])[0]
    faults = {
        "prompt lost the question": ({"prompt": lambda r: r["prompt"].replace(r["question"].strip()[-80:], ""), "generate": wrong}, None),
        "stopped before stating an answer": ({"generate": lambda r: {"text": gsm.MARKER.split(r["answer"])[0].rsplit(". ", 1)[0],
                                                                     "tokens": r["output_tokens"] // 2}}, None),
        "hit the token limit": ({"generate": lambda r: {"text": r["answer"][: len(r["answer"]) // 2], "tokens": r["max_tokens"]}}, None),
        "extracted the wrong number": ({"extract": first_number},
                                       lambda r: not gsm.same(first_number({"text": r["answer"]}), gsm.number(r["answer"]))),
        "wrong answer (every check passed)": ({"generate": wrong}, None),
    }
    out = {}
    for expected, (fault, applies) in faults.items():
        cases = [r for r in recs if applies is None or applies(r)]
        traces = [gsm.trace(r, fault) for r in cases]
        failed = [t for t in traces if t.status == "failure"]
        out[expected] = {"injected": len(cases), "failed": len(failed),
                         "blamed_right": sum(kind(blame(t)) == expected for t in failed)}
    return out


def bench():
    rows, reg, inj = per_version(), regression(), injection()
    pct = lambda k, n: f"{100 * k / n:.0f}%" if n else "—"
    lines = ["## Where each version's GSM8K failures come from", "",
             "| Version | Stop sequence | Accuracy | Failures | " + " | ".join(KINDS[:4]) + " |", "|---|---|---|---|" + "---|" * 4]
    for r in rows:
        lines.append(f"| {r['version']} | {json.dumps(r['stop'])[1:-1] or 'none'} | {100 * r['accuracy']:.1f}% | {r['failures']} | "
                     + " | ".join(pct(r["blame"].get(k, 0), r["failures"]) for k in KINDS[:4]) + " |")
    lines += ["", f"## The {reg['base']} → {reg['candidate']} regression", "",
              f"{reg['broke']} questions broke (right before, wrong after). Blamed on:", ""]
    lines += [f"- {k}: {v} ({pct(v, reg['broke'])})" for k, v in sorted(reg["blame"].items(), key=lambda kv: -kv[1])]
    lines += ["", f"Stop sequence: {reg['base']} {reg['stop']['base'] or 'none'}, {reg['candidate']} {reg['stop']['candidate']!r}. "
              "Broken answers, in full:", ""]
    lines += [f"- {json.dumps(e['answer'])}" for e in reg["examples"]]
    lines += ["", "## Injection test: one step broken on purpose (200 correct GPT-4o traces)", "",
              "| Fault injected | Traces | Failed | Blamed on the right step and problem |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['injected']} | {v['failed']} | {v['blamed_right']} ({pct(v['blamed_right'], v['failed'])}) |" for k, v in inj.items()]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "bench.md").write_text("\n".join(lines) + "\n")
    (RESULTS / "summary.json").write_text(json.dumps({"versions": rows, "regression": reg, "injection": inj}, indent=1))
    return "\n".join(lines)
