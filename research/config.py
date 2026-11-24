import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

CACHE = ROOT / "cache"
DATA = ROOT / "data"
for d in (CACHE / "search", CACHE / "pages", CACHE / "llm", DATA):
    d.mkdir(parents=True, exist_ok=True)

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "openai/gpt-oss-120b")
SECOND_MODEL = os.getenv("SECOND_MODEL", "openai/gpt-oss-120b")  # independent cross-check model (Groq)
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "app-research-agent")

# Extraction model(s). A Groq model id (default), or "cli:<name>" to run through a local LLM
# command-line client (set LLM_CLI to its executable). A comma list rotates models by block of
# BLOCK_SIZE apps (apps 1-20 -> model 0, 21-40 -> model 1 ...), e.g. two Groq models to stay
# inside the free tier's daily token limit.
MODEL_ROTATION = [m.strip() for m in os.getenv("MODEL_ROTATION", "openai/gpt-oss-120b").split(",") if m.strip()]
LLM_CLI = os.getenv("LLM_CLI", "")
LLM_CLI_STRIP_ENV = [x.strip() for x in os.getenv("LLM_CLI_STRIP_ENV", "").split(",")]
BLOCK_SIZE = int(os.getenv("BLOCK_SIZE", "20"))


def model_for(n: int) -> str:
    return MODEL_ROTATION[((n - 1) // BLOCK_SIZE) % len(MODEL_ROTATION)]


def key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:24]


def cache_get(kind: str, k: str):
    p = CACHE / kind / f"{k}.json"
    return json.loads(p.read_text()) if p.exists() else None


def cache_put(kind: str, k: str, value):
    (CACHE / kind / f"{k}.json").write_text(json.dumps(value, ensure_ascii=False, indent=1))
    return value


def load_apps():
    import yaml

    return yaml.safe_load((ROOT / "apps.yaml").read_text())
