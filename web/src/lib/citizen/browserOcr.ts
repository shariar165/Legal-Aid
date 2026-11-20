"use client";

import type { OcrLine } from "@/lib/api";

/* In-browser OCR (spec 28). On a server without OCR (the lite demo), Citizen reads the photo on the device with
   tesseract.js, Bangla + English, and sends only the lines and their confidences: the image never leaves the phone.
   The worker, the wasm core and the models are served from /ocr (scripts/copy-ocr.mjs), never from a CDN. */

const MAX_SIDE = 2200; // the server's EasyOCR path shrinks to the same size (ingestion.ocr_image)
const IMAGE_EXT = /\.(png|jpe?g|webp|bmp|gif|heic|heif|tiff?)$/i;
/* Mean line confidence under which a photo is sent back to be retaken (spec 28 calibration): photos this blurry
   (0.06-0.22 on the test set) were read at 59-84% of their text and never yielded the salary, while every readable
   test photo, Bangla ones included, scored 0.29 or more. */
const MIN_MEAN_CONF = 0.25;

export class OcrError extends Error {
  constructor(public code: "ocr_unreadable" | "ocr_empty" | "ocr_blurry" | "ocr_failed") {
    super(code);
  }
}

export const isImage = (file: File) => file.type.startsWith("image/") || IMAGE_EXT.test(file.name);

/** The photo, upright (EXIF orientation applied) and no larger than MAX_SIDE. */
async function prepare(file: File): Promise<HTMLCanvasElement> {
  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    throw new OcrError("ocr_unreadable"); // e.g. HEIC on a browser that cannot decode it
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * scale);
  canvas.height = Math.round(bmp.height * scale);
  canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
  bmp.close();
  return canvas;
}

/**
 * Read a photo on the device. `onProgress` gets 0..1: loading the engine and models is the first fifth, recognition
 * the rest. Each line's confidence is its weakest word's, as the server's EasyOCR path does (ingestion.py).
 */
export async function readPhoto(file: File, onProgress: (p: number) => void): Promise<OcrLine[]> {
  const canvas = await prepare(file);
  const { createWorker, OEM } = await import("tesseract.js");
  let worker: Awaited<ReturnType<typeof createWorker>> | null = null;
  try {
    worker = await createWorker(["ben", "eng"], OEM.LSTM_ONLY, {
      workerPath: "/ocr/worker.min.js",
      corePath: "/ocr/core",
      langPath: "/ocr/lang",
      gzip: true,
      logger: (m) => {
        if (m.status === "recognizing text") onProgress(0.2 + 0.8 * m.progress);
        else if (typeof m.progress === "number") onProgress(0.2 * m.progress);
      },
    });
    const { data } = await worker.recognize(canvas, {}, { blocks: true });
    const lines: OcrLine[] = [];
    for (const block of data.blocks ?? []) {
      for (const para of block.paragraphs) {
        for (const line of para.lines) {
          const text = line.text.replace(/\s+/g, " ").trim();
          if (!text) continue;
          const confs = line.words.map((w) => w.confidence).filter((c) => Number.isFinite(c));
          const conf = (confs.length ? Math.min(...confs) : line.confidence) / 100;
          lines.push({ text, conf: Math.round(Math.max(0, Math.min(1, conf)) * 1000) / 1000 });
        }
      }
    }
    if (!lines.length) throw new OcrError("ocr_empty");
    if (lines.reduce((a, l) => a + l.conf, 0) / lines.length < MIN_MEAN_CONF) throw new OcrError("ocr_blurry");
    return lines;
  } catch (e) {
    if (e instanceof OcrError) throw e;
    console.error("[ocr]", e);
    throw new OcrError("ocr_failed");
  } finally {
    await worker?.terminate();
  }
}
