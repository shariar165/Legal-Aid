"""The MCP server: tools answer from the corpus and the verifier, PII is refused, HTTP needs the bearer token."""

import asyncio
import contextlib
import json

import pytest
from mcp import Client
from starlette.applications import Starlette
from starlette.testclient import TestClient

from ain import mcp_server
from ain.retrieval import get_corpus

from .conftest import DOCS

TOKEN = "test-token-123"


def _data(result):
    assert not result.is_error, result.content
    if result.structured_content is not None:
        data = result.structured_content
        return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data
    return json.loads(result.content[0].text)


async def _call(name, args):
    async with Client(mcp_server.server) as client:
        return await client.call_tool(name, args)


def test_lists_tools_resources_and_prompt():
    async def go():
        async with Client(mcp_server.server) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            prompts = {p.name for p in (await client.list_prompts()).prompts}
            playbook = await client.read_resource("ain://playbook/rules")
            return tools, prompts, playbook

    tools, prompts, playbook = asyncio.run(go())
    assert {"search_law", "get_section", "verify_citation", "wage_truth", "analyze_contract", "list_countries"} <= tools
    assert "review_contract" in prompts
    assert "rules" in playbook.contents[0].text


def test_search_law_is_bilingual_and_pack_filtered():
    hits = _data(asyncio.run(_call("search_law", {"query": "passport kept by employer", "k": 5})))
    assert hits and all(get_corpus().get(h["citation_id"]) for h in hits)
    bn = _data(asyncio.run(_call("search_law", {"query": "মাতৃত্বকালীন ছুটি", "packs": ["bd_labour"], "k": 3})))
    assert bn and all("bd_labour" in h["packs"] for h in bn)


def test_get_section_returns_verbatim_text():
    sec = get_corpus().sections[0]
    got = _data(asyncio.run(_call("get_section", {"citation_id": sec.citation_id})))
    assert got["text"] == sec.text and got["url"] == sec.url
    assert asyncio.run(_call("get_section", {"citation_id": "NOPE-s999"})).is_error


def test_verify_citation_runs_the_gates():
    sec = next(s for s in get_corpus().sections if s.status == "in_force" and len(s.text) > 80)
    quote = sec.text[:60]
    ok = _data(asyncio.run(_call("verify_citation", {"citation_id": sec.citation_id, "proposition": sec.heading, "quote": quote})))
    assert [g["gate"] for g in ok["gates"]] == ["existence", "fidelity", "entailment", "currency"]
    assert ok["gates"][0]["status"] == "pass" and ok["gates"][1]["status"] == "pass"
    made_up = _data(asyncio.run(_call("verify_citation", {"citation_id": "BD-FAKE-s1", "proposition": "anything"})))
    assert made_up["verdict"] == "dropped"


def test_verify_citation_refuses_pii():
    res = asyncio.run(_call("verify_citation", {"citation_id": "x", "proposition": "Passport no. A01234567 was kept", "quote": None}))
    assert res.is_error and "personal data" in res.content[0].text


def test_wage_truth_is_arithmetic():
    calc = _data(asyncio.run(_call("wage_truth", {"salary": 1200, "country": "MY", "deductions": [{"label": "housing", "amount": 650}]})))
    assert calc["net"] == 550 and calc["minimum_wage"] == 1700 and calc["below_minimum"]


def test_analyze_contract_returns_only_verified_citations():
    text = (DOCS / "migrant_my_contract.txt").read_text(encoding="utf-8")
    out = _data(asyncio.run(_call("analyze_contract", {"text": text})))
    assert len(out["risks"]) >= 3
    cited = [c for r in out["risks"] for c in r["citations"]]
    assert cited and all(c["verdict"] in ("verified", "partial") for c in cited)


def test_http_needs_the_bearer_token(monkeypatch):
    monkeypatch.setenv("AIN_MCP_TOKEN", TOKEN)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        stop = asyncio.Event()
        task = asyncio.create_task(mcp_server.serve_http_sessions(stop))
        await asyncio.sleep(0)
        yield
        stop.set()
        await task

    app = Starlette(routes=mcp_server.http_routes(), lifespan=lifespan)
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "MCP-Protocol-Version": "2025-06-18"}
    with TestClient(app, base_url="http://127.0.0.1:8000") as http:
        assert http.post("/api/mcp", json=body, headers=headers).status_code == 401
        assert http.post("/api/mcp", json=body, headers={**headers, "Authorization": "Bearer wrong"}).status_code == 401
        r = http.post("/api/mcp", json=body, headers={**headers, "Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200, r.text
        assert "search_law" in r.text


@pytest.mark.parametrize("country", ["Atlantis"])
def test_wage_truth_unknown_country_is_an_error(country):
    assert asyncio.run(_call("wage_truth", {"salary": 100, "country": country})).is_error


def test_metrics_endpoint_lists_corpus_routing_mcp_and_eval():
    from ain.api import app

    with TestClient(app) as http:
        m = http.get("/api/metrics").json()
    assert m["corpus"]["sections"] == len(get_corpus().sections)
    assert sum(m["corpus"]["by_kind"].values()) == m["corpus"]["sections"]
    assert {r["role"] for r in m["llm"]["roles"]} >= {"fast", "reasoner", "judge", "bench_a", "bench_b", "bench_c", "chairman"}
    assert "search_law" in m["mcp"]["tools"] and m["mcp"]["http_enabled"] is False
    assert m["eval"]["results"] and all("recall" in r for r in m["eval"]["results"])
