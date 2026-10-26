"""Ain Copilot as an MCP server: the verified-law tools, for any MCP client (Claude Desktop, Claude Code, Cursor…).

    python -m ain.mcp_server               stdio (local: register it in .mcp.json / claude_desktop_config.json)
    POST /api/mcp                          streamable HTTP, mounted in ain/api.py (needs AIN_MCP_TOKEN)

The tools reuse the engine as it is: hybrid retrieval over the corpus, the 4-gate verifier, the arithmetic wage
calculator and the full pipeline. Nothing here adds legal logic, and the guarantees stay the same: law comes only
from the corpus, a citation is only as good as its gates, and text with an identifier in it never reaches a model.
"""

from __future__ import annotations

import asyncio
import hmac
import os

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.server.transport_security import TransportSecuritySettings

from ain import config, countries
from ain.agents import calculator, verifier
from ain.agents.pii import find_pii
from ain.llm import LLM
from ain.models import Claim, Deduction, DocFacts, PackDecision, RouteDecision, Section
from ain.orchestrator import new_job, run_pipeline
from ain.retrieval import get_corpus

EXCERPT_CHARS = 500
MAX_CONTRACT_CHARS = 200_000

server = MCPServer(
    name="ain-copilot",
    title="Ain Copilot: verified Bangladesh labour and migration law",
    version="1.0",
    instructions=(
        "Statutes, ILO standards and destination-country labour law for Bangladeshi workers, as verbatim official "
        "text. Cite only citation_ids returned by search_law or get_section, and check a legal claim with "
        "verify_citation before relying on it. Decision support, not legal advice."
    ),
)


def _refuse_pii(**fields: str | None) -> None:
    for name, text in fields.items():
        if text and (hits := find_pii(text)):
            kinds = ", ".join(sorted({k for k, _ in hits}))
            raise ToolError(f"`{name}` contains personal data ({kinds}). Redact it first; Ain never sends identifiers to a model.")


def _brief(s: Section, score: float | None = None) -> dict:
    out = {
        "citation_id": s.citation_id,
        "act": s.act_en,
        "section": s.section,
        "heading": s.heading,
        "kind": s.kind,
        "status": s.status,
        "packs": s.packs,
        "url": s.url,
        "excerpt": s.text[:EXCERPT_CHARS] + ("…" if len(s.text) > EXCERPT_CHARS else ""),
    }
    if score is not None:
        out["score"] = round(score, 4)
    return out


def _route_for(packs: list[str], reason: str) -> RouteDecision:
    return RouteDecision(packs=[PackDecision(pack=p, label=p, reason=reason) for p in packs])


@server.tool()
def search_law(query: str, packs: list[str] | None = None, k: int = 5, include_repealed: bool = False) -> list[dict]:
    """Hybrid search (BM25 + multilingual dense, RRF fusion) over Ain's corpus of verbatim official law.

    Works in English or Bangla; for the best recall ask in both. `packs` narrows the search, e.g. ["bd_labour"],
    ["bd_epz"] (factories inside an EPZ), ["bd_migration"], ["my_employment"], ["sa_labour"], ["ilo"],
    ["std_recruitment"] (voluntary standards, not law); list_countries gives each country's pack.
    """
    hits = get_corpus().search(query, packs=set(packs) if packs else None, k=max(1, min(k, 20)), include_repealed=include_repealed)
    return [_brief(s, score) for s, score in hits]


@server.tool()
def get_section(citation_id: str) -> dict:
    """The full text of one section, with its status (in force / amended / repealed), what superseded it, and the
    official source link."""
    s = get_corpus().get(citation_id)
    if s is None:
        raise ToolError(f"{citation_id} is not in the corpus. Use search_law to find a citation_id.")
    return {
        **_brief(s),
        "act_bn": s.act,
        "year": s.year,
        "jurisdiction": s.jurisdiction,
        "text": s.text,
        "lang": s.lang,
        "superseded_by": s.superseded_by,
        "amendment_notes": s.amendment_notes,
        "source": s.source,
        "retrieved_at": s.retrieved_at,
    }


