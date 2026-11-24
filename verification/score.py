"""Score pass files against the reference labels, per field, on the review sample.

python -m verification.score data/pass1_frozen.jsonl data/pass2.jsonl  -> data/scores.json + table

A prediction of "unknown" counts as wrong (it is an honest gap, but still a miss for a
toolkit engineer); `coverage` reports how many fields were answered at all.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict

from research import config
from research.schema import FIELDS

UNKNOWN = ("unknown", "", None)
LIST_FIELDS = {"auth_methods", "api_styles"}


def load_labels(path=None) -> dict:
    path = path or config.ROOT / "verification" / "human_labels.csv"
    labels: dict = defaultdict(dict)
    for row in csv.DictReader(open(path)):
        split = lambda s: [x for x in s.split("|") if x]
        labels[row["app_id"]][row["field"]] = {
            "status": row["status"], "ok": split(row["ok"]), "req": split(row["req"]), "allow": split(row["allow"]),
            "url": row["evidence_url"], "note": row["note"], "audit": row.get("audit", ""),
        }
    return labels


def norm_val(v) -> str:
    return str(v).strip().lower()


def is_correct(field: str, pred, label: dict, pass1_pred=None) -> bool:
    if field in LIST_FIELDS:
        p = pred if isinstance(pred, list) else ([] if pred in UNKNOWN else [pred])
        p = {norm_val(x) for x in p if norm_val(x) not in ("unknown", "")}
        if not p:
            return False
        req, allow = {norm_val(x) for x in label["req"]}, {norm_val(x) for x in label["allow"]}
        return req <= p <= (req | allow)
    if norm_val(pred) in ("unknown", "", "none") and field != "main_blocker":
        return False
    if field == "one_liner":
        # judged on the pass-1 text; a changed one-liner must be re-judged by hand
        return "accurate" in label["ok"] and (pass1_pred is None or pred == pass1_pred)
    return norm_val(pred) in {norm_val(x) for x in label["ok"]}


def score(pass_path: str, labels: dict, pass1: dict | None = None) -> dict:
    recs = {r["id"]: r for r in map(json.loads, open(pass_path))}
    per = {f: {"correct": 0, "total": 0, "answered": 0} for f in FIELDS}
    misses = []
    for app, fields in labels.items():
        r = recs[app]
        for f, lab in fields.items():
            if lab["status"] != "labeled":
                continue
            pred = r[f]["value"]
            ok = is_correct(f, pred, lab, (pass1 or {}).get(app, {}).get(f))
            per[f]["total"] += 1
            per[f]["correct"] += ok
            per[f]["answered"] += norm_val(pred) not in ("unknown", "", "[]")
            if not ok:
                misses.append({"app": app, "name": r["name"], "field": f, "pred": pred,
                               "truth": lab["ok"] or {"req": lab["req"], "allow": lab["allow"]},
                               "evidence_url": lab["url"], "note": lab["note"]})
    tot_c = sum(v["correct"] for v in per.values())
    tot = sum(v["total"] for v in per.values())
    return {"file": pass_path, "overall": {"correct": tot_c, "total": tot, "accuracy": round(tot_c / tot, 4) if tot else 0},
            "per_field": {f: {**v, "accuracy": round(v["correct"] / v["total"], 4) if v["total"] else None} for f, v in per.items()},
            "misses": misses}


def main(paths: list[str]):
    labels = load_labels()
    p1 = {r["id"]: {f: r[f]["value"] for f in FIELDS} for r in map(json.loads, open(paths[0]))}
    results = [score(p, labels, p1) for p in paths]
    print(f"{'field':<14}" + "".join(f"{p.split('/')[-1][:18]:>20}" for p in paths))
    for f in FIELDS:
        print(f"{f:<14}" + "".join(f"{r['per_field'][f]['correct']:>8}/{r['per_field'][f]['total']:<3}{(r['per_field'][f]['accuracy'] or 0):>7.0%}  " for r in results))
    print(f"{'OVERALL':<14}" + "".join(f"{r['overall']['correct']:>8}/{r['overall']['total']:<3}{r['overall']['accuracy']:>7.1%}  " for r in results))
    (config.DATA / "scores.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))
    return results


if __name__ == "__main__":
    main(sys.argv[1:] or [str(config.DATA / "pass1_frozen.jsonl")])
