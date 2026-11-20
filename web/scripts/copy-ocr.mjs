// Copy the in-browser OCR files (spec 28) from node_modules into public/ocr/, so they are served by our own origin
// and no third-party CDN sees the visit: tesseract.js's worker, the LSTM-only wasm cores (the browser picks one by
// its SIMD support) and the Bangla + English models (4.0.0_best_int, the LSTM-only "best" integer models).
// Runs before `next dev` and `next build`; public/ocr/ is not committed.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const nm = join(web, "node_modules");
const out = join(web, "public", "ocr");

const files = [
  ["tesseract.js/dist/worker.min.js", "worker.min.js"],
  ["tesseract.js/LICENSE.md", "LICENSE-tesseract.js.md"],
  ["tesseract.js-core/LICENSE", "core/LICENSE"],
  ...["relaxedsimd-lstm", "simd-lstm", "lstm"].map((v) => [`tesseract.js-core/tesseract-core-${v}.wasm.js`, `core/tesseract-core-${v}.wasm.js`]),
  ...["ben", "eng"].map((l) => [`@tesseract.js-data/${l}/4.0.0_best_int/${l}.traineddata.gz`, `lang/${l}.traineddata.gz`]),
];

for (const [from, to] of files) {
  mkdirSync(dirname(join(out, to)), { recursive: true });
  copyFileSync(join(nm, from), join(out, to));
}
console.log(`copy-ocr: ${files.length} files -> public/ocr`);
