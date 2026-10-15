"""Paths, environment and model routing."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
CORPUS_FILE = BACKEND / "corpus" / "processed" / "corpus.jsonl"
EMBEDDINGS_FILE = BACKEND / "corpus" / "processed" / "embeddings.npy"
PLAYBOOK_DIR = BACKEND / "ain" / "playbook"
DEMO_DIR = BACKEND / "demo"
OCR_CACHE_DIR = DEMO_DIR / "ocr_cache"
CACHE_DIR = BACKEND / ".cache"
RUNS_DIR = BACKEND / "runs"

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class RoleConfig:
    role: str
    provider: str
    model: str


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    key_env: str

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.key_env) or None


@lru_cache
def _raw() -> dict:
    with open(BACKEND / "ain" / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def role(name: str) -> RoleConfig:
    r = _raw()["roles"][name]
    return RoleConfig(role=name, provider=r["provider"], model=r["model"])


def provider(name: str) -> ProviderConfig:
    p = _raw()["providers"][name]
    return ProviderConfig(name=name, base_url=p["base_url"], key_env=p["key_env"])


def bench_severities() -> set[str]:
    return set(_raw()["bench"]["severities"])


def quote_threshold() -> int:
    return int(_raw()["verifier"]["quote_fidelity_threshold"])


def llm_mode() -> str:
    """live | replay | fake. Defaults to live when any key is configured, else fake."""
    mode = os.getenv("AIN_LLM_MODE")
    if mode:
        return mode
    has_key = any(provider(p).api_key for p in ("groq", "openrouter"))
    return "live" if has_key else "fake"


def dense_enabled() -> bool:
    return os.getenv("AIN_DENSE", "1") != "0"
