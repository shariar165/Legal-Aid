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
  brand: { bn: "যুক্তি", en: "Jukti" },
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
    countryLabel: { bn: "কোন দেশে কাজ?", en: "Which country is the job in?" },
    countryAuto: { bn: "চুক্তি দেখে বুঝে নিন", en: "Find it in the contract" },
    policyAdd: { bn: "কোম্পানির নিজের নীতিমালা যোগ করুন (ঐচ্ছিক)", en: "Add the company's own policy (optional)" },
    policySub: {
      bn: "চুক্তি কোম্পানির নিজের প্রতিশ্রুতি ভাঙছে কি না দেখব",
      en: "We check whether the contract breaks the company's own promises",
    },
    policyChosen: { bn: "কোম্পানির নীতিমালা:", en: "Company policy:" },
    policyRemove: { bn: "বাদ দিন", en: "Remove" },
    more: { bn: "আরও বিকল্প", en: "More options" },
    moreSub: { bn: "কাজের দেশ, কোম্পানির নীতিমালা", en: "Country of work, company policy" },
    samplesTitle: { bn: "অথবা একটি নমুনা চুক্তি দিয়ে দেখুন", en: "Or try a sample contract" },
    counselLink: { bn: "আইনজীবী / এনজিও মোড", en: "Lawyer / NGO mode" },
    saveLink: { bn: "অ্যাকাউন্ট খুলে ফলাফল সংরক্ষণ করুন", en: "Save my results in an account" },
    offline: {
      bn: "সার্ভারের সঙ্গে যোগাযোগ হচ্ছে না। একটু পরে আবার চেষ্টা করুন।",
      en: "Cannot reach the server. Please try again in a moment.",
    },
  },

  analyzing: {
    title: { bn: "আপনার চুক্তি পড়া হচ্ছে…", en: "Reading your contract…" },
    titleDone: { bn: "আপনার চুক্তি পড়া শেষ", en: "Your contract has been read" },
    eta: { bn: "এক মিনিটের মতো লাগবে।", en: "This takes about a minute." },
    etaDone: { bn: "ফলাফল দেখতে নিচের বোতামে চাপ দিন।", en: "Press the button below to see the result." },
    progressLabel: { bn: "বিশ্লেষণের অগ্রগতি", en: "Analysis progress" },
    ocrTitle: { bn: "এই লেখাটি দেখে নিন", en: "Please check this" },
    ocrBody: {
      bn: "ছবিটা ঝাপসা। আপনার বেতন কি এটাই লেখা আছে?",
      en: "The photo is blurry. Is this the salary written in it?",
    },
    ocrYes: { bn: "হ্যাঁ, ঠিক আছে", en: "Yes, correct" },
    ocrConfirmed: { bn: "ঠিক আছে", en: "Correct" },
    ocrFix: { bn: "না, ঠিক করুন", en: "No, fix it" },
    ocrInput: { bn: "সঠিক বেতন লিখুন", en: "Type the correct salary" },
    ocrSave: { bn: "সংরক্ষণ করুন", en: "Save" },
    ocrNeeded: {
      bn: "ফলাফল দেখার আগে উপরের বেতনটি নিশ্চিত করুন।",
      en: "Confirm the salary above before seeing the result.",
    },
    seeResult: { bn: "ফলাফল দেখুন", en: "See result" },
    liveLabel: { bn: "এখন যা হচ্ছে", en: "Happening now" },
    failed: { bn: "বিশ্লেষণ শেষ করা যায়নি।", en: "The analysis could not be completed." },
    retry: { bn: "আবার চেষ্টা করুন", en: "Try again" },
    ocrLowConf: { bn: "ছবি থেকে পড়ার নিশ্চয়তা", en: "Reading confidence" },
    // in-browser OCR (spec 28)
    deviceOcr: { bn: "ফোনেই ছবি পড়া হচ্ছে", en: "Reading the photo on your phone" },
    deviceOcrNote: {
      bn: "ছবিটি আপনার ফোন থেকে বাইরে যাবে না, শুধু লেখাটুকু যাবে।",
      en: "The photo stays on your phone; only its text is sent.",
    },
    ocr_unreadable: {
      bn: "এই ছবিটি খোলা যাচ্ছে না। JPG বা PNG ছবি দিন, অথবা PDF আপলোড করুন।",
      en: "This photo could not be opened. Use a JPG or PNG photo, or upload a PDF.",
    },
    ocr_empty: {
      bn: "ছবিতে কোনো লেখা পড়া গেল না। আলোতে, সোজা করে আবার ছবি তুলুন।",
      en: "No text could be read in the photo. Take it again in good light, straight on.",
    },
    ocr_blurry: {
      bn: "ছবিটি খুব ঝাপসা, লেখা ঠিকমতো পড়া যাচ্ছে না। আলোতে, কাগজ সোজা রেখে, কাছ থেকে আবার ছবি তুলুন।",
      en: "The photo is too blurry to read. Take it again in good light, with the page flat and close up.",
    },
    ocr_failed: {
      bn: "ফোনে ছবি পড়া গেল না। আবার চেষ্টা করুন, অথবা PDF আপলোড করুন।",
      en: "The photo could not be read on this phone. Try again, or upload a PDF.",
    },
  },

  // a /r/<id> link whose result this device cannot open (spec 28)
  gone: {
    title: { bn: "এই ফলাফলটি আর নেই", en: "This result is no longer here" },
    body: {
      bn: "ফলাফল শুধু যে ফোনে বিশ্লেষণ করা হয়েছে সেখানেই খোলে, আর ৭ দিন পরে মুছে যায়।",
      en: "A result opens only on the device that ran it, and is deleted after 7 days.",
    },
    rerun: { bn: "আবার চালান", en: "Run it again" },
    home: { bn: "নতুন চুক্তি দেখান", en: "Check a contract" },
  },

  // read-aloud on a device without a voice for the language (spec 28)
  voice: {
    none: {
      bn: "এই ডিভাইসের ব্রাউজারে বাংলা পড়ে শোনানোর কণ্ঠ নেই। লেখাটি পড়ে দেখুন, অথবা কাউকে পড়ে শোনাতে বলুন।",
      en: "This browser has no English voice to read this aloud. Please read the text instead.",
    },
    // computers only: Chrome and Firefox there have no Bangla voice, Edge has natural bn-BD voices
    edge: { bn: "কম্পিউটারে Microsoft Edge ব্রাউজারে খুললে বাংলায় পড়ে শোনানো যায়।" },
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
    openSource: { bn: "সরকারি উৎসে দেখুন", en: "Open official source" },
    letterTitle: { bn: "এজেন্সিকে পাঠানোর চিঠি", en: "Letter to send to the agency" },
    letterSub: {
      bn: "এই চিঠিতে কোন শর্ত বদলাতে হবে আর কোন আইনে, তা লেখা আছে।",
      en: "This letter lists the terms to change and the law behind each one.",
    },
    copy: { bn: "কপি করুন", en: "Copy" },
    copied: { bn: "কপি হয়েছে", en: "Copied" },
    share: { bn: "শেয়ার করুন", en: "Share" },
    memoLink: { bn: "আইনজীবীর জন্য পূর্ণ আইনি মেমো", en: "Full legal memo for a lawyer" },
    memoSub: {
      bn: "প্রতিটি আইনি দাবির যাচাই-তালিকা, ভার্চুয়াল বেঞ্চের রায়সহ",
      en: "With the verification ledger and the Virtual Bench ruling",
    },
    dangers: { bn: "বড় বিপদ", en: "serious dangers" },
    mismatches: { bn: "কথা আর কাগজে অমিল", en: "told vs. paper" },
    noDanger: { bn: "বড় কোনো বিপদ পাওয়া যায়নি", en: "No serious danger found" },
    workIn: { bn: "কাজের দেশ", en: "Country of work" },
    helpThere: { bn: "সেখানে সাহায্যের জন্য:", en: "For help there:" },
    offlineMode: {
      bn: "অফলাইন ডেমো মোড: আইনের যাচাই আসল, ভাষা মডেলের উত্তর নমুনা।",
      en: "Offline demo mode: law checks are real, language-model answers are samples.",
    },
  },

  /* the optional step after the result: what the agent said, compared with the paper (spec 20, phase 2) */
  promise: {
    title: { bn: "এজেন্ট আপনাকে কী বলেছিল?", en: "What did the agent tell you?" },
    lead: {
      bn: "চাইলে লিখে দিন। চুক্তিতে যা লেখা, তার সঙ্গে মিলিয়ে দেখাব কোথায় অমিল।",
      en: "If you like, type it in. We compare it with what the contract says and show where they differ.",
    },
    open: { bn: "উত্তর দিন", en: "Answer" },
    edit: { bn: "উত্তর বদলান", en: "Change answers" },
    salary: { bn: "মাসে কত বেতন দেবে বলেছিল?", en: "What monthly salary were you told?" },
    amount: { bn: "টাকার অঙ্ক", en: "Amount" },
    currency: { bn: "মুদ্রা", en: "Currency" },
    noDeductions: { bn: "বেতন থেকে টাকা কাটার কথা কী বলেছিল?", en: "What were you told about money taken from your salary?" },
    dedNone: { bn: "কিছু কাটবে না", en: "Nothing would be taken" },
    dedSome: { bn: "কাটবে বলেছিল", en: "Some would be taken" },
    ticket: { bn: "বিমানের টিকিটের টাকা কে দেবে বলেছিল?", en: "Who did they say pays for the air ticket?" },
    passport: { bn: "আপনার পাসপোর্ট কার কাছে থাকবে বলেছিল?", en: "Who did they say keeps your passport?" },
    unsure: { bn: "মনে নেই", en: "Not sure" },
    employer: { bn: "মালিক", en: "Employer" },
    agency: { bn: "এজেন্সি", en: "Agency" },
    me: { bn: "আমি নিজে", en: "Me" },
    kept: { bn: "আপনার উত্তর এই ফলাফলের সঙ্গে রাখা হয়।", en: "Your answers are kept with this result." },
    save: { bn: "চুক্তির সঙ্গে মেলান", en: "Compare with the contract" },
    saving: { bn: "মেলানো হচ্ছে…", en: "Comparing…" },
    cancel: { bn: "বাতিল", en: "Cancel" },
    failed: { bn: "উত্তর রাখা যায়নি। আবার চেষ্টা করুন।", en: "Your answers could not be saved. Please try again." },
    resultsTitle: { bn: "যা বলেছিল আর চুক্তিতে যা লেখা", en: "What you were told and what the contract says" },
    none: {
      bn: "আপনার উত্তরের সঙ্গে চুক্তির কোনো অমিল পাওয়া যায়নি।",
      en: "Your answers do not differ from what the contract says.",
    },
    status: {
      verified: { bn: "ধারা যাচাইকৃত", en: "Section verified" },
      partial: { bn: "আংশিক যাচাই", en: "Partly verified" },
      not_verified: { bn: "আইন যাচাই হয়নি", en: "Law not verified" },
      not_verified_yet: { bn: "এখনো যাচাই হয়নি", en: "Not verified yet" },
    },
    pendingNote: {
      bn: "এটা আপনার কথার ওপর দাঁড়িয়ে। আইনজীবী বা এনজিও পূর্ণ মেমো থেকে আইনটি যাচাই করতে পারেন।",
      en: "This rests on what you told us. A lawyer or NGO can verify the law from the full memo.",
    },
  },
} as const;

