"""Virtual Bench (ভার্চুয়াল বেঞ্চ): an LLM council modelled on a Supreme Court bench.

Three judges from different model families decide independently, review each other's
anonymised opinions ("Justice A/B/C"), may revise, and a Chief Justice (a fourth model)
writes the majority opinion and records any dissent. Any dissent flags the claim for human
review. A judge whose call fails on every model route gives "no opinion" and does not vote; the claim is flagged for
human review, and with fewer than two opinions the bench has no quorum and the single-judge check (Gate 3) decides. Judges see ONLY the retrieved statute text, the proposition and the clause finding -
never their own background knowledge of the law - so they cannot agree on a section that is
not in front of them.

Each judge answers two questions, under different rules:
- the VERDICT (does the text support the proposition?) is one neutral test, worded
  identically for all three judges (`VERDICT_TEST`) and decided from the statute text alone;
- the SEVERITY, the reasoning and the council chat go through the judge's personality: a
  reasoning lens - Sunny (happy) looks for remedies and exceptions, Regal (proud) tests the
  strict wording and definitions, Grey (gloomy) asks how the clause can be exploited and
  whether the worker could really enforce the right - plus a voice, a borderline-severity
  lean and a peer-review stance. With `severity_rubric` on, the severity follows one written rubric (`SEVERITY_RUBRIC`),
  the same for every judge, and the lens shapes only the reasoning and the advice.

Three OpenRouter quota savers sit behind flags in ain/config.yaml (`bench:`), each off until
eval/bench_quality.py shows that it leaves the answers unchanged:
- review_only_on_disagreement: skip the peer-review round when all three first opinions already
  agree on both verdict and severity;
- batch_bench: one call per judge for up to `batch_size` claims, in a different order for each
  judge. Every answer must quote a phrase from its own statute text (checked in code); a claim
  whose answer is missing, malformed or quotes the wrong text is re-run on its own;
- statute_window: long sections are cut down to whole sub-sections, always keeping the cited sub-section,
  the claim's quote, the definitions they use, and every proviso and exception; never cutting a sentence.

Without the window the judges read the whole cited section. Only a section over `STATUTE_MAX_CHARS` (a handful of long
definition and schedule sections) is cut, by the same anchored window, so a cited sub-section or a proviso is never lost.
"""

from __future__ import annotations

import asyncio
import random
import re
from collections import Counter
from dataclasses import dataclass

from ain import config
from ain.llm import LLM, LLMError
from ain.models import BenchOpinion, BenchResult, Claim, Risk, Section
from ain.retrieval import nfc, tokenize



@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    title: str
    seat: str
    role: str
    tagline: str
    lens_label: str  # shown first in the UI and the memo; the name is flavour
    lens: str
    voice: str
    disposition: str
    review_stance: str

    @property
    def label(self) -> str:
        return f"{self.lens_label} ({self.name}, {self.seat})"

    def personality(self, leans: bool = True, rubric: bool = False) -> str:
        """Shapes severity, reasoning and chat only; the verdict test (`VERDICT_TEST`) stays outside it.
        `leans=False` drops the one-notch borderline severity lean (config `bench_leans`), keeping lens and voice.
        `rubric=True` (config `severity_rubric`): the rating follows `SEVERITY_RUBRIC`, so the personality drops the lean
        and the severity stance in peer review and shapes only the reasoning, the advice and the voice."""
        if rubric:
            return (
                f"PERSONALITY (it shapes your reasoning, your advice and your voice - never the verdict or the severity rating): "
                f"You are {self.name}, {self.title}. Lens: {self.lens} Voice: {self.voice} "
                f"Your personality never changes what the statute text says or which rubric level applies."
            )
        lean = f"Severity: {self.disposition} " if leans else ""
        return (
            f"PERSONALITY (it shapes your severity, your reasoning and your voice - never the verdict): You are {self.name}, "
            f"{self.title}. Lens: {self.lens} Voice: {self.voice} {lean}"
            f"Peer review: {self.review_stance} Your personality never changes what the statute text says."
        )


PERSONAS = [
    Persona(
        id="happy", name="Sunny", title="the Constructive AI", seat="Justice A", role="bench_a",
        tagline="Every bad clause has a fix. Let's find it.", lens_label="Remedies",
        lens="remedies and exceptions - look in the text for provisos, exemptions, cures and rights the worker can invoke, "
        "and how the clause could be fixed or renegotiated; weigh how far a remedy the text offers reduces the harm.",
        voice="warm, upbeat and encouraging; you lead with the way out.",
        disposition="on a genuinely borderline call you rate one notch lower, but you never deny a risk the text plainly shows.",
        review_stance="you are open-minded and readily move your severity if a colleague's reasoning is better.",
    ),
    Persona(
        id="proud", name="Regal", title="the Proud AI", seat="Justice B", role="bench_b",
        tagline="The words decide, so I read them closely.", lens_label="Text",
        lens="strict wording and definitions - test the clause against the exact words, defined terms and conditions of the "
        "section, element by element, and infer nothing the text does not say.",
        voice="confident, formal and a little grand; you quote the statute precisely.",
        disposition="you call severity exactly as the text and the finding warrant, no more and no less.",
        review_stance="you keep your severity unless a colleague shows the text plainly says otherwise.",
    ),
    Persona(
        id="gloomy", name="Grey", title="the Gloomy AI", seat="Justice C", role="bench_c",
        tagline="Assume it will go wrong. It usually does.", lens_label="Enforcement",
        lens="worst case and enforceability - ask how an employer could exploit the clause, and whether the worker could "
        "realistically enforce the right the text gives (cost, distance, proof, fear of retaliation).",
        voice="melancholy and wary; you describe how the clause will hurt the weaker party in practice.",
        disposition="on a genuinely borderline call you rate one notch higher, but you never invent a risk the text does not support.",
        review_stance="you lower your severity only reluctantly, and never towards optimism without clear text.",
    ),
]
BY_ID = {p.id: p for p in PERSONAS}
SEV = ["low", "medium", "high", "critical"]
REASONING_CHARS = 1200

