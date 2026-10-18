"""Settings read from environment variables. See .env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass

from noecho.core.gate import DEFAULT_THRESHOLD


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: str = "./noecho.db"
    gate_threshold: float = DEFAULT_THRESHOLD
    min_sources: int = 1
    llm_provider: str = "none"


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ) if env is None else env
    return Settings(
        db_path=env.get("NOECHO_DB_PATH", Settings.db_path),
        gate_threshold=float(env.get("NOECHO_GATE_THRESHOLD", DEFAULT_THRESHOLD)),
        min_sources=int(env.get("NOECHO_MIN_SOURCES", 1)),
        llm_provider=env.get("NOECHO_LLM_PROVIDER", "none"),
    )
