"""Virtual Bench (ভার্চুয়াল বেঞ্চ): an LLM council modelled on a Supreme Court bench.

Three judges from different model families decide independently, review each other's
anonymised opinions ("Justice A/B/C"), may revise, and a Chief Justice (a fourth model)
writes the majority opinion and records any dissent. Each judge is a council member with a
personality - Sunny (happy), Regal (proud), Grey (gloomy) - that colours its voice, how it
reads a borderline severity and how readily it revises; never what the statute says. Any dissent flags the claim for
human review. Judges see ONLY the retrieved statute text, the proposition and the clause
finding - never their own background knowledge of the law - so they cannot agree on a
section that is not in front of them.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass

from ain import config
from ain.llm import LLM
from ain.models import BenchOpinion, BenchResult, Claim, Risk, Section



@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    title: str
    seat: str
    role: str
    tagline: str
    voice: str
    disposition: str
    review_stance: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.seat})"

    def personality(self) -> str:
        return (
            f"PERSONALITY: You are {self.name}, {self.title}. Voice: {self.voice} "
            f"Severity: {self.disposition} Peer review: {self.review_stance} "
            "Your personality never changes what the statute text says."
        )


PERSONAS = [
    Persona(
        id="happy", name="Sunny", title="the Happy AI", seat="Justice A", role="bench_a",
        tagline="Every bad clause has a fix. Let's find it.",
        voice="warm, upbeat and encouraging; you lead with the remedy or the way out.",
        disposition="on a genuinely borderline call you rate one notch lower, but you never deny a risk the text plainly shows.",
        review_stance="you are open-minded and happy to revise if a colleague reads the text better.",
    ),
    Persona(
        id="proud", name="Regal", title="the Proud AI", seat="Justice B", role="bench_b",
        tagline="The text is clear. I have read it correctly.",
        voice="confident, formal and a little grand; you quote the statute precisely.",
        disposition="you call severity exactly as the text and the finding warrant, no more and no less.",
        review_stance="you keep your opinion unless the statute text plainly proves you wrong.",
    ),
    Persona(
        id="gloomy", name="Grey", title="the Gloomy AI", seat="Justice C", role="bench_c",
        tagline="Assume it will go wrong. It usually does.",
        voice="melancholy and wary; you describe how the clause will hurt the weaker party in practice.",
        disposition="on a genuinely borderline call you rate one notch higher, but you never invent a risk the text does not support.",
        review_stance="you revise only reluctantly, and never towards optimism without clear text.",
    ),
]
BY_ID = {p.id: p for p in PERSONAS}
SEV = ["low", "medium", "high", "critical"]

JUDGE_SYSTEM = """You are a judge on a three-member bench. Decide ONLY from the statute text provided; do not use outside
knowledge of the law. Question 1: does the statute text SUPPORT the legal proposition ("supports"), say nothing about it
("neutral"), or contradict it ("contradicts")? Question 2: given the contract finding, how severe is the risk for the
weaker party ("critical"|"high"|"medium"|"low")?
{personality}
Return JSON: {{"verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "2-3 sentences citing the text, in your voice"}}"""

REVIEW_SYSTEM = """You sat on a three-member bench. You see your own opinion and the anonymised opinions of the other two
judges. Re-read the statute text. You may keep or revise your verdict and severity. Decide ONLY from the statute text.
{personality}
Return JSON: {{"verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "...", "revised": true|false}}"""

CHAIR_SYSTEM = """You are the Chief Justice. Write the bench's ruling from the judges' final opinions: a short majority
opinion (2-3 sentences) and, if any judge disagrees with the majority verdict or severity, a one-sentence dissent
naming the member as labelled (e.g. "Grey (Justice C)"). The judges have personalities (happy, proud, gloomy); weigh
their reasoning, not their mood. Rely only on the statute text and the opinions.
Return JSON: {"majority_opinion": "...", "dissent": "... or null"}"""


def _case(claim: Claim, section: Section, risk: Risk) -> str:
    return (
        f"STATUTE: {section.act_en}, s.{section.section} - {section.heading}\n"
        f"TEXT:\n{section.text[:3000]}\n\n"
        f"PROPOSITION: {claim.proposition}\n"
        f"CONTRACT FINDING: {risk.finding}"
    )


FAKE_REASONING = {
    "happy": "Good news: the text of {cid} speaks to this directly, so the fix is clear.",
    "proud": "The text of {cid} is unambiguous and bears directly on the proposition.",
    "gloomy": "The text of {cid} bears on this, and I fear the worker will feel it.",
}


def _fake_opinion(p: Persona, claim: Claim, risk: Risk, fake_verdict: str) -> dict:
    sev = risk.severity
    # a deterministic stand-in for real disagreement: Sunny reads contract-law clashes more leniently
    if p.id == "happy" and risk.category in ("valid_abroad_void_bd", "regime_conflict"):
        sev = SEV[max(0, SEV.index(sev) - 1)]
    return {"verdict": fake_verdict, "severity": sev, "reasoning": FAKE_REASONING[p.id].format(cid=claim.citation_id)}


async def convene(llm: LLM, claim: Claim, section: Section, risk: Risk, fake_verdict: str) -> BenchResult:
    case = _case(claim, section, risk)
    first = await asyncio.gather(
        *(
            llm.json(
                role=p.role, system=JUDGE_SYSTEM.format(personality=p.personality()), user=case, task="bench_opinion",
                agent=f"Virtual Bench · {p.label}", fake=lambda p=p: _fake_opinion(p, claim, risk, fake_verdict),
            )
            for p in PERSONAS
        )
    )
    models = {p.role: model_name(llm, p.role) for p in PERSONAS}
    opinions = [_clean(p, models[p.role], op) for p, op in zip(PERSONAS, first)]

    async def review(i: int) -> dict:
        me = opinions[i]
        others = "\n".join(f"{o.seat}: verdict={o.verdict}, severity={o.severity}. {o.reasoning}" for j, o in enumerate(opinions) if j != i)
        user = f"{case}\n\nYOUR OPINION: verdict={me.verdict}, severity={me.severity}. {me.reasoning}\n\nOTHER JUDGES (anonymised):\n{others}"
        p = PERSONAS[i]
        return await llm.json(
            role=p.role, system=REVIEW_SYSTEM.format(personality=p.personality()), user=user, task="bench_review", agent=f"Virtual Bench · {p.label}",
            fake=lambda: {"verdict": me.verdict, "severity": me.severity, "reasoning": me.reasoning, "revised": False},
        )

    reviewed = await asyncio.gather(*(review(i) for i in range(3)))
    final = []
    for p, op, before in zip(PERSONAS, reviewed, opinions):
        o = _clean(p, models[p.role], op)
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
            dissent = f"{_label(d)} dissents: verdict {d.verdict}, severity {d.severity}."
        return {
            "majority_opinion": f"The bench holds by {vote} that the statute text {majority_verdict} the proposition; severity is {majority_severity}.",
            "dissent": dissent,
        }

    ops = "\n".join(f"{_label(o)}: verdict={o.verdict}, severity={o.severity}. {o.reasoning}" for o in final)
    chair = await llm.json(
        role="chairman", system=CHAIR_SYSTEM, task="bench_chair", agent="Virtual Bench · Chief Justice", fake=fake_chair,
        user=f"{case}\n\nFINAL OPINIONS:\n{ops}\n\nRESULT: {vote}; majority verdict {majority_verdict}, majority severity {majority_severity}.",
    )
    dissent = chair.get("dissent")
    if isinstance(dissent, str) and dissent.strip().lower() in ("", "null", "none"):
        dissent = None
    if dissenters and not dissent:
        dissent = f"{_label(dissenters[0])}: verdict {dissenters[0].verdict}, severity {dissenters[0].severity}."
    return BenchResult(
        question=claim.proposition,
        opinions=final,
        majority_verdict=majority_verdict,
        majority_severity=majority_severity,  # type: ignore[arg-type]
        vote=vote,
        majority_opinion=str(chair.get("majority_opinion") or fake_chair()["majority_opinion"]),
        dissent=dissent if dissenters else None,
        human_review=bool(dissenters),
        chairman_model=model_name(llm, "chairman"),
    )


def model_name(llm: LLM, role: str) -> str:
    return llm.resolve(role)[1] if llm.mode != "fake" else f"{config.role(role).model} (offline stand-in)"


def _label(o: BenchOpinion) -> str:
    return f"{o.name} ({o.seat})" if o.name else o.seat


def _clean(p: Persona, model: str, op: dict) -> BenchOpinion:
    verdict = op.get("verdict") if op.get("verdict") in ("supports", "neutral", "contradicts") else "neutral"
    sev = op.get("severity") if op.get("severity") in SEV else "medium"
    return BenchOpinion(
        seat=p.seat, model=model, persona=p.id, name=p.name, verdict=verdict, severity=sev, reasoning=str(op.get("reasoning", ""))[:600]
    )