# Identical for every judge, and kept outside the personality block: the lens must not move the verdict.
VERDICT_TEST = """Question 1 (verdict) is the same neutral test for every judge on the bench. Reading the statute text alone,
does it SUPPORT the legal proposition ("supports"), say nothing about it ("neutral"), or contradict it ("contradicts")?
Decide it first and on the text only; your lens, voice and severity lean play no part in it."""

# Question 2 as the judges' personalities answer it (severity_rubric off) ...
SEVERITY_QUESTION = """Question 2 (severity): given the contract finding, how severe is the risk for the weaker party
("critical"|"high"|"medium"|"low")? Answer it, and write your reasoning, through your personality below."""
REVIEW_SEVERITY = """You may
keep or revise your severity and reasoning, through your personality below."""
# ... and under one written rubric, the same for every judge (severity_rubric on)
SEVERITY_RUBRIC = """Question 2 (severity): rate the risk the contract finding creates for the weaker party by this written rubric,
the same for every judge. Take the FIRST level that applies:
  "critical" - a criminal offence, a forced-labour indicator, or the worker's passport or liberty withheld;
  "high"     - a statutory entitlement denied, or a major loss of money;
  "medium"   - a right restricted, but a remedy is available;
  "low"      - procedural or documentary.
The rating follows the rubric alone. Write your reasoning and your advice through your personality below; it never
moves the rating."""
REVIEW_RUBRIC = """Revise your
severity only where the rubric shows another level applies; keep or revise your reasoning through your personality.
""" + SEVERITY_RUBRIC

JUDGE_SYSTEM = """You are a judge on a three-member bench. Decide ONLY from the statute text provided; do not use outside
knowledge of the law.
{verdict_test}
{severity_question}
{personality}
Return JSON: {{"verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "2-3 sentences citing the text, through your lens and in your voice"}}"""

REVIEW_SYSTEM = """You sat on a three-member bench. You see your own opinion and the anonymised opinions of the other two
judges. Re-read the statute text. Decide ONLY from the statute text.
{verdict_test}
Change your verdict only if the statute text shows you misread it - never because of a colleague's lens or mood. {review_severity}
{personality}
Return JSON: {{"verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "...", "revised": true|false}}"""

CHAIR_SYSTEM = """You are the Chief Justice. Write the bench's ruling from the judges' final opinions: a short majority
opinion (2-3 sentences) and, if any judge disagrees with the majority verdict or severity, a one-sentence dissent
naming the member as labelled (e.g. "Enforcement (Grey, Justice C)"). Each judge read the severity through a lens (Sunny: remedies
and exceptions; Regal: strict wording; Grey: worst case and enforceability) and a mood; weigh their reasoning, not their
mood. The verdict is a plain question of what the statute text says. Rely only on the statute text and the opinions.
Return JSON: {"majority_opinion": "...", "dissent": "... or null"}"""


# Batched calls ask the same two questions about several separate cases at once.
BATCH_RULES = """You are given {n} SEPARATE cases, each with its own statute text. Judge every case independently and ONLY
from ITS OWN statute text - never from another case's text. For each case copy one short phrase (5-15 words) exactly as
it appears in THAT case's statute text: the words your verdict rests on."""

JUDGE_BATCH_SYSTEM = """You are a judge on a three-member bench. Decide ONLY from the statute text provided; do not use outside
knowledge of the law.
{batch_rules}
{verdict_test}
{severity_question}
{personality}
Return JSON: {{"opinions": [{{"case": "C1", "quote": "phrase copied from C1's statute text", "verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "2-3 sentences citing the text, through your lens and in your voice"}}, ...one per case]}}"""

REVIEW_BATCH_SYSTEM = """You sat on a three-member bench. For each case you see your own opinion and the anonymised opinions of the
other two judges. Re-read that case's statute text. Decide ONLY from the statute text.
{batch_rules}
{verdict_test}
Change your verdict only if the statute text shows you misread it - never because of a colleague's lens or mood. {review_severity}
{personality}
Return JSON: {{"opinions": [{{"case": "C1", "quote": "phrase copied from C1's statute text", "verdict": "supports|neutral|contradicts", "severity": "...", "reasoning": "...", "revised": true|false}}, ...one per case]}}"""

