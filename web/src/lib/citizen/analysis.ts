import type { L10n } from "./i18n";

export type CitationStatus = "verified" | "partial";

export interface Citation {
  name: L10n;
  status: CitationStatus;
}

export type CardKind = "danger" | "todo" | "deadline";

export interface ResultCard {
  kind: CardKind;
  title: L10n;
  /** Large callout shown above the lines (deadline card). */
  big?: L10n;
  lines: L10n[];
  citations: Citation[];
}

export interface AnalysisResult {
  /** Number of serious risks, shown in the warning banner. */
  dangerCount: number;
  cards: ResultCard[];
}

/** A value the OCR step could not read confidently and needs the user to confirm. */
export interface OcrCheck {
  field: "salary";
  currency: string;
  value: string;
}

export type StepId = "read" | "redact" | "match" | "verify";

export interface AnalysisStep {
  id: StepId;
  running: L10n;
  done: L10n;
  /** Simulated duration in ms. */
  ms: number;
}

export const STEPS: AnalysisStep[] = [
  { id: "read", running: { bn: "ছবি পড়া হচ্ছে…", en: "Reading the photo…" }, done: { bn: "ছবি পড়া হয়েছে", en: "Photo read" }, ms: 1400 },
  {
    id: "redact",
    running: { bn: "আপনার নাম ও পাসপোর্ট নম্বর গোপন রাখা হচ্ছে…", en: "Hiding your name and passport number…" },
    done: { bn: "আপনার নাম ও পাসপোর্ট নম্বর গোপন রাখা হয়েছে", en: "Your name and passport number are hidden" },
    ms: 1200,
  },
  { id: "match", running: { bn: "আইনের সঙ্গে মেলানো হচ্ছে…", en: "Matching with the law…" }, done: { bn: "আইনের সঙ্গে মেলানো হয়েছে", en: "Matched with the law" }, ms: 2200 },
  { id: "verify", running: { bn: "প্রতিটি আইন যাচাই করা হচ্ছে…", en: "Checking every law…" }, done: { bn: "প্রতিটি আইন যাচাই করা হয়েছে", en: "Every law checked" }, ms: 1800 },
];

const ILO29: L10n = { bn: "আইএলও কনভেনশন ২৯ · Art. __", en: "ILO Convention 29 · Art. __" };
const BD_OEMA: L10n = { bn: "বৈদেশিক কর্মসংস্থান আইন ২০১৩ · s.__", en: "Overseas Employment and Migrants Act 2013 · s.__" };
const MY_EA: L10n = { bn: "কর্মসংস্থান আইন ১৯৫৫ (মালয়েশিয়া) · s.__", en: "Employment Act 1955 (Malaysia) · s.__" };
const BD_OEMA_VISA: L10n = {
  bn: "বৈদেশিক কর্মসংস্থান আইন ২০১৩ · s.__ (পদ ও ভিসা)",
  en: "Overseas Employment and Migrants Act 2013 · s.__ (post & visa)",
};

/**
 * Sample analysis used until the backend is connected. Section numbers are
 * left as "__" placeholders, as in the design — they must come from the
 * verified-citation pipeline, never be filled in by hand.
 */
export const SAMPLE_RESULT: AnalysisResult = {
  dangerCount: 2,
  cards: [
    {
      kind: "danger",
      title: { bn: "বিপদ কী", en: "What is the danger" },
      lines: [
        { bn: "মালিক আপনার পাসপোর্ট নিজের কাছে রেখে দেবে। এটা বেআইনি।", en: "Your employer will keep your passport. This is illegal." },
        { bn: "নিয়োগের খরচ আপনার বেতন থেকে কাটা হবে।", en: "Recruitment costs will be cut from your salary." },
        { bn: "খরচ কাটার পর বেতন কথা দেওয়া বেতনের চেয়ে কম হবে।", en: "After the cuts, your pay will be less than what was promised." },
      ],
      citations: [
        { name: ILO29, status: "verified" },
        { name: BD_OEMA, status: "verified" },
        { name: MY_EA, status: "verified" },
      ],
    },
    {
      kind: "todo",
      title: { bn: "কী করবেন", en: "What to do" },
      lines: [
        { bn: "সই করার আগে এজেন্সিকে এই শর্তগুলো বদলাতে বলুন।", en: "Before signing, ask the agency to change these terms." },
        { bn: "পাসপোর্ট সবসময় নিজের কাছে রাখুন।", en: "Always keep your passport with you." },
        { bn: "বিদেশ যাওয়ার আগে BMET অফিসে চুক্তিটি দেখান।", en: "Show the contract at a BMET office before going abroad." },
      ],
      citations: [
        { name: BD_OEMA, status: "verified" },
        { name: BD_OEMA_VISA, status: "partial" },
      ],
    },
    {
      kind: "deadline",
      title: { bn: "শেষ তারিখ", en: "Deadline" },
      big: { bn: "ফ্লাইটের আগে", en: "Before your flight" },
      lines: [
        {
          bn: "BMET ছাড়পত্র নেওয়ার আগেই চুক্তি ঠিক করান। পরে বদলানো কঠিন।",
          en: "Fix the contract before you get BMET clearance. It is hard to change later.",
        },
      ],
      citations: [{ name: BD_OEMA, status: "verified" }],
    },
  ],
};

export const SAMPLE_OCR_CHECK: OcrCheck = { field: "salary", currency: "RM", value: "1,200" };
