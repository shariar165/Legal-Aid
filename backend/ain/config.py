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

load_dotenv(ROOT / ".env")

# user data: accounts/sessions DB, the at-rest encryption key, and the encrypted analysis results
DATA_DIR = Path(os.getenv("AIN_DATA_DIR") or BACKEND / ".data")
DB_FILE = Path(os.getenv("AIN_DB") or DATA_DIR / "ain.db")
RUNS_DIR = Path(os.getenv("AIN_RUNS_DIR") or BACKEND / "runs")


@dataclass(frozen=True)
class RoleConfig:
    role: str
    provider: str
    model: str
    fallbacks: tuple[str, ...] = ()  # same-provider alternates (OpenRouter `models` routing)
    backup: RoleConfig | None = None  # the other provider, when this one has no key or is exhausted


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    key_env: str
    rpm: int = 30
    max_parallel: int = 0  # concurrent calls per model; 0 = no limit beyond the per-job semaphore
    free_only: bool = False
    reasoning: dict | None = None
    max_tokens_floor: int = 0  # reasoning models spend part of max_tokens thinking
    tpm: int = 0  # tokens per minute per model; 0 = no token pacing

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.key_env) or None


class ConfigError(ValueError):
    pass


def is_free_model(model: str) -> bool:
    return model.endswith(":free") or model == "openrouter/free"


# Model families, matched on the model name: two judges from one family share training data and blind spots.
FAMILIES = ("gpt-oss", "qwen", "llama", "gemma", "gemini", "claude", "deepseek", "mistral", "dots", "xing", "allam", "nemotron", "glm", "kimi")


def model_family(model: str) -> str:
    name = model.lower().split("/")[-1]
    return next((f for f in FAMILIES if f in name), model.lower().split("/")[0])


def validate(raw: dict) -> None:
    """Refuse a routing table that could spend money on a free-only provider."""
    providers = raw["providers"]
    for name, r in raw["roles"].items():
        for entry in (r, r.get("backup")):
            if not entry:
                continue
            prov = entry.get("provider")
            if prov not in providers:
                raise ConfigError(f"role '{name}': unknown provider '{prov}'")
            if providers[prov].get("free_only"):
                paid = [m for m in (entry["model"], *(entry.get("fallbacks") or ())) if not is_free_model(m)]
                if paid:
                    raise ConfigError(f"role '{name}': {prov} is free-only, but {', '.join(paid)} is not a free model")


@lru_cache
def _raw() -> dict:
    with open(BACKEND / "ain" / "config.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    validate(raw)
    return raw


def _role(name: str, r: dict) -> RoleConfig:
    backup = r.get("backup")
    return RoleConfig(
        role=name,
        provider=r["provider"],
        model=r["model"],
        fallbacks=tuple(r.get("fallbacks") or ()),
        backup=_role(name, backup) if backup else None,
    )


def role(name: str) -> RoleConfig:
    return _role(name, _raw()["roles"][name])


def role_names() -> list[str]:
    return list(_raw()["roles"])


def provider(name: str) -> ProviderConfig:
    p = _raw()["providers"][name]
    return ProviderConfig(
        name=name,
        base_url=p["base_url"],
        key_env=p["key_env"],
        rpm=int(p.get("rpm", 30)),
        max_parallel=int(p.get("max_parallel", 0)),
        free_only=bool(p.get("free_only")),
        reasoning=p.get("reasoning"),
        max_tokens_floor=int(p.get("max_tokens_floor", 0)),
        tpm=int(p.get("tpm", 0)),
    )


def bench_severities() -> set[str]:
    return set(_raw()["bench"]["severities"])


def bench_settings() -> dict:
    return dict(_raw()["bench"])


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


def cors_origins() -> list[str]:
    """Browser origins allowed to call the API with the session cookie."""
    raw = os.getenv("AIN_CORS") or "http://localhost:3000,http://127.0.0.1:3000"
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def cookie_secure() -> bool:
    return os.getenv("AIN_COOKIE_SECURE", "0") == "1"
