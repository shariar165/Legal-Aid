"""HTTP API for the Ain Copilot UI.

    uvicorn ain.api:app --port 8000        (from backend/)
"""

from __future__ import annotations

import asyncio
import json
import os
import re

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ain import auth, config, countries
from ain.agents import ablation, council
from ain.auth import Principal, owned_job, require_account, require_principal
from ain.export import memo_docx
from ain.llm import LLM, PIILeakError
from ain.models import (
    AblationResult,
    AnalysisResult,
    CouncilChatRequest,
    CouncilChatResponse,
    CouncilDeliberateRequest,
    CouncilDeliberateResponse,
    CouncilMember,
    Credentials,
    Destination,
    JobSummary,
    Me,
    Risk,
    Section,
)
from ain.orchestrator import JOBS, delete_result, load_result, new_job, run_pipeline, save_result
from ain.retrieval import get_corpus

MAX_BYTES = 15 * 1024 * 1024
ALLOWED = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

SAMPLES = [
    {
        "id": "migrant_photo",
        "file": "migrant_my_contract_photo.jpg",
        "kind": "image",
        "title": {"bn": "মালয়েশিয়ার চাকরির চুক্তি (ছবি)", "en": "Malaysia job contract (photo)"},
        "subtitle": {"bn": "প্রবাসী কর্মী · মোবাইলে তোলা ছবি", "en": "Migrant worker · phone photo"},
    },
    {
        "id": "migrant_text",
        "file": "migrant_my_contract.txt",
        "kind": "text",
        "title": {"bn": "মালয়েশিয়ার চাকরির চুক্তি (লেখা)", "en": "Malaysia job contract (text)"},
        "subtitle": {"bn": "প্রবাসী কর্মী · ডিজিটাল কপি", "en": "Migrant worker · digital copy"},
    },
    {
        "id": "migrant_sa",
        "file": "migrant_sa_contract.txt",
        "kind": "text",
        "title": {"bn": "সৌদি আরবের চাকরির চুক্তি", "en": "Saudi Arabia job contract"},
        "subtitle": {"bn": "প্রবাসী কর্মী · নির্মাণ শ্রমিক", "en": "Migrant worker · construction labourer"},
    },
    {
        "id": "migrant_sa_policy",
        "file": "migrant_sa_contract.txt",
        "policy_file": "employer_policy_sample.txt",
        "kind": "text",
        "title": {"bn": "সৌদি চুক্তি + কোম্পানির নিজের নীতি", "en": "Saudi contract + the employer's own policy"},
        "subtitle": {"bn": "চুক্তি কি কোম্পানির নিজের প্রতিশ্রুতি ভাঙছে?", "en": "Does the contract break the company's own promises?"},
    },
    {
        "id": "rmg_epz",
        "file": "rmg_dhaka_epz.txt",
        "kind": "text",
        "title": {"bn": "ঢাকা ইপিজেড কারখানা · ইইউ ক্রেতার চুক্তি", "en": "Dhaka EPZ factory · EU buyer agreement"},
        "subtitle": {"bn": "সাপ্লাই চুক্তি + নিয়োগপত্র", "en": "Supply agreement + appointment letter"},
    },
    {
        "id": "control",
        "file": "control_clean.txt",
        "kind": "text",
        "title": {"bn": "নিয়ন্ত্রণ চুক্তি (আইনসম্মত শর্ত)", "en": "Control agreement (compliant terms)"},
        "subtitle": {"bn": "নির্ভুলতা যাচাইয়ের জন্য", "en": "For precision testing"},
    },
]

PURGE_EVERY_S = 3600

app = FastAPI(title="Ain Copilot API", version="1.0")
# added first so CORS stays outermost: preflights are answered and a 403 still carries CORS headers
app.add_middleware(auth.SecurityMiddleware, origins=config.cors_origins())
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)
_tasks: set[asyncio.Task] = set()


