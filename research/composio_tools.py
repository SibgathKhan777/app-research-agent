"""Thin wrapper over the Composio SDK: every web call the agent makes goes through here.

- search(): Composio TAVILY_SEARCH (provider key passed per call as custom auth)
- extract(): Composio TAVILY_EXTRACT, used when a direct fetch returns nothing readable
- composio_toolkits(): Composio's own toolkit catalogue, for the "already in Composio?" column

Results are cached on disk so reruns are deterministic and cost nothing.
"""
from __future__ import annotations

import time

from . import config

_client = None


def client():
    global _client
    if _client is None:
        if not config.COMPOSIO_API_KEY:
            raise RuntimeError("COMPOSIO_API_KEY is not set (see .env.example)")
        from composio import Composio

        _client = Composio(api_key=config.COMPOSIO_API_KEY)
    return _client


def _tavily_auth():
    if not config.TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set (see .env.example)")
    return {
        "base_url": "https://api.tavily.com",
        "parameters": [
            # Composio's TAVILY toolkit reads a credential field literally named `api_key`
            {"name": "api_key", "value": config.TAVILY_API_KEY, "in": "header"}
        ],
    }


def _execute(slug: str, arguments: dict, retries: int = 3) -> dict:
    last = None
    for attempt in range(retries):
        try:
            res = client().tools.execute(
                slug,
                arguments,
                user_id=config.COMPOSIO_USER_ID,
                custom_auth_params=_tavily_auth(),
                dangerously_skip_version_check=True,
            )
            res = res if isinstance(res, dict) else res.model_dump()
            # `successful` can come back as a bool or as the string "True"/"False"
            if str(res.get("successful")).lower() == "true":
                data = res.get("data") or {}
                return data if isinstance(data, dict) else {}
            last = res.get("error")
        except Exception as e:  # network / rate limit
            last = repr(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{slug} failed: {last}")


def _results(data: dict) -> list[dict]:
    # Composio wraps provider payloads; accept either shape
    body = data.get("response_data", data)
    return body.get("results", []) if isinstance(body, dict) else []


def search(query: str, max_results: int = 6, include_domains: list[str] | None = None) -> list[dict]:
    k = config.key("tavily_search", query, max_results, include_domains)
    hit = config.cache_get("search", k)
    if hit is not None:
        return hit
    args = {"query": query, "max_results": max_results, "search_depth": "basic", "include_raw_content": True}
    if include_domains:
        args["include_domains"] = include_domains
    out = [
        {
            "url": r.get("url"),
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "raw": r.get("raw_content") or "",
        }
        for r in _results(_execute("TAVILY_SEARCH", args))
        if r.get("url")
    ]
    return config.cache_put("search", k, out)


def extract(url: str) -> str:
    k = config.key("tavily_extract", url)
    hit = config.cache_get("search", k)
    if hit is not None:
        return hit
    data = _execute("TAVILY_EXTRACT", {"urls": [url]})
    res = _results(data)
    text = (res[0].get("raw_content") if res else "") or ""
    return config.cache_put("search", k, text)


def composio_toolkits() -> list[str]:
    """Slugs of every toolkit Composio already ships (cached)."""
    hit = config.cache_get("search", "composio_toolkits")
    if hit is not None:
        return hit
    slugs, cursor = set(), None
    for _ in range(50):  # the API pages at 1000; follow the cursor to the end
        page = client().toolkits.list(cursor=cursor, limit=1000, managed_by="all")
        for i in page.items:
            slugs.add(i.slug.lower())
        cursor = getattr(page, "next_cursor", None)
        if not cursor or not page.items:
            break
    return config.cache_put("search", "composio_toolkits", sorted(slugs))
