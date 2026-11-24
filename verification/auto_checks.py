"""Automated verification loops over a pass file. No LLM, no search credits.

  1. grounding   - evidence quote must occur in the page the agent read
  2. rules       - cross-field consistency (a record must not contradict itself)
  3. support     - the quote / pages must actually mention what the value claims
  4. links       - evidence URL is live and on the vendor's own domain
  5. mcp         - official MCP registry lookup + Composio toolkit list, never model memory

python -m verification.auto_checks data/pass1_frozen.jsonl   -> data/auto_checks.json
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx

from research import config
from research.discover import UA, is_official
from research.grounding import norm, quote_in_page
from research.schema import FIELDS

UNKNOWN = ("unknown", None, [], "")

AUTH_TERMS = {
    "oauth2": r"oauth",
    "api_key": r"api[ _-]?key|api[ _-]?token|access token|personal access token|private app|secret key|token",
    "basic": r"basic auth|basic authentication|http basic|username and password|username:password|basic",
    "bearer_token": r"bearer",
    "jwt": r"\bjwt\b|json web token",
    "session_login": r"session|cookie|log ?in",
}
SUPPORT_TERMS = {
    "access_tier": r"free|\$0|no cost|trial|plan|pricing|price|paid|subscription|sales|approv|review|partner|sandbox|sign ?up|developer account|enterprise|request access|apply|install",
    "openapi_spec": r"openapi|swagger",
    "official_mcp": r"\bmcp\b|model context protocol",
    "api_styles": r"rest|graphql|soap|rpc|websocket|sdk|endpoint|http",
}


def page_texts(app_id: str) -> dict:
    p = config.DATA / "pages" / f"{app_id}.json"
    return {x["url"]: x["text"] for x in json.loads(p.read_text())} if p.exists() else {}


def flag(out, field, check, detail, severity="error"):
    out.append({"field": field, "check": check, "severity": severity, "detail": detail})


# ---------- 1 + 3: grounding and support ----------

def check_quotes(r: dict, texts: dict, out: list):
    for f in FIELDS:
        c = r[f]
        if c["value"] in UNKNOWN or not c["evidence"]:
            if f not in ("openapi_spec",):  # unknown is an honest answer, but worth a look
                flag(out, f, "unknown", "no supported value", "info")
            continue
        ev = c["evidence"][0]
        if not quote_in_page(ev["quote"], texts.get(ev["url"], "")):
            flag(out, f, "grounding", f"quote not found in {ev['url']}")
        pat = SUPPORT_TERMS.get(f)
        if pat and c["value"] not in (False, "False") and not re.search(pat, norm(ev["quote"])):
            sev = "error" if f in ("official_mcp", "openapi_spec") else "warn"  # true-claims need a literal mention
            flag(out, f, "support", f"quote does not mention {f.replace('_', ' ')}: {ev['quote'][:90]!r}", sev)
    # every claimed auth method must be mentioned somewhere in the official pages read
    methods = r["auth_methods"]["value"] if isinstance(r["auth_methods"]["value"], list) else []
    corpus = norm(" ".join(t for u, t in texts.items() if is_official(u, r.get("_domains", []))))
    for m in methods:
        if m in AUTH_TERMS and not re.search(AUTH_TERMS[m], corpus):
            flag(out, "auth_methods", "support", f"'{m}' claimed but never mentioned in the official pages read")


# ---------- 2: consistency rules ----------

def check_rules(r: dict, out: list):
    v = {f: r[f]["value"] for f in FIELDS}
    b, mb, tier, dl = v["buildability"], v["main_blocker"], v["access_tier"], v["delivery"]
    if b == "ready" and mb not in ("none",):
        flag(out, "main_blocker", "rule", f"buildability=ready but main_blocker={mb}")
    if b in ("ready_with_friction", "blocked") and mb == "none":
        flag(out, "main_blocker", "rule", f"buildability={b} but main_blocker=none")
    if tier in ("contact_sales", "partner_gated") and b == "ready":
        flag(out, "buildability", "rule", f"access_tier={tier} but buildability=ready")
    if tier == "paid_plan" and b == "ready":
        flag(out, "buildability", "rule", "access_tier=paid_plan but buildability=ready", "warn")
    if dl == "no_public_api" and b != "blocked":
        flag(out, "buildability", "rule", f"delivery=no_public_api but buildability={b}")
    if dl in ("local_cli", "oss_library") and mb not in ("local_only_tool", "none"):
        flag(out, "main_blocker", "rule", f"delivery={dl} but main_blocker={mb}", "warn")
    a = v["auth_methods"] if isinstance(v["auth_methods"], list) else []
    if "none" in a and len(a) > 1:
        flag(out, "auth_methods", "rule", f"'none' listed together with {a}")
    if dl == "hosted_api" and a == ["none"]:
        flag(out, "auth_methods", "rule", "hosted API with no auth at all", "warn")


# ---------- 4: links ----------

def url_status(url: str) -> int:
    k = config.key("status", url)
    hit = config.cache_get("pages", k)
    if hit is not None:
        return hit["status"]
    try:
        s = httpx.get(url, headers=UA, timeout=20, follow_redirects=True).status_code
    except Exception:
        s = 0
    config.cache_put("pages", k, {"status": s})
    return s


def check_links(r: dict, status: dict, out: list):
    for f in FIELDS:
        for ev in r[f]["evidence"]:
            s = status.get(ev["url"])
            if s and s >= 400 and s not in (401, 403, 429):  # 401/403/429 = bot wall, page exists
                flag(out, f, "link", f"evidence URL returns {s}: {ev['url']}")
            elif s == 0:
                flag(out, f, "link", f"evidence URL unreachable: {ev['url']}", "warn")
            if not is_official(ev["url"], r.get("_domains", [])) and f != "official_mcp":
                flag(out, f, "link", f"evidence not on vendor domain: {ev['url']}", "warn")


# ---------- 5: MCP registry + Composio ----------

def registry_search(term: str) -> list[dict]:
    k = config.key("mcp_registry", term)
    hit = config.cache_get("search", k)
    if hit is not None:
        return hit
    out, cursor = [], None
    for _ in range(3):
        params = {"search": term, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        try:
            d = httpx.get("https://registry.modelcontextprotocol.io/v0/servers", params=params, timeout=30).json()
        except Exception:
            break
        for s in d.get("servers", []):
            srv = s.get("server", s)
            out.append({"name": srv.get("name", ""), "repo": (srv.get("repository") or {}).get("url") or "",
                        "remotes": [x.get("url", "") for x in srv.get("remotes") or []]})
        cursor = (d.get("metadata") or {}).get("nextCursor")
        if not cursor:
            break
    return config.cache_put("search", k, out)


def _stem(domain: str) -> str:
    host = domain.split("/")[0].lower()
    parts = [p for p in host.split(".") if p not in ("www", "com", "io", "ai", "co", "app", "dev", "org", "net", "so", "us", "cn", "video", "help", "docs", "developers")]
    return parts[0] if parts else host


_ORG_SUFFIX = re.compile(r"[-_]?(labs|com|inc|hq|ai|dev|io|app|official|team|oss|hq)$")


def _org_matches(owner: str, stems: set) -> bool:
    o = owner.lower()
    cands = {o, _ORG_SUFFIX.sub("", o), o.replace("-", ""), o.removeprefix("get"), o.removesuffix("hq")}
    return bool(cands & stems)


def mcp_lookup(app: dict) -> dict:
    """Official = the vendor's own namespace, host or GitHub org. Substring look-alikes are community."""
    domains = [d.split("/")[0].lower() for d in app.get("domains", [])]
    gh_orgs = {d.split("/")[1].lower() for d in app.get("domains", []) if d.startswith("github.com/") and d.count("/") >= 1}
    stems = {_stem(d) for d in domains if not d.startswith("github.com")} | {app["id"].split("-")[0]} | gh_orgs
    stems = {s for s in stems if len(s) >= 3}
    generic = {"google", "meta", "microsoft", "amazon", "zoho", "ads", "business", "api", "app", "the", "cli", "ai"}
    product_tokens = [t for t in app["id"].split("-") if t not in generic and len(t) >= 3]
    official, community = [], []
    vendor_domains = [d for d in domains if not d.startswith("github.com")]
    # broad terms ("github", "sentry") overflow the result pages, so also query the vendor's namespaces
    terms = sorted(stems) + [".".join(reversed(d.split("."))) for d in vendor_domains] \
        + [f"io.github.{st}" for st in sorted(stems)] + [f"io.github.get{st}" for st in sorted(stems)]
    seen_names = set()
    for s in terms:
        for e in registry_search(s):
            if e["name"] in seen_names:
                continue
            seen_names.add(e["name"])
            ns = e["name"].split("/")[0].lower()
            rev = ".".join(reversed(ns.split(".")))  # com.notion -> notion.com
            hosts = [(urlparse(u).hostname or "").lower() for u in e["remotes"]]
            repo_owner = (urlparse(e["repo"]).path.strip("/").split("/") or [""])[0].lower()
            gh_owner = ns.split(".", 2)[2] if ns.startswith("io.github.") else ""
            is_off = (any(rev == d or rev.endswith("." + d) for d in vendor_domains)
                      or any(h == d or h.endswith("." + d) for h in hosts for d in vendor_domains)
                      or (gh_owner and _org_matches(gh_owner, stems))
                      or (repo_owner and _org_matches(repo_owner, stems) and not gh_owner and rev.split(".")[0] in stems))
            related = any(st in e["name"].lower() or st in repo_owner for st in stems)
            # parent-company orgs (Meta, Microsoft, Google) host many unrelated servers: unless the
            # namespace is the app's own primary domain, the server name must name the product too
            primary = vendor_domains[0] if vendor_domains else ""
            own_ns = bool(primary) and (rev == primary or rev.endswith("." + primary))
            nm = e["name"].lower().replace("-", "").replace("_", "")
            names_product = any(t.replace("_", "") in nm for t in product_tokens)
            if is_off and (own_ns or names_product):
                official.append(e["name"])
            elif related:
                community.append(e["name"])
    return {"registry_official": sorted(set(official)), "registry_community": sorted(set(community))[:15]}


