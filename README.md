# app-research-agent

An agent that researches an app's integration readiness (auth, self-serve vs gated access, API surface, MCP, buildability), cites a page and verbatim quote for every answer, and then checks its own work.

It was run on 100 apps across 10 categories. The findings, the patterns, and an honest accuracy report are in the case study: **`docs/index.html`** (GitHub Pages). The data is in `docs/data/` (`results.json`, `results.csv`, `patterns.json`, `human_labels.csv`, `accuracy.json`).

## Results in brief

- 37 apps are clean "build it today", 53 are buildable with friction, 10 are blocked. The most common blocker is a paid plan (30 apps).
- OAuth 2 is near-universal (83 apps); 62 accept both OAuth and an API key.
- **Accuracy, measured, with its limits:** on a hand-checked sample of 20 apps (2 per category, fixed seed, 199 fields) the first pass was 91.5% correct. Across all 100 apps, answers whose quote can be found on the cited page went from 86.2% to 98.2% after the verification loops.
- My first repair step lowered sample accuracy to 89.5% (it blanked fields it could not re-prove). The fix reports 92.0%, but it was designed after seeing the sample, so treat that number as optimistic. The page lists all three variants and every remaining miss.
- The labels were written by an AI assistant from live vendor docs, not by the agent under test; one person audited 5 of them at random and agreed with all 5. That is too few to estimate label error.

## How it works

```
research/discover.py   search (Composio Tavily toolkit) + fetch pages, per-question coverage, cached
research/extract.py    BM25 passage selection -> LLM fills 10 fields, each with source id + verbatim quote
research/grounding.py  mechanical check: does the quote occur in the page the agent read?
verification/          auto_checks (grounding, rules, links, MCP registry), repair, second_model,
                       sample, make_labels, score
analysis/patterns.py   merges the final pass and computes every number shown on the page
webpage/build_page.py  renders docs/index.html from the computed JSON (no hand-typed numbers)
```

Pass 1 is frozen (`data/pass1_frozen.jsonl`, checksum in `data/pass1_frozen.manifest.json`). Verification writes separate files (`data/pass2.jsonl`), never over it.

Search and page extraction go through the Composio SDK (`TAVILY_SEARCH`, `TAVILY_EXTRACT`). The extraction model is either a Groq-hosted model or any LLM command-line client you point `LLM_CLI` at (pass 1 used the latter, labelled `hosted-llm-1` in the data).

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add COMPOSIO_API_KEY and TAVILY_API_KEY (+ GROQ_API_KEY for the Groq backend)

python -m research.run --app notion                       # one app from apps.yaml
python -m research.run --custom "Linear|linear.app"       # any app
python -m research.run --all --workers 5                  # all 100 (resumable: --from N)
```

Extraction backend: `MODEL_ROTATION=openai/gpt-oss-120b` (default, Groq) or `MODEL_ROTATION=cli:<model>` with `LLM_CLI=<your client executable>` (see `.env.example`). Without a Tavily key, discovery falls back to probing well-known official pages.

Verification and the page:

```bash
python -m verification.auto_checks data/pass1_frozen.jsonl   # grounding, rules, links, MCP registry
python -m verification.repair                                # re-derive flagged fields -> data/pass2.jsonl
python -m verification.score data/pass1_frozen.jsonl data/pass2.jsonl
python -m analysis.patterns && python -m webpage.build_page --repo <your repo url>
python -m pytest
```

**Run one app from GitHub:** Actions, `research-one`, Run workflow, enter `Name|domain.com`. Add `COMPOSIO_API_KEY`, `TAVILY_API_KEY` and `GROQ_API_KEY` as repository secrets. The workflow uses the Groq backend (a local client login is not available in Actions), so its answers can differ from pass 1.

## Where a human was needed

API keys; the schema and the definition of "buildable"; reading sites that block bots or render docs only in a browser; hand-labelling the 20-app sample (done by the AI assistant against live docs); and the audit of 5 labels (done by a person). Everything else ran unattended.
