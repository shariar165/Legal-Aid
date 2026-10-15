"""Human-readable, bilingual citation labels built from corpus records (never typed by hand)."""

from __future__ import annotations

import re

from ain.models import L10n, Section

EN_TO_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

BN_ACT_NAMES = {
    "BD-CONTRACT-1872": "চুক্তি আইন, ১৮৭২",
    "BD-STAMP-1899": "স্ট্যাম্প আইন, ১৮৯৯",
    "BD-FERA-1947": "বৈদেশিক মুদ্রা নিয়ন্ত্রণ আইন, ১৯৪৭",
    "BD-CPC-1908": "দেওয়ানী কার্যবিধি, ১৯০৮",
    "ILO-C029": "আইএলও কনভেনশন ২৯ (জবরদস্তিমূলক শ্রম)",
    "ILO-C095": "আইএলও কনভেনশন ৯৫ (মজুরি সুরক্ষা)",
    "ILO-C181": "আইএলও কনভেনশন ১৮১ (বেসরকারি নিয়োগ সংস্থা)",
    "MY-EA-1955": "কর্মসংস্থান আইন ১৯৫৫ (মালয়েশিয়া)",
    "MY-MWO-2024": "ন্যূনতম মজুরি আদেশ ২০২৪ (মালয়েশিয়া)",
    "EU-CSDDD-2024": "ইইউ করপোরেট টেকসই যথাযথ-পরিশ্রম নির্দেশনা ২০২৪/১৭৬০",
    "EU-GDPR-2016": "ইইউ সাধারণ উপাত্ত সুরক্ষা প্রবিধান (GDPR)",
    "BD-GFET-2018": "বাংলাদেশ ব্যাংক বৈদেশিক মুদ্রা লেনদেন নির্দেশিকা ২০১৮",
    "BD-FENOTIF-1977": "বাংলাদেশ ব্যাংক প্রজ্ঞাপন FE 1/77-BB",
    "BD-FECIRC-2020-13": "বাংলাদেশ ব্যাংক এফই সার্কুলার ১৩/২০২০",
}

SHORT_EN = {
    "BD-LABOUR-2006": "Bangladesh Labour Act 2006",
    "BD-EPZLABOUR-2019": "Bangladesh EPZ Labour Act 2019",
    "BD-OEMA-2013": "Overseas Employment and Migrants Act 2013",
    "BD-TRAFFICKING-2026": "Human Trafficking and Migrant Smuggling Act 2026",
    "BD-TRAFFICKING-2012": "Human Trafficking Act 2012",
    "BD-PDP-2026": "Personal Data Protection Act 2026",
    "MY-EA-1955": "Employment Act 1955 (Malaysia)",
    "MY-MWO-2024": "Minimum Wages Order 2024 (Malaysia)",
    "EU-CSDDD-2024": "EU CSDDD 2024/1760",
    "EU-GDPR-2016": "EU GDPR",
    "BD-GFET-2018": "Bangladesh Bank GFET 2018",
    "BD-FENOTIF-1977": "Bangladesh Bank Notification FE 1/77-BB",
    "BD-FECIRC-2020-13": "Bangladesh Bank FE Circular 13/2020",
    "ILO-C029": "ILO Convention 29",
    "ILO-C095": "ILO Convention 95",
    "ILO-C181": "ILO Convention 181",
}


def _unit(sec: Section) -> tuple[str, str]:
    if sec.act_key.startswith(("ILO-", "EU-")):
        return "Art.", "অনুচ্ছেদ"
    if sec.act_key.startswith(("BD-GFET", "BD-FENOTIF", "BD-FECIRC", "MY-MWO")):
        return "para", "অনুচ্ছেদ"
    return "s.", "ধারা"


def label(sec: Section) -> L10n:
    en_act = SHORT_EN.get(sec.act_key, re.sub(r"^The\s+", "", sec.act_en).replace(",", ""))
    bn_act = BN_ACT_NAMES.get(sec.act_key, sec.act.replace(",", "") if sec.lang == "bn" else en_act)
    u_en, u_bn = _unit(sec)
    section_bn = sec.section.replace("Ch.8 para 13", "অধ্যায় ৮ অনুচ্ছেদ ১৩").translate(EN_TO_BN_DIGITS)
    sec_en = sec.section if sec.section.startswith("Ch.") else f"{u_en} {sec.section}".replace("s. ", "s.")
    sec_bn = section_bn if sec.section.startswith("Ch.") else f"{u_bn} {section_bn}"
    return L10n(en=f"{en_act} · {sec_en}", bn=f"{bn_act} · {sec_bn}")