@server.tool()
async def verify_citation(citation_id: str, proposition: str, quote: str | None = None) -> dict:
    """Check one legal claim with Ain's verifier: G1 the section exists, G2 the quote is verbatim (fuzzy, if given),
    G3 a judge model decides from the section text alone whether it supports the proposition, G4 the law is still in
    force. Verdict: verified / partial / dropped. Whether the section applies to a particular document (e.g. the
    Labour Act inside an EPZ) is decided by analyze_contract, which knows the document."""
    _refuse_pii(proposition=proposition, quote=quote)
    corpus = get_corpus()
    sec = corpus.get(citation_id)
    claim = Claim(id="mcp-1", risk_id="mcp", proposition=proposition, citation_id=citation_id, quote=quote, origin="drafter")
    route = _route_for(sec.packs if sec else [], "the section's own law pack (MCP call, no document)")
    v = await verifier.verify_claim(LLM(mode=config.llm_mode()), corpus, route, claim, None, use_bench=False)
    return {
        "verdict": v.verdict,
        "gates": [g.model_dump() for g in v.gates],
        "section": _brief(v.section) if v.section else None,
    }


@server.tool()
def wage_truth(salary: float, country: str, deductions: list[dict] | None = None) -> dict:
    """Plain arithmetic, no model: monthly salary minus monthly deductions, compared with the country's legal
    minimum wage and deduction cap (each tied to a corpus citation). `country` is a name or code (e.g. "MY",
    "Saudi Arabia"); `deductions` items are {label, amount, per: "month" | "once"} in the salary's currency."""
    c = countries.by_name(country)
    if c is None:
        raise ToolError(f"No labour law in the corpus for {country!r}. Supported: {', '.join(x.code for x in countries.load_countries())}.")
    facts = DocFacts(salary_amount=salary, salary_currency=c.currency, deductions=[Deduction(**d) for d in deductions or []])
    calc = calculator.compute(facts, _route_for([c.pack], f"country of work: {c.name['en']}"), confirmed=True)
    if calc is None:
        return {"currency": c.currency, "net": salary, "note": "No deductions given and no minimum wage in the corpus for this country."}
    return calc.model_dump()


@server.tool()
async def analyze_contract(text: str, country: str | None = None) -> dict:
    """Run the whole Ain pipeline on a contract: ingestion, PII Shield, jurisdiction router, playbook + adversarial
    counsel, wage check, 4-gate verifier with the Virtual Bench, critic and memo. Personal data is redacted before
    any model call. Returns the risks with only their verified citations, the routed law packs and the wage check.
    On free-tier keys a long contract takes minutes."""
    if len(text) > MAX_CONTRACT_CHARS:
        raise ToolError(f"Contract too long ({len(text):,} chars, max {MAX_CONTRACT_CHARS:,}).")
    c = countries.by_name(country) if country else None
    r = await run_pipeline(new_job("mcp_contract.txt"), text.encode("utf-8"), "mcp_contract.txt", confirm_timeout=0.1, destination=c.code if c else None)
    verified = {v.claim.id: v for v in r.ledger if v.verdict in ("verified", "partial")}
    return {
        "llm_mode": r.llm_mode,
        "law_packs": [p.pack for p in r.route.packs],
        "excluded_packs": [{"pack": p.pack, "reason": p.reason} for p in r.route.excluded],
        "scope_note": r.route.scope_note.en if r.route.scope_note else None,
        "risks": [
            {
                "title": k.title.en,
                "severity": k.severity,
                "origin": k.origin,
                "status": k.status,
                "finding": k.finding,
                "action": k.action.en,
                "clash": k.clash,
                "citations": [
                    {"citation_id": verified[i].claim.citation_id, "verdict": verified[i].verdict, "proposition": verified[i].claim.proposition}
                    for i in k.claim_ids
                    if i in verified
                ],
            }
            for k in r.risks
            if k.status != "dropped"
        ],
        "claims_dropped": sum(1 for v in r.ledger if v.verdict == "dropped"),
        "wage": r.wage.model_dump() if r.wage else None,
    }


