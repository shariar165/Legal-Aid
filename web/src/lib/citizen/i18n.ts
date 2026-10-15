export type Lang = "bn" | "en";

/** A string in both supported languages. */
export type L10n = Record<Lang, string>;

/** BCP-47 tag used for speech synthesis. */
export const SPEECH_LANG: Record<Lang, string> = { bn: "bn-BD", en: "en-US" };

/** Bengali uses Bengali digits (১, ২ …); English uses Latin digits. */
export function formatNumber(n: number, lang: Lang): string {
  return new Intl.NumberFormat(lang === "bn" ? "bn-BD" : "en-US").format(n);
}

export const STRINGS = {
  brand: { bn: "আইন কপাইলট", en: "Ain Copilot" },
  brandMark: { bn: "আ", en: "আ" },
  langSwitch: { bn: "ভাষা", en: "Language" },

  home: {
    title: { bn: "আপনার চুক্তিপত্র কি নিরাপদ?", en: "Is your contract safe?" },
    lead: {
      bn: "চুক্তির ছবি তুলুন। আমরা সহজ ভাষায় বলে দেব কোথায় বিপদ আছে।",
      en: "Take a photo of your contract. We will tell you in simple words where the dangers are.",
    },
    camera: { bn: "ছবি তুলুন", en: "Take a photo" },
    cameraSub: { bn: "Take a photo of your contract", en: "চুক্তির ছবি তুলুন" },
    upload: { bn: "ফাইল আপলোড করুন", en: "Upload a file" },
    uploadSub: { bn: "Upload PDF or photo", en: "PDF বা ছবি আপলোড করুন" },
    howTo: { bn: "শুনুন: কীভাবে ব্যবহার করবেন", en: "Listen: how to use this" },
    howToStop: { bn: "থামুন", en: "Stop" },
    howToScript: {
      bn: "চুক্তির ছবি তুলুন বোতামে চাপ দিন। পুরো পাতাটা যেন ছবিতে আসে। অথবা ফাইল আপলোড করুন। আমরা চুক্তিটি পড়ে সহজ ভাষায় বলে দেব কোথায় বিপদ আছে, আর আপনি কী করবেন।",
      en: "Press the take a photo button. Make sure the whole page is in the picture. Or upload a file. We will read the contract and tell you in simple words where the dangers are, and what you should do.",
    },
    privacy: {
      bn: "আপনার নাম ও পাসপোর্ট নম্বর গোপন রাখা হয়।",
      en: "Your name and passport number are kept private.",
    },
    disclaimer: { bn: "সিদ্ধান্তে সহায়তা, আইনি পরামর্শ নয়।", en: "Decision support, not legal advice." },
  },

  analyzing: {
    title: { bn: "আপনার চুক্তি পড়া হচ্ছে…", en: "Reading your contract…" },
    titleDone: { bn: "আপনার চুক্তি পড়া শেষ", en: "Your contract has been read" },
    eta: { bn: "এক মিনিটের মতো লাগবে।", en: "This takes about a minute." },
    etaDone: { bn: "ফলাফল দেখতে নিচের বোতামে চাপ দিন।", en: "Press the button below to see the result." },
    progressLabel: { bn: "বিশ্লেষণের অগ্রগতি", en: "Analysis progress" },
    ocrTitle: { bn: "⚠ এই লেখাটি দেখে নিন", en: "⚠ Please check this" },
    ocrBody: {
      bn: "ছবিটা ঝাপসা। আপনার বেতন কি এটাই লেখা আছে?",
      en: "The photo is blurry. Is this the salary written in it?",
    },
    ocrYes: { bn: "হ্যাঁ, ঠিক আছে", en: "Yes, correct" },
    ocrConfirmed: { bn: "✓ ঠিক আছে", en: "✓ Correct" },
    ocrFix: { bn: "না, ঠিক করুন", en: "No, fix it" },
    ocrInput: { bn: "সঠিক বেতন লিখুন (RM)", en: "Type the correct salary (RM)" },
    ocrSave: { bn: "সংরক্ষণ করুন", en: "Save" },
    ocrNeeded: {
      bn: "ফলাফল দেখার আগে উপরের বেতনটি নিশ্চিত করুন।",
      en: "Confirm the salary above before seeing the result.",
    },
    seeResult: { bn: "ফলাফল দেখুন →", en: "See result →" },
  },

  result: {
    title: { bn: "ফলাফল", en: "Result" },
    back: { bn: "ফিরে যান", en: "Back" },
    bannerBody: {
      bn: "সই করার বা বিদেশ যাওয়ার আগে এগুলো ঠিক করান।",
      en: "Get these fixed before you sign or travel abroad.",
    },
    listen: { bn: "শুনুন", en: "Listen" },
    stop: { bn: "থামুন", en: "Stop" },
    playAria: { bn: "শুনুন", en: "Play audio" },
    pauseAria: { bn: "থামুন", en: "Pause audio" },
    details: { bn: "বিস্তারিত", en: "Details" },
    basis: { bn: "যে আইনের ভিত্তিতে বলা হয়েছে:", en: "Based on these laws:" },
    verified: { bn: "যাচাইকৃত", en: "Verified" },
    partial: { bn: "আংশিক", en: "Partial" },
    disclaimer: {
      bn: "সিদ্ধান্তে সহায়তা, আইনি পরামর্শ নয় · Decision support, not legal advice",
      en: "Decision support, not legal advice · সিদ্ধান্তে সহায়তা, আইনি পরামর্শ নয়",
    },
    help: { bn: "প্রবাসী কল্যাণ হেল্পডেস্কে যোগাযোগ", en: "Contact migrant welfare helpdesk" },
    helpSub: { bn: "Contact migrant welfare helpdesk", en: "প্রবাসী কল্যাণ হেল্পডেস্কে যোগাযোগ" },
    calling: { bn: "কল করা হচ্ছে…", en: "Calling…" },
  },
} as const;

export function bannerTitle(count: number, lang: Lang): string {
  return lang === "bn"
    ? `সাবধান! চুক্তিতে ${formatNumber(count, "bn")}টি বড় বিপদ আছে`
    : `Warning! Your contract has ${count} serious ${count === 1 ? "risk" : "risks"}`;
}
