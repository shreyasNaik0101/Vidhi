"""Central config, read from environment (.env). No secrets in code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
RAW_DIR = DATA_DIR / "raw"
GOLDEN_DIR = DATA_DIR / "golden"


def _get(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if val is None:
        raise KeyError(f"Required env var {key!r} is not set (see .env.example)")
    return val


@dataclass(frozen=True)
class Config:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://rbi:rbi@localhost:5433/rbi")

    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model_extract: str = os.getenv("OLLAMA_MODEL_EXTRACT", "gemma3:4b")
    ollama_model_parse: str = os.getenv("OLLAMA_MODEL_PARSE", "qwen3:8b")
    ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

    max_spend_usd: float = float(os.getenv("MAX_SPEND_USD", "15.00"))
    llm_cache_path: Path = REPO_ROOT / os.getenv("LLM_CACHE_PATH", "data/llm_cache.db")

    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    bedrock_escalation_model_id: str = os.getenv(
        "BEDROCK_ESCALATION_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
    )
    bedrock_pricing_path: Path = REPO_ROOT / os.getenv(
        "BEDROCK_PRICING_PATH", "src/rbi/llm/pricing.json"
    )

    rbi_user_agent: str = os.getenv(
        "RBI_USER_AGENT", "rbi-timeline-research/0.1 (portfolio project)"
    )
    fetch_delay_seconds: float = float(os.getenv("FETCH_DELAY_SECONDS", "2"))


config = Config()