@server.tool()
def list_countries() -> list[dict]:
    """Destination countries whose labour law is in the corpus, with the law pack to pass to search_law."""
    return [
        {"code": c.code, "name": c.name["en"], "pack": c.pack, "law": c.label, "currency": c.currency,
         "minimum_wage": c.min_wage, "deduction_cap": c.deduction_cap}
        for c in countries.load_countries()
    ]


@server.resource("ain://corpus/{citation_id}", name="statute-section", mime_type="text/plain")
def section_text(citation_id: str) -> str:
    """The verbatim text of one corpus section."""
    s = get_corpus().get(citation_id)
    if s is None:
        raise ResourceNotFoundError(f"{citation_id} is not in the corpus.")
    return f"{s.act_en}, s.{s.section}: {s.heading}\nStatus: {s.status}\nSource: {s.url}\n\n{s.text}"


@server.resource("ain://playbook/rules", name="risk-playbook", mime_type="application/yaml")
def playbook_rules() -> str:
    """Ain's YAML risk playbook: each rule's trigger, severity and anchored citations."""
    return "\n---\n".join(p.read_text(encoding="utf-8") for p in sorted(config.PLAYBOOK_DIR.glob("*.yaml")))


@server.prompt()
def review_contract(contract_excerpt: str) -> str:
    """Review a clause or contract with Ain's tools, citing only verified law."""
    return (
        "Review this contract text for the worker's risks under Bangladesh law, the ILO standards and the law of the "
        "country of work. Use search_law (ask in English and Bangla), read each candidate with get_section, and run "
        "verify_citation on every legal claim. Cite only claims whose verdict is verified, by citation_id, and say "
        "which claims were dropped and why. For the whole document, call analyze_contract instead.\n\n"
        f"<contract>\n{contract_excerpt}\n</contract>"
    )


# ---------------------------------------------------------------- streamable HTTP (mounted by ain/api.py)


def http_token() -> str | None:
    return os.getenv("AIN_MCP_TOKEN") or None


def _allowed_hosts() -> list[str]:
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    if space := os.getenv("SPACE_HOST"):  # Hugging Face Spaces
        hosts.append(space)
    hosts += [h.strip() for h in os.getenv("AIN_MCP_HOSTS", "").split(",") if h.strip()]
    return hosts


class BearerGuard:
    """Rejects HTTP MCP requests without `Authorization: Bearer $AIN_MCP_TOKEN` (constant-time compare)."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        got = dict(scope.get("headers") or []).get(b"authorization", b"")
        if scope["type"] == "http" and not hmac.compare_digest(got, b"Bearer " + self.token):
            await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
            await send({"type": "http.response.body", "body": b'{"error":"missing or wrong bearer token"}'})
            return
        await self.app(scope, receive, send)


def http_routes(path: str = "/api/mcp") -> list:
    """The streamable-HTTP route, behind the bearer guard. Stateless + JSON responses, so it works through the
    Next.js /api proxy (no long-lived SSE stream to buffer). Run `serve_http_sessions()` while the app is up."""
    app = server.streamable_http_app(
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(allowed_hosts=_allowed_hosts(), allowed_origins=[]),
    )
    routes = [r for r in app.routes if getattr(r, "path", None) == path]
    for r in routes:
        r.app = BearerGuard(r.app, http_token() or "")
    return routes


async def serve_http_sessions(stop: asyncio.Event) -> None:
    async with server.session_manager.run():
        await stop.wait()


if __name__ == "__main__":
    server.run("stdio")
