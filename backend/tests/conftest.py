"""Tests run fully offline: fake LLM answers, BM25-only retrieval (no model download)."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["AIN_LLM_MODE"] = "fake"
os.environ["AIN_DENSE"] = "0"
os.environ["HF_HUB_OFFLINE"] = "1"
# never pick up the real keys from ../.env (load_dotenv does not override variables that are already set)
os.environ["GROQ_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
# accounts DB, encryption key and stored results go to a throwaway dir, never the real backend/.data or runs/
_DATA = tempfile.mkdtemp(prefix="ain-test-")
os.environ["AIN_DATA_DIR"] = _DATA
os.environ["AIN_DB"] = str(Path(_DATA) / "ain.db")
os.environ["AIN_RUNS_DIR"] = str(Path(_DATA) / "runs")
os.environ["AIN_CORS"] = "http://localhost:3000"
os.environ["AIN_COOKIE_SECURE"] = "0"  # TestClient talks plain http
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from ain import config  # noqa: E402
from ain.llm import LLM  # noqa: E402

DOCS = config.DEMO_DIR / "docs"


class RecordingLLM(LLM):
    """Fake-mode LLM that keeps every outbound payload so tests can inspect what would have left the machine."""

    def __init__(self, overrides=None, **kw):
        super().__init__(mode="fake", **kw)
        self.payloads: list[dict] = []
        self.overrides = overrides or {}

    async def json(self, *, role, system, user, task, agent, fake=None, **kw):
        self.payloads.append({"role": role, "task": task, "agent": agent, "system": system, "user": user})
        for prefix, answer in self.overrides.items():
            if task.startswith(prefix):
                fake = (lambda a=answer: a(role, user) if callable(a) else a)
        return await super().json(role=role, system=system, user=user, task=task, agent=agent, fake=fake, **kw)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    from ain import auth

    auth.LIMITER.reset()


@pytest.fixture
def docs():
    return DOCS


@pytest.fixture
def corpus():
    from ain.retrieval import get_corpus

    return get_corpus()
