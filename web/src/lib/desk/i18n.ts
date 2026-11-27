/* Case Desk strings, Bangla first (spec 20). Same pattern as lib/citizen/i18n.ts. Legal quotes are never translated:
   they stay in their source language. Ledger cells, mismatch sentences and labels come bilingual from the backend. */

import type { Party, Severity } from "../api";
import { formatNumber, type L10n, type Lang } from "../citizen/i18n";

export type { L10n, Lang } from "../citizen/i18n";

/** Counts in the reader's digits (৭ / 7); money stays as written on the contract (RM 1,200). */
export const num = (n: number, lang: Lang) => formatNumber(n, lang);

export const TERM_NAME: Record<string, L10n> = {
  salary: { bn: "মূল বেতন", en: "Basic salary" },
  deductions: { bn: "মাসিক কর্তন", en: "Monthly deductions" },
  recruitment_cost: { bn: "নিয়োগের খরচ", en: "Recruitment cost" },
  hours_per_day: { bn: "কাজের সময়", en: "Working hours" },
  ticket: { bn: "যাওয়ার টিকিট", en: "Ticket out" },
  passport: { bn: "পাসপোর্ট", en: "Passport" },
  contract_months: { bn: "চুক্তির মেয়াদ", en: "Contract term" },
};

export const SEVERITY_NAME: Record<Severity, L10n> = {
  critical: { bn: "সংকটজনক", en: "Critical" },
  high: { bn: "উচ্চ", en: "High" },
  medium: { bn: "মাঝারি", en: "Medium" },
  low: { bn: "নিম্ন", en: "Low" },
};

export const PARTY_NAME: Record<Party, L10n> = {
  worker: { bn: "কর্মী", en: "Worker" },
  employer: { bn: "মালিক", en: "Employer" },
  agency: { bn: "এজেন্সি", en: "Agency" },
};