VERDICTS = ("supports", "neutral", "contradicts")


def system_prompt(template: str, p: Persona, n: int = 1, leans: bool = True, rubric: bool = False) -> str:
    return template.format(
        verdict_test=VERDICT_TEST, personality=p.personality(leans, rubric), batch_rules=BATCH_RULES.format(n=n),
        severity_question=SEVERITY_RUBRIC if rubric else SEVERITY_QUESTION, review_severity=REVIEW_RUBRIC if rubric else REVIEW_SEVERITY,
    )


def chair_system(opts: Options) -> str:
    if not opts.severity_rubric:
        return CHAIR_SYSTEM
    return CHAIR_SYSTEM.replace(
        "Each judge read the severity through a lens",
        "Severity follows one written rubric, the same for every judge (critical: criminal offence, forced-labour indicator, "
        "passport or liberty withheld; high: statutory entitlement denied or major money loss; medium: right restricted but a "
        "remedy available; low: procedural or documentary). Each judge reasoned through a lens",
    )


@dataclass(frozen=True)
class Options:
    """The quota savers (see the module docstring). `from_config` reads ain/config.yaml `bench:`."""

    review_only_on_disagreement: bool = False
    batch: bool = False
    batch_size: int = 4
    statute_window: bool = False
    window_chars: int = 1500
    leans: bool = True  # bench_leans: the one-notch borderline severity lean in each judge's prompt
    review_on_wide_spread: bool = False  # human review only on a verdict split or a severity spread of 2+ notches
    severity_rubric: bool = False  # one written severity rubric for all judges; the lens shapes only reasoning and advice
    temperature: float = 0.1

    @classmethod
    def from_config(cls) -> Options:
        b = config.bench_settings()
        return cls(
            review_only_on_disagreement=bool(b.get("review_only_on_disagreement", False)),
            batch=bool(b.get("batch_bench", False)),
            batch_size=int(b.get("batch_size", 4)),
            statute_window=bool(b.get("statute_window", False)),
            window_chars=int(b.get("window_chars", 1500)),
            leans=bool(b.get("bench_leans", True)),
            review_on_wide_spread=bool(b.get("human_review_on_wide_spread", False)),
            severity_rubric=bool(b.get("severity_rubric", False)),
        )


@dataclass
class Case:
    claim: Claim
    section: Section
    risk: Risk
    fake_verdict: str
    text: str  # the statute text the judges are shown

    @property
    def prompt(self) -> str:
        return _case(self.claim, self.section, self.risk, self.text)


def _case(claim: Claim, section: Section, risk: Risk, text: str | None = None) -> str:
    return (
        f"STATUTE: {section.act_en}, s.{section.section} - {section.heading}\n"
        f"TEXT:\n{cited_text(section, claim) if text is None else text}\n\n"
        f"PROPOSITION: {claim.proposition}\n"
        f"CONTRACT FINDING: {risk.finding}"
    )


# ------------------------------------------------------------------ statute window

# Provisos and exceptions are never trimmed: they are where a general rule stops applying.
PROVISO = re.compile(
    r"provided\s+(?:that|further|also|no)|তবে\s*শর্ত|unless|except|notwithstanding|subject\s+to|যদি\s*না|ব্যতীত|সাপেক্ষে|সত্ত্বেও",
    re.I,
)
# a sub-section starts at "(1)", "(a)", "(ক)", "(১)", "Exception 1.", "Explanation", "Illustrations" or a "12. " item
_UNIT_START = re.compile(
    r"(?<!\S)(?:\((?:\d{1,2}[A-Z]?|[a-z]{1,4}|[০-৯]{1,2}|[ক-হ][া-ৌ]?)\)|Exception\b|Explanation\b|Illustrations?\b|\d{1,2}\.(?=\s+\S))"
)
_CLAUSE_END = (".", ";", ":", "।", "—", "–", "-")
_SENTENCE = re.compile(r"(?<=[.।!?])\s+")


