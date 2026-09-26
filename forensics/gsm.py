"""A real pipeline to trace: HELM Lite's grade-school maths runs (GSM8K), replayed from the
recorded requests and answers of each model version.

Four steps. prompt: the few-shot prompt built for the question. generate: the model's
answer, under the request's stop sequence and token limit. extract: the final number, as
the harness takes it (the last number in the answer). score: that number against the gold.

Each step's check: the prompt contains the question; the answer is complete (it states a
result after an answer marker such as "the answer is", "Answer:" or "Therefore", and did
not hit the token limit); the extracted number is the one the answer states. Downloaded on first use into FORENSICS_DATA (default ~/.cache/forensics).
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

import yaml

from .trace import Tracer

BUCKET = "https://storage.googleapis.com/crfm-helm-public/lite/benchmark_output/runs"
LISTING = "https://storage.googleapis.com/storage/v1/b/crfm-helm-public/o"
VERSIONS = Path(__file__).with_name("versions.yaml")
NUMBER = re.compile(r"-?[\d,]*\.?\d+")
MARKER = re.compile(r"\banswer\b\W{0,4}(?:is\b)?|\btherefore\b|\bthus\b", re.I)    # where an answer states its result


def versions():
    return yaml.safe_load(VERSIONS.read_text())["versions"]


def get_json(url, path, tries=4):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(tries):
            try:
                with urllib.request.urlopen(url, timeout=300) as r:
                    body = r.read()
                break
            except OSError:
                if attempt == tries - 1:
                    raise
                time.sleep(2 ** attempt)
        path.write_bytes(body)
    return json.loads(path.read_text())


def stated(text):
    """The number an answer states as its result: the first number after its last answer marker."""
    marks = list(MARKER.finditer(text or ""))
    if not marks:
        return None
    found = NUMBER.findall(text[marks[-1].end(): marks[-1].end() + 160])
    return found[0].replace(",", "").rstrip(".") if found else None


def number(text):
    found = NUMBER.findall(text or "")
    return found[-1].replace(",", "").rstrip(".") if found else None


def same(a, b):
    try:
        return a is not None and b is not None and float(a) == float(b)
    except ValueError:
        return False


def cache():
    return Path(os.environ.get("FORENSICS_DATA", Path.home() / ".cache" / "forensics"))


def gsm_run(helm, release):
    """The name of this model's GSM8K run in a release (names carry extra settings in some releases)."""
    names, token = [], None
    while True:
        q = {"prefix": f"lite/benchmark_output/runs/{release}/gsm:", "delimiter": "/", "maxResults": 1000}
        if token:
            q["pageToken"] = token
        page = get_json(f"{LISTING}?{urllib.parse.urlencode(q)}", cache() / "listing" / f"{release}-{token or 0}.json")
        names += [p.rstrip("/").rsplit("/", 1)[1] for p in page.get("prefixes", [])]
        token = page.get("nextPageToken")
        if not token:
            return next(n for n in names if re.search(rf"(?:^|[,:])model={re.escape(helm)}(?:,|$)", n))


@lru_cache(None)
def records(version):
    """[{"id", "question", "gold", "prompt", "stop", "max_tokens", "answer", "output_tokens", "correct"}] as recorded."""
    v = versions()[version]
    run = urllib.parse.quote(gsm_run(v["helm"], v["release"]), safe="")
    base, local = f"{BUCKET}/{v['release']}/{run}", cache() / v["release"] / run
    preds = get_json(f"{base}/display_predictions.json", local / "p.json")
    reqs = {r["instance_id"]: r["request"] for r in get_json(f"{base}/display_requests.json", local / "r.json")}
    insts = {i["id"]: i for i in get_json(f"{base}/instances.json", local / "i.json")}
    out = []
    for p in preds:
        i, r = insts[p["instance_id"]], reqs[p["instance_id"]]
        gold = number(next(ref["output"]["text"] for ref in i["references"] if "correct" in ref["tags"]))
        out.append({"id": p["instance_id"], "question": i["input"]["text"], "gold": gold, "prompt": r["prompt"],
                    "stop": r.get("stop_sequences", []), "max_tokens": r.get("max_tokens"), "answer": p["predicted_text"],
                    "output_tokens": int(p["stats"].get("num_output_tokens", 0)),
                    "correct": int(p["stats"]["final_number_exact_match"] >= 1)})
    return out


def check_prompt(rec, prompt):
    return "" if rec["question"].strip()[-80:] in prompt else "the question is missing from the prompt"


def check_answer(rec, answer):
    if rec["max_tokens"] and answer["tokens"] >= rec["max_tokens"] - 1:
        return f"cut off at the token limit ({rec['max_tokens']})"
    if stated(answer["text"]) is None:
        return f"stopped before stating an answer (the request stops at {rec['stop']!r})"
    return ""


def check_extract(answer, extracted):
    said = stated(answer["text"])
    if said is not None and not same(said, extracted):
        return f"took {extracted}, but the answer states {said}"
    return ""


def trace(rec, faults=None):
    """Replay one question through the traced pipeline. `faults` swaps in broken steps (for the injection test)."""
    faults = faults or {}
    tracer = Tracer()
    t = tracer.start(question=rec["id"])

    @tracer.step("prompt", check=check_prompt)
    def prompt(r):
        return faults.get("prompt", lambda r: r["prompt"])(r)

    @tracer.step("generate", check=lambda p, a: check_answer(rec, a))
    def generate(p):
        return faults.get("generate", lambda r: {"text": r["answer"], "tokens": r["output_tokens"]})(rec)

    @tracer.step("extract", check=check_extract)
    def extract(a):
        return faults.get("extract", lambda a: number(a["text"]))(a)

    @tracer.step("score")
    def score(x):
        return same(x, rec["gold"])

    ok = score(extract(generate(prompt(rec))))
    t.status = "success" if (ok if faults else rec["correct"]) else "failure"
    return t
