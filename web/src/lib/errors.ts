/* Errors people can act on (spec 29 step 1.4, F10). Every failure has a stable code: from the HTTP status (ApiError),
   from the job's error event (the backend's `code`), from the browser OCR (OcrError) or "offline". The screens show
   the message and the next action for the code; the raw text stays behind a "Details" disclosure. */

import { ApiError } from "./api";
import { OcrError } from "./citizen/browserOcr";
import type { L10n } from "./citizen/i18n";

export type ErrorCode =
  | "unsupported_type"
  | "too_large"
  | "busy"
  | "offline"
  | "not_found"
  | "ocr_unavailable"
  | "ocr_unreadable"
  | "ocr_empty"
  | "ocr_blurry"
  | "ocr_failed"
  | "failed";

/** The next things a person can do: take a photo instead, open a sample, or go back and try again. */
export type ErrorAction = "photo" | "sample" | "retry";

const KNOWN = new Set<string>([
  "unsupported_type", "too_large", "busy", "offline", "not_found",
  "ocr_unavailable", "ocr_unreadable", "ocr_empty", "ocr_blurry", "ocr_failed", "failed",
]);

export function asErrorCode(code: string | null | undefined): ErrorCode | null {
  return code && KNOWN.has(code) ? (code as ErrorCode) : null;
}

/** The code for something thrown while starting or loading an analysis. */
export function errorCodeOf(e: unknown): ErrorCode {
  if (e instanceof OcrError) return e.code;
  if (e instanceof ApiError) return e.code;
  const msg = e instanceof Error ? e.message : String(e);
  return msg.includes("Failed to fetch") || msg === "offline" ? "offline" : "failed";
}

/** Raw text worth showing under "Details": not when it is only the code itself. */
export function errorDetail(raw: string | null, code: ErrorCode): string | null {
  return raw && raw !== code ? raw : null;
}

interface ErrorCopy {
  title: L10n;
  body: L10n;
  actions: ErrorAction[];
}

export const ERRORS: Record<ErrorCode, ErrorCopy> = {
  unsupported_type: {
    title: { bn: "এই ধরনের ফাইল পড়া যায় না", en: "This kind of file can't be read" },
    body: {
      bn: "চুক্তির একটি ছবি তুলুন, অথবা PDF বা Word (DOCX) ফাইল দিন।",
      en: "Take a photo of the contract, or upload a PDF or Word (DOCX) file.",
    },
    actions: ["photo", "retry"],
  },
  too_large: {
    title: { bn: "ফাইলটি অনেক বড়", en: "The file is too large" },
    body: {
      bn: "সর্বোচ্চ ১৫ MB। চুক্তির একটি ছবি তুলুন, অথবা ছোট একটি ফাইল দিন।",
      en: "The limit is 15 MB. Take a photo of the contract, or upload a smaller file.",
    },
    actions: ["photo", "retry"],
  },
  busy: {
    title: { bn: "সার্ভার এখন ব্যস্ত", en: "The service is busy right now" },
    body: {
      bn: "একটি নমুনা চুক্তি খুলে দেখুন, অথবা এক মিনিট পরে আবার চেষ্টা করুন।",
      en: "Open a sample contract, or try again in a minute.",
    },
    actions: ["sample", "retry"],
  },
  offline: {
    title: { bn: "সার্ভারে পৌঁছানো যাচ্ছে না", en: "The server can't be reached" },
    body: {
      bn: "ইন্টারনেট সংযোগ দেখে একটু পরে আবার চেষ্টা করুন।",
      en: "Check the internet connection, then try again in a moment.",
    },
    actions: ["retry"],
  },
  not_found: {
    title: { bn: "এই বিশ্লেষণটি পাওয়া যাচ্ছে না", en: "This analysis isn't available" },
    body: {
      bn: "এটি মুছে ফেলা হয়েছে, অথবা অন্য কোনো ফোন বা অ্যাকাউন্টের।",
      en: "It may have been deleted, or it belongs to another account or device.",
    },
    actions: ["retry"],
  },
  ocr_unavailable: {
    title: { bn: "এখানে ছবি পড়া যাচ্ছে না", en: "Photos can't be read here" },
    body: {
      bn: "চুক্তিটি PDF, Word বা টেক্সট ফাইল হিসেবে দিন, অথবা একটি নমুনা খুলে দেখুন।",
      en: "Upload the contract as a PDF, Word or text file, or open a sample.",
    },
    actions: ["sample", "retry"],
  },
  ocr_unreadable: {
    title: { bn: "ছবিটি খোলা যাচ্ছে না", en: "The photo could not be opened" },
    body: {
      bn: "এই ছবিটি খোলা যাচ্ছে না। JPG বা PNG ছবি দিন, অথবা PDF আপলোড করুন।",
      en: "This photo could not be opened. Use a JPG or PNG photo, or upload a PDF.",
    },
    actions: ["photo", "retry"],
  },
  ocr_empty: {
    title: { bn: "ছবিতে লেখা পাওয়া গেল না", en: "No text in the photo" },
    body: {
      bn: "ছবিতে কোনো লেখা পড়া গেল না। আলোতে, সোজা করে আবার ছবি তুলুন।",
      en: "No text could be read in the photo. Take it again in good light, straight on.",
    },
    actions: ["photo", "retry"],
  },
  ocr_blurry: {
    title: { bn: "ছবিটি ঝাপসা", en: "The photo is blurry" },
    body: {
      bn: "ছবিটি খুব ঝাপসা, লেখা ঠিকমতো পড়া যাচ্ছে না। আলোতে, কাগজ সোজা রেখে, কাছ থেকে আবার ছবি তুলুন।",
      en: "The photo is too blurry to read. Take it again in good light, with the page flat and close up.",
    },
    actions: ["photo", "retry"],
  },
  ocr_failed: {
    title: { bn: "ফোনে ছবি পড়া গেল না", en: "The photo could not be read" },
    body: {
      bn: "ফোনে ছবি পড়া গেল না। আবার চেষ্টা করুন, অথবা PDF আপলোড করুন।",
      en: "The photo could not be read on this phone. Try again, or upload a PDF.",
    },
    actions: ["photo", "retry"],
  },
  failed: {
    title: { bn: "বিশ্লেষণ শেষ করা যায়নি", en: "The analysis could not be completed" },
    body: {
      bn: "আবার চেষ্টা করুন। বারবার এমন হলে একটি নমুনা চুক্তি খুলে দেখুন।",
      en: "Please try again. If it keeps happening, open a sample contract.",
    },
    actions: ["retry", "sample"],
  },
};

export const ERROR_UI = {
  photo: { bn: "ছবি তুলুন", en: "Take a photo" },
  sample: { bn: "নমুনা চুক্তি দেখুন", en: "Open a sample" },
  retry: { bn: "আবার চেষ্টা করুন", en: "Try again" },
  details: { bn: "বিস্তারিত", en: "Details" },
} satisfies Record<string, L10n>;
