// Spec 28 calibration: read photos with tesseract.js exactly as the browser does (src/lib/citizen/browserOcr.ts:
// ben+eng, LSTM only, the models in public/ocr/lang, weakest word = line confidence) and write each photo's lines
// as JSON next to it, for backend/scripts scoring. Usage: node scripts/ocr-calibrate.mjs <photo>... (after copy-ocr)
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import { createWorker, OEM } from "tesseract.js";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const worker = await createWorker(["ben", "eng"], OEM.LSTM_ONLY, { langPath: join(web, "public", "ocr", "lang"), gzip: true, cachePath: join(web, ".next", "cache", "ocr") });
for (const photo of process.argv.slice(2)) {
  const t = Date.now();
  // the browser downscales to 2200px on the long side, upright (browserOcr.prepare)
  const img = await sharp(photo).rotate().resize(2200, 2200, { fit: "inside", withoutEnlargement: true }).png().toBuffer();
  const { data } = await worker.recognize(img, {}, { blocks: true });
  const lines = [];
  for (const b of data.blocks ?? []) for (const p of b.paragraphs) for (const l of p.lines) {
    const text = l.text.replace(/\s+/g, " ").trim();
    if (!text) continue;
    const confs = l.words.map((w) => w.confidence).filter(Number.isFinite);
    const r = (c) => Math.round(Math.max(0, Math.min(1, c / 100)) * 1000) / 1000;
    const nums = l.words.filter((w) => /[0-9০-৯]/.test(w.text)).map((w) => w.confidence).filter(Number.isFinite);
    lines.push({ text, conf: r(confs.length ? Math.min(...confs) : l.confidence), ...(nums.length ? { num_conf: r(Math.min(...nums)) } : {}),
                 words: l.words.map((w) => [w.text, Math.round(w.confidence)]) });
  }
  writeFileSync(photo.replace(/\.\w+$/, ".tess.json"), JSON.stringify(lines, null, 1));
  console.log(`${photo.split(/[\/]/).pop()}: ${lines.length} lines in ${((Date.now() - t) / 1000).toFixed(1)}s`);
}
await worker.terminate();
