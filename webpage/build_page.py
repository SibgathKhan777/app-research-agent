"""Render docs/index.html (+ data files) from the computed JSON. No numbers are typed here.

python -m webpage.build_page [--repo https://github.com/OWNER/NAME]
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil

from research import config
from research.grounding import quote_in_page
from research.schema import FIELDS
from verification.grounding_report import page_texts

DOCS = config.ROOT / "docs"
TRUE = (True, "True", "true")


def evidence_rate(path) -> tuple[int, int]:
    g = t = 0
    for r in map(json.loads, open(path)):
        tx = page_texts(r["id"])
        for f in FIELDS:
            c, ev = r[f], r[f]["evidence"]
            if c["value"] in ("unknown", None, []) or not ev:
                continue
            t += 1
            if "verified:mcp_registry" in c["flags"] or (quote_in_page(ev[0]["quote"], tx.get(ev[0]["url"], "")) and "repair:unproven" not in c["flags"]):
                g += 1
    return g, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="https://github.com/OWNER/app-research-agent")
    ap.add_argument("--pages", default="")
    args = ap.parse_args()

    rows = json.loads((config.DATA / "results.json").read_text())
    P = json.loads((config.DATA / "patterns.json").read_text())
    scores = json.loads((config.DATA / "scores.json").read_text())
    summ = json.loads((config.DATA / "phase3_summary.json").read_text())
    manifest = json.loads((config.DATA / "pass1_frozen.manifest.json").read_text())
    g1, t1 = evidence_rate(config.DATA / "pass1_frozen.jsonl")
    g2, t2 = evidence_rate(config.DATA / "pass2.jsonl")
    sample = json.loads((config.ROOT / "verification" / "sample.json").read_text())

    names = {r["id"]: r["name"] for r in rows}
    data = {
        "rows": [{k: v for k, v in r.items() if not k.endswith("_flags")} for r in rows],
        "patterns": P,
        "fields": FIELDS,
        "variants": summ["variants"],
        "per_field": {v["name"]: s["per_field"] for v, s in zip(summ["variants"], scores)},
        "misses": scores[2]["misses"],
        "sample": [names[i] for i in sample["ids"]],
        "evidence": {"p1": [g1, t1], "p2": [g2, t2]},
        "audit": summ["audit"],
        "labelled": summ["fields_labelled"],
        "frozen": {"sha": manifest["sha256"][:12], "at": manifest["frozen_at"][:10]},
        "repo": args.repo,
        "pages": args.pages,
    }
    html = (config.ROOT / "webpage" / "template.html").read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    DOCS.mkdir(exist_ok=True)
    (DOCS / "data").mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html)
    (DOCS / ".nojekyll").write_text("")

    # agent-consumable data
    (DOCS / "data" / "results.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    cols = ["n", "name", "category", "access_tier", "buildability", "main_blocker", "auth_methods", "delivery", "api_styles",
            "api_breadth", "openapi_spec", "official_mcp", "in_composio", "docs_url", "one_liner", "notes"]
    with open(DOCS / "data" / "results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([("|".join(r[c]) if isinstance(r[c], list) else r[c]) for c in cols])
    shutil.copy(config.ROOT / "verification" / "human_labels.csv", DOCS / "data" / "human_labels.csv")
    (DOCS / "data" / "patterns.json").write_text(json.dumps(P, indent=1, ensure_ascii=False))
    (DOCS / "data" / "accuracy.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False))
    (DOCS / "llms.txt").write_text(
        "# Integration-readiness research: 100 apps\n\n"
        "> For each of 100 SaaS and developer apps: auth methods, self-serve vs gated access, API surface, MCP, "
        "buildability verdict and the main blocker, each with an evidence URL and verbatim quote.\n\n"
        "- [results.json](data/results.json): full records with per-field evidence\n"
        "- [results.csv](data/results.csv): flat table\n"
        "- [patterns.json](data/patterns.json): cross-app counts\n"
        "- [human_labels.csv](data/human_labels.csv): hand-checked reference labels for the 20-app sample\n"
        "- [accuracy.json](data/accuracy.json): measured accuracy per variant\n\n"
        f"Accuracy: see index.html. Hand-checked sample accuracy {summ['variants'][-1]['accuracy']:.1%} on {summ['fields_labelled']} fields (n=20 apps); "
        "values are claims with evidence, not guarantees.\n")
    print("built", DOCS / "index.html", f"({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
