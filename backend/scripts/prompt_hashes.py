"""Prompt-hash report (spec 29, Gate 2): which samples' model prompts a change moves, so which ones need a re-warm.

Runs every sample offline (fake mode, no network) and hashes each model call's role, task, system and user text.
A prompt that changes here changes the LLM cache key live too (AGENTS.md rule 8). Fake answers differ from live ones,
so a prompt that follows a model's answer may move live where it does not here; read a clean diff as "no change
from this edit's own inputs" (retrieval, playbook, prompts), not as a promise about every live call.

  python -m scripts.prompt_hashes --out before.json
  python -m scripts.prompt_hashes --out after.json --against before.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path

from ain import api, config
from ain.llm import LLM
from ain.models import Promises
from ain.orchestrator import new_job, run_pipeline


class HashingLLM(LLM):
    def __init__(self) -> None:
        super().__init__(mode="fake")
        self.prompt_hashes: list[str] = []

    async def json(self, *, role, system, user, task, agent, fake=None, **kw):
        h = hashlib.sha256(json.dumps([role, task, system, user], ensure_ascii=False).encode()).hexdigest()[:16]
        self.prompt_hashes.append(f"{task}:{h}")
        return await super().json(role=role, system=system, user=user, task=task, agent=agent, fake=fake, **kw)


async def sample_hashes(s: dict) -> list[str]:
    name = s["file"]
    data = (config.DEMO_DIR / "docs" / name).read_bytes()
    told = (Promises.model_validate_json((config.DEMO_DIR / "promises" / s["promises_file"]).read_text(encoding="utf-8"))
            if "promises_file" in s and config.ledger_enabled() else None)
    policy = ((config.DEMO_DIR / "docs" / s["policy_file"]).read_bytes(), s["policy_file"]) if "policy_file" in s else None
    llm = HashingLLM()
    await run_pipeline(new_job(name), data, name, "sample" if s["kind"] == "text" else None, "fake",
                       confirm_timeout=1, llm=llm, policy=policy, promises=told)
    return sorted(llm.prompt_hashes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--against")
    a = ap.parse_args()
    report = {s["id"]: asyncio.run(sample_hashes(s)) for s in api.SAMPLES}
    Path(a.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"wrote {a.out}: {len(report)} samples, ledger={config.ledger_enabled()}")
    if a.against:
        before = json.loads(Path(a.against).read_text(encoding="utf-8"))
        for sid, calls in report.items():
            old, new = Counter(before.get(sid, [])), Counter(calls)
            moved = sorted({c.split(":")[0] for c in (old - new) + (new - old)})
            print(f"{sid:20} {'unchanged' if old == new else f'CHANGED ({sum((new - old).values())} of {len(calls)} prompts new): ' + ', '.join(moved)}")


if __name__ == "__main__":
    main()
