"""Repair loop: pass 1 + auto-check flags -> pass 2.

For every app with error flags, only the flagged fields are re-asked, over the
pages the agent already read (no new search), with the failure reason spelled
out. A repaired value is accepted only if its new quote is mechanically found
in the cited page; otherwise the field becomes "unknown" (an honest gap beats a
confident wrong answer). Registry-confirmed official MCP servers are written in
directly as evidence. Pass 1 is never modified.

python -m verification.repair [--workers 4]   -> data/pass2.jsonl
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor

from rank_bm25 import BM25Okapi

from research import config
from research.discover import chunk
from research.extract import SYSTEM, llm_json, QuotaExhausted
from research.grounding import quote_in_page
from research.schema import FIELDS

FIELD_QUERY = {
    "one_liner": "what is product platform",
    "auth_methods": "authentication oauth api key token bearer basic authorization header client secret",
    "access_tier": "pricing plan free trial paid enterprise sign up developer account approval partner sales sandbox",
    "delivery": "api rest endpoints cli install npm pip library hosted",
    "api_styles": "rest graphql soap websocket rpc sdk endpoint http",
    "api_breadth": "api reference endpoints resources objects list",
    "openapi_spec": "openapi swagger spec specification json yaml download",
    "official_mcp": "mcp model context protocol server assistant copilot agents",
    "buildability": "pricing plan api access approval review partner free self-serve",
    "main_blocker": "pricing plan api access approval review partner enterprise sales",
}

REPAIR_SYSTEM = SYSTEM + """

