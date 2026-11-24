"""Merge the final pass into one results table and compute the cross-app patterns.

Every number shown on the case-study page comes from data/patterns.json, which this
script computes from data/pass2.jsonl - nothing is typed by hand.

python -m analysis.patterns  -> data/results.json, data/patterns.json
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from research import config
from research.schema import FIELDS

FINAL = config.DATA / "pass2.jsonl"
TRUE = (True, "True", "true")


def listify(v):
    return v if isinstance(v, list) else ([] if v in ("unknown", None) else [v])


def merge() -> list[dict]:
    checks = json.loads((config.DATA / "auto_checks.json").read_text())
    rows = []
    for r in map(json.loads, open(FINAL)):
        c = checks[r["id"]]
        row = {k: r[k] for k in ("n", "id", "name", "category", "docs_url", "notes")}
        row["extract_model"] = r.get("extract_model")
        for f in FIELDS:
            v = r[f]["value"]
            row[f] = v
            ev = r[f]["evidence"][0] if r[f]["evidence"] else None
            row[f + "_ev"] = {"url": ev["url"], "quote": ev["quote"]} if ev else None
            row[f + "_flags"] = r[f]["flags"]
        row["mcp_registry"] = c["mcp"]["registry_official"]
        row["composio_toolkits"] = c["composio_toolkits"]
        row["in_composio"] = bool(c["composio_toolkits"])
        row["needs_human"] = any(f["severity"] == "error" for f in c["flags"]) or any(
            "repair:unproven" in row[f + "_flags"] for f in FIELDS)
        rows.append(row)
    return sorted(rows, key=lambda x: x["n"])


def pct(a, b):
    return round(100 * a / b) if b else 0


def analyse(rows: list[dict]) -> dict:
    n = len(rows)
    cats = sorted({r["category"] for r in rows})
    P: dict = {"n": n, "categories": cats}

    auth = Counter(m for r in rows for m in set(listify(r["auth_methods"])))
    P["auth_counts"] = dict(auth.most_common())
    P["auth_combo"] = dict(Counter("+".join(sorted(set(listify(r["auth_methods"])))) for r in rows).most_common(6))
    P["tier_counts"] = dict(Counter(r["access_tier"] for r in rows).most_common())
    P["buildability_counts"] = dict(Counter(r["buildability"] for r in rows).most_common())
    P["blocker_counts"] = dict(Counter(r["main_blocker"] for r in rows).most_common())
    P["delivery_counts"] = dict(Counter(r["delivery"] for r in rows).most_common())
    P["style_counts"] = dict(Counter(s for r in rows for s in set(listify(r["api_styles"]))).most_common())

    gated = ("paid_plan", "admin_approval", "partner_gated", "contact_sales")
    by_cat = {}
    for c in cats:
        rs = [r for r in rows if r["category"] == c]
        by_cat[c] = {
            "n": len(rs),
            "self_serve_free": sum(r["access_tier"] == "self_serve_free" for r in rs),
            "trial": sum(r["access_tier"] == "self_serve_trial" for r in rs),
            "gated": sum(r["access_tier"] in gated for r in rs),
            "ready": sum(r["buildability"] == "ready" for r in rs),
            "friction": sum(r["buildability"] == "ready_with_friction" for r in rs),
            "blocked": sum(r["buildability"] == "blocked" for r in rs),
            "mcp": sum(r["official_mcp"] in TRUE for r in rs),
            "oauth2": sum("oauth2" in listify(r["auth_methods"]) for r in rs),
        }
    P["by_category"] = by_cat

    # MCP and Composio coverage
    mcp_yes = [r for r in rows if r["official_mcp"] in TRUE]
    P["mcp_yes"], P["mcp_registry_confirmed"] = len(mcp_yes), sum(bool(r["mcp_registry"]) for r in rows)
    P["composio_covered"] = sum(r["in_composio"] for r in rows)
    P["composio_gap_ready"] = sorted(r["name"] for r in rows if not r["in_composio"] and r["buildability"] in ("ready", "ready_with_friction"))
    P["easy_wins"] = sorted(r["name"] for r in rows if not r["in_composio"] and r["buildability"] == "ready")
    P["blocked_apps"] = sorted(r["name"] for r in rows if r["buildability"] == "blocked")
    P["needs_human"] = sum(r["needs_human"] for r in rows)

    # cross-field patterns (computed co-occurrences)
    oauth_only = [r for r in rows if listify(r["auth_methods"]) == ["oauth2"]]
    P["oauth_only"] = len(oauth_only)
    P["oauth_and_key"] = sum({"oauth2", "api_key"} <= set(listify(r["auth_methods"])) for r in rows)
    P["free_and_mcp"] = sum(r["access_tier"] == "self_serve_free" and r["official_mcp"] in TRUE for r in rows)
    P["free_ready"] = sum(r["access_tier"] == "self_serve_free" and r["buildability"] == "ready" for r in rows)
    P["review_blocker_oauth"] = sum(r["main_blocker"] == "app_review_or_approval" and "oauth2" in listify(r["auth_methods"]) for r in rows)
    P["review_blocker"] = sum(r["main_blocker"] == "app_review_or_approval" for r in rows)
    P["openapi_yes"] = sum(r["openapi_spec"] in TRUE for r in rows)
    P["openapi_unknown"] = sum(r["openapi_spec"] in ("unknown", None) for r in rows)
    P["gated_total"] = sum(r["access_tier"] in gated for r in rows)

    most_gated = max(cats, key=lambda c: (by_cat[c]["gated"] + by_cat[c]["trial"], c))
    most_open = max(cats, key=lambda c: (by_cat[c]["self_serve_free"], c))
    most_mcp = max(cats, key=lambda c: (by_cat[c]["mcp"], c))
    P["most_gated_category"], P["most_open_category"], P["most_mcp_category"] = most_gated, most_open, most_mcp

    top_auth = list(auth)[0]
    top_block = [b for b in P["blocker_counts"] if b != "none"][0]
    P["headlines"] = [
        f"{pct(auth['oauth2'], n)}% of the {n} apps accept OAuth 2, {pct(auth.get('api_key', 0), n)}% accept an API key or token, and {P['oauth_and_key']} accept both. OAuth 2 is close to universal; the key or token is what makes a single-account integration quick to start.",
        f"{P['tier_counts'].get('self_serve_free', 0)} apps look free to start (treat as an upper bound: on the hand-checked sample the commonest error was calling a gated API free); {P['gated_total']} need a paid plan, approval, a partnership or sales; {P['tier_counts'].get('self_serve_trial', 0)} are trial-only. {most_gated} is the most gated category.",
        f"Only {P['buildability_counts'].get('ready', 0)} apps are clean 'build it today'; {P['buildability_counts'].get('ready_with_friction', 0)} are buildable with friction and {P['buildability_counts'].get('blocked', 0)} are blocked. The most common blocker is '{top_block.replace('_', ' ')}' ({P['blocker_counts'][top_block]} apps).",
        f"{P['mcp_yes']} apps are said to document an official MCP server, but only {P['mcp_registry_confirmed']} are confirmed in the official MCP registry (the rest rely on the vendor's own docs). {most_mcp} leads. Either way, an MCP server is now common for SaaS.",
        f"{P['review_blocker']} apps put their gate at app review, not at signup: you can get a token in minutes and still not ship to other users. OpenAPI specs are public for only {P['openapi_yes']} apps, so 'generate the toolkit from a spec' works for a minority.",
        f"{P['composio_covered']} of {n} already have a Composio toolkit (slug match); {len(P['composio_gap_ready'])} buildable apps do not, {len(P['easy_wins'])} of them clean 'ready': that list is the backlog.",
    ]
    return P


if __name__ == "__main__":
    rows = merge()
    (config.DATA / "results.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    P = analyse(rows)
    (config.DATA / "patterns.json").write_text(json.dumps(P, indent=1, ensure_ascii=False))
    for h in P["headlines"]:
        print("-", h)
    print("\ntier:", P["tier_counts"], "\nbuild:", P["buildability_counts"], "\nblockers:", P["blocker_counts"])
    print("\nneeds_human:", P["needs_human"], "| easy wins:", P["easy_wins"][:10], "| blocked:", P["blocked_apps"])
    print("most gated:", P["most_gated_category"], "| most open:", P["most_open_category"], "| most mcp:", P["most_mcp_category"])
