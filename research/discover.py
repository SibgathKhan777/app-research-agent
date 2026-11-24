"""Stage 1+2: find and read the pages that answer the research questions for one app."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
import trafilatura

from . import composio_tools as ct
from . import config

QUERIES = {
    "overview": "what is {name} product overview",
    "docs": "{name} developer API documentation",
    "auth": "{name} API authentication OAuth API key how to get credentials",
    "access": "{name} API access requirements pricing plan developer account partner",
    "mcp": "{name} official MCP server model context protocol",
}

UA = {"User-Agent": "Mozilla/5.0 (app-research-agent; +https://github.com)"}


def host_of(url: str) -> str:
    p = urlparse(url)
    return (p.netloc + p.path).lower().removeprefix("www.")


def is_official(url: str, domains: list[str]) -> bool:
    h = host_of(url)
    for d in domains:
        d = d.lower()
        if "/" in d:  # github.com/org style
            if h.startswith(d):
                return True
        elif h.split("/")[0] == d or h.split("/")[0].endswith("." + d):
            return True
    return False


def fetch(url: str) -> str:
    """Direct fetch -> readable text. Falls back to Composio TAVILY_EXTRACT for JS-rendered pages."""
    k = config.key("page", url)
    hit = config.cache_get("pages", k)
    if hit is not None:
        return hit["text"]
    text = ""
    try:
        r = httpx.get(url, headers=UA, timeout=20, follow_redirects=True)
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            text = trafilatura.extract(r.text, include_links=False, include_tables=True) or ""
        elif r.status_code == 200 and r.headers.get("content-type", "").startswith(("text/", "application/json")):
            text = r.text
    except Exception:
        pass
    via = "direct"
    if len(text) < 400:
        try:
            text, via = ct.extract(url) or text, "tavily_extract"
        except Exception:
            pass
    config.cache_put("pages", k, {"url": url, "via": via, "text": text})
    return text


def canon(url: str) -> str:
    """URL identity for dedupe: no fragment, no query string, no trailing slash."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc.lower().removeprefix('www.')}{p.path.rstrip('/')}"


PER_QUERY = {"overview": 1, "docs": 2, "auth": 3, "access": 3, "mcp": 2}


PROBE_PATHS = ["", "/developers", "/developer", "/api", "/docs", "/pricing", "/llms.txt", "/integrations"]


def _search(q: str, state: dict, **kw) -> list[dict]:
    """Search, but a spent search quota degrades the app to direct probing instead of failing it."""
    try:
        return ct.search(q, **kw)
    except Exception as e:
        if "usage limit" in str(e).lower() or "exceeds" in str(e).lower():
            state["search_down"] = True
            return []
        raise


def probe(app: dict, seen: set) -> list[dict]:
    """Fallback when search is unavailable: fetch well-known official paths directly."""
    out = []
    for d in app.get("domains", [])[:2]:
        host = d.split("/")[0]
        for base in (f"https://{host}", f"https://developers.{host}", f"https://docs.{host}", f"https://api.{host}"):
            for path in (PROBE_PATHS if base.endswith(host) and base.count(".") == host.count(".") else [""]):
                url = base + path
                if canon(url) in seen:
                    continue
                seen.add(canon(url))
                text = fetch(url)
                if len(text) > 200:
                    out.append({"url": url, "official": True, "found_by": "probe", "text": text})
    return out


def discover(app: dict) -> list[dict]:
    """Returns pages [{url, official, text, found_by}] for an app.

    Pages are chosen by question coverage, not length: each research question
    (overview, docs, auth, access, mcp) keeps its own top results, so one long
    reference page can't crowd out the auth guide or the pricing page.
    """
    domains = app.get("domains", [])
    state = {"search_down": False}
    seen: set[str] = set()
    chosen: list[dict] = []

    hint = app["hint"]
    if "." in hint.split("/")[0]:
        url = "https://" + hint
        text = fetch(url)
        seen.add(canon(url))
        if len(text) > 200:
            chosen.append({"url": url, "official": True, "found_by": "hint", "text": text})

    for qkey, tpl in QUERIES.items():
        q = tpl.format(name=app["name"])
        # official-domain search first, open web second (catches community MCPs, partner pages)
        results = []
        if domains:
            results += _search(q, state, max_results=5, include_domains=[d.split("/")[0] for d in domains])
        results += _search(q, state, max_results=5)
        kept = 0
        for r in results:
            if kept >= PER_QUERY[qkey]:
                break
            url = r["url"].split("#")[0]
            if canon(url) in seen:
                continue
            off = is_official(url, domains)
            if not off and qkey != "mcp":
                continue  # non-official pages are only trusted for MCP discovery
            seen.add(canon(url))
            text = r["raw"] if len(r.get("raw") or "") > 400 else fetch(url)
            if len(text) <= 200:
                continue
            chosen.append({"url": url, "official": off, "found_by": qkey, "text": text})
            kept += 1
    if state["search_down"]:
        chosen += probe(app, seen)
    return chosen


def chunk(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text)
    out, i = [], 0
    while i < len(text):
        out.append(text[i : i + size])
        i += size - overlap
    return out
