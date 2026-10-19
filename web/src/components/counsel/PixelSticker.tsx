import type { PersonaId } from "@/lib/api";
import styles from "./counsel.module.css";

/* Pixel-art mood stickers for the three council members, ported from the Claude Design file
   "Mood Stickers.dc.html" (Happy → Sunny, Proud → Regal, Gloomy → Grey). The design draws each
   cell as a box-shadow; here each colour is one SVG path in viewBox cells, so a sticker stays
   crisp from an 18px vote badge up to the empty-chat hero, and layers animate in cell units. */

type Dot = [y: number, x: number, ch: string];
type Cell = [x: number, y: number, color: string];
type Motion = "hop" | "puff" | "sigh";
type Anim = "twinkle" | "beat" | "shine" | "glint" | "drift" | "fall" | "drip";

interface LayerSpec {
  dots: Dot[];
  anim: Anim;
  dur: number;
  delay?: number;
  under?: string; // palette key drawn beneath the layer; white otherwise
  hideStill?: boolean; // only visible while animating
}

interface Mood {
  g: string[][];
  motion: Motion;
  dur: number;
  layers: LayerSpec[];
}

interface Built {
  w: number;
  h: number;
  base: [string, string][];
  motion: Motion;
  dur: number;
  layers: { paths: [string, string][]; cx: number; cy: number; anim: Anim; dur: number; delay?: number; hideStill?: boolean }[];
}

const MOTION: Record<Motion, string> = { hop: styles.stkHop, puff: styles.stkPuff, sigh: styles.stkSigh };
const LAYER: Record<Anim, string> = {
  twinkle: styles.stkTwinkle,
  beat: styles.stkBeat,
  shine: styles.stkShine,
  glint: styles.stkGlint,
  drift: styles.stkDrift,
  fall: styles.stkFall,
  drip: styles.stkDrip,
};

/* body colours from the design's own swatches, in each persona's hue */
const BODY_COLOR: Record<PersonaId, string> = { happy: "#E9B544", proud: "#8F82E3", gloomy: "#8C9AB0" };
const INK = "#2B1D18";
const WHITE = "#FFFFFF";
const OUTLINE = 2; // die-cut margin in cells (the design's default)
const ROUND = 3; // closing radius that rounds the die-cut

/* ------------------------------------------------------------------ helpers (as in the design) */

