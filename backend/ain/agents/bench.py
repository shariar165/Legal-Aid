"""Virtual Bench (ভার্চুয়াল বেঞ্চ): an LLM council modelled on a Supreme Court bench.

Three judges from different model families decide independently, review each other's
anonymised opinions ("Justice A/B/C"), may revise, and a Chief Justice (a fourth model)
writes the majority opinion and records any dissent. Any dissent flags the claim for
human review. Judges see ONLY the retrieved statute text, the proposition and the clause
finding - never their own background knowledge of the law - so they cannot agree on a
section that is not in front of them.
"""

from __future__ import annotations

import asyncio
from collections import Counter

from ain import config
from ain.llm import LLM
from ain.models import BenchOpinion, BenchResult, Claim, Risk, Section

SEATS = [("Justice A", "bench_a"), ("Justice B", "bench_b"), ("Justice C", "bench_c")]
SEV = ["low", "medium", "high", "critical"]

JUDGE_SYSTEM = """You are a judge on a three-member bench. Decide ONLY from the statute text provided; do not use outside
knowledge of the law. Question 1: does the statute text SUPPORT the legal proposition ("supports"), say nothing about it
("neutral"), or contradict it ("contradicts")? Question 2: given the contract finding, how severe is the risk for the
weaker party ("critical"|"high"|"medium"|"low")?
Return JSON: {"verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "2-3 sentences citing the text"}"""

REVIEW_SYSTEM = """You sat on a three-member bench. You see your own opinion and the anonymised opinions of the other two
judges. Re-read the statute text. You may keep or revise your verdict and severity. Decide ONLY from the statute text.
Return JSON: {"verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "...", "revised": true|false}"""

CHAIR_SYSTEM = """You are the Chief Justice. Write the bench's ruling from the judges' final opinions: a short majority
opinion (2-3 sentences) and, if any judge disagrees with the majority verdict or severity, a one-sentence dissent
naming the seat (e.g. "Justice C"). Rely only on the statute text and the opinions.
Return JSON: {"majority_opinion": "...", "dissent": "... or null"}"""


def _case(claim: Claim, section: Section, risk: Risk) -> str:
    return (
        f"STATUTE: {section.act_en}, s.{section.section} - {section.heading}\n"
        f"TEXT:\n{section.text[:3000]}\n\n"
        f"PROPOSITION: {claim.proposition}\n"
        f"CONTRACT FINDING: {risk.finding}"
    )


def _fake_opinion(seat: str, claim: Claim, risk: Risk, fake_verdict: str) -> dict:
    sev = risk.severity
    # a deterministic stand-in for real disagreement: Justice C reads contract-law clashes more narrowly
    if seat == "Justice C" and risk.category in ("valid_abroad_void_bd", "regime_conflict"):
        sev = SEV[max(0, SEV.index(sev) - 1)]
    return {"verdict": fake_verdict, "severity": sev, "reasoning": f"The cited text of {claim.citation_id} bears directly on the proposition."}


async def convene(llm: LLM, claim: Claim, section: Section, risk: Risk, fake_verdict: str) -> BenchResult:
    case = _case(claim, section, risk)
    first = await asyncio.gather(
        *(
            llm.json(role=role, system=JUDGE_SYSTEM, user=case, task="bench_opinion", agent=f"Virtual Bench · {seat}", fake=lambda s=seat: _fake_opinion(s, claim, risk, fake_verdict))
            for seat, role in SEATS
        )
    )
    models = {role: (llm.resolve(role)[1] if llm.mode != "fake" else f"{config.role(role).model} (offline stand-in)") for _, role in SEATS}
    opinions = [_clean(seat, models[role], op) for (seat, role), op in zip(SEATS, first)]

    async def review(i: int) -> dict:
        me = opinions[i]
        others = "\n".join(f"{o.seat}: verdict={o.verdict}, severity={o.severity}. {o.reasoning}" for j, o in enumerate(opinions) if j != i)
        user = f"{case}\n\nYOUR OPINION: verdict={me.verdict}, severity={me.severity}. {me.reasoning}\n\nOTHER JUDGES (anonymised):\n{others}"
        return await llm.json(
            role=SEATS[i][1], system=REVIEW_SYSTEM, user=user, task="bench_review", agent=f"Virtual Bench · {me.seat}",
            fake=lambda: {"verdict": me.verdict, "severity": me.severity, "reasoning": me.reasoning, "revised": False},
        )

    reviewed = await asyncio.gather(*(review(i) for i in range(3)))
    final = []
    for (seat, role), op, before in zip(SEATS, reviewed, opinions):
        o = _clean(seat, models[role], op)
        o.revised = o.verdict != before.verdict or o.severity != before.severity
        final.append(o)

    verdicts = Counter(o.verdict for o in final)
    majority_verdict, votes = verdicts.most_common(1)[0]
    severities = sorted((SEV.index(o.severity) for o in final))
    majority_severity = SEV[severities[1]]  # median of three
    # a judge dissents if they differ from the majority on the verdict OR on severity
    dissenters = [o for o in final if o.verdict != majority_verdict or o.severity != majority_severity]
    vote = f"{3 - len(dissenters)}–{len(dissenters)}"

    def fake_chair() -> dict:
        dissent = None
        if dissenters:
            d = dissenters[0]
            dissent = f"{d.seat} dissents: verdict {d.verdict}, severity {d.severity}."
        return {
            "majority_opinion": f"The bench holds by {vote} that the statute text {majority_verdict} the proposition; severity is {majority_severity}.",
            "dissent": dissent,
        }

    ops = "\n".join(f"{o.seat}: verdict={o.verdict}, severity={o.severity}. {o.reasoning}" for o in final)
    chair = await llm.json(
        role="chairman", system=CHAIR_SYSTEM, task="bench_chair", agent="Virtual Bench · Chief Justice", fake=fake_chair,
        user=f"{case}\n\nFINAL OPINIONS:\n{ops}\n\nRESULT: {vote}; majority verdict {majority_verdict}, majority severity {majority_severity}.",
    )
    dissent = chair.get("dissent")
    if isinstance(dissent, str) and dissent.strip().lower() in ("", "null", "none"):
        dissent = None
    if dissenters and not dissent:
        dissent = f"{dissenters[0].seat}: verdict {dissenters[0].verdict}, severity {dissenters[0].severity}."
    return BenchResult(
        question=claim.proposition,
        opinions=final,
        majority_verdict=majority_verdict,
        majority_severity=majority_severity,  # type: ignore[arg-type]
        vote=vote,
        majority_opinion=str(chair.get("majority_opinion") or fake_chair()["majority_opinion"]),
        dissent=dissent if dissenters else None,
        human_review=bool(dissenters),
        chairman_model=llm.resolve("chairman")[1] if llm.mode != "fake" else f"{config.role('chairman').model} (offline stand-in)",
    )


def _clean(seat: str, model: str, op: dict) -> BenchOpinion:
    verdict = op.get("verdict") if op.get("verdict") in ("supports", "neutral", "contradicts") else "neutral"
    sev = op.get("severity") if op.get("severity") in SEV else "medium"
    return BenchOpinion(seat=seat, model=model, verdict=verdict, severity=sev, reasoning=str(op.get("reasoning", ""))[:600])
