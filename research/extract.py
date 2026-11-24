"""Stage 3: LLM extraction over retrieved chunks. Every field must cite a source id + a verbatim quote."""
from __future__ import annotations

import json
import re
import time

from rank_bm25 import BM25Okapi

from . import config
from .discover import chunk
from .schema import FIELDS

TOPICS = {
    "overview": "what is product platform helps teams software",
    "auth": "authentication oauth oauth2 api key token bearer basic authorization header client id secret scopes",
    "access": "pricing plan paid enterprise free trial sign up developer account partner program approval review contact sales request access",
    "surface": "rest graphql endpoints reference resources openapi swagger spec webhooks sandbox rate limit sdk",
    "mcp": "mcp model context protocol server assistant copilot agents",
}

SYSTEM = """You are a meticulous API research analyst at an integrations company.
You read excerpts from an app's documentation and fill a JSON research record.

RULES
- Use ONLY the numbered sources given. Never use prior knowledge for a value you cannot quote.
- Each field: {"value": ..., "source": "S<n>", "quote": "<verbatim substring copied exactly from that source, 5-40 words>", "confidence": "high|medium|low"}.
- The quote must be copied character-for-character from the source text. Do not paraphrase inside quote.
- A quote is ONE continuous passage from ONE source. Never join passages with "..." and never quote across table cells.
- If no source supports a field, set value to "unknown", source to null, quote to null, confidence "low".
- Output a single JSON object, no markdown.

FIELDS AND ALLOWED VALUES
one_liner: string, what the product does in <= 15 words (quote the description it came from).
auth_methods: list from [oauth2, api_key, basic, bearer_token, jwt, session_login, none, other]. Personal access tokens / private app tokens count as api_key. List every method the API accepts.
access_tier: one of
  self_serve_free  - any developer can sign up and create credentials free (free plan, free dev account, dev store, sandbox)
  self_serve_trial - self-serve but credentials only work during a time-limited trial
  paid_plan        - API needs a paid subscription or a specific paid tier
  admin_approval   - needs app review, developer application or admin approval before real use
  partner_gated    - partner program / invite-only / allowlist
  contact_sales    - API access only by contacting sales
  unknown
delivery: one of [hosted_api, mcp_only, local_cli, oss_library, no_public_api]
api_styles: list from [rest, graphql, soap, rpc, websocket, sdk_only, none]
api_breadth: one of [narrow, medium, broad, unknown]  (narrow: <10 resources/endpoints; medium: 10-50; broad: 50+ or a full platform API)
openapi_spec: true / false / "unknown" (true only if a public OpenAPI/Swagger spec is mentioned)
official_mcp: true / false / "unknown" (true only if the vendor itself publishes or documents an MCP server)
buildability: one of
  ready               - self-serve credentials + documented API: an agent toolkit could be built today
  ready_with_friction - buildable, but something slows it: app review for public use, paid tier for some endpoints, narrow API, per-tenant setup
  blocked             - cannot be built without a paid plan, partnership, sales, or there is no public API
main_blocker: one of [none, paid_plan_required, partner_or_sales_gate, app_review_or_approval, no_public_api, enterprise_only, local_only_tool, unclear_docs, other]
docs_url: the best developer docs URL among the sources (string)
notes: <= 40 words of anything a toolkit engineer must know (rate limits, regions, per-tenant base URL...). No quote needed.

Consistency: buildability "ready" requires main_blocker "none". access_tier contact_sales/partner_gated implies buildability "blocked" unless a self-serve path is also quoted."""


def select_context(pages: list[dict], per_topic: int = 4, max_chars: int = 20000) -> tuple[str, dict]:
    chunks, owners = [], []
    for i, p in enumerate(pages):
        for c in chunk(p["text"]):
            chunks.append(c)
            owners.append(i)
    if not chunks:
        return "", {}
    bm = BM25Okapi([re.findall(r"\w+", c.lower()) for c in chunks])
    picked: list[int] = []
    for q in TOPICS.values():
        scores = bm.get_scores(q.split())
        for j in sorted(range(len(chunks)), key=lambda j: -scores[j])[:per_topic]:
            if j not in picked:
                picked.append(j)
    # always include the head of the homepage / overview / docs landing (product description for one_liner)
    for i, p in enumerate(pages):
        if p.get("found_by") in ("hint", "overview", "docs") and i in owners:
            j = owners.index(i)
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


class QuotaExhausted(RuntimeError):
    """The model's daily token budget is spent; retrying now only wastes time."""


CLI_EFFORT = "medium"  # extraction is structured reading; high effort mostly adds latency


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)  # tolerate ```json fences or a stray sentence
    return json.loads(m.group(0) if m else text)


