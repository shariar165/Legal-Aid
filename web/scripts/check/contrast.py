"""WCAG contrast of the token pairs in globals.css, light and dark (spec 26).

  python contrast.py [path/to/globals.css]     # default: web/src/app/globals.css; exits 1 if a pair fails
"""
import io
import re
import sys
from pathlib import Path

path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "src" / "app" / "globals.css"
css = io.open(path, encoding="utf-8").read()
root = css[css.index(":root {"):css.index("\n}\n", css.index(":root {"))]
dark = css[css.index(':root[data-theme="dark"]'):]
dark = dark[:dark.index("\n  }\n")]
def parse(b): return dict(re.findall(r"--([\w-]+):\s*([^;]+);", b))
L = parse(root); D = {**L, **parse(dark)}
def res(t, k):
    v = t[k].strip()
    m = re.fullmatch(r"var\(--([\w-]+)\)", v)
    return res(t, m.group(1)) if m else v
def lum(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def cr(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la + .05) / (lb + .05)
TEXT = [(f, b) for f in ("ink", "ink-2", "muted") for b in ("bg", "card", "subtle", "paper")] + [
    ("link", "bg"), ("link", "card"), ("on-accent", "accent"), ("on-accent", "accent-hover"), ("card", "accent"),
    ("accent", "card"), ("accent", "bg"), ("accent", "accent-tint"), ("on-deep", "deep"), ("on-deep-muted", "deep"),
    ("sand-ink", "sand"), ("gold-ink", "gold"), ("highlight-ink", "highlight"), ("lg-paid-ink", "lg-paid-tint"),
    ("muted", "accent-tint"), ("ok", "card"), ("warn", "card"), ("bad", "card")]
for k in ("ok", "warn", "bad"): TEXT.append((f"{k}-ink", f"{k}-tint"))
for k in ("critical", "high", "medium", "low"): TEXT.append((f"sev-{k}-ink", f"sev-{k}-tint"))
for k in ("happy", "proud", "gloomy"): TEXT += [(f"p-{k}-ink", f"p-{k}-tint"), (f"p-{k}", "card")]
# --line-strong is left out on purpose: spec 26 keeps those hairlines decorative (~1.75:1), never the only cue.
UI = [(f"sev-{k}", "card") for k in ("critical", "high", "medium", "low")] + [("focus", "bg"), ("sand", "deep"), ("gold", "deep")]
bad = 0
for name, t in (("light", L), ("dark", D)):
    for pairs, need in ((TEXT, 4.5), (UI, 3.0)):
        for f, b in pairs:
            r = cr(res(t, f), res(t, b))
            if r < need:
                bad += 1; print(f"FAIL {name:5} {f:18} on {b:14} {r:5.2f} < {need}")
print("all pass" if not bad else f"{bad} failing pairs")
sys.exit(1 if bad else 0)