/** Which laws were checked for the country of work, or that we do not have its law yet. */
export function countryCheckLine(dest: { name: L10n; of: L10n | null; supported: boolean }, lang: Lang): string {
  if (dest.supported && dest.of) {
    return lang === "bn"
      ? `${dest.of.bn} শ্রম আইন, বাংলাদেশের আইন ও আইএলও মান দিয়ে যাচাই করা হয়েছে।`
      : `Checked against ${dest.of.en} labour law, Bangladesh law and ILO standards.`;
  }
  return lang === "bn"
    ? `${dest.name.bn}-এর শ্রম আইন আমাদের কাছে এখনো নেই। শুধু বাংলাদেশের আইন ও আইএলও মান দেখা হয়েছে।`
    : `We do not have the labour law of ${dest.name.en} yet. Only Bangladesh law and ILO standards were checked.`;
}

export function bannerTitle(count: number, lang: Lang): string {
  if (count === 0) return lang === "bn" ? "বড় কোনো বিপদ পাওয়া যায়নি" : "No serious danger found";
  return lang === "bn"
    ? `সাবধান! চুক্তিতে ${formatNumber(count, "bn")}টি বড় বিপদ আছে`
    : `Warning! Your contract has ${count} serious ${count === 1 ? "risk" : "risks"}`;
}
