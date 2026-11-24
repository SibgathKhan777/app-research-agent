"""Print, per app and field, whether each evidence quote is found in the page the agent read.

python -m verification.grounding_report data/pass1.jsonl [--quiet]
"""
import json
import sys

from research import config
from research.grounding import quote_in_page
from research.schema import FIELDS


def page_texts(app_id: str) -> dict:
    p = config.DATA / "pages" / f"{app_id}.json"
    return {x["url"]: x["text"] for x in json.loads(p.read_text())} if p.exists() else {}


def report(path: str, quiet: bool = False):
    tot = grounded = unknown = 0
    for line in open(path):
        r = json.loads(line)
        texts = page_texts(r["id"])
        if not quiet:
            print(f"\n== {r['name']}  docs={r.get('docs_url')}")
        for f in FIELDS:
            c = r[f]
            ev = c["evidence"]
            if c["value"] in ("unknown", None, []) or not ev:
                unknown += 1
                mark = "unknown/no-evidence"
            else:
                tot += 1
                ok = quote_in_page(ev[0]["quote"], texts.get(ev[0]["url"], ""))
                grounded += ok
                mark = "GROUNDED" if ok else "NOT-IN-PAGE"
            if not quiet:
                q = ev[0]["quote"][:80] if ev else ""
                print(f"   {f:<13} {str(c['value'])[:42]:<42} {mark:<19} {q}")
    print(f"\nquotes grounded: {grounded}/{tot}   unknown/no-evidence fields: {unknown}")


if __name__ == "__main__":
    report(sys.argv[1], quiet="--quiet" in sys.argv)