def _background(coro) -> None:
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def _delete_job_files(job_ids: list[str]) -> None:
    for job_id in job_ids:
        delete_result(job_id)


@app.on_event("startup")
async def warm() -> None:
    async def _warm():
        corpus = await asyncio.to_thread(get_corpus)
        if corpus.dense_ready:
            await asyncio.to_thread(corpus.search, "warm up", None, 1)

    async def _purge():
        while True:
            _delete_job_files(await asyncio.to_thread(auth.purge_expired))
            await asyncio.sleep(PURGE_EVERY_S)

    _background(_warm())
    _background(_purge())


# ---------------------------------------------------------------- accounts


def _start_session(response: Response, p: Principal, token: str) -> Me:
    auth.set_cookie(response, token, p.expires_at)
    return Me(kind="account", email=p.email)


@app.post("/api/auth/signup", response_model=Me)
def signup(body: Credentials, request: Request, response: Response) -> Me:
    key = f"signup:{auth.client_ip(request)}"
    if auth.LIMITER.blocked(key, auth.SIGNUP_LIMIT, auth.SIGNUP_WINDOW):
        raise HTTPException(429, "Too many sign-up attempts. Try again later.")
    auth.LIMITER.hit(key)
    p, token = auth.signup(body.email, body.password, auth.principal(request))
    return _start_session(response, p, token)


@app.post("/api/auth/login", response_model=Me)
def login(body: Credentials, request: Request, response: Response) -> Me:
    keys = [f"login-ip:{auth.client_ip(request)}", f"login-email:{body.email.strip().lower()}"]
    if any(auth.LIMITER.blocked(k, auth.LOGIN_LIMIT, auth.LOGIN_WINDOW) for k in keys):
        raise HTTPException(429, "Too many failed sign-in attempts. Try again in 15 minutes.")
    try:
        p, token = auth.login(body.email, body.password, auth.principal(request))
    except HTTPException:
        for k in keys:
            auth.LIMITER.hit(k)
        raise
    return _start_session(response, p, token)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    p = auth.principal(request)
    if p is not None:
        auth.logout(p)
    auth.clear_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me", response_model=Me)
def me(request: Request, response: Response) -> Me:
    p = auth.principal(request)
    if p is None:
        return Me(kind=None)
    if not p.is_guest:
        auth.set_cookie(response, request.cookies[auth.COOKIE], p.expires_at)  # keep the browser cookie in step with the sliding expiry
    return Me(kind=p.kind, email=p.email)


@app.delete("/api/auth/me")
def delete_account(response: Response, p: Principal = Depends(require_account)) -> dict:
    """Right to erasure: the account, its sessions, and every analysis it owns."""
    _delete_job_files(auth.delete_user(p.user_id))
    auth.clear_cookie(response)
    return {"ok": True}


@app.get("/api/jobs", response_model=list[JobSummary])
def my_jobs(request: Request) -> list[JobSummary]:
    p = auth.principal(request)
    return [JobSummary(**j) for j in auth.list_jobs(p.user_id)] if p else []


@app.delete("/api/jobs/{job_id}", dependencies=[Depends(owned_job)])
def delete_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job and job.status in ("running", "waiting"):
        raise HTTPException(409, "The analysis is still running.")
    auth.forget_job(job_id)
    delete_result(job_id)
    return {"ok": True}


# ---------------------------------------------------------------- analysis


@app.get("/api/health")
def health() -> dict:
    corpus = get_corpus()
    return {
        "ok": True,
        "llm_mode": config.llm_mode(),
        "providers": {p: bool(config.provider(p).api_key) for p in ("groq", "openrouter")},
        "corpus_sections": len(corpus.sections),
        "acts": len({s.act_key for s in corpus.sections}),
        "dense_retrieval": corpus.dense_ready,
    }