def cli_json(system: str, user: str, model: str, timeout: int = 300) -> dict:
    """One single-turn, tool-less call through a local LLM command-line client in headless mode.

    The executable comes from LLM_CLI (set in .env). If this script is launched from inside another
    agent's shell, that parent's variables can hide the client's own login: LLM_CLI_STRIP_ENV is a
    comma list of variable-name prefixes to drop from the child's environment.
    """
    import os
    import subprocess

    if not config.LLM_CLI:
        raise RuntimeError("LLM_CLI is not set: point it at your LLM command-line client, or use a Groq model")
    cmd = [config.LLM_CLI, "-p", "--model", model, "--tools", "", "--system-prompt", system,
           "--output-format", "json", "--no-session-persistence", "--strict-mcp-config",
           "--settings", json.dumps({"effortLevel": CLI_EFFORT})]
    strip = tuple(x for x in config.LLM_CLI_STRIP_ENV if x)
    env = {k: v for k, v in os.environ.items() if not (strip and k.startswith(strip))}
    last = ""
    for attempt in range(4):
        p = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=timeout, cwd=config.CACHE, env=env)
        try:
            out = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = (p.stderr or p.stdout)[:300]
            time.sleep(5 * (attempt + 1))
            continue
        if out.get("is_error"):
            last = str(out.get("result"))[:300]
            if "logged in" in last.lower():
                raise RuntimeError(f"LLM CLI: {last}")
            if "usage" in last.lower() and ("out of" in last.lower() or "limit" in last.lower()):
                raise QuotaExhausted(f"LLM CLI: {last}")
            time.sleep(10 * (attempt + 1))
            continue
        try:
            data = _parse_json(out["result"])
        except (json.JSONDecodeError, KeyError) as e:
            last = f"{e}: {str(out.get('result'))[:200]}"
            # re-ask with the parse error, instead of re-sending the identical prompt
            user = (user.split("\n\nNOTE: your previous reply")[0]
                    + f"\n\nNOTE: your previous reply was not valid JSON ({e}). Reply with ONE valid JSON object. "
                      "Inside string values, escape every double quote as \\\" or choose a quote without inner quotes.")
            continue
        data["_model_used"] = next(iter(out.get("modelUsage") or {}), model)
        return data
    raise RuntimeError(f"LLM CLI failed after retries: {last}")


def llm_json(system: str, user: str, model: str) -> dict:
    """model "cli:<name>" runs through the local command-line client; anything else is a Groq model id."""
    is_cli = model.startswith("cli:")
    name = model[4:] if is_cli else model
    k = config.key("llm", name, CLI_EFFORT, system, user) if is_cli else config.key("llm", model, system, user)
    hit = config.cache_get("llm", k)
    if hit is not None:
        return hit
    if is_cli:
        return config.cache_put("llm", k, cli_json(system, user, name))
    from groq import Groq

    client = Groq(api_key=config.GROQ_API_KEY)
    for attempt in range(8):
        try:
            r = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            out = json.loads(r.choices[0].message.content)
            return config.cache_put("llm", k, out)
        except Exception as e:
            msg = str(e)
            if "tokens per day" in msg or "(TPD)" in msg:
                m = re.search(r"try again in ([^.]+?\.?\d*s)", msg)
                raise QuotaExhausted(f"{model} daily quota spent (retry in {m.group(1) if m else '?'})") from e
            wait = 20
            m = re.search(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)", msg)
            if m:
                wait = int(m.group(1) or 0) * 60 + float(m.group(2)) / (1000 if m.group(3) == "ms" else 1) + 1
            elif "json" in msg.lower() or "validate" in msg.lower():
                wait = 1
            time.sleep(min(wait * (1 + attempt * 0.3), 90))
    raise RuntimeError(f"LLM failed after retries: {model}")


def to_record(app: dict, raw: dict, srcmap: dict, pages: list[dict], pass_name: str) -> dict:
    rec = {k: app[k] for k in ("n", "id", "name", "category", "hint")}
    for f in FIELDS:
        v = raw.get(f) or {}
        if not isinstance(v, dict):
            v = {"value": v}
        url = srcmap.get(str(v.get("source") or "").strip("[]"))
        ev = [{"url": url, "quote": v.get("quote") or ""}] if url and v.get("quote") else []
        rec[f] = {"value": v.get("value", "unknown"), "evidence": ev, "confidence": v.get("confidence", "low"), "flags": []}
    d = raw.get("docs_url")
    rec["docs_url"] = d.get("value") if isinstance(d, dict) else d
    n = raw.get("notes")
    rec["notes"] = n.get("value") if isinstance(n, dict) else (n or "")
    rec["sources"] = [p["url"] for p in pages]
    rec["pass_name"] = pass_name
    return rec


def extract(app: dict, pages: list[dict], model: str | None = None, pass_name: str = "pass1") -> dict:
    model = model or config.EXTRACT_MODEL
    ctx, srcmap = select_context(pages)
    user = f"APP: {app['name']} (category: {app['category']}; hint: {app['hint']} {app.get('note','')})\n\nSOURCES\n{ctx or '(no sources found)'}"
    raw = llm_json(SYSTEM, user, model)
    rec = to_record(app, raw, srcmap, pages, pass_name)
    rec["extract_model"] = raw.get("_model_used", model)
    rec["_srcmap"] = srcmap
    return rec