function hex(h: string) {
  h = h.replace("#", "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}

function mix(a: string, b: string, t: number) {
  const pa = hex(a);
  const pb = hex(b);
  return "#" + pa.map((v, i) => Math.round(v + (pb[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

function palette(b: string): Record<string, string> {
  return {
    K: INK, B: b, S: mix(b, INK, 0.25), H: mix(b, WHITE, 0.4),
    L: "#86B85C", l: "#4F7D36", P: "#FF9EA6", R: "#EE4F6A", M: "#9E2B33",
    G: "#F5C443", Y: "#C98A1A", W: WHITE, T: "#4FB0EA", t: "#A9DDF7", C: "#CDD3DD", c: "#9AA3B3",
  };
}

const grid = (W: number, H: number) => Array.from({ length: H }, () => Array<string>(W).fill("."));

function stamp(g: string[][], rows: string[], ox: number, oy: number) {
  rows.forEach((row, y) => [...row].forEach((ch, x) => { if (ch !== ".") g[y + oy][x + ox] = ch; }));
}

function rowsToDots(rows: string[], ox: number, oy: number) {
  const d: Dot[] = [];
  rows.forEach((row, y) => [...row].forEach((ch, x) => { if (ch !== ".") d.push([y + oy, x + ox, ch]); }));
  return d;
}

function dots(g: string[][], list: Dot[], ox: number, oy: number) {
  list.forEach(([y, x, ch]) => { g[y + oy][x + ox] = ch; });
}

const off = (list: Dot[], ox: number, oy: number): Dot[] => list.map(([y, x, ch]) => [y + oy, x + ox, ch]);

function kernel(rad: number) {
  const k: [number, number][] = [];
  for (let dy = -rad; dy <= rad; dy++) for (let dx = -rad; dx <= rad; dx++) if (dx * dx + dy * dy <= rad * rad + 1) k.push([dx, dy]);
  return k;
}

function morph(m: Uint8Array, GW: number, GH: number, rad: number, dilate: boolean) {
  const ker = kernel(rad);
  const o = new Uint8Array(GW * GH);
  for (let y = 0; y < GH; y++)
    for (let x = 0; x < GW; x++) {
      let v = dilate ? 0 : 1;
      for (const [dx, dy] of ker) {
        const nx = x + dx;
        const ny = y + dy;
        const on = nx >= 0 && ny >= 0 && nx < GW && ny < GH && m[ny * GW + nx];
        if (dilate && on) { v = 1; break; }
        if (!dilate && !on) { v = 0; break; }
      }
      o[y * GW + x] = v;
    }
  return o;
}

/* ------------------------------------------------------------------ sprites (verbatim from the design) */

const BODY = [
  "......KKKKKKKK......",
  "....KKBBBBBBBBKK....",
  "...KBHHBBBBBBBBBK...",
  "..KBHBBBBBBBBBBBBK..",
  "..KHBBBBBBBBBBBBBK..",
  ".KBBBBBBBBBBBBBBBBK.",
  ".KBBBBBBBBBBBBBBBSK.",
  ".KBBBBBBBBBBBBBBBSK.",
  ".KBBBBBBBBBBBBBBBSK.",
  ".KBBBBBBBBBBBBBBBSK.",
  ".KBBBBBBBBBBBBBBBSK.",
  ".KBBBBBBBBBBBBBBBSK.",
  "..KBBBBBBBBBBBBSSK..",
  "...KSSSSSSSSSSSSK...",
  "....KSSSKKKKSSSK....",
  "....KKKKK..KKKKK....",
];
const SPROUT = [
  "...........KKK......",
  ".......KK.lLLLK.....",
  "......KLLLlKKK......",
  ".......KK.l.........",
];
const WILT = [
  "....................",
  "..........lll.......",
  "..........l.KLK.....",
  "..........l.KLLK....",
];
const CLOUD = [
  "....KKK.....",
  "..KKCCCKKK..",
  ".KCCCCCCCCK.",
  "KCCCCCCCCCCK",
  "KccccccccccK",
  ".KKKKKKKKKK.",
];

const row = (y: number, a: number, b: number, ch: string): Dot[] => Array.from({ length: b - a + 1 }, (_, i) => [y, a + i, ch]);
const sparkle = (y: number, x: number): Dot[] => [[y - 1, x, "G"], [y, x - 1, "G"], [y, x, "W"], [y, x + 1, "G"], [y + 1, x, "G"]];

function base(W: number, H: number, ox: number, oy: number, sprout: string[]) {
  const g = grid(W, H);
  stamp(g, sprout, ox, oy);
  stamp(g, BODY, ox, oy + 4);
  return g;
}

function mood(p: PersonaId): Mood {
  if (p === "happy") {
    const g = base(26, 24, 3, 3, SPROUT);
    dots(g, [
      [9, 6, "K"], [10, 5, "K"], [10, 7, "K"], [9, 13, "K"], [10, 12, "K"], [10, 14, "K"],
      [11, 4, "P"], [11, 5, "P"], [11, 14, "P"], [11, 15, "P"],
      ...row(11, 8, 11, "K"), [12, 8, "K"], [12, 9, "M"], [12, 10, "M"], [12, 11, "K"], [13, 9, "K"], [13, 10, "K"],
    ], 3, 3);
    return { g, motion: "hop", dur: 1.1, layers: [
      { dots: sparkle(2, 22), anim: "twinkle", dur: 1.6 },
      { dots: [[8, 24, "G"]], anim: "twinkle", dur: 1.6, delay: 0.8 },
      { dots: [[2, 1, "R"], [2, 3, "R"], ...row(3, 0, 4, "R"), ...row(4, 1, 3, "R"), [5, 2, "R"]], anim: "beat", dur: 1.1 },
    ] };
  }
  if (p === "proud") {
    const g = base(26, 24, 3, 3, SPROUT);
    dots(g, [
      ...row(9, 2, 17, "K"), ...row(10, 4, 8, "K"), ...row(10, 11, 15, "K"), ...row(11, 5, 7, "K"), ...row(11, 12, 14, "K"),
      [10, 5, "W"], [10, 12, "W"],
      ...row(13, 8, 10, "K"), [12, 11, "K"],
    ], 3, 3);
    return { g, motion: "puff", dur: 2.6, layers: [
      { dots: sparkle(2, 22), anim: "twinkle", dur: 2 },
      { dots: sparkle(7, 1), anim: "twinkle", dur: 2, delay: 1 },
      { dots: off([[14, 9, "G"], [14, 10, "G"], [15, 8, "G"], [15, 9, "W"], [15, 10, "G"], [15, 11, "G"], [16, 9, "Y"], [16, 10, "Y"]], 3, 3), under: "B", anim: "shine", dur: 2.6 },
      { dots: off([[11, 6, "W"], [11, 13, "W"]], 3, 3), under: "K", hideStill: true, anim: "glint", dur: 2.6 },
    ] };
  }
  const g = base(26, 30, 3, 9, WILT);
  dots(g, [
    [9, 5, "K"], [8, 6, "K"], [8, 7, "K"], [8, 12, "K"], [8, 13, "K"], [9, 14, "K"],
    [10, 6, "K"], [10, 7, "W"], [11, 6, "K"], [11, 7, "K"], [10, 12, "K"], [10, 13, "W"], [11, 12, "K"], [11, 13, "K"],
    [14, 9, "K"], [14, 10, "K"], [15, 8, "K"], [15, 11, "K"],
  ], 3, 9);
  return { g, motion: "sigh", dur: 3.4, layers: [
    { dots: rowsToDots(CLOUD, 7, 0), anim: "drift", dur: 4 },
    { dots: [[6, 10, "T"], [7, 10, "T"]], anim: "fall", dur: 1.4 },
    { dots: [[7, 13, "T"], [8, 13, "T"]], anim: "fall", dur: 1.4, delay: 0.47 },
    { dots: [[6, 16, "T"], [7, 16, "T"]], anim: "fall", dur: 1.4, delay: 0.93 },
    { dots: off([[12, 6, "T"], [13, 6, "T"], [14, 6, "t"]], 3, 9), under: "B", anim: "drip", dur: 2.8 },
  ] };
}

/* ------------------------------------------------------------------ build once per persona */

/* one path per colour, made of horizontal runs */
function paths(cells: Cell[]): [string, string][] {
  const byColor = new Map<string, Map<number, number[]>>();
  for (const [x, y, c] of cells) {
    const rows = byColor.get(c) ?? new Map<number, number[]>();
    byColor.set(c, rows);
    const xs = rows.get(y) ?? [];
    rows.set(y, xs);
    xs.push(x);
  }
  return [...byColor].map(([c, rows]) => {
    let d = "";
    for (const [y, xs] of rows) {
      xs.sort((a, b) => a - b);
      for (let i = 0; i < xs.length; ) {
        let j = i;
        while (j + 1 < xs.length && xs[j + 1] === xs[j] + 1) j++;
        d += `M${xs[i]} ${y}h${j - i + 1}v1h-${j - i + 1}z`;
        i = j + 1;
      }
    }
    return [c, d];
  });
}

function build(persona: PersonaId): Built {
  const m = mood(persona);
  const pal = palette(BODY_COLOR[persona]);
  const g = m.g;
  const H = g.length;
  const W = g[0].length;
  const P = OUTLINE + ROUND + 1;
  m.layers.forEach((l) => dots(g, l.dots, 0, 0));
  const GW = W + 2 * P;
  const GH = H + 2 * P;
  const mask = new Uint8Array(GW * GH);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (g[y][x] !== ".") mask[(y + P) * GW + x + P] = 1;
  const cut = morph(morph(mask, GW, GH, OUTLINE + ROUND, true), GW, GH, ROUND, false);
  let x0 = GW, y0 = GH, x1 = 0, y1 = 0;
  for (let y = 0; y < GH; y++)
    for (let x = 0; x < GW; x++)
      if (cut[y * GW + x]) {
        x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      }
  // what shows beneath an animated layer when it moves away
  const under = new Map<string, string>();
  m.layers.forEach((l) => l.dots.forEach(([y, x]) => under.set(`${y},${x}`, l.under ? pal[l.under] : WHITE)));
  const cells: Cell[] = [];
  for (let y = y0; y <= y1; y++)
    for (let x = x0; x <= x1; x++) {
      const gy = y - P;
      const gx = x - P;
      const ch = gy >= 0 && gx >= 0 && gy < H && gx < W ? g[gy][gx] : ".";
      const c = under.get(`${gy},${gx}`) ?? (ch !== "." ? pal[ch] : cut[y * GW + x] ? WHITE : null);
      if (c) cells.push([x - x0, y - y0, c]);
    }
  const layers = m.layers.map((l) => {
    const pts: Cell[] = l.dots.map(([y, x, ch]) => [x + P - x0, y + P - y0, pal[ch]]);
    return {
      paths: paths(pts),
      cx: pts.reduce((a, p) => a + p[0], 0) / pts.length + 0.5,
      cy: pts.reduce((a, p) => a + p[1], 0) / pts.length + 0.5,
      anim: l.anim,
      dur: l.dur,
      delay: l.delay,
      hideStill: l.hideStill,
    };
  });
  return { w: x1 - x0 + 1, h: y1 - y0 + 1, base: paths(cells), motion: m.motion, dur: m.dur, layers };
}

const BUILT = new Map<PersonaId, Built>();

function sticker(p: PersonaId) {
  let b = BUILT.get(p);
  if (!b) {
    b = build(p);
    BUILT.set(p, b);
  }
  return b;
}

/* ------------------------------------------------------------------ component */

/* The sticker fitted inside a size × size box. Decorative: the caller supplies the accessible name. */
export function PixelSticker({ persona, size, animate = false, className }: { persona: PersonaId; size: number; animate?: boolean; className?: string }) {
  const s = sticker(persona);
  const k = size / Math.max(s.w, s.h);
  return (
    <svg
      className={[styles.stk, animate && MOTION[s.motion], className].filter(Boolean).join(" ")}
      width={s.w * k}
      height={s.h * k}
      viewBox={`0 0 ${s.w} ${s.h}`}
      shapeRendering="crispEdges"
      aria-hidden="true"
      focusable="false"
      style={animate ? { animationDuration: `${s.dur}s` } : undefined}
    >
      {s.base.map(([c, d]) => (
        <path key={c} fill={c} d={d} />
      ))}
      {s.layers.map((l, i) => (
        <g
          key={i}
          className={animate ? LAYER[l.anim] : undefined}
          style={{
            transformBox: "view-box",
            transformOrigin: `${l.cx}px ${l.cy}px`,
            opacity: l.hideStill ? 0 : undefined,
            ...(animate && { animationDuration: `${l.dur}s`, animationDelay: l.delay ? `${l.delay}s` : undefined }),
          }}
        >
          {l.paths.map(([c, d]) => (
            <path key={c} fill={c} d={d} />
          ))}
        </g>
      ))}
    </svg>
  );
}
