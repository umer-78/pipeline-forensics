"""python -m forensics.demo   write the live demo's data (docs/data.json) from results/summary.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(out=ROOT / "docs"):
    summary = json.loads((ROOT / "results" / "summary.json").read_text())
    out.mkdir(exist_ok=True)
    (out / "data.json").write_text(json.dumps(summary, indent=1))
    print(f"wrote {out / 'data.json'}: {len(summary['versions'])} versions")


if __name__ == "__main__":
    build()
