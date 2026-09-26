"""Traces: every run of a pipeline is a trace, every step a span.

A span records the step's input, output, how long it took, token counts, the model's own
confidence if it gave one, any error, and the result of the step's check: a small function
that says whether this step's output is sound, whatever happens downstream. Instrumenting a
step is one decorator. Traces are written as JSON files and indexed in SQLite.
"""
import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Span:
    step: str
    input: object = None
    output: object = None
    ok: bool = True               # the step's own check
    problem: str = ""             # what the check found
    error: str = ""
    seconds: float = 0.0
    tokens: dict = field(default_factory=dict)
    confidence: float = None


@dataclass
class Trace:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    spans: list = field(default_factory=list)
    status: str = "success"       # success, failure (final output wrong) or error
    meta: dict = field(default_factory=dict)

    def span(self, step):
        return next(s for s in self.spans if s.step == step)


class Tracer:
    """@tracer.step("extract", check=fn) wraps a step; fn(input, output) returns "" if sound, else the problem."""

    def __init__(self):
        self.current = None

    def start(self, **meta):
        self.current = Trace(meta=meta)
        return self.current

    def step(self, name, check=None):
        def wrap(fn):
            def run(value, **kw):
                span = Span(name, input=value)
                start = time.perf_counter()
                try:
                    out = fn(value, **kw)
                    span.output = out
                    if check:
                        span.problem = check(value, out) or ""
                        span.ok = not span.problem
                    return out
                except Exception as e:
                    span.ok, span.error = False, f"{type(e).__name__}: {e}"
                    self.current.status = "error"
                    raise
                finally:
                    span.seconds = time.perf_counter() - start
                    self.current.spans.append(span)
            return run
        return wrap


class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.folder / "index.db")
        self.db.execute("CREATE TABLE IF NOT EXISTS traces (id TEXT PRIMARY KEY, at REAL, status TEXT, blamed TEXT, meta TEXT)")

    def add(self, trace, blamed=""):
        (self.folder / f"{trace.id}.json").write_text(json.dumps(asdict(trace), default=str, indent=1))
        self.db.execute("INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?)",
                        (trace.id, time.time(), trace.status, blamed, json.dumps(trace.meta, default=str)))
        self.db.commit()

    def failures(self):
        return [r[0] for r in self.db.execute("SELECT id FROM traces WHERE status != 'success' ORDER BY at")]