@app.get("/api/samples")
def samples() -> list[dict]:
    return [
        {**{k: v for k, v in s.items() if k not in ("file", "policy_file")}, "with_policy": "policy_file" in s}
        for s in SAMPLES
        if (config.DEMO_DIR / "docs" / s["file"]).exists()
    ]


@app.get("/api/countries")
def destination_countries() -> list[Destination]:
    """Destination countries whose labour law is in the corpus (for the country picker)."""
    return [countries.as_destination(c) for c in countries.load_countries()]


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    name = os.path.basename(file.filename or "upload")
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise HTTPException(415, f"Unsupported file type {ext or '(none)'}. Use PDF, DOCX, TXT or an image.")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 15 MB).")
    return name, data


@app.post("/api/analyze")
async def analyze(
    file: UploadFile | None = File(None),
    sample_id: str | None = Form(None),
    llm_mode: str | None = Form(None),
    destination_country: str | None = Form(None),
    policy: UploadFile | None = File(None),  # the employer's own policy or handbook, checked against the contract
    owner: Principal = Depends(require_principal),
) -> dict:
    policy_doc = None
    if file is not None:
        name, data = await _read_upload(file)
        kind = None
    elif sample_id:
        sample = next((s for s in SAMPLES if s["id"] == sample_id), None)
        if not sample:
            raise HTTPException(404, "Unknown sample")
        name = sample["file"]
        data = (config.DEMO_DIR / "docs" / name).read_bytes()
        kind = "sample" if sample["kind"] == "text" else None
        if "policy_file" in sample:
            policy_doc = ((config.DEMO_DIR / "docs" / sample["policy_file"]).read_bytes(), sample["policy_file"])
    else:
        raise HTTPException(400, "Send a file or a sample_id.")
    if llm_mode and llm_mode not in ("live", "replay", "fake"):
        raise HTTPException(400, "llm_mode must be live, replay or fake")
    if destination_country and not countries.by_name(destination_country):
        raise HTTPException(400, "Unknown destination_country. See /api/countries.")
    if policy is not None:
        policy_name, policy_data = await _read_upload(policy)
        policy_doc = (policy_data, policy_name)

    job = new_job(name)
    auth.record_job(owner.user_id, job.id, name)
    task = asyncio.create_task(run_pipeline(job, data, name, kind, llm_mode, destination=destination_country, policy=policy_doc))
    _tasks.add(task)
    task.add_done_callback(lambda t: (_tasks.discard(t), t.exception() if not t.cancelled() else None))
    return {"job_id": job.id, "name": name}


@app.get("/api/jobs/{job_id}", dependencies=[Depends(owned_job)])
def job_status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        if load_result(job_id):
            return {"job_id": job_id, "status": "done", "events": 0, "error": None}
        raise HTTPException(404, "Unknown job")
    return {"job_id": job.id, "status": job.status, "events": len(job.events), "error": job.error}


@app.get("/api/jobs/{job_id}/events", dependencies=[Depends(owned_job)])
async def job_events(job_id: str, last_event_id: int | None = None):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")

    async def gen():
        start = (last_event_id + 1) if last_event_id is not None else 0
        async for i, ev in job.stream(start):
            if ev is None:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"id": str(i), "event": "trace", "data": ev.model_dump_json()}
        yield {"event": "end", "data": json.dumps({"status": job.status, "error": job.error})}

    return EventSourceResponse(gen())


class ConfirmBody(BaseModel):
    field: str = "salary"
    value: str


@app.post("/api/jobs/{job_id}/confirm", dependencies=[Depends(owned_job)])
def confirm(job_id: str, body: ConfirmBody) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    digits = re.sub(r"[^\d.]", "", body.value.translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")))
    try:
        value = float(digits)
    except ValueError:
        raise HTTPException(422, "Not a number") from None
    if value <= 0:
        raise HTTPException(422, "Salary must be positive")
    job.confirm(value)
    return {"ok": True, "value": value}


def _result_or_409(job_id: str) -> AnalysisResult:
    r = load_result(job_id)
    if r is None:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "Unknown job")
        raise HTTPException(409, f"Job is {job.status}" + (f": {job.error}" if job.error else ""))
    return r


