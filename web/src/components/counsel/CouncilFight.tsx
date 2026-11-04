"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement } from "react";
import { mix, morph, palette } from "./PixelSticker";
import styles from "./counsel.module.css";

/* The council's deliberation loading scene, ported from the Claude Design file "Council Deliberation.dc.html"
   (council-fight.jsx, built on the Mood Fight kit in mood-fight.jsx). Remedies, Text and Enforcement brawl,
   the Chief Justice calls ORDER! and everyone walks home, so the 16.9 s loop is seamless. Like the design,
   every cell is a box-shadow and every pose is a pure function of one clock T on a 1920×1080 stage,
   scaled down to fit the chat column. */

type Face = "happy" | "happyHurt" | "happyKo" | "proud" | "proudHurt" | "proudKo" | "gloomy" | "gloomySmile";
type Sprout = "sprout" | "wilt";
type Origin = "center" | "left" | "right";
type Ease = (u: number) => number;
type Dot = [y: number, x: number, ch: string];

interface Sprite {
  w: number;
  h: number;
  ps: number;
  ox: number;
  oy: number;
  shadow: string;
}

interface Pose {
  x: number;
  y: number;
  sx: number;
  sy: number;
  rot: number;
  vis: number;
  origin: Origin;
  face: Face;
  sprout: Sprout;
  crispy: boolean;
}

const INK = "#2B1D18";
const CREAM = "#F3E9DC";
const GOLD = "#F5C443";
const RED = "#EE4F6A";
const BLUE = "#4FB0EA";
const FONT = "var(--font-pixel), monospace";
const GY = 860;
const PS = 12;
const HOME = { happy: 520, proud: 1080, gloomy: 1560 };
/* the stickers' body colours (PixelSticker BODY_COLOR) and the lenses' labels */
const COLOR = { happy: "#E9B544", proud: "#8F82E3", gloomy: "#8C9AB0" };
const LENS = { happy: "REMEDIES", proud: "TEXT", gloomy: "ENFORCEMENT" };

/* the design's OM_SCENES; CUES are each scene's start */
const SCENES = [
  ["Standoff", 1.1],
  ["HappyAttack", 3.2],
  ["ProudStrike", 3.4],
  ["Brawl", 3.2],
  ["Storm", 3.6],
  ["Settle", 2.4],
] as const;
type SceneName = (typeof SCENES)[number][0];
const CUES = {} as Record<SceneName, number>;
let END = 0;
for (const [name, dur] of SCENES) {
  CUES[name] = END;
  END += dur;
}

/* ------------------------------------------------------------------ motion helpers (as in the design) */

