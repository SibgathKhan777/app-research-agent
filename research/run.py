"""CLI: python -m research.run --app notion | --first 5 | --all"""
from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config
from .discover import discover
from .extract import QuotaExhausted, extract


def research_app(app: dict, model: str | None = None, verbose: bool = True) -> dict:
    t0 = time.time()
    model = model or config.model_for(app["n"])
    pages = discover(app)
    # keep the exact texts the agent read, so grounding checks and human review see the same thing
    (config.DATA / "pages").mkdir(exist_ok=True)
    (config.DATA / "pages" / f"{app['id']}.json").write_text(json.dumps(pages, ensure_ascii=False))
    rec = extract(app, pages, model=model)
    rec["_trace"] = {
        "seconds": round(time.time() - t0, 1),
        "pages": [{"url": p["url"], "official": p["official"], "found_by": p["found_by"], "chars": len(p["text"])} for p in pages],
    }
    if verbose:
        print(f"[{app['n']:>3}] {app['name']:<28} pages={len(pages):<2} auth={rec['auth_methods']['value']} "
              f"tier={rec['access_tier']['value']} build={rec['buildability']['value']} [{rec['extract_model'].split('/')[-1]}] ({rec['_trace']['seconds']}s)", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--app", help="app id or name, e.g. notion")
    g.add_argument("--first", type=int)
    g.add_argument("--all", action="store_true")
    g.add_argument("--ids", help="comma-separated app ids")
    g.add_argument("--custom", help='any app, not in apps.yaml: "Name|domain.com" e.g. "Linear|linear.app"')
    g.add_argument("--from", dest="start", type=int, help="resume: every app from number N to the end")
    ap.add_argument("--out", default=str(config.DATA / "pass1.jsonl"))
    ap.add_argument("--workers", type=int, default=1, help="apps researched in parallel")
    args = ap.parse_args()

    apps = config.load_apps()
    if args.app:
        a = args.app.lower()
        apps = [x for x in apps if x["id"] == a or x["name"].lower() == a]
    elif args.first:
        apps = apps[: args.first]
    elif args.custom:
        name, domain = [x.strip() for x in args.custom.split("|", 1)]
        slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
        apps = [{"n": 901, "id": slug, "name": name, "category": "Custom", "hint": domain, "note": "", "domains": [domain]}]
        args.out = str(config.DATA / f"custom_{slug}.jsonl")
    elif args.start:
        apps = [x for x in apps if x["n"] >= args.start]
    elif args.ids:
        want = args.ids.split(",")
        apps = [x for x in apps if x["id"] in want]

    done = {}
    try:
        for line in open(args.out):
            r = json.loads(line)
            done[r["id"]] = r
    except FileNotFoundError:
        pass
    spent: set[str] = set()  # models whose daily quota ran out during this run
    lock = threading.Lock()

    def save():
        with open(args.out, "w") as f:
            for r in sorted(done.values(), key=lambda r: r["n"]):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def one(app):
        model = config.model_for(app["n"])
        if model in spent:
            print(f"[{app['n']:>3}] {app['name']} SKIPPED: {model} quota spent, rerun later", flush=True)
            return
        try:
            rec = research_app(app, model=model)
        except QuotaExhausted as e:
            spent.add(model)
            print(f"[{app['n']:>3}] {app['name']} SKIPPED: {e}", flush=True)
            return
        except Exception as e:
            print(f"[{app['n']:>3}] {app['name']} FAILED: {e}", flush=True)
            return
        with lock:
            old = done.get(app["id"])
            if old and old.get("extract_model", "openai/gpt-oss-120b") != rec["extract_model"]:
                # same app, other model: keep it as a free cross-model comparison
                old.setdefault("extract_model", "openai/gpt-oss-120b")
                with open(config.DATA / "pass1_offblock.jsonl", "a") as f:
                    f.write(json.dumps(old, ensure_ascii=False) + "\n")
            done[app["id"]] = rec
            save()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, apps))


if __name__ == "__main__":
    main()
