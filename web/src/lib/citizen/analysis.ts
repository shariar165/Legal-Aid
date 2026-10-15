import type { StepId } from "../useAnalysis";
import type { L10n } from "./i18n";

export type { CardKind, CitizenCard as ResultCard, CitizenCitation as Citation, CitizenView } from "../api";
export type { OcrCheck, StepId } from "../useAnalysis";

export interface AnalysisStep {
  id: StepId;
  running: L10n;
  done: L10n;
  /** Agents whose progress messages are shown under this step. */
  agents: string[];
}

/**
 * The four steps the worker sees. Each one completes when the backend emits the matching
 * `step` event, so the progress is real, not simulated.
 */
export const STEPS: AnalysisStep[] = [
  { id: "read", running: { bn: "ছবি পড়া হচ্ছে…", en: "Reading the photo…" }, done: { bn: "ছবি পড়া হয়েছে", en: "Photo read" }, agents: ["Ingestion"] },
  {
    id: "redact",
    running: { bn: "আপনার নাম ও পাসপোর্ট নম্বর গোপন রাখা হচ্ছে…", en: "Hiding your name and passport number…" },
    done: { bn: "আপনার নাম ও পাসপোর্ট নম্বর গোপন রাখা হয়েছে", en: "Your name and passport number are hidden" },
    agents: ["PII Shield"],
  },
  {
    id: "match",
    running: { bn: "আইনের সঙ্গে মেলানো হচ্ছে…", en: "Matching with the law…" },
    done: { bn: "আইনের সঙ্গে মেলানো হয়েছে", en: "Matched with the law" },
    agents: ["Jurisdiction Router", "Risk Analyst", "Adversarial Counsel", "Wage Calculator"],
  },
  {
    id: "verify",
    running: { bn: "প্রতিটি আইন যাচাই করা হচ্ছে…", en: "Checking every law…" },
    done: { bn: "প্রতিটি আইন যাচাই করা হয়েছে", en: "Every law checked" },
    agents: ["Citation Verifier", "Virtual Bench", "Critic", "Memo Drafter"],
  },
];