const Easing = {
  easeInOutCubic: (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  easeOutBack: (t: number) => 1 + 2.70158 * Math.pow(t - 1, 3) + 1.70158 * Math.pow(t - 1, 2),
  easeOutExpo: (t: number) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
};
const MOTION = { move: Easing.easeInOutCubic, pop: Easing.easeOutBack, hit: Easing.easeOutExpo };

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function tw(T: number, a: number, b: number, from: number, to: number, ease?: Ease) {
  if (T <= a) return from;
  if (T >= b) return to;
  const u = (T - a) / (b - a);
  return from + (to - from) * (ease ? ease(u) : u);
}

function track(T: number, keys: [number, number][]) {
  if (T <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    if (T < keys[i][0]) return tw(T, keys[i - 1][0], keys[i][0], keys[i - 1][1], keys[i][1], MOTION.move);
  }
  return keys[keys.length - 1][1];
}

function arc(T: number, a: number, b: number, h: number) {
  if (T <= a || T >= b) return 0;
  const u = (T - a) / (b - a);
  return -4 * h * u * (1 - u);
}

function land(T: number, at: number, amt: number) {
  const d = T - at;
  if (d < 0 || d > 0.7) return { sx: 1, sy: 1 };
  const e = amt * Math.exp(-d * 7) * Math.cos(d * 18);
  return { sx: 1 + e * 0.8, sy: 1 - e };
}

function idleHop(d: number, period: number, h: number) {
  const u = (d % period) / period;
  if (u < 0.7) {
    const v = u / 0.7;
    return { y: -4 * h * v * (1 - v), sx: 0.96, sy: 1.05 };
  }
  const g = Math.sin(((u - 0.7) / 0.3) * Math.PI) * 0.1;
  return { y: 0, sx: 1 + g * 0.8, sy: 1 - g };
}

function rnd(n: number) {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

/* ------------------------------------------------------------------ pixel sprites (verbatim from the design) */

const SC = new Map<string, Sprite>();

/* rows of palette keys → one box-shadow per cell, with a rounded white die-cut of radius r */
function makeSprite(key: string, build: () => string[] | string[][], pal: Record<string, string>, ps: number, r: number): Sprite {
  const ck = `${key}|${ps}|${r}`;
  const hit = SC.get(ck);
  if (hit) return hit;
  const rows = build();
  const H = rows.length;
  const W = rows[0].length;
  const k = r > 0 ? 3 : 0;
  const P = r > 0 ? r + k + 1 : 0;
  const GW = W + 2 * P;
  const GH = H + 2 * P;
  const m = new Uint8Array(GW * GH);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (rows[y][x] !== ".") m[(y + P) * GW + x + P] = 1;
  const cut = r > 0 ? morph(morph(m, GW, GH, r + k, true), GW, GH, k, false) : m;
  let x0 = GW, y0 = GH, x1 = 0, y1 = 0;
  for (let y = 0; y < GH; y++)
    for (let x = 0; x < GW; x++)
      if (cut[y * GW + x]) {
        x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      }
  const parts: string[] = [];
  for (let y = y0; y <= y1; y++)
    for (let x = x0; x <= x1; x++) {
      const gy = y - P;
      const gx = x - P;
      const ch = gy >= 0 && gx >= 0 && gy < H && gx < W ? rows[gy][gx] : ".";
      const c = ch !== "." ? (pal[ch] ?? INK) : cut[y * GW + x] ? "#FFFFFF" : null;
      if (c) parts.push(`${(x - x0 + 1) * ps}px ${(y - y0 + 1) * ps}px 0 0.5px ${c}`);
    }
  const s = { w: (x1 - x0 + 1) * ps, h: (y1 - y0 + 1) * ps, ps, ox: (P - x0) * ps, oy: (P - y0) * ps, shadow: parts.join(",") };
  SC.set(ck, s);
  return s;
}

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
const SPROUT = ["...........KKK......", ".......KK.lLLLK.....", "......KLLLlKKK......", ".......KK.l........."];
const WILT = ["....................", "..........lll.......", "..........l.KLK.....", "..........l.KLLK...."];
const CLOUD = ["....KKK.....", "..KKCCCKKK..", ".KCCCCCCCCK.", "KCCCCCCCCCCK", "KccccccccccK", ".KKKKKKKKKK."];
const SKYCLOUD = ["....CCC.....", "..CCCCCCCC..", ".CCCCCCCCCC.", "CCCCCCCCCCCC", "cccccccccccc"];
const SHADES = ["KKKKKKKKKKKKKKKK", "..KWKKK..KWKKK..", "...KKK....KKK..."];
const STAR = ["....K....", "...KGK...", "KKKKGKKKK", "KGGGWGGGK", ".KGGGGGK.", "..KGGGK..", ".KGGKGGK.", ".KGK.KGK.", ".KK...KK."];
const HEART = [".KK.KK.", "KRRKRRK", "KRWRRRK", "KRRRRRK", ".KRRRK.", "..KRK..", "...K..."];
const SPARK = ["..G..", "..G..", "GGWGG", "..G..", "..G.."];
const BOLT = ["....KKKK", "...KGGK.", "..KGWK..", ".KGWGK..", "KGGGGKKK", "KKKGWGGK", "..KGWGK.", "..KGGK..", ".KGWK...", ".KGK....", "KGK.....", "KK......"];

function puffRows(r: number) {
  const n = 2 * r + 1;
  const rows: string[] = [];
  const inside = (dx: number, dy: number) => dx * dx + dy * dy <= r * r + r * 0.6;
  for (let y = 0; y < n; y++) {
    let s = "";
    for (let x = 0; x < n; x++) {
      const dx = x - r;
      const dy = y - r;
      if (!inside(dx, dy)) {
        s += ".";
        continue;
      }
      const edge = !inside(dx + 1, dy) || !inside(dx - 1, dy) || !inside(dx, dy + 1) || !inside(dx, dy - 1);
      s += edge ? "K" : dy > r * 0.35 ? "d" : "D";
    }
    rows.push(s);
  }
  return rows;
}

const row = (y: number, a: number, b: number, ch: string): Dot[] => Array.from({ length: b - a + 1 }, (_, i) => [y, a + i, ch]);
const BADGE: Dot[] = [[14, 9, "G"], [14, 10, "G"], [15, 8, "G"], [15, 9, "W"], [15, 10, "G"], [15, 11, "G"], [16, 9, "Y"], [16, 10, "Y"]];
const CHEEKS: Dot[] = [[11, 4, "P"], [11, 5, "P"], [11, 14, "P"], [11, 15, "P"]];
const HURT_EYES: Dot[] = [[8, 5, "K"], [9, 6, "K"], [10, 5, "K"], [8, 14, "K"], [9, 13, "K"], [10, 14, "K"]];
const KO_EYES: Dot[] = [[8, 5, "K"], [8, 7, "K"], [9, 6, "K"], [10, 5, "K"], [10, 7, "K"], [8, 12, "K"], [8, 14, "K"], [9, 13, "K"], [10, 12, "K"], [10, 14, "K"]];
const SQUIGGLE: Dot[] = [[13, 8, "K"], [12, 9, "K"], [13, 10, "K"], [12, 11, "K"]];
const GLOOM_EYES: Dot[] = [[9, 5, "K"], [8, 6, "K"], [8, 7, "K"], [8, 12, "K"], [8, 13, "K"], [9, 14, "K"], [10, 6, "K"], [10, 7, "W"], [11, 6, "K"], [11, 7, "K"], [10, 12, "K"], [10, 13, "W"], [11, 12, "K"], [11, 13, "K"]];
const SHADES_FACE: Dot[] = [...row(9, 2, 17, "K"), ...row(10, 4, 8, "K"), ...row(10, 11, 15, "K"), ...row(11, 5, 7, "K"), ...row(11, 12, 14, "K"), [10, 5, "W"], [10, 12, "W"]];
const FACES: Record<Face, Dot[]> = {
  happy: [[9, 6, "K"], [10, 5, "K"], [10, 7, "K"], [9, 13, "K"], [10, 12, "K"], [10, 14, "K"], ...CHEEKS, ...row(11, 8, 11, "K"), [12, 8, "K"], [12, 9, "M"], [12, 10, "M"], [12, 11, "K"], [13, 9, "K"], [13, 10, "K"]],
  happyHurt: [...HURT_EYES, ...CHEEKS, [12, 9, "K"], [12, 10, "K"], [13, 8, "K"], [13, 9, "M"], [13, 10, "M"], [13, 11, "K"], [14, 9, "K"], [14, 10, "K"]],
  happyKo: [...KO_EYES, ...SQUIGGLE],
  proud: [...SHADES_FACE, ...row(13, 8, 10, "K"), [12, 11, "K"], ...BADGE],
  proudHurt: [...HURT_EYES, ...row(12, 8, 11, "K"), [13, 8, "K"], [13, 11, "K"], ...BADGE],
  proudKo: [...KO_EYES, ...SQUIGGLE, ...BADGE],
  gloomy: [...GLOOM_EYES, [14, 9, "K"], [14, 10, "K"], [15, 8, "K"], [15, 11, "K"]],
  gloomySmile: [...GLOOM_EYES, [14, 8, "K"], [15, 9, "K"], [15, 10, "K"], [14, 11, "K"]],
};

function charRows(face: Face, sprout: Sprout) {
  const g = Array.from({ length: 20 }, () => Array<string>(20).fill("."));
  const st = (rows: string[], oy: number) => rows.forEach((r, y) => [...r].forEach((ch, x) => { if (ch !== ".") g[y + oy][x] = ch; }));
  st(sprout === "wilt" ? WILT : SPROUT, 0);
  st(BODY, 4);
  FACES[face].forEach(([y, x, ch]) => { g[y][x] = ch; });
  return g;
}

function charSprite(face: Face, sprout: Sprout, body: string, ps: number, r: number) {
  return makeSprite(`c:${face}:${sprout}:${body}`, () => charRows(face, sprout), palette(body), ps, r);
}

/* ------------------------------------------------------------------ sprite elements */

function Pix({ s, x = 0, y = 0, style }: { s: Sprite; x?: number; y?: number; style?: CSSProperties }) {
  return (
    <div style={{ position: "absolute", left: x, top: y, width: s.w, height: s.h, ...style }}>
      <div style={{ position: "absolute", left: -s.ps, top: -s.ps, width: s.ps, height: s.ps, boxShadow: s.shadow }} />
    </div>
  );
}

function PixC({ s, cx, cy, sc = 1, rot = 0, op = 1 }: { s: Sprite; cx: number; cy: number; sc?: number; rot?: number; op?: number }) {
  return (
    <Pix
      s={s}
      x={cx - s.w / 2}
      y={cy - s.h / 2}
      style={{ transform: `rotate(${rot}deg) scale(${sc})`, opacity: op, visibility: op > 0.001 && sc > 0.001 ? "visible" : "hidden" }}
    />
  );
}

function Char({ s, st }: { s: Sprite; st: Pose }) {
  const footY = s.oy + 20 * s.ps;
  const ox = st.origin === "left" ? 0 : st.origin === "right" ? s.w : s.w / 2;
  return (
    <Pix
      s={s}
      x={st.x - s.w / 2}
      y={GY - footY + st.y}
      style={{
        transformOrigin: `${ox}px ${footY}px`,
        transform: `rotate(${st.rot}deg) scale(${st.sx},${st.sy})`,
        opacity: st.vis,
        visibility: st.vis ? "visible" : "hidden",
      }}
    />
  );
}

/* outlined pixel lettering (POW!, ORDER!) */
function big({ key, text, x, y, size, color, sc = 1, rot = 0, op = 1 }: { key: string; text: string; x: number; y: number; size: number; color: string; sc?: number; rot?: number; op?: number }) {
  const o = Math.max(3, Math.round(size * 0.055));
  const d = [[o, 0], [-o, 0], [0, o], [0, -o], [o, o], [-o, o], [o, -o], [-o, -o], [0, o * 2.4], [o, o * 2.4], [-o, o * 2.4]];
  return (
    <div
      key={key}
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%,-50%) rotate(${rot}deg) scale(${sc})`,
        opacity: op,
        visibility: op > 0.001 && sc > 0.001 ? "visible" : "hidden",
        fontFamily: FONT,
        fontWeight: 700,
        fontSize: size,
        lineHeight: 1,
        color,
        whiteSpace: "nowrap",
        letterSpacing: "0.02em",
        textShadow: d.map(([a, b]) => `${a}px ${b}px 0 ${INK}`).join(","),
      }}
    >
      {text}
    </div>
  );
}

/* ------------------------------------------------------------------ choreography: every pose is a pure function of T */

const HITS: [t: number, who: "h" | "p", text: string, x: number, y: number, rot: number][] = [
  [0.6, "h", "POW!", 640, 560, -8],
  [1.0, "p", "BAM!", 970, 600, 7],
  [1.4, "h", "WHAP!", 690, 470, 6],
  [1.8, "p", "BONK!", 950, 490, -6],
  [2.2, "h", "POW!", 650, 620, 8],
  [2.6, "p", "OOF!", 930, 570, -7],
];
const { HappyAttack: A, ProudStrike: P, Brawl: B, Storm: S, Settle: E } = CUES;

function pose(x: number, face: Face, sprout: Sprout = "sprout"): Pose {
  return { x, y: 0, sx: 1, sy: 1, rot: 0, vis: 1, origin: "center", face, sprout, crispy: false };
}

function happyState(T: number) {
  const st = pose(HOME.happy, "happy");
  const mul = (q: { sx: number; sy: number }) => { st.sx *= q.sx; st.sy *= q.sy; };
  const idle = (d: number) => { const h = idleHop(d, 0.55, 26); st.y += h.y; mul(h); };
  if (T < A) {
    idle(T);
    return st;
  }
  if (T < B) {
    if (T < A + 0.35) {
      const k = Math.sin((clamp((T - A) / 0.35, 0, 1) * Math.PI) / 2);
      st.sy *= 1 - 0.22 * k;
      st.sx *= 1 + 0.16 * k;
    }
    st.x = T < A + 1.05 ? tw(T, A + 0.35, A + 0.95, 520, 690) : T < A + 1.45 ? tw(T, A + 1.05, A + 1.45, 690, 860) : tw(T, A + 1.45, A + 2.15, 860, 560);
    st.y += arc(T, A + 0.35, A + 0.95, 150) + arc(T, A + 1.05, A + 2.15, 130);
    if ((T > A + 0.35 && T < A + 0.95) || (T > A + 1.05 && T < A + 1.45)) { st.sx *= 0.92; st.sy *= 1.1; }
    mul(land(T, A + 0.95, 0.2));
    st.rot = tw(T, A + 1.45, A + 2.1, 0, -360, MOTION.move);
    mul(land(T, A + 2.15, 0.25));
    if (T >= A + 2.4 && T < P + 2.3) { const h = idleHop(T - A - 2.4, 0.5, 30); st.y += h.y; mul(h); }
    if (T >= P + 2.3) {
      st.face = "happyHurt";
      st.x = tw(T, P + 2.3, P + 2.9, 560, 400, MOTION.hit);
      st.y += arc(T, P + 2.3, P + 2.9, 90);
      st.rot = tw(T, P + 2.3, P + 2.9, 0, -360, MOTION.hit);
      mul(land(T, P + 2.9, 0.3));
      if (T > P + 2.9) st.rot += 7 * Math.sin((T - P - 2.9) * 14) * Math.exp(-(T - P - 2.9) * 1.5);
    }
    return st;
  }
  if (T < S + 2.65) {
    st.face = "happyHurt";
    st.x = tw(T, B, B + 0.4, 400, 680, MOTION.move);
    if (T < B + 0.4) { st.sx *= 1.12; st.sy *= 0.9; st.rot = 12; } else st.vis = 0;
    return st;
  }
  if (T < E + 0.6) {
    Object.assign(st, { x: 680, face: "happyKo", sprout: "wilt", crispy: true, origin: "left" });
    const u = clamp((T - S - 2.95) / 0.4, 0, 1);
    st.rot = -90 * u * u * (1 - tw(T, E + 0.3, E + 0.6, 0, 1, MOTION.move));
    if (T < S + 2.95) st.x += (rnd(Math.floor(T * 40)) - 0.5) * 10;
    return st;
  }
  // back on its feet, it hops home
  if (T < E + 0.8) {
    const k = Math.sin((clamp((T - E - 0.6) / 0.2, 0, 1) * Math.PI) / 2);
    st.sy *= 1 - 0.18 * k;
    st.sx *= 1 + 0.12 * k;
  }
  st.x = tw(T, E + 0.8, E + 1.4, 680, HOME.happy, MOTION.move);
  st.y += arc(T, E + 0.8, E + 1.4, 120);
  mul(land(T, E + 1.4, 0.25));
  if (T >= END - 0.55) idle(T - END + 0.55);
  return st;
}

function proudState(T: number) {
  const st = pose(HOME.proud, "proud");
  const mul = (q: { sx: number; sy: number }) => { st.sx *= q.sx; st.sy *= q.sy; };
  const puff = (t: number, amt: number) => {
    const p = (0.5 - 0.5 * Math.cos((t * Math.PI * 2) / 1.6)) * amt;
    st.sx *= 1 + 0.04 * p;
    st.sy *= 1 + 0.05 * p;
    st.rot += 3 * p;
  };
  if (T < A + 1.45) {
    puff(T, 1);
    return st;
  }
  if (T < B) {
    st.face = "proudHurt";
    st.x = tw(T, A + 1.45, A + 1.95, 1080, 1210, MOTION.hit);
    const d0 = T - A - 1.45;
    st.rot += 20 * Math.exp(-d0 * 4) * Math.cos(d0 * 14);
    mul(land(T, A + 1.45, 0.22));
    if (T >= P) {
      const d = T - P;
      if (d > 0.05 && d < 0.5) st.rot += 7 * Math.sin(d * 32) * (1 - d / 0.5);
      if (T >= P + 0.8) st.face = "proud";
      mul(land(T, P + 0.8, 0.15));
      const ch = tw(T, P + 1.0, P + 2.0, 0, 1, MOTION.move) * (1 - tw(T, P + 2.0, P + 2.6, 0, 1, MOTION.move));
      st.sx *= 1 + 0.1 * ch;
      st.sy *= 1 + 0.12 * ch;
      st.rot += 7 * ch;
      if (T > P + 1.6 && T < P + 2.0) st.x += (rnd(Math.floor(T * 40)) - 0.5) * 6;
      st.x += tw(T, P + 2.0, P + 2.2, 0, 34, MOTION.hit) - tw(T, P + 2.3, P + 2.9, 0, 34, MOTION.move);
      if (T >= P + 2.8) puff(T - P - 2.8, 1);
    }
    return st;
  }
  if (T < S + 2.65) {
    st.face = "proudHurt";
    st.x = tw(T, B, B + 0.4, 1210, 920, MOTION.move);
    if (T < B + 0.4) { st.sx *= 1.12; st.sy *= 0.9; st.rot = -12; } else st.vis = 0;
    return st;
  }
  if (T < E + 0.6) {
    Object.assign(st, { x: 920, face: "proudKo", sprout: "wilt", crispy: true, origin: "right" });
    const u = clamp((T - S - 3.0) / 0.4, 0, 1);
    st.rot = 90 * u * u * (1 - tw(T, E + 0.3, E + 0.6, 0, 1, MOTION.move));
    if (T < S + 3.0) st.x += (rnd(Math.floor(T * 40) + 5) - 0.5) * 10;
    return st;
  }
  // dusts itself off and struts home
  st.x = tw(T, E + 0.8, E + 1.4, 920, HOME.proud, MOTION.move);
  st.y += arc(T, E + 0.8, E + 1.4, 60);
  mul(land(T, E + 1.4, 0.2));
  puff(T - END, tw(T, E + 1.5, E + 1.9, 0, 1));
  return st;
}

function gloomyState(T: number) {
  const st = pose(HOME.gloomy, "gloomy", "wilt");
  const br = 0.5 - 0.5 * Math.cos((T * Math.PI * 2) / (END / 5));
  st.sy *= 1 - 0.035 * br;
  st.sx *= 1 + 0.02 * br;
  const sg = Math.sin(clamp((T - S) / 0.9, 0, 1) * Math.PI);
  st.sy *= 1 - 0.14 * sg;
  st.sx *= 1 + 0.08 * sg;
  if (T >= E + 0.2 && T < E + 1.9) {
    st.face = "gloomySmile";
    st.sprout = "sprout";
    st.y += arc(T, E + 0.2, E + 0.6, 50);
    const q = land(T, E + 0.6, 0.2);
    st.sx *= q.sx;
    st.sy *= q.sy;
  }
  // ...and sighs back into its usual self before the loop starts again
  const s2 = Math.sin(clamp((T - E - 1.9) / (END - E - 1.9), 0, 1) * Math.PI);
  st.sy *= 1 - 0.1 * s2;
  st.sx *= 1 + 0.06 * s2;
  return st;
}

function cloudState(T: number) {
  const bx = HOME.gloomy + 20;
  const by = GY - 330;
  const x = track(T, [[S + 0.7, bx], [S + 1.6, 1250], [S + 2.4, 800], [E + 0.3, 800], [E + 1.3, bx]]);
  const y = track(T, [[S + 0.7, by], [S + 1.6, 270], [S + 2.4, 260], [E + 0.3, 260], [E + 1.3, by]]);
  const sc = track(T, [[S + 0.7, 1], [S + 1.6, 4], [E + 0.3, 4], [E + 1.3, 1]]);
  return { x, y: y + 8 * Math.sin((T * Math.PI * 2) / 2.8), sc, storm: clamp((sc - 1) / 3, 0, 1) };
}

function hpOf(who: "h" | "p" | "g", t: number) {
  if (who === "g") return 100;
  if (t >= E + 0.6) return tw(t, E + 0.6, E + 1.6, 0, 100, MOTION.move);
  let v = 100;
  if (who === "h" && t >= P + 2.3) v = 58;
  if (who === "p" && t >= A + 1.45) v = 62;
  HITS.forEach((h) => { if (h[1] === who && t >= B + h[0]) v -= 12; });
  if (t >= S + 2.6) v = 0;
  return v;
}

/* ------------------------------------------------------------------ the scene */

const crisp = (c: string) => mix(c, INK, 0.55);
const PAL = palette(COLOR.happy);
const LAYER: CSSProperties = { position: "absolute", left: 0, top: 0, width: 1920, height: 1080, transformOrigin: "0 0" };
const BACK = [[-175, -40], [175, -50], [-95, -150], [95, -165], [0, -90]];
const FRONT = [[-140, 45], [0, 70], [140, 40]];
const RAIN_V = (1200 * Math.max(1, Math.round((END * 1100) / 1200))) / END; // whole laps per loop

function hills(color: string, h: (i: number) => number) {
  return Array.from({ length: 160 }, (_, i) => (
    <div key={i} style={{ position: "absolute", left: -320 + i * 16, top: GY + 300 - h(i) * 16, width: 17, height: h(i) * 16, background: color }} />
  ));
}

function Fight({ T, label }: { T: number; label: string }) {
  const farHills = useMemo(() => hills("#E9CBAB", (i) => Math.round(26 + 6 * Math.sin(i * 0.09) + 3 * Math.sin(i * 0.23 + 2))), []);
  const nearHills = useMemo(() => hills("#DDB08B", (i) => Math.round(21 + 4 * Math.sin(i * 0.13 + 1) + 2 * Math.sin(i * 0.37))), []);

  const hs = happyState(T);
  const pr = proudState(T);
  const gs = gloomyState(T);
  const cl = cloudState(T);
  const hSpr = charSprite(hs.face, hs.sprout, hs.crispy ? crisp(COLOR.happy) : COLOR.happy, PS, 2);
  const pSpr = charSprite(pr.face, pr.sprout, pr.crispy ? crisp(COLOR.proud) : COLOR.proud, PS, 2);
  const gSpr = charSprite(gs.face, gs.sprout, COLOR.gloomy, PS, 2);

  // camera: starts and ends on the same wide shot so the loop is seamless
  const camX = track(T, [[0, 960], [A, 960], [A + 0.5, 830], [A + 2.4, 800], [P + 0.3, 1140], [P + 1.9, 1160], [P + 2.25, 860], [B + 0.2, 800], [B + 2.4, 800], [S + 0.3, 1000], [E + 0.4, 1000], [E + 1.6, 960]]);
  const camY = track(T, [[0, 560], [A, 560], [A + 0.5, 640], [P + 0.3, 650], [P + 1.9, 670], [P + 2.25, 650], [B + 0.2, 640], [B + 2.4, 640], [S + 0.3, 480], [E + 0.4, 480], [E + 1.6, 560]]);
  const camS = track(T, [[0, 1.04], [A, 1.04], [A + 0.5, 1.45], [P + 0.3, 1.6], [P + 1.9, 1.85], [P + 2.25, 1.4], [B + 0.2, 1.6], [B + 2.4, 1.6], [S + 0.3, 1.0], [S + 2.5, 1.0], [S + 2.7, 1.05], [E + 0.4, 1.05], [E + 1.6, 1.04]]);
  let amp = 0;
  const imp = (t0: number, a: number) => { const d = T - t0; if (d >= 0 && d < 0.8) amp += a * Math.exp(-d * 7); };
  imp(A + 1.45, 18);
  imp(P + 2.3, 14);
  HITS.forEach((h) => imp(B + h[0], 9));
  imp(S + 2.6, 30);
  imp(E, 16);
  if (T > B + 0.4 && T < S + 2.65) amp += 3;
  const fr = Math.floor(T * 30);
  const shX = amp * (rnd(fr) * 2 - 1);
  const shY = amp * (rnd(fr + 999) * 2 - 1);
  const camT = (f: number) => {
    const s = 1 + (camS - 1) * f;
    const cx = 960 + (camX - 960) * f;
    const cy = 540 + (camY - 540) * f;
    return `translate(${960 + shX * f}px,${540 + shY * f}px) scale(${s}) translate(${-cx}px,${-cy}px)`;
  };

  const skyCloud = makeSprite("skycloud", () => SKYCLOUD, { C: "#FFFBF5", c: "#F1E2D2" }, 14, 0);
  const shades = makeSprite("shades", () => SHADES, PAL, PS, 1);
  const star = makeSprite("star", () => STAR, PAL, PS, 1);
  const starSm = makeSprite("star", () => STAR, PAL, 8, 1);
  const heart = makeSprite("heart", () => HEART, PAL, PS, 1);
  const spark = makeSprite("spark", () => SPARK, PAL, PS, 0);
  const bolt = makeSprite("bolt", () => BOLT, PAL, 18, 1);
  const puff = makeSprite("puff7", () => puffRows(7), PAL, 14, 0);
  const dust = makeSprite("puff3", () => puffRows(3), PAL, 10, 0);
  const smoke = makeSprite("smoke3", () => puffRows(3), { K: INK, D: "#9A949C", d: "#77717A" }, 10, 0);
  const cloudSpr = makeSprite("cloud", () => CLOUD, PAL, PS, 0);
  const stormSpr = makeSprite("stormcloud", () => CLOUD, { K: INK, C: "#7D8496", c: "#565C6E" }, PS, 0);

  // HUD
  const trail = (w: "h" | "p" | "g") => {
    let s = 0;
    for (let k = 0; k < 8; k++) s += hpOf(w, T - 0.2 - 0.08 * k);
    return s / 8;
  };
  const panels = [
    { name: LENS.happy, w: "h" as const, face: hs.vis ? hs.face : ("happyHurt" as const), sprout: hs.sprout, col: hs.crispy ? crisp(COLOR.happy) : COLOR.happy },
    { name: LENS.proud, w: "p" as const, face: pr.vis ? pr.face : ("proudHurt" as const), sprout: pr.sprout, col: pr.crispy ? crisp(COLOR.proud) : COLOR.proud },
    { name: LENS.gloomy, w: "g" as const, face: gs.face, sprout: gs.sprout, col: COLOR.gloomy },
  ];

  // fx timings
  const flyU = clamp((T - A - 1.45) / 1.15, 0, 1);
  const dropU = clamp((T - P - 0.45) / 0.35, 0, 1);
  const charge = tw(T, P + 1.0, P + 2.0, 0, 1, MOTION.move) * (1 - tw(T, P + 2.0, P + 2.3, 0, 1, MOTION.hit));
  const badgeX = pr.x;
  const badgeY = GY - 54 * pr.sy;
  const beamStart = 1190;
  const beamEnd = 600;
  const beamLen = tw(T, P + 2.0, P + 2.3, 0, beamStart - beamEnd, MOTION.hit);
  const beamTh = 44 * (1 - tw(T, P + 2.45, P + 2.62, 0, 1, MOTION.move));
  const beamOn = T >= P + 2.0 && T < P + 2.62;
  const cloudOn = T >= B + 0.4 && T < S + 2.95;
  const cAppear = tw(T, B + 0.4, B + 0.65, 0, 1, MOTION.pop);
  const cPoof = tw(T, S + 2.65, S + 2.95, 0, 1, MOTION.hit);
  const cn = Math.floor(T * 12);
  const pn = Math.floor(T * 7);
  const puffEl = (o: number[], i: number) => {
    const dx = (rnd(cn * 7 + i) - 0.5) * 34;
    const dy = (rnd(cn * 13 + i) - 0.5) * 26;
    const sc = (0.9 + rnd(cn * 3 + i) * 0.2) * cAppear * (1 + 0.5 * cPoof);
    return <PixC key={`pf${i}`} s={puff} cx={800 + o[0] * (1 + 0.6 * cPoof) + dx} cy={GY - 170 + o[1] + dy} sc={sc} op={cloudOn ? 1 - cPoof : 0} />;
  };
  const peekH = charSprite("happyHurt", "sprout", COLOR.happy, PS, 2);
  const peekP = charSprite("proudHurt", "sprout", COLOR.proud, PS, 2);

  const smiling = T >= E + 0.2 && T < E + 1.9;
  const rainN = (smiling ? 0 : 5) + Math.round(75 * cl.storm);
  const rainW = 144 * cl.sc * 0.8;
  const rainTop = cl.y + 26 * cl.sc;
  const drops: ReactElement[] = [];
  for (let i = 0; i < rainN; i++) {
    const y = rainTop + ((T * RAIN_V + rnd(i + 1) * 1200) % 1200);
    const x = cl.x + (rnd(i + 50) - 0.5) * rainW;
    drops.push(<div key={`r${i}`} style={{ position: "absolute", left: x, top: y, width: 8, height: 26, background: BLUE, visibility: y < GY - 20 ? "visible" : "hidden" }} />);
  }
  const tearOn = gs.face === "gloomy" && cl.storm < 0.05;
  const tph = (T % 2.8) / 2.8;
  const tearDy = tph < 0.3 ? 0 : 70 * Math.pow((tph - 0.3) / 0.7, 2);
  const tearOp = tph < 0.3 ? tph / 0.3 : 1 - (tph - 0.3) / 0.7;
  const flash = Math.max(
    T >= S + 2.6 ? 0.85 * Math.exp(-(T - S - 2.6) * 7) : 0,
    T >= S + 2.8 ? 0.5 * Math.exp(-(T - S - 2.8) * 9) : 0,
    T >= E ? 0.35 * Math.exp(-(T - E) * 8) : 0,
  );
  const boltOn = (T >= S + 2.6 && T < S + 2.72) || (T >= S + 2.8 && T < S + 2.92);
  const darkness = cl.storm * 0.42;
  const word = (key: string, text: string, t0: number, x: number, y: number, size: number, rot: number, dur: number) =>
    big({
      key, text, x, y, size, color: GOLD, rot,
      sc: tw(T, t0, t0 + 0.22, 0, 1, MOTION.pop) * (1 + 0.15 * tw(T, t0 + 0.22, t0 + dur, 0, 1)),
      op: T >= t0 ? 1 - tw(T, t0 + dur - 0.15, t0 + dur, 0, 1) : 0,
    });
  const dustAt = (key: string, x: number, t0: number) => {
    const u = clamp((T - t0) / 0.5, 0, 1);
    const on = T >= t0 && T < t0 + 0.5;
    return [-1, 1].map((s) => <PixC key={key + s} s={dust} cx={x + s * (90 + 90 * Math.sqrt(u))} cy={GY - 20 - 20 * u} sc={1 - 0.6 * u} op={on ? 1 - u : 0} />);
  };
  const shadowEl = (key: string, st: Pose, w: number) => (
    <div
      key={key}
      style={{
        position: "absolute", left: st.x - w / 2, top: GY - 9, width: w, height: 18, borderRadius: "50%", background: "rgba(43,29,24,0.2)",
        transform: `scale(${1 - Math.min(0.6, -st.y / 500)})`, visibility: st.vis && st.origin === "center" ? "visible" : "hidden",
      }}
    />
  );
  const dots = Math.max(0, Math.floor((T % 2) / 0.5));

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: "#F8EEE2", fontFamily: FONT }}>
      {([["#F8EEE2", 0, 260], ["#F5E4D1", 260, 200], ["#F1D8C0", 460, 160], ["#ECCBAE", 620, 460]] as const).map(([c, top, h]) => (
        <div key={c} style={{ position: "absolute", left: 0, top, width: 1920, height: h, background: c }} />
      ))}
      <div style={{ ...LAYER, transform: camT(0.15) }}>
        {[[260, 170, 0], [1180, 110, 2], [1900, 290, 4]].map(([x, y, ph]) => (
          <Pix key={ph} s={skyCloud} x={x - 200 + 60 * Math.sin((T * Math.PI * 2) / END + ph)} y={y} />
        ))}
        {farHills}
      </div>
      <div style={{ ...LAYER, transform: camT(0.35) }}>{nearHills}</div>

      <div style={{ ...LAYER, transform: camT(1) }}>
        <div style={{ position: "absolute", left: -800, top: GY - 6, width: 3600, height: 40, background: INK }} />
        <div style={{ position: "absolute", left: -800, top: GY, width: 3600, height: 22, background: "#86B85C" }} />
        <div style={{ position: "absolute", left: -800, top: GY + 22, width: 3600, height: 10, background: "#4F7D36" }} />
        <div style={{ position: "absolute", left: -800, top: GY + 32, width: 3600, height: 900, background: "repeating-conic-gradient(#A8774F 0 25%, #9A6A45 0 50%) 0 0 / 64px 64px" }} />
        {shadowEl("sh-g", gs, 220)}
        {shadowEl("sh-p", pr, 210)}
        {shadowEl("sh-h", hs, 210)}
        {drops}
        <Char s={gSpr} st={gs} />
        <Char s={pSpr} st={pr} />
        <Char s={hSpr} st={hs} />
        <div
          style={{
            position: "absolute", left: gs.x - 48, top: GY - 96 + gs.y + tearDy, width: 12, height: 12, background: BLUE, opacity: tearOp,
            visibility: tearOn ? "visible" : "hidden", boxShadow: "0 12px 0 0 #A9DDF7",
          }}
        />
        <PixC s={cloudSpr} cx={cl.x} cy={cl.y} sc={cl.sc} />
        <PixC s={stormSpr} cx={cl.x} cy={cl.y} sc={cl.sc} op={cl.storm} />

        <PixC s={shades} cx={1080 + 760 * flyU} cy={GY - 114 - 640 * flyU + 380 * flyU * flyU} rot={900 * flyU} op={T >= A + 1.45 && T < A + 2.6 ? 1 : 0} />
        <PixC s={shades} cx={pr.x} cy={GY - 114 - 360 * (1 - dropU * dropU)} op={T >= P + 0.45 && T < P + 0.8 ? 1 : 0} />
        <PixC s={spark} cx={pr.x + 70} cy={GY - 124} sc={Math.sin(clamp((T - P - 0.8) / 0.4, 0, 1) * Math.PI) * 1.4} rot={45} />
        {Array.from({ length: 10 }, (_, i) => {
          const ph = ((((T - P - 1.0) * 1.6 + rnd(i + 3)) % 1) + 1) % 1;
          const ang = rnd(i) * Math.PI * 2;
          const rr = 260 * (1 - ph);
          return (
            <div
              key={`cp${i}`}
              style={{
                position: "absolute", left: badgeX + Math.cos(ang) * rr - 6, top: badgeY + Math.sin(ang) * rr - 6, width: 12, height: 12, background: GOLD,
                boxShadow: `0 0 0 3px ${INK}`, opacity: ph, visibility: T > P + 1.0 && T < P + 2.0 ? "visible" : "hidden",
              }}
            />
          );
        })}
        <PixC s={star} cx={badgeX} cy={badgeY} sc={(0.4 + 1.1 * charge) * (T > P + 1.0 ? 1 : 0)} rot={T * 200} op={charge > 0.01 ? 1 : 0} />
        <div
          style={{
            position: "absolute", left: beamStart - beamLen, top: GY - 60 - beamTh / 2, width: beamLen, height: beamTh, background: GOLD,
            boxShadow: `0 0 0 6px ${INK}, 0 0 0 12px #FFFFFF`, visibility: beamOn ? "visible" : "hidden",
          }}
        >
          <div style={{ position: "absolute", left: 0, right: 0, top: "35%", height: "30%", background: "#FFFFFF" }} />
        </div>
        <PixC s={star} cx={beamStart - beamLen} cy={GY - 60} sc={1.2} rot={T * 400} op={beamOn && T < P + 2.45 ? 1 : 0} />
        {[-70, 10, 80].map((dx, i) => {
          const t0 = A + 2.2 + i * 0.12;
          const u = clamp((T - t0) / 1.1, 0, 1);
          return (
            <PixC
              key={`ht${i}`} s={heart} cx={560 + dx + Math.sin(u * 8 + i) * 14} cy={GY - 260 - 200 * u}
              sc={tw(T, t0, t0 + 0.25, 0, 1, MOTION.pop)} op={T >= t0 && u < 1 ? 1 - Math.max(0, (u - 0.7) / 0.3) : 0}
            />
          );
        })}

        {BACK.map((o, i) => puffEl(o, i))}
        <PixC
          s={peekH} cx={680 + (rnd(pn * 5) - 0.5) * 140} cy={GY - 200 + (rnd(pn * 5 + 1) - 0.5) * 150} sc={0.72 * cAppear}
          rot={(rnd(pn * 5 + 2) - 0.5) * 80} op={cloudOn && T < S + 2.65 ? 1 : 0}
        />
        <PixC
          s={peekP} cx={920 + (rnd(pn * 9) - 0.5) * 140} cy={GY - 200 + (rnd(pn * 9 + 1) - 0.5) * 150} sc={0.72 * cAppear}
          rot={(rnd(pn * 9 + 2) - 0.5) * 80} op={cloudOn && T < S + 2.65 ? 1 : 0}
        />
        {FRONT.map((o, i) => puffEl(o, i + 10))}
        {HITS.map((h, hi) => {
          const t0 = B + h[0];
          return [0, 1, 2, 3].map((k) => {
            const ang = (k * Math.PI) / 2 + 0.6 + hi;
            const dd = tw(T, t0, t0 + 0.5, 0, 300, MOTION.hit);
            return (
              <PixC
                key={`bs${hi}${k}`} s={starSm} cx={800 + Math.cos(ang) * (120 + dd)} cy={GY - 190 + Math.sin(ang) * (90 + dd * 0.7)} rot={dd * 2}
                op={T >= t0 && T < t0 + 0.5 ? 1 - tw(T, t0 + 0.25, t0 + 0.5, 0, 1) : 0}
              />
            );
          });
        })}
        {HITS.map((h, hi) => word(`bw${hi}`, h[2], B + h[0], h[3], h[4], 64, h[5], 0.45))}

        {([[400, "sh"], [1210, "sp"]] as const).map(([sx0, k]) =>
          [0, 1, 2].map((i) => {
            const ph = ((T - S - 2.75) / 1.4 + i / 3) % 1;
            return (
              <PixC
                key={k + i} s={smoke} cx={sx0 + (i - 1) * 50 + Math.sin(ph * 6 + i) * 16} cy={GY - 120 - 160 * ph} sc={0.6 + 0.7 * ph}
                op={T > S + 2.75 && T < E + 0.6 ? 1 - ph : 0}
              />
            );
          }),
        )}
        {dustAt("kh", 420, S + 3.35)}
        {dustAt("kp", 1200, S + 3.4)}
        {dustAt("uh", 680, E + 0.6)}
        {dustAt("up", 920, E + 0.6)}
        {dustAt("lh", HOME.happy, E + 1.4)}
        {dustAt("lp", HOME.proud, E + 1.4)}

        <PixC s={star} cx={980} cy={GY - 170} sc={tw(T, A + 1.45, A + 1.6, 0, 2.2, MOTION.hit)} rot={20} op={T >= A + 1.45 ? 1 - tw(T, A + 1.6, A + 1.85, 0, 1) : 0} />
        <PixC s={star} cx={600} cy={GY - 60} sc={tw(T, P + 2.3, P + 2.45, 0, 2.2, MOTION.hit)} rot={-15} op={T >= P + 2.3 ? 1 - tw(T, P + 2.45, P + 2.7, 0, 1) : 0} />
        {word("bonk", "BONK!", A + 1.45, 990, GY - 330, 84, -8, 0.8)}
        {word("zap", "ZAP!", P + 2.3, 470, GY - 320, 84, 6, 0.8)}
        {[[-60, 0], [70, 0.1]].map(([dx, d], i) => (
          <PixC key={`gs${i}`} s={spark} cx={HOME.gloomy + dx} cy={GY - 290 + i * 40} sc={Math.sin(clamp((T - E - 0.2 - d) / 0.6, 0, 1) * Math.PI) * 1.5} rot={45 * i} />
        ))}
      </div>

      <div style={{ position: "absolute", inset: 0, background: "#1E2233", opacity: darkness }} />
      <div style={{ position: "absolute", inset: 0, background: "#FFFFFF", opacity: flash }} />
      <div style={{ ...LAYER, transform: camT(1) }}>
        <Pix s={bolt} x={800 - bolt.w / 2} y={cl.y + 90} style={{ visibility: boltOn ? "visible" : "hidden" }} />
        {word("krak", "KRAK!", S + 2.62, 1090, 470, 120, -6, 0.9)}
      </div>

      {panels.map((p, i) => {
        const portrait = charSprite(p.face, p.sprout, p.col, 4, 1);
        const v = hpOf(p.w, T);
        return (
          <div
            key={p.name}
            style={{
              position: "absolute", left: 60 + i * 620, top: 40, width: 560, boxSizing: "border-box", display: "flex", alignItems: "center", gap: 20,
              background: INK, padding: "12px 24px 12px 12px", boxShadow: "0 0 0 6px #FFFFFF",
            }}
          >
            <div style={{ position: "relative", width: portrait.w, height: portrait.h, flex: "none" }}>
              <Pix s={portrait} />
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", color: CREAM, fontSize: 30, lineHeight: 1 }}>
                <span>{p.name}</span>
                <span style={{ color: v === 0 ? RED : "#C9B8AA", fontSize: 24 }}>{v === 0 ? "K.O." : Math.round(v)}</span>
              </div>
              <div style={{ position: "relative", height: 26, background: "#5A3F36", boxShadow: `0 0 0 4px ${CREAM}` }}>
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${trail(p.w)}%`, background: RED }} />
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${v}%`, background: GOLD }} />
              </div>
            </div>
          </div>
        );
      })}

      <div style={{ position: "absolute", inset: 0, transform: `translate(${shX * 0.6}px,${shY * 0.6}px)` }}>
        {[0, 1, 2, 3, 4, 5, 6, 7].map((k) => {
          const ang = (k * Math.PI) / 4 + 0.3;
          const dd = tw(T, E, E + 0.6, 0, 420, MOTION.hit);
          return (
            <PixC
              key={`os${k}`} s={starSm} cx={960 + Math.cos(ang) * (160 + dd)} cy={430 + Math.sin(ang) * (100 + dd * 0.6)} rot={dd}
              op={T >= E && T < E + 0.6 ? 1 - tw(T, E + 0.3, E + 0.6, 0, 1) : 0}
            />
          );
        })}
        {big({
          key: "order", text: "ORDER!", x: 960, y: 430, size: 220, color: GOLD, rot: -4,
          sc: tw(T, E, E + 0.3, 2.6, 1, MOTION.pop), op: T >= E ? tw(T, E, E + 0.1, 0, 1) * (1 - tw(T, E + 1.0, E + 1.3, 0, 1)) : 0,
        })}
      </div>

      <div style={{ position: "absolute", left: 0, right: 0, top: 960, display: "flex", justifyContent: "center" }}>
        <div
          style={{
            position: "relative", background: INK, color: CREAM, fontSize: 44, lineHeight: 1, letterSpacing: "0.12em",
            padding: "16px 64px 16px 28px", boxShadow: "0 0 0 6px #FFFFFF", whiteSpace: "nowrap",
          }}
        >
          {label}
          <span style={{ position: "absolute", left: "calc(100% - 52px)", top: 16 }}>{".".repeat(dots)}</span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ clock + fit */

/* The loop clock in seconds; it stays at 0 (everyone at home) when the viewer prefers reduced motion. */
function useLoopClock() {
  const [T, setT] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    // rAF's timestamp is the frame's start, which can precede a performance.now() taken here, so `now - t0` could
    // go negative on the first frame (and ".".repeat(-1) throws). Take t0 from the first frame instead.
    let t0 = -1;
    const tick = (now: number) => {
      if (t0 < 0) t0 = now;
      setT(((now - t0) / 1000) % END);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  return T;
}

/* The 1920×1080 stage scaled to the frame's width. */
export default function CouncilFight({ label = "DELIBERATING" }: { label?: string }) {
  const T = useLoopClock();
  const frameRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setScale(e.contentRect.width / 1920));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={frameRef} className={styles.fight} role="img" aria-label="The council is deliberating">
      {scale > 0 && (
        <div style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080, transformOrigin: "0 0", transform: `scale(${scale})` }}>
          <Fight T={T} label={label} />
        </div>
      )}
    </div>
  );
}
