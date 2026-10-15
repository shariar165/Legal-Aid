import pytest

from ain.agents.pii import find_pii, redact, rehydrate
from ain.llm import LLM, PIILeakError

SAMPLE = """Worker's Name: Mohammad Karim Uddin
কর্মীর নাম: মোঃ করিম উদ্দিন
Passport No: EB0123456
NID No: 1987654321
Mobile: +8801712345678
Alt mobile: ০১৮১২৩৪৫৬৭৮
Email: karim.uddin@example.com
Permanent Address: Village Char Kalia, District Bhola
Salary RM 1,200 per month for 12 months."""


def test_identifiers_are_redacted():
    r = redact(SAMPLE)
    for secret in ("Karim Uddin", "করিম উদ্দিন", "EB0123456", "1987654321", "+8801712345678", "০১৮১২৩৪৫৬৭৮", "karim.uddin@example.com", "Char Kalia"):
        assert secret not in r.text, secret
    kinds = {x.kind for x in r.redactions}
    assert {"NAME", "PASSPORT", "NID", "PHONE", "EMAIL", "ADDRESS"} <= kinds
    assert find_pii(r.text) == []


def test_money_and_terms_survive_redaction():
    r = redact(SAMPLE)
    assert "RM 1,200" in r.text and "12 months" in r.text


def test_same_value_same_placeholder_and_round_trip():
    text = "Passport No: EB0123456. Later: EB0123456 is kept by the employer."
    r = redact(text)
    assert r.text.count("[PASSPORT_1]") == 2
    assert rehydrate(r.text, r.mapping) == text


async def test_llm_blocks_unredacted_payload():
    llm = LLM(mode="fake")
    with pytest.raises(PIILeakError):
        await llm.json(role="fast", system="x", user="Passport No: EB0123456", task="t", agent="test", fake=lambda: {})
    assert llm.blocked == 1