def _sentences(text: str) -> list[str]:
    """Whole sentences; a full stop after a short label or abbreviation ("a.", "2.", "No.") does not end one."""
    out, start = [], 0
    for m in _SENTENCE.finditer(text):
        before = text[start : m.start()].split()
        if not before or len(before[-1].rstrip(".।!?")) <= 2:
            continue
        out.append(text[start : m.start()].strip())
        start = m.end()
    out.append(text[start:].strip())
    return [x for x in out if x]
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def units(text: str) -> list[str]:
    """Split a section into sub-sections, each kept together with what it cannot be read without.

    A marker starts a unit only after a clause end or a line break, so a cross-reference such as "paragraph (4)(e)"
    stays inside its sentence. A bare number or heading ("24.", "Illustrations") joins the unit after it, and the
    lettered items of a list ("(a)", "(ক)") join the lead-in that introduces them ("... the following deductions:"),
    so an item is never shown without the sentence it completes.
    """
    cuts = [0]
    for m in _UNIT_START.finditer(text):
        gap = text[: m.start()]
        if m.start() and ("\n" in gap[len(gap.rstrip()):] or gap.rstrip().endswith(_CLAUSE_END)):
            cuts.append(m.start())
    cuts.append(len(text))
    out: list[str] = []
    pending = ""
    for raw in (text[a:b].strip() for a, b in zip(cuts, cuts[1:])):
        if not raw:
            continue
        item = bool(_ITEM.match(raw.lstrip("[")))
        if len(raw) < 25 and not item:  # a bare number or heading: it belongs to what follows
            pending = f"{pending} {raw}".strip()
            continue
        unit = f"{pending} {raw}".strip() if pending else raw
        pending = ""
        if out and item and out[-1].rstrip().endswith(_CLAUSE_END):
            out[-1] = f"{out[-1]}\n{unit}"
        else:
            out.append(unit)
    if pending and out:
        out[-1] = f"{out[-1]}\n{pending}"
    elif pending:
        out.append(pending)
    return out


_ITEM = re.compile(r"\((?:[a-z]{1,4}|[ক-হ][া-ৌ]?)\)")

# the sub-section a proposition cites: "s.24(8)", "Art. 13(12)", "s.31(গ)", "para 3(1)", "s.24(4)(e)", "section 26(1)"
_CITED = re.compile(
    r"(?:\bss?\.|\bsections?|\bart\.?|\barticles?|\bpara(?:graph)?s?\.?|\brules?|\breg(?:ulation)?s?\.?)\s*\d+[A-Z]?\s*"
    r"((?:\((?:\d{1,3}[A-Z]?|[a-z]{1,4}|[০-৯]{1,3}|[ক-হ][া-ৌ]?)\))+)",
    re.I,
)
_LABEL = re.compile(r"\(([^()]+)\)")
# a defined term: "wages" means ..., “worker” includes ..., "শ্রমিক" অর্থ ...
_DEFINED = re.compile(r"[\"“‘']([^\"”’']{2,60})[\"”’']\s*(?:means|includes|shall\s+mean|shall\s+include|has\s+the\s+meaning|অর্থ|বলিতে)", re.I)


def cited_labels(proposition: str) -> list[list[str]]:
    """The sub-section labels a proposition cites, e.g. "s.24(4)(e) and s.24(8)" -> [["4", "e"], ["8"]] (digits as 0-9)."""
    return [[x.translate(_BN_DIGITS).lower() for x in _LABEL.findall(m.group(1))] for m in _CITED.finditer(nfc(proposition))]


def _starts_with(unit: str, label: str) -> bool:
    """The unit opens with "(label)" or "label." (after a bare section number such as "24. ", "12. [" or "২২। ")."""
    head = re.sub(r"^\[?\d{1,3}[A-Z]?[.।]\s*\[?(?=\()", "", nfc(unit)[:40].translate(_BN_DIGITS).lower())
    return head.startswith(f"({label})") or re.match(rf"{re.escape(label)}\.\s", head) is not None


def _holds_item(unit: str, label: str) -> bool:
    """A list item "(label)" inside the unit: lettered items stay with the lead-in sentence they complete."""
    return re.search(rf"(?:^|\s)\({re.escape(label)}\)", nfc(unit).translate(_BN_DIGITS).lower()) is not None


def anchor_units(parts: list[str], claim: Claim | None) -> set[int]:
    """Units the claim points at: the sub-section(s) it cites and the unit(s) holding its quote. Empty when the claim
    names no sub-section and has no quote, or when they cannot be found (the window then works by overlap alone)."""
    if claim is None:
        return set()
    out: set[int] = set()
    for labels in cited_labels(claim.proposition):
        start = next((i for i, u in enumerate(parts) if _starts_with(u, labels[0])), None)
        if start is None:  # "s.31(গ)": an item inside its lead-in unit
            start = next((i for i, u in enumerate(parts) if _holds_item(u, labels[0])), None)
        if start is None:
            continue
        out.add(start)
        for lab in labels[1:]:  # "(4)(e)": the item after "(4)", when it is a unit of its own
            if _holds_item(parts[start], lab):
                continue
            nxt = next((i for i in range(start + 1, len(parts)) if _starts_with(parts[i], lab) or _holds_item(parts[i], lab)), None)
            if nxt is not None:
                out.add(nxt)
    if claim.quote:
        q = _flat(claim.quote)
        for piece in {q[:60], q[-60:]}:  # a quote that runs over two units keeps both
            out |= {i for i, u in enumerate(parts) if piece in _flat(u)}
    return out


def _definitions(parts: list[str], keep: set[int], query: str) -> set[int]:
    """Units defining a term that the anchored units or the query use."""
    used = _flat(" ".join(parts[i] for i in keep) + " " + query)
    return {i for i, u in enumerate(parts) for t in _DEFINED.findall(nfc(u)) if _flat(t) in used}


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", nfc(text).translate(_BN_DIGITS)))