def check_mcp(r: dict, m: dict, out: list):
    claim = r["official_mcp"]["value"]
    if m["registry_official"] and claim not in (True, "True", "true"):
        flag(out, "official_mcp", "mcp_registry", f"registry lists official server(s) {m['registry_official'][:3]} but agent said {claim}")
    if claim in (True, "True", "true") and not m["registry_official"]:
        ev = r["official_mcp"]["evidence"]
        url = ev[0]["url"] if ev else ""
        sev = "error" if not ev or not is_official(url, r.get("_domains", [])) else "warn"
        flag(out, "official_mcp", "mcp_registry", f"agent says official MCP; not in registry; evidence {url or 'none'}", sev)


# ---------- driver ----------

def run(path: str) -> dict:
    apps = {a["id"]: a for a in config.load_apps()}
    from research.composio_tools import composio_toolkits
    toolkits = set(composio_toolkits())
    recs = [json.loads(l) for l in open(path)]
    for r in recs:
        r["_domains"] = apps[r["id"]].get("domains", [])
    urls = sorted({ev["url"] for r in recs for f in FIELDS for ev in r[f]["evidence"]})
    with ThreadPoolExecutor(16) as pool:
        status = dict(zip(urls, pool.map(url_status, urls)))
    with ThreadPoolExecutor(8) as pool:
        mcps = dict(zip([r["id"] for r in recs], pool.map(lambda r: mcp_lookup(apps[r["id"]]), recs)))
    report = {}
    for r in recs:
        out: list = []
        check_quotes(r, page_texts(r["id"]), out)
        check_rules(r, out)
        check_links(r, status, out)
        check_mcp(r, mcps[r["id"]], out)
        slug_hits = sorted(t for t in toolkits if t == r["id"].replace("-", "_") or t.startswith(r["id"].replace("-", "_") + "_"))
        report[r["id"]] = {"n": r["n"], "name": r["name"], "flags": out, "mcp": mcps[r["id"]], "composio_toolkits": slug_hits}
    return report


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else str(config.DATA / "pass1_frozen.jsonl")
    rep = run(path)
    outp = config.DATA / ("auto_checks.json" if "pass1" in path else "auto_checks_" + path.split("/")[-1].replace(".jsonl", ".json"))
    outp.write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    from collections import Counter
    sev = Counter((f["check"], f["severity"]) for v in rep.values() for f in v["flags"])
    print("flags by check/severity:", dict(sorted(sev.items())))
    err_apps = [v["name"] for v in rep.values() if any(f["severity"] == "error" for f in v["flags"])]
    print(f"apps with >=1 error flag: {len(err_apps)}/100")
    print(f"official MCP in registry: {sum(bool(v['mcp']['registry_official']) for v in rep.values())} apps;",
          f"in Composio: {sum(bool(v['composio_toolkits']) for v in rep.values())} apps")
    print("written", outp)