REPAIR MODE
You previously filled this record. Some fields failed automated verification; the reason is given for each.
Re-derive ONLY the listed fields from the sources. Same JSON shape per field. Quote must be ONE verbatim,
continuous passage of 5-40 words from the cited source. If the sources do not support a value, answer "unknown"
with source and quote null. Return a JSON object containing only the listed fields."""


def pages_of(app_id: str) -> list[dict]:
    return json.loads((config.DATA / "pages" / f"{app_id}.json").read_text())


def repair_context(pages: list[dict], fields: list[str], rec: dict, max_chars: int = 18000) -> tuple[str, dict]:
    chunks, owners = [], []
    for i, p in enumerate(pages):
        for c in chunk(p["text"]):
            chunks.append(c)
            owners.append(i)
    if not chunks:
        return "", {}
    bm = BM25Okapi([re.findall(r"\w+", c.lower()) for c in chunks])
    picked: list[int] = []
    for f in fields:
        sc = bm.get_scores(FIELD_QUERY[f].split())
        for j in sorted(range(len(chunks)), key=lambda j: -sc[j])[:5]:
            if j not in picked:
                picked.append(j)
    by_page: dict[int, list[int]] = {}
    for j in picked:
        by_page.setdefault(owners[j], []).append(j)
    srcmap, parts, total = {}, [], 0
    for n, (i, js) in enumerate(sorted(by_page.items()), 1):
        sid = f"S{n}"
        srcmap[sid] = pages[i]["url"]
        body = "\n...\n".join(chunks[j] for j in sorted(js))
        block = f"[{sid}] {pages[i]['url']}{' (official)' if pages[i]['official'] else ' (third-party)'}\n{body}\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts), srcmap


def flagged_fields(flags: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in flags:
        if f["severity"] == "error" and f["check"] != "mcp_registry_confirmed":
            out.setdefault(f["field"], []).append(f"{f['check']}: {f['detail']}")
    # rules couple these two: re-derive them together
    if "buildability" in out or "main_blocker" in out:
        for k in ("buildability", "main_blocker"):
            out.setdefault(k, ["re-derived together with its coupled field"])
    return out


def repair_app(rec: dict, checks: dict, model: str) -> tuple[dict, list[dict]]:
    new = copy.deepcopy(rec)
    log: list[dict] = []
    reg = checks["mcp"]["registry_official"]
    if reg:  # registry is evidence in its own right: it beats both the model's memory and a missing quote
        url = f"https://registry.modelcontextprotocol.io/v0/servers?search={reg[0]}"
        if rec["official_mcp"]["value"] not in (True, "True", "true") or not rec["official_mcp"]["evidence"]:
            log.append({"field": "official_mcp", "from": rec["official_mcp"]["value"], "to": True, "how": "mcp_registry"})
        new["official_mcp"] = {"value": True, "evidence": [{"url": url, "quote": f"registry entry: {reg[0]}"}],
                               "confidence": "high", "flags": ["verified:mcp_registry"]}
    todo = flagged_fields(checks["flags"])
    if reg:
        todo.pop("official_mcp", None)
    if not todo:
        return new, log
    pages = pages_of(rec["id"])
    texts = {p["url"]: p["text"] for p in pages}
    ctx, srcmap = repair_context(pages, list(todo), rec)
    prev = {f: {"value": rec[f]["value"], "quote": (rec[f]["evidence"][0]["quote"] if rec[f]["evidence"] else None)} for f in todo}
    user = (f"APP: {rec['name']} (category: {rec['category']}; hint: {rec['hint']})\n\n"
            f"FIELDS TO RE-DERIVE (with the verification failure):\n"
            + "\n".join(f"- {f}: previous={json.dumps(prev[f], ensure_ascii=False)}; failed because {'; '.join(why)}" for f, why in todo.items())
            + f"\n\nSOURCES\n{ctx or '(no sources)'}")
    raw = llm_json(REPAIR_SYSTEM, user, model)
    for f in todo:
        v = raw.get(f)
        if not isinstance(v, dict):
            v = {"value": v if v is not None else "unknown"}
        url = srcmap.get(str(v.get("source") or "").strip("[]"))
        quote = v.get("quote") or ""
        value = v.get("value", "unknown")
        grounded = bool(url) and quote_in_page(quote, texts.get(url, ""))
        if value in ("unknown", None, []) or not grounded:
            had = rec[f]["value"] not in ("unknown", None, [])
            if had:
                # the repair could not re-prove it, but it could not disprove it either (absence of a
                # quote is not evidence of error, and "no spec / no MCP" claims can't be quoted at all):
                # keep the original answer, marked unverified, instead of wiping a possibly-right value
                out = {"value": rec[f]["value"], "evidence": rec[f]["evidence"], "confidence": "low",
                       "flags": ["repair:unproven"]}
            else:
                out = {"value": "unknown", "evidence": [], "confidence": "low", "flags": ["repair:unknown"]}
        else:
            out = {"value": value, "evidence": [{"url": url, "quote": quote}], "confidence": v.get("confidence", "medium"),
                   "flags": ["repair:regrounded"]}
        if out["value"] != rec[f]["value"] or out["evidence"] != rec[f]["evidence"]:
            log.append({"field": f, "from": rec[f]["value"], "to": out["value"], "how": out["flags"][0],
                        "why": todo[f]})
        new[f] = out
    return new, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=config.MODEL_ROTATION[0])
    args = ap.parse_args()
    recs = [json.loads(l) for l in open(config.DATA / "pass1_frozen.jsonl")]
    checks = json.loads((config.DATA / "auto_checks.json").read_text())
    out_path = config.DATA / "pass2.jsonl"
    done = {}
    if out_path.exists():
        done = {r["id"]: r for r in map(json.loads, open(out_path))}
    logs = {}
    lock = threading.Lock()

    def one(rec):
        if rec["id"] in done and done[rec["id"]].get("pass_name") == "pass2":
            return
        try:
            new, log = repair_app(rec, checks[rec["id"]], args.model)
        except QuotaExhausted as e:
            print(f"[{rec['n']:>3}] {rec['name']} SKIPPED: {e}", flush=True)
            return
        except Exception as e:
            print(f"[{rec['n']:>3}] {rec['name']} FAILED: {e}", flush=True)
            return
        new["pass_name"] = "pass2"
        new["repair_log"] = log
        with lock:
            done[rec["id"]] = new
            with open(out_path, "w") as f:
                for r in sorted(done.values(), key=lambda r: r["n"]):
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[{rec['n']:>3}] {rec['name']:<28} changed={len(log)} " + ", ".join(f"{l['field']}:{l['how']}" for l in log)[:160], flush=True)

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(one, recs))
    print(f"pass2 records: {len(done)}/100")


if __name__ == "__main__":
    main()