def window(text: str, query: str, limit: int, claim: Claim | None = None) -> str:
    """Keep whole sub-sections up to about `limit` chars; return the text untouched when it already fits.

    Always kept, even if that goes over the limit: the sub-section the claim cites and the unit(s) holding its quote
    (`anchor_units`), the definitions of terms they use, the opening unit (it names the subject and the actors), every
    unit with a proviso or exception, and the closing unit (often a penalty or rule that governs what comes before it).
    The other units are added by overlap with the query (words, and numbers counted double), best first. Omitted
    stretches are marked "[...]" so the judge knows the text is incomplete. Without sub-sections the same is done
    with whole sentences; a text that is one long sentence is never cut.
    """
    if len(text) <= limit:
        return text
    parts = units(text)
    if len(parts) == 1:  # no sub-sections: whole sentences instead
        parts = _sentences(text)
    if len(parts) < 3:  # the opening and closing parts are always kept, so there is nothing to cut
        return text
    want, nums = set(tokenize(query)), _numbers(query)
    anchors = anchor_units(parts, claim)
    keep = {0, len(parts) - 1} | {i for i, u in enumerate(parts) if PROVISO.search(u)} | anchors
    keep |= _definitions(parts, anchors, query)
    used = sum(len(parts[i]) for i in keep)

    def score(i: int) -> int:
        return len(set(tokenize(parts[i])) & want) + 2 * len(_numbers(parts[i]) & nums)

    for i in sorted(set(range(len(parts))) - keep, key=lambda i: (-score(i), i)):
        if score(i) > 0 and used + len(parts[i]) <= limit:
            keep.add(i)
            used += len(parts[i])
    # a unit that stops mid-sentence ("... or unless" + "(3) it is a promise") keeps the unit that finishes it
    for i in range(len(parts) - 1):
        if i in keep and not parts[i].rstrip().endswith(_CLAUSE_END):
            keep.add(i + 1)
    out: list[str] = []
    for i in sorted(keep):
        if out and i - 1 not in keep:
            out.append("[...]")
        out.append(parts[i])
    return "\n".join(out)


# The judges (bench and single-judge verifier) and the council read the whole cited section up to this length; the few
# longer sections (long definition and schedule sections) go through the anchored window at this limit instead.
STATUTE_MAX_CHARS = 8000


def cited_text(section: Section, claim: Claim | None = None, query: str = "") -> str:
    """What a judge reads of a cited section: all of it, or for a very long one the anchored window."""
    return window(section.text, query or (claim.proposition if claim else section.heading), STATUTE_MAX_CHARS, claim)


def statute_text(section: Section, query: str, opts: Options, claim: Claim | None = None) -> str:
    if not opts.statute_window:
        return cited_text(section, claim, query)
    return window(section.text, query, opts.window_chars, claim)


# ------------------------------------------------------------------ quote check for batched answers


def _flat(t: str) -> str:
    t = nfc(t).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(t.casefold().split())


def quote_in(quote: object, text: str) -> bool:
    """True when the quoted phrase (pieces around an ellipsis may be quoted separately) occurs in `text`."""
    if not isinstance(quote, str):
        return False
    pieces = [x.strip(" \"'.,;:()[]-–—") for x in re.split(r"\[\.\.\.\]|\.\.\.|…", _flat(quote))]
    pieces = [x for x in pieces if x]
    hay = _flat(text)
    return bool(pieces) and max(len(x) for x in pieces) >= 12 and all(x in hay for x in pieces)


def _fake_quote(section: Section) -> str:
    return " ".join(section.text.split()[:8])


# ------------------------------------------------------------------ the bench

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


async def convene(llm: LLM, claim: Claim, section: Section, risk: Risk, fake_verdict: str, opts: Options | None = None) -> BenchResult:
    return (await convene_many(llm, [(claim, section, risk, fake_verdict)], opts))[0]


async def convene_many(
    llm: LLM, items: list[tuple[Claim, Section, Risk, str]], opts: Options | None = None, stats: Counter | None = None
) -> list[BenchResult]:
    """Run the bench on several claims: opinions, peer review, then one Chief Justice ruling per claim."""
    opts = opts or Options.from_config()
    stats = Counter() if stats is None else stats
    cases = [Case(c, s, r, fv, statute_text(s, f"{c.proposition} {r.finding}", opts, c)) for c, s, r, fv in items]
    stats["statute_trimmed"] += sum(c.text != c.section.text for c in cases)
    first = await _round(llm, cases, opts, stats)

    skip = {k for k, ops in enumerate(first) if opts.review_only_on_disagreement and _agree(ops)}
    stats["reviews_skipped"] += len(skip)
    # peer review needs at least two opinions to compare
    review = [k for k, ops in enumerate(first) if k not in skip and sum(isinstance(o, BenchOpinion) for o in ops) >= 2]
    finals: list[list[Seat]] = list(first)
    notes: list[list[str]] = [[] for _ in cases]
    if review:
        again = await _round(llm, [cases[k] for k in review], opts, stats, before=[first[k] for k in review])
        for k, ops in zip(review, again):
            merged: list[Seat] = []
            for o, b in zip(ops, first[k]):
                if isinstance(o, NoOpinion) and isinstance(b, BenchOpinion):  # the review call failed: the first opinion stands
                    notes[k].append(f"{_label(b)}'s review call failed, so its first opinion stands")
                    o = b
                elif isinstance(o, BenchOpinion) and isinstance(b, BenchOpinion):
                    o.revised = o.verdict != b.verdict or o.severity != b.severity
                merged.append(o)
            finals[k] = merged
    reviewed = set(review)
    return list(await asyncio.gather(*(_rule(llm, c, f, k in reviewed, opts, notes[k]) for k, (c, f) in enumerate(zip(cases, finals)))))


