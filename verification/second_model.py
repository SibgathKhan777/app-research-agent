"""Independent cross-check: a second model (different provider) re-extracts the same pages.

Fields where the two models disagree are flagged; scoring later shows whether
disagreement actually predicts errors (it is cheap, so it is worth knowing).

python -m verification.second_model [--ids a,b | --sample]  -> data/xcheck.jsonl
"""
from __future__ import annotations

import argparse
import json

from research import config
from research.extract import QuotaExhausted, extract
from research.schema import FIELDS


def same(f, a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return {str(x).lower() for x in (a or [])} == {str(x).lower() for x in (b or [])}
    return str(a).lower() == str(b).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--model", default=config.SECOND_MODEL)
    args = ap.parse_args()
    apps = {a["id"]: a for a in config.load_apps()}
    ids = json.loads((config.ROOT / "verification" / "sample.json").read_text())["ids"] if args.sample else args.ids.split(",")
    out = config.DATA / "xcheck.jsonl"
    done = {r["id"]: r for r in map(json.loads, open(out))} if out.exists() else {}
    for i in ids:
        if i in done:
            continue
        pages = json.loads((config.DATA / "pages" / f"{i}.json").read_text())
        try:
            rec = extract(apps[i], pages, model=args.model, pass_name="xcheck")
        except QuotaExhausted as e:
            print(f"{i}: SKIPPED {e}")
            break
        except Exception as e:
            print(f"{i}: FAILED {e}")
            continue
        done[i] = rec
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()))
        print(f"{i}: ok")
    base = {r["id"]: r for r in map(json.loads, open(config.DATA / "pass1_frozen.jsonl"))}
    dis = {i: [f for f in FIELDS[1:] if not same(f, base[i][f]["value"], r[f]["value"])] for i, r in done.items()}
    (config.DATA / "xcheck_disagreements.json").write_text(json.dumps(dis, indent=1))
    n = sum(len(v) for v in dis.values())
    print(f"cross-checked {len(done)} apps; {n} field disagreements over {len(done) * (len(FIELDS) - 1)} fields")


if __name__ == "__main__":
    main()