export const DESK = {
  langGroup: { bn: "কেস ডেস্কের ভাষা", en: "Case Desk language" },

  hero: {
    region: { bn: "চার খাতার সারাংশ", en: "Four Ledgers summary" },
    term: (n: number, lang: Lang) => (lang === "bn" ? `${num(n, "bn")} মাসের চুক্তি` : `${n}-month contract`),
    // Bangla puts the verb last: "what was said ... RM 1,250 less ... comes to hand", not the English clause order
    toldLess: { bn: ["যা বলা হয়েছিল তার চেয়ে মাসে ", " কম হাতে আসবে"], en: ["On paper, take-home is ", " a month less than the worker was told"] },
    toldMet: { bn: "যা বলা হয়েছিল তার সমান বা বেশি হাতে আসবে", en: "On paper, take-home is at least what the worker was told" },
    toldLessYou: { bn: ["আপনাকে যা বলা হয়েছিল তার চেয়ে মাসে ", " কম হাতে আসবে"], en: ["On paper, you take home ", " a month less than you were told"] },
    toldMetYou: { bn: "আপনাকে যা বলা হয়েছিল তার সমান বা বেশি হাতে আসবে", en: "On paper, you take home at least what you were told" },
    deducted: { bn: ["কাগজের বেতন থেকে মাসে ", " কেটে নেওয়া হবে"], en: ["", " a month is taken from the salary on paper"] },
    nothingDeducted: { bn: "কাগজের বেতন থেকে কিছু কাটা হবে না", en: "Nothing is taken from the salary on paper" },
    risks: (n: number, lang: Lang) => (lang === "bn" ? `চুক্তিতে ${num(n, "bn")}টি ঝুঁকি` : `${n} ${n === 1 ? "risk" : "risks"} in the contract`),
    terms: { bn: "শর্ত মেলানো", en: "terms compared" },
    mismatches: { bn: "অমিল", en: "mismatches" },
    said: { bn: "কথা", en: "Told" },
    saidSub: { bn: "এজেন্ট যা বলেছিল", en: "what the agent said" },
    paper: { bn: "কাগজ", en: "Paper" },
    paperSub: { bn: "চুক্তিতে লেখা", en: "written in the contract" },
    takeHome: { bn: "হাতে", en: "Take-home" },
    takeHomeSub: { bn: "কাগজ অনুযায়ী, বেতন-স্লিপ নয়", en: "on paper, not a payslip" },
    minimum: { bn: "আইন · ন্যূনতম", en: "Law · minimum" },
    otherCurrency: { bn: "অন্য মুদ্রায়, মাপে আঁকা নয়", en: "another currency, not drawn to scale" },
    stepsLead: { bn: "হাতে আসে", en: "Take-home" },
    stepFrom: (a: number, b: number | null, lang: Lang) =>
      lang === "bn" ? (b ? `মাস ${num(a, "bn")}–${num(b, "bn")}` : `মাস ${num(a, "bn")} থেকে`) : b ? `months ${a}–${b}` : `from month ${a}`,
    addSaid: { bn: "যা বলা হয়েছিল যোগ করুন", en: "Add what was said" },
    editSaid: { bn: "যা বলা হয়েছিল বদলান", en: "Edit what was said" },
  },

  money: {
    projected: { bn: "প্রক্ষেপিত দাবি", en: "Projected claim" },
    noLines: { bn: "যাচাই করা আইনের ওপর দাঁড়ানো কোনো প্রক্ষেপিত লাইন নেই।", en: "No projected line rests on verified law." },
    term: { bn: "মেয়াদ", en: "Term" },
    months: { bn: "মাস", en: "months" },
    confirm: { bn: "ঠিক আছে", en: "Correct" },
    change: { bn: "বদলান", en: "Change" },
    save: { bn: "সংরক্ষণ", en: "Save" },
    cancel: { bn: "বাতিল", en: "Cancel" },
    noTerm: { bn: "চুক্তিতে মেয়াদ পাওয়া যায়নি", en: "No term found in the contract" },
    termInput: { bn: "চুক্তির মেয়াদ, মাসে", en: "Contract term in months" },
    gap: { bn: "প্রতিশ্রুতির ফারাক", en: "Promise gap" },
    breakEven: { bn: "খরচ উঠতে", en: "Cost earned back in" },
    minimum: { bn: "সর্বনিম্ন", en: "Minimum" },
    atLeast: (n: number, lang: Lang) => (lang === "bn" ? `অন্তত ${num(n, "bn")} মাস` : `at least ${n} months`),
    notWithin: { bn: "মেয়াদের মধ্যে নয়", en: "Not within the term" },
    rate: { bn: "ব্যবহারকারীর দেওয়া হার", en: "User-entered rate" },
    account: { bn: "কর্মীর কথা", en: "worker's account" },
    // short labels for the compact row; the full ones head the details
    claimShort: { bn: "প্রক্ষেপিত ক্ষতি", en: "Projected loss" },
    breakEvenShort: { bn: "খরচ উঠতে", en: "Break-even" },
    details: { bn: "বিস্তারিত", en: "Details" },
    detailsHide: { bn: "বিস্তারিত লুকান", en: "Hide details" },
  },

  rows: {
    title: { bn: "চার খাতা", en: "Four Ledgers" },
    riskTitle: { bn: "কাগজ ও আইন", en: "Paper and law" },
    otherRisks: { bn: "এই চুক্তির অন্য ঝুঁকি", en: "Other risks in this contract" },
    ne: { bn: "অমিল", en: "Mismatch" },
    eq: { bn: "মিল", en: "Match" },
    dash: { bn: "তুলনা নেই", en: "No comparison" },
    count: (n: number, lang: Lang) => (lang === "bn" ? `${num(n, "bn")} অমিল` : `${n} ${n === 1 ? "mismatch" : "mismatches"}`),
    said: { bn: "কথা", en: "Told" },
    paper: { bn: "কাগজ", en: "Paper" },
    paid: { bn: "টাকা", en: "Paid" },
    law: { bn: "আইন", en: "Law" },
    notSaid: { bn: "বলা হয়নি", en: "Not said" },
    notOnPaper: { bn: "কাগজে নেই", en: "Not on paper" },
    noPayslip: { bn: "বেতন-স্লিপ যোগ হয়নি", en: "No payslip yet" },
    noPayslips: { bn: "বেতন-স্লিপ: এখনো যোগ হয়নি", en: "Payslips: not added yet" },
    clause: (n: number, lang: Lang) => (lang === "bn" ? `ধারা ${num(n, "bn")}` : `Clause ${n}`),
    violation: { bn: "লঙ্ঘন", en: "Violation" },
    verified: { bn: "ধারা যাচাইকৃত", en: "Section verified" }, // the gates verify the cited section, not that anyone broke it
    partial: { bn: "আংশিক", en: "Partial" },
    notVerified: { bn: "যাচাই হয়নি", en: "Not verified" },
    pending: { bn: "এখনো যাচাই হয়নি", en: "Not verified yet" },
    noLaw: { bn: "যাচাই করা আইন নেই", en: "No verified law" },
    pendingBanner: {
      bn: "যা বলা হয়েছিল তা থেকে একটি নতুন ঝুঁকি এসেছে। আইনের সঙ্গে এখনো যাচাই হয়নি, তাই এটি এখনো কোনো ঝুঁকির তালিকায় নেই।",
      en: "What was said raised a new risk. It has not been checked against the law yet, so it is not on the risk list.",
    },
    verify: { bn: "যাচাই করুন", en: "Verify" },
    verifying: { bn: "যাচাই হচ্ছে…", en: "Verifying…" },
    empty: { bn: "এই চুক্তিতে মেলানোর মতো কোনো শর্ত বা ঝুঁকি পাওয়া যায়নি।", en: "No term or risk to compare in this contract." },
  },

  evidence: {
    region: { bn: "নির্বাচিত শর্তের প্রমাণ", en: "Evidence for the selected term" },
    file: { bn: "প্রমাণের ফাইল", en: "Evidence file" },
    saidPaper: { bn: "কথা ≠ কাগজ", en: "Told ≠ paper" },
    paperLaw: { bn: "কাগজ ≠ আইন", en: "Paper ≠ law" },
    worker: { bn: "কর্মীকে বলা হয়েছিল", en: "The worker was told" },
    saidOn: (d: string, lang: Lang) => (lang === "bn" ? `তারিখ ${d}` : `on ${d}`),
    contract: (c: string, lang: Lang) => (lang === "bn" ? `চুক্তি বলছে · ${c}` : `The contract says · ${c}`),
    law: { bn: "আইন বলছে · হুবহু উদ্ধৃতি", en: "The law says · verbatim" },
    lawPending: { bn: "যে আইনে যাচাই হবে · হুবহু উদ্ধৃতি", en: "The law it will be checked against · verbatim" },
    noQuote: { bn: "এই দাবির কোনো উদ্ধৃতি নেই।", en: "This claim has no quote." },
    gates: { bn: "৪টি যাচাই", en: "The 4 checks" },
    gateName: [
      { bn: "G1 অস্তিত্ব", en: "G1 Exists" },
      { bn: "G2 উদ্ধৃতি", en: "G2 Quote" },
      { bn: "G3 সমর্থন", en: "G3 Meaning" },
      { bn: "G4 চালু", en: "G4 In force" },
    ] as L10n[],
    gateStatus: {
      pass: { bn: "পাস", en: "passed" },
      warn: { bn: "সতর্কতা", en: "warning" },
      fail: { bn: "ব্যর্থ", en: "failed" },
      skip: { bn: "চলেনি", en: "not run" },
    } as Record<string, L10n>,
    bench: { bn: "বেঞ্চ", en: "Bench" },
    council: { bn: "কাউন্সিলের ভোট", en: "Council vote" },
    noBench: {
      bn: "ভার্চুয়াল বেঞ্চ শুধু সংকটজনক ও উচ্চ ঝুঁকিতে বসে; এই ঝুঁকি একজন বিচারক যাচাই করেছে।",
      en: "The Virtual Bench sits on critical and high risks only; one judge checked this one.",
    },
    agreement: {
      unanimous: { bn: "সর্বসম্মত", en: "Unanimous" },
      majority: { bn: "সংখ্যাগরিষ্ঠ", en: "Majority" },
      split: { bn: "বিভক্ত", en: "Split" },
      no_quorum: { bn: "কোরাম হয়নি", en: "No quorum" },
    } as Record<string, L10n>,
    evidence: { bn: "প্রমাণ", en: "Evidence" },
    item: {
      clause: { bn: "চুক্তির ধারা", en: "Contract clause" },
      account: { bn: "যা বলা হয়েছিল তার বিবরণ", en: "Account of what was said" },
      accountDated: { bn: "যা বলা হয়েছিল তার বিবরণ, তারিখসহ", en: "Account of what was said, dated" },
      law: { bn: "যাচাই করা আইন", en: "Verified law" },
      payslip: { bn: "বেতন-স্লিপ", en: "Payslip" },
    },
    have: { bn: "আছে", en: "Have" },
    need: { bn: "লাগবে", en: "Needed" },
    ask: { bn: "কাউন্সিলকে জিজ্ঞাসা করুন", en: "Ask the council" },
    askPending: { bn: "যাচাইয়ের পর কাউন্সিলকে জিজ্ঞাসা করা যাবে", en: "The council can be asked once it is verified" },
    disclaimer: { bn: "সিদ্ধান্তে সহায়তা, আইনি পরামর্শ নয়।", en: "Decision support, not legal advice." },
  },

  contract: {
    title: { bn: "চুক্তি", en: "Contract" },
    full: { bn: "চুক্তির পুরো লেখা", en: "Full contract text" },
    redacted: { bn: "নাম, ফোন ও পরিচয় নম্বর লুকানো আছে।", en: "Names, phone and ID numbers are hidden." },
  },

  form: {
    title: { bn: "এজেন্ট কী বলেছিল?", en: "What did the agent say?" },
    lead: {
      bn: "কর্মী যা শুনেছেন তাই লিখুন। যেকোনো ঘর খালি রাখা যায়। এতে কোনো এআই কল হয় না।",
      en: "Type what the worker was told. Any field can stay empty. No AI call is made.",
    },
    salary: { bn: "মাসিক বেতন", en: "Monthly salary" },
    currency: { bn: "মুদ্রা", en: "Currency" },
    noDeductions: { bn: "বেতন থেকে টাকা কাটার কথা কী বলেছিল?", en: "What was said about deductions from the salary?" },
    dedNone: { bn: "কিছু কাটবে না", en: "Nothing would be deducted" },
    dedSome: { bn: "কাটবে বলেছিল", en: "Deductions were mentioned" },
    unknown: { bn: "জানি না", en: "Don't know" },
    recruitment: { bn: "চাকরি পেতে আগেই কত দিয়েছেন", en: "Already paid to get the job" },
    hours: { bn: "দিনে কত ঘণ্টা কাজ", en: "Hours of work a day" },
    ticket: { bn: "যাওয়ার টিকিট কে দেবে", en: "Who pays the ticket out" },
    passport: { bn: "পাসপোর্ট কার কাছে থাকবে", en: "Who keeps the passport" },
    months: { bn: "চুক্তির মেয়াদ, মাসে", en: "Contract term in months" },
    saidOn: { bn: "কবে বলেছিল", en: "When it was said" },
    note: { bn: "নোট", en: "Note" },
    noteHint: { bn: "নাম ও ফোন নম্বর সংরক্ষণের আগে লুকানো হয়।", en: "Names and phone numbers are hidden before it is stored." },
    rate: { bn: "বিনিময় হার (ঐচ্ছিক)", en: "Exchange rate (optional)" },
    rateHint: {
      bn: "দুই মুদ্রার অঙ্ক মেলাতে কেবল এই হার ব্যবহার হয়; যুক্তির নিজের কোনো হার নেই।",
      en: "Amounts in two currencies are compared only through this rate; Jukti has no rate of its own.",
    },
    rateOne: { bn: "১", en: "1" },
    save: { bn: "সংরক্ষণ করুন", en: "Save" },
    saving: { bn: "সংরক্ষণ হচ্ছে…", en: "Saving…" },
    cancel: { bn: "বাতিল", en: "Cancel" },
  },
};

export const t = (s: L10n, lang: Lang) => s[lang];