@dataclass
class NoOpinion:
    """A seat whose call failed on every model route: it gives no opinion and does not vote."""

    persona: Persona
    error: str


Seat = BenchOpinion | NoOpinion


def _agree(ops: list[Seat]) -> bool:
    """All three judges already agree on both verdict and severity, so peer review has nothing to settle."""
    return all(isinstance(o, BenchOpinion) for o in ops) and len({(o.verdict, o.severity) for o in ops}) == 1  # type: ignore[union-attr]


Answer = tuple[dict, dict]  # (the judge's JSON, which provider/model actually answered)


async def _round(llm: LLM, cases: list[Case], opts: Options, stats: Counter, before: list[list[Seat]] | None = None) -> list[list[Seat]]:
    """One round (first opinions, or peer review when `before` is given). Returns [case][judge]. A call that fails on
    every route leaves that seat with no opinion instead of failing the bench; a seat with no first opinion sits out the review."""

    async def judge(j: int, p: Persona) -> list[Seat]:
        sits = [k for k in range(len(cases)) if before is None or isinstance(before[k][j], BenchOpinion)]
        answers: dict[int, Answer | NoOpinion | None] = dict.fromkeys(sits)
        chunks: list[list[int]] = []
        if opts.batch and len(sits) > 1:
            order = list(sits)
            # a different case order for each judge, so no position effect is shared by the whole bench
            random.Random(p.id + "|" + "|".join(c.claim.id for c in cases)).shuffle(order)
            chunks = [order[i : i + opts.batch_size] for i in range(0, len(order), opts.batch_size)]
            chunks = [ch for ch in chunks if len(ch) > 1]  # a lone leftover case runs as a normal single call
            got = await asyncio.gather(*(_batch_call(llm, p, j, [cases[k] for k in ch], [before[k] for k in ch] if before else None, opts, stats) for ch in chunks))
            for ch, res in zip(chunks, got):
                for k, a in zip(ch, res):
                    answers[k] = a
        redo = [k for k in sits if answers[k] is None]
        stats["batch_reruns"] += sum(1 for k in redo if any(k in ch for ch in chunks))

        async def single(k: int) -> Answer | NoOpinion:
            try:
                return await _single_call(llm, p, j, cases[k], before[k] if before else None, opts)  # type: ignore[arg-type]
            except LLMError as e:
                stats["no_opinion"] += 1
                return NoOpinion(p, str(e))

        for k, a in zip(redo, await asyncio.gather(*(single(k) for k in redo))):
            answers[k] = a
        seats: list[Seat] = []
        for k in range(len(cases)):
            a = answers.get(k)
            if k not in answers:  # no first opinion, so nothing to review
                seats.append(before[k][j])  # type: ignore[index]
            elif isinstance(a, NoOpinion):
                seats.append(a)
            else:
                op, info = a  # type: ignore[misc]
                seats.append(_clean(p, _answered_by(llm, p.role, info), op, info))
        return seats

    per_judge = await asyncio.gather(*(judge(j, p) for j, p in enumerate(PERSONAS)))
    return [[per_judge[j][k] for j in range(len(PERSONAS))] for k in range(len(cases))]


def _review_user(case: Case, before: list[Seat], j: int) -> str:
    me = before[j]
    assert isinstance(me, BenchOpinion)
    others = "\n".join(
        f"{o.seat}: verdict={o.verdict}, severity={o.severity}. {o.reasoning}" for i, o in enumerate(before) if i != j and isinstance(o, BenchOpinion)
    )
    return f"{case.prompt}\n\nYOUR OPINION: verdict={me.verdict}, severity={me.severity}. {me.reasoning}\n\nOTHER JUDGES (anonymised):\n{others}"


def _keep(me: BenchOpinion) -> dict:
    return {"verdict": me.verdict, "severity": me.severity, "reasoning": me.reasoning, "revised": False}


async def _single_call(llm: LLM, p: Persona, j: int, case: Case, before: list[Seat] | None, opts: Options) -> Answer:
    agent = f"Virtual Bench · {p.label}"
    info: dict = {}
    if before is None:
        data = await llm.json(
            role=p.role, system=system_prompt(JUDGE_SYSTEM, p, leans=opts.leans, rubric=opts.severity_rubric), user=case.prompt, task="bench_opinion", agent=agent,
            fake=lambda: _fake_opinion(p, case.claim, case.risk, case.fake_verdict), temperature=opts.temperature, info=info,
        )
    else:
        data = await llm.json(
            role=p.role, system=system_prompt(REVIEW_SYSTEM, p, leans=opts.leans, rubric=opts.severity_rubric), user=_review_user(case, before, j),
            task="bench_review", agent=agent, fake=lambda: _keep(before[j]), temperature=opts.temperature, info=info,  # type: ignore[arg-type]
        )
    return data, info


