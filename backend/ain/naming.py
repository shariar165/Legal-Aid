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
    "ILO-CEACR-C087-2023": "আইএলও বিশেষজ্ঞ কমিটির পর্যবেক্ষণ, কনভেনশন ৮৭ (বাংলাদেশ, ২০২৩)",
    "ILO-CEACR-C098-2023": "আইএলও বিশেষজ্ঞ কমিটির পর্যবেক্ষণ, কনভেনশন ৯৮ (বাংলাদেশ, ২০২৩)",
    "ILO-CEACR-C029-2021": "আইএলও বিশেষজ্ঞ কমিটির পর্যবেক্ষণ, কনভেনশন ২৯ (বাংলাদেশ, ২০২১)",
    "MY-EA-1955": "কর্মসংস্থান আইন ১৯৫৫ (মালয়েশিয়া)",
    "MY-MWO-2024": "ন্যূনতম মজুরি আদেশ ২০২৪ (মালয়েশিয়া)",
    "SA-LABOR-2005": "সৌদি শ্রম আইন (রাজকীয় ডিক্রি এম/৫১)",
    "AE-LABOUR-2021": "আমিরাতের শ্রম সম্পর্ক ডিক্রি-আইন ৩৩/২০২১",
    "QA-LABOUR-2004": "কাতারের শ্রম আইন (আইন ১৪/২০০৪)",
    "OM-LABOUR-2023": "ওমানের শ্রম আইন (রাজকীয় ডিক্রি ৫৩/২০২৩)",
    "KW-LABOUR-2010": "কুয়েতের বেসরকারি খাত শ্রম আইন (আইন ৬/২০১০)",
    "BH-LABOUR-2012": "বাহরাইনের বেসরকারি খাত শ্রম আইন (আইন ৩৬/২০১২)",
    "BH-LMRA-2006": "বাহরাইনের শ্রমবাজার নিয়ন্ত্রণ আইন (আইন ১৯/২০০৬)",
    "SG-EFMA-1990": "বিদেশি জনশক্তি নিয়োগ আইন ১৯৯০ (সিঙ্গাপুর)",
    "SG-EA-1968": "কর্মসংস্থান আইন ১৯৬৮ (সিঙ্গাপুর)",
    "SG-PA-2007": "পাসপোর্ট আইন ২০০৭ (সিঙ্গাপুর)",
    "STD-ILO-FAIR-2019": "আইএলও ন্যায্য নিয়োগ নীতিমালা ২০১৯",
    "STD-EPP": "এমপ্লয়ার পেস নীতি: চাকরির খরচ মালিকের",
    "STD-RBA-2024": "আরবিএ আচরণবিধি ৮.০",
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
    "SA-LABOR-2005": "Saudi Labor Law",
    "AE-LABOUR-2021": "UAE Labour Relations Decree-Law 33/2021",
    "QA-LABOUR-2004": "Qatar Labour Law 14/2004",
    "OM-LABOUR-2023": "Oman Labour Law 53/2023",
    "KW-LABOUR-2010": "Kuwait Labour Law 6/2010",
    "BH-LABOUR-2012": "Bahrain Labour Law 36/2012",
    "BH-LMRA-2006": "Bahrain Labour Market Law 19/2006",
    "SG-EFMA-1990": "Employment of Foreign Manpower Act 1990 (Singapore)",
    "SG-EA-1968": "Employment Act 1968 (Singapore)",
    "SG-PA-2007": "Passports Act 2007 (Singapore)",
    "STD-ILO-FAIR-2019": "ILO Fair Recruitment Principles 2019",
    "STD-EPP": "Employer Pays Principle",
    "STD-RBA-2024": "RBA Code of Conduct 8.0",
    "EU-CSDDD-2024": "EU CSDDD 2024/1760",
    "EU-GDPR-2016": "EU GDPR",
    "BD-GFET-2018": "Bangladesh Bank GFET 2018",
    "BD-FENOTIF-1977": "Bangladesh Bank Notification FE 1/77-BB",
    "BD-FECIRC-2020-13": "Bangladesh Bank FE Circular 13/2020",
    "ILO-C029": "ILO Convention 29",
    "ILO-C095": "ILO Convention 95",
    "ILO-C181": "ILO Convention 181",
    "ILO-CEACR-C087-2023": "ILO CEACR observation on C87 (Bangladesh, 2023)",
    "ILO-CEACR-C098-2023": "ILO CEACR observation on C98 (Bangladesh, 2023)",
    "ILO-CEACR-C029-2021": "ILO CEACR observation on C29 (Bangladesh, 2021)",
}


def _unit(sec: Section) -> tuple[str, str]:
    if sec.kind == "company_policy":
        return "clause", "অনুচ্ছেদ"
    if sec.kind == "supervisory":  # an observation is cited by its topic, not by a number
        return "", ""
    if sec.act_key == "STD-EPP":  # a single statement, no numbered parts
        return "", ""
    if sec.act_key.startswith("STD-ILO-FAIR"):
        return "principle", "নীতি"
    if sec.act_key.startswith("STD-RBA"):
        return "§", "অংশ"
    if sec.act_key.startswith(("ILO-", "EU-", "SA-", "AE-", "QA-", "OM-", "KW-", "BH-")):  # Gulf laws number articles
        return "Art.", "অনুচ্ছেদ"
    if sec.act_key.startswith(("BD-GFET", "BD-FENOTIF", "BD-FECIRC", "MY-MWO")):
        return "para", "অনুচ্ছেদ"
    return "s.", "ধারা"


def label(sec: Section) -> L10n:
    en_act = SHORT_EN.get(sec.act_key, re.sub(r"^The\s+", "", sec.act_en).replace(",", ""))
    bn_act = BN_ACT_NAMES.get(sec.act_key, sec.act.replace(",", "") if sec.lang == "bn" else en_act)
    if sec.kind == "company_policy" and sec.jurisdiction == "COMPANY":  # a company's own published policy
        company = sec.act_en.split(": ", 1)[0]
        en_act, bn_act = f"{company} · published policy", f"{company} · প্রকাশিত নীতি"
    elif sec.kind == "company_policy":  # "Employer policy: handbook.pdf" / "কোম্পানির নীতি: handbook.pdf"
        bn_act = "কোম্পানির নীতি: " + sec.act_en.split(": ", 1)[-1]
    if sec.kind == "standard":  # never let a voluntary code read like a statute
        en_act, bn_act = f"{en_act} (voluntary standard)", f"{bn_act} (স্বেচ্ছামূলক মান, আইন নয়)"
    if sec.kind == "supervisory":  # nor an ILO supervisory comment like a court ruling or a statute
        en_act, bn_act = f"{en_act} · {sec.heading} (ILO supervisory, interpretive)", f"{bn_act} · {sec.heading} (আইএলও পর্যবেক্ষণ, ব্যাখ্যামূলক, আইন নয়)"
    u_en, u_bn = _unit(sec)
    if not u_en:
        return L10n(en=en_act, bn=bn_act)
    section_bn = sec.section.replace("Ch.8 para 13", "অধ্যায় ৮ অনুচ্ছেদ ১৩").translate(EN_TO_BN_DIGITS)
    sec_en = sec.section if sec.section.startswith("Ch.") else f"{u_en} {sec.section}".replace("s. ", "s.")
    sec_bn = section_bn if sec.section.startswith("Ch.") else f"{u_bn} {section_bn}"
    return L10n(en=f"{en_act} · {sec_en}", bn=f"{bn_act} · {sec_bn}")
