"""Tests run fully offline: fake LLM answers, BM25-only retrieval (no model download)."""

import os
import sys
from pathlib import Path

os.environ["AIN_LLM_MODE"] = "fake"
os.environ["AIN_DENSE"] = "0"
os.environ["HF_HUB_OFFLINE"] = "1"
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


@pytest.fixture
def docs():
    return DOCS


@pytest.fixture
def corpus():
    from ain.retrieval import get_corpus

    return get_corpus()