async def _batch_call(
    llm: LLM, p: Persona, j: int, chunk: list[Case], before: list[list[Seat]] | None, opts: Options, stats: Counter
) -> list[Answer | None]:
    """One call for several cases. An answer is accepted only if it has the case id, a valid verdict and severity,
    and a quote found in that case's own statute text; anything else comes back as None and is re-run alone."""
    labels = [f"C{i + 1}" for i in range(len(chunk))]
    blocks = [f"=== CASE {lab} ===\n{_review_user(c, before[i], j) if before else c.prompt}" for i, (lab, c) in enumerate(zip(labels, chunk))]

    def fake() -> dict:
        ops = []
        for i, (lab, c) in enumerate(zip(labels, chunk)):
            base = _keep(before[i][j]) if before else _fake_opinion(p, c.claim, c.risk, c.fake_verdict)  # type: ignore[arg-type]
            ops.append({"case": lab, "quote": _fake_quote(c.section), **base})
        return {"opinions": ops}

    stats["batch_calls"] += 1
    info: dict = {}
    try:
        data = await llm.json(
            role=p.role, system=system_prompt(REVIEW_BATCH_SYSTEM if before else JUDGE_BATCH_SYSTEM, p, len(chunk), opts.leans, opts.severity_rubric),
            user="\n\n".join(blocks), task="bench_review_batch" if before else "bench_opinion_batch", agent=f"Virtual Bench · {p.label}",
            fake=fake, temperature=opts.temperature, max_tokens=1500 * len(chunk), info=info,
        )
    except LLMError:
        stats["batch_call_failed"] += 1
        return [None] * len(chunk)
    items = data.get("opinions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        stats["batch_bad_json"] += 1
        return [None] * len(chunk)
    by_id: dict[str, dict] = {}
    for it in items:
        if isinstance(it, dict) and it.get("case") in labels:
            by_id.setdefault(it["case"], it)
    out: list[Answer | None] = []
    for lab, c in zip(labels, chunk):
        it = by_id.get(lab)
        if it is None:
            stats["batch_missing_id"] += 1
        elif it.get("verdict") not in VERDICTS or it.get("severity") not in SEV:
            stats["batch_bad_fields"] += 1
            it = None
        elif not quote_in(it.get("quote"), c.section.text):
            stats["batch_bad_quote"] += 1
            it = None
        else:
            stats["batch_answers_ok"] += 1
        out.append((it, info) if it is not None else None)
    return out


def _same_family(final: list[BenchOpinion]) -> list[str]:
    """Judges whose answering models are of one family (only a fallback can do that: the configured chains never share a model)."""
    fams = Counter(config.model_family(o.model) for o in final)
    return [_label(o) for o in final if fams[config.model_family(o.model)] > 1]


def _no_quorum(case: Case, answered: list[BenchOpinion], missing: list[NoOpinion], reasons: list[str]) -> BenchResult:
    """Fewer than two judges answered: the bench does not rule, the single-judge check (Gate 3) decides, and a human reviews it."""
    names = " and ".join(o.persona.label for o in missing)
    return BenchResult(
        question=case.claim.proposition,
        opinions=answered,
        majority_verdict="neutral",
        majority_severity=case.risk.severity,
        vote="no quorum",
        agreement="no_quorum",
        majority_opinion=f"No quorum: {names} gave no opinion, so the bench did not rule; the single-judge check decides this claim.",
        human_review=True,
        review_reason="; ".join(["no quorum, fewer than two judges answered", *reasons]),
        chairman_model="none (no quorum)",
        peer_review=False,
        no_opinion=[o.persona.label for o in missing],
        quorum=False,
    )


async def _rule(llm: LLM, case: Case, final: list[Seat], reviewed: bool, opts: Options, notes: list[str] | None = None) -> BenchResult:
    answered = [o for o in final if isinstance(o, BenchOpinion)]
    missing = [o for o in final if isinstance(o, NoOpinion)]
    no_opinion = [f"{o.persona.label} gave no opinion (every model route failed)" for o in missing]
    if len(answered) < 2:
        return _no_quorum(case, answered, missing, no_opinion + (notes or []))
    verdicts = Counter(o.verdict for o in answered)
    top, votes = verdicts.most_common(1)[0]
    agreement = "unanimous" if votes == 3 else "majority" if votes == 2 else "split"
    # 1-1-1 (or 1-1 with a seat missing): no majority holds that the text supports the proposition, so the gate must not pass
    majority_verdict = top if votes >= 2 else "neutral"
    severities = sorted(SEV.index(o.severity) for o in answered)
    # the median of three; with one seat missing, the higher of the two, so a failed call never lowers a risk
    majority_severity = SEV[severities[1]]
    spread = severities[-1] - severities[0]
    severity_range = f"{SEV[severities[0]]}–{SEV[severities[-1]]}" if spread == 1 else None
    # a judge dissents if they differ from the majority on the verdict OR on severity
    dissenters = [o for o in answered if o.verdict != majority_verdict or o.severity != majority_severity]
    if agreement == "split":
        vote = "–".join("1" * len(answered))
    else:
        vote = f"{len(answered) - len(dissenters)}–{len(dissenters)}"
    if missing:
        vote += f" ({len(missing)} no opinion)"

    reasons = no_opinion + (notes or [])
    if agreement == "split":
        reasons.append(f"verdict split {vote}")
    elif agreement == "majority":
        reasons.append(f"verdicts differ ({votes}–{3 - votes})")
    if spread >= 2:
        reasons.append(f"severity spread of {spread} notches")
    elif spread == 1 and not opts.review_on_wide_spread:
        reasons.append("severity differs by one notch")
    human_review = bool(reasons)

    def fake_chair() -> dict:
        dissent = None
        if dissenters:
            d = dissenters[0]
            dissent = f"{_label(d)} dissents: verdict {d.verdict}, severity {d.severity}."
        if agreement == "split":
            held = f"The bench is split {vote}, so no majority finds that the statute text supports the proposition; median severity is {majority_severity}."
        else:
            held = f"The bench holds by {vote} that the statute text {majority_verdict} the proposition; severity is {majority_severity}."
        return {"majority_opinion": held, "dissent": dissent}

    ops = "\n".join(
        [f"{_label(o)}: verdict={o.verdict}, severity={o.severity}. {o.reasoning}" for o in answered]
        + [f"{o.persona.label}: no opinion (its model could not be reached)" for o in missing]
    )
    if agreement == "split":
        result = f"RESULT: verdicts split {vote}, no majority (treated as not supported); median severity {majority_severity}."
    else:
        result = f"RESULT: {vote}; majority verdict {majority_verdict}, majority severity {majority_severity}."
    info: dict = {}
    try:
        chair = await llm.json(
            role="chairman", system=chair_system(opts), task="bench_chair", agent="Virtual Bench · Chief Justice", fake=fake_chair,
            user=f"{case.prompt}\n\nFINAL OPINIONS:\n{ops}\n\n{result}", info=info,
        )
        chairman = _answered_by(llm, "chairman", info)
    except LLMError:  # the votes decide the ruling; without the Chief Justice its text is written from them
        chair, chairman = fake_chair(), "none (the Chief Justice could not be reached; the ruling text is written from the votes)"
    dissent = chair.get("dissent")
    if isinstance(dissent, str) and dissent.strip().lower() in ("", "null", "none"):
        dissent = None
    if dissenters and not dissent:
        dissent = f"{_label(dissenters[0])}: verdict {dissenters[0].verdict}, severity {dissenters[0].severity}."
    return BenchResult(
        question=case.claim.proposition,
        opinions=answered,
        majority_verdict=majority_verdict,
        majority_severity=majority_severity,  # type: ignore[arg-type]
        vote=vote,
        agreement=agreement,  # type: ignore[arg-type]
        severity_range=severity_range,
        majority_opinion=str(chair.get("majority_opinion") or fake_chair()["majority_opinion"]),
        dissent=dissent if dissenters else None,
        human_review=human_review,
        review_reason="; ".join(reasons) or None,
        chairman_model=chairman,
        peer_review=reviewed,
        same_family=_same_family(answered),
        no_opinion=[o.persona.label for o in missing],
    )


def model_name(llm: LLM, role: str) -> str:
    """The model the next call for this role will try first (shown before any call has been made)."""
    return llm.resolve(role)[1] if llm.mode != "fake" else f"{config.role(role).model} (offline stand-in)"


def _answered_by(llm: LLM, role: str, info: dict) -> str:
    """The model that actually answered a call; offline stand-ins keep the configured name."""
    if info.get("provider") in (None, "fake"):
        return model_name(llm, role)
    return info["model"]


def _label(o: BenchOpinion) -> str:
    p = BY_ID.get(o.persona)
    return p.label if p else o.seat


def _clean(p: Persona, model: str, op: dict, info: dict | None = None) -> BenchOpinion:
    verdict = op.get("verdict") if op.get("verdict") in VERDICTS else "neutral"
    sev = op.get("severity") if op.get("severity") in SEV else "medium"
    return BenchOpinion(
        seat=p.seat, model=model, persona=p.id, name=p.name, lens=p.lens_label, verdict=verdict, severity=sev,
        reasoning=clip(str(op.get("reasoning", "")), REASONING_CHARS), fallback=bool((info or {}).get("fallback")),
    )


_SENTENCE_END = re.compile(r"""[.!?।][)"'”’\]]*(?=\s|$)""")


def clip(text: str, limit: int) -> str:
    """Shorten to at most `limit` chars, ending on a whole sentence where one ends in the second half."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    ends = [m.end() for m in _SENTENCE_END.finditer(cut)]
    if ends and ends[-1] > limit // 2:
        return cut[: ends[-1]]
    return cut[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