@app.get("/api/jobs/{job_id}/result", response_model=AnalysisResult, dependencies=[Depends(owned_job)])
def result(job_id: str) -> AnalysisResult:
    return _result_or_409(job_id)


@app.get("/api/jobs/{job_id}/memo.docx", dependencies=[Depends(owned_job)])
def memo(job_id: str) -> Response:
    r = _result_or_409(job_id)
    return Response(
        memo_docx(r),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="ain-copilot-memo-{job_id}.docx"'},
    )


@app.post("/api/jobs/{job_id}/ablation", response_model=AblationResult, dependencies=[Depends(owned_job)])
async def run_ablation(job_id: str) -> AblationResult:
    r = _result_or_409(job_id)
    if r.ablation is None:
        r.ablation = await ablation.run(LLM(mode=r.llm_mode), get_corpus(), r)
        save_result(r)
    return r.ablation


@app.get("/api/council", response_model=list[CouncilMember])
def council_members() -> list[CouncilMember]:
    return council.members(LLM(mode=council.chat_mode(config.llm_mode())))


PII_MESSAGE = "Your message contains personal identifiers (a phone number, NID, passport, account or name). Please remove them and ask again."


def _council_risk(r: AnalysisResult, risk_id: str | None) -> Risk | None:
    if not risk_id:
        return None
    risk = next((k for k in r.risks if k.id == risk_id), None)
    if risk is None:
        raise HTTPException(404, "Unknown risk")
    return risk


def _save_council_calls(r: AnalysisResult, llm: LLM) -> None:
    r.privacy.outbound_calls.extend(llm.calls)
    save_result(r)


@app.post("/api/jobs/{job_id}/council/chat", response_model=CouncilChatResponse, dependencies=[Depends(owned_job)])
async def council_chat(job_id: str, body: CouncilChatRequest) -> CouncilChatResponse:
    r = _result_or_409(job_id)
    unknown = [m for m in body.members if m not in council.BY_ID]
    if unknown:
        raise HTTPException(422, f"Unknown council member: {', '.join(unknown)}")
    risk = _council_risk(r, body.risk_id)
    llm = LLM(mode=council.chat_mode(r.llm_mode))
    try:
        replies = await council.chat(llm, r, body.message.strip(), body.members, risk, body.history, body.language)
    except PIILeakError:
        raise HTTPException(422, PII_MESSAGE) from None
    _save_council_calls(r, llm)
    return CouncilChatResponse(replies=replies)


@app.post("/api/jobs/{job_id}/council/deliberate", response_model=CouncilDeliberateResponse, dependencies=[Depends(owned_job)])
async def council_deliberate(job_id: str, body: CouncilDeliberateRequest) -> CouncilDeliberateResponse:
    """Round 2: the members respond to each other's first answers, then the Chief Justice rules."""
    r = _result_or_409(job_id)
    if len({x.member for x in body.replies if x.member in council.BY_ID}) < 2:
        raise HTTPException(422, "Deliberation needs first answers from at least two council members.")
    risk = _council_risk(r, body.risk_id)
    llm = LLM(mode=council.chat_mode(r.llm_mode))
    try:
        rebuttals, ruling = await council.deliberate(llm, r, body.message.strip(), body.replies, risk, body.history, body.language)
    except PIILeakError:
        raise HTTPException(422, PII_MESSAGE) from None
    _save_council_calls(r, llm)
    return CouncilDeliberateResponse(rebuttals=rebuttals, ruling=ruling)


@app.get("/api/corpus/{citation_id}", response_model=Section)
def corpus_section(citation_id: str) -> Section:
    sec = get_corpus().get(citation_id)
    if not sec:
        raise HTTPException(404, "No such section")
    return sec
