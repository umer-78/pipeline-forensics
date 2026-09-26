import json

import pytest

from forensics import gsm
from forensics.analyze import blame, flag, summary
from forensics.trace import Store, Tracer

REC = {"id": "q1", "question": "Ann has 3 apples and buys 4 more. How many apples does she have?", "gold": "7",
       "prompt": "Q: Ann has 3 apples and buys 4 more. How many apples does she have?\nA:", "stop": ["\n\n"],
       "max_tokens": 400, "answer": "She has 3 + 4 = 7 apples. The answer is 7.", "output_tokens": 14, "correct": 1}


def test_stated_answer_formats():
    assert gsm.stated("3 + 4 = 7. The answer is 7.") == "7"
    assert gsm.stated("**Answer:** It will take Jay 5 hours to have 60 snowballs.") == "5"
    assert gsm.stated("Therefore, she has 1,200 left.") == "1200"
    assert gsm.stated("She has 3 + 4 = 7 apples.") is None


def test_clean_trace_and_each_fault_is_blamed_on_its_step():
    assert gsm.trace(REC).status == "success" and blame(gsm.trace(REC)) is None
    wrong = lambda r: {"text": "3 + 4 = 8. The answer is 8.", "tokens": 12}
    cases = {"prompt": {"prompt": lambda r: "Q: \nA:", "generate": wrong},
             "generate": {"generate": lambda r: {"text": "She starts with 3 apples.", "tokens": 6}},
             "extract": {"extract": lambda a: "3"}}
    for step, fault in cases.items():
        t = gsm.trace(REC, fault)
        assert t.status == "failure" and blame(t)[0] == step, step
    t = gsm.trace(REC, {"generate": wrong})
    assert blame(t) == ("generate", "every check passed, but the answer is wrong")
    cut = gsm.trace(REC, {"generate": lambda r: {"text": "She has 3 + 4 =", "tokens": 400}})
    assert "token limit" in blame(cut)[1]


def test_tracer_records_errors_and_the_store_indexes(tmp_path):
    tracer = Tracer()
    trace = tracer.start(doc="d1")

    @tracer.step("parse", check=lambda i, o: "" if o else "empty")
    def parse(x):
        return x.strip()

    @tracer.step("explode")
    def explode(x):
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        explode(parse("  "))
    assert trace.status == "error" and trace.spans[0].problem == "empty" and "bad input" in trace.spans[1].error
    assert blame(trace) == ("parse", "empty")
    store = Store(tmp_path)
    store.add(trace, "parse")
    assert store.failures() == [trace.id] and json.loads((tmp_path / f"{trace.id}.json").read_text())["meta"]["doc"] == "d1"
    flag(trace, "empty document", tmp_path / "eval.jsonl")
    assert json.loads((tmp_path / "eval.jsonl").read_text())["blamed_step"] == "parse"
    assert summary([trace]) == [(("parse", "empty"), 1)]
