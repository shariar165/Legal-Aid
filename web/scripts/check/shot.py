"""Headless Chrome over CDP: run JS in the app's origin, save screenshots (spec 20) and audit pages (spec 29 step 0.1).

  python shot.py eval "<async js expression>"
  python shot.py snap <path> <width> <out.png> [--height 900] [--full] [--wait 2500] [--js "<js before snap>"]
                       [--theme light|dark] [--print out.pdf] [--clear-cookies] [--reload]
  python shot.py audit <path> <width> [--theme light|dark] [--js "<js before measuring>"] [--login] [--json]
  python shot.py audit-all [--sample migrant_text] [--widths 390,820,1440] [--themes light,dark] [--only a,b]
                       [--out NAME] [--against baseline] [--shots DIR]

--theme stores the choice in localStorage (spec 26) before the page loads. --print also emulates print media and saves
a PDF of the page (A4) next to the screenshot, which is then taken in print media too.

`audit` measures one page as a first visit (cache off): axe-core WCAG 2.2 AA violations, tap targets, small Latin and
Bangla text, sideways scroll, page height, and font and CSS bytes (decoded and on the wire). The rules are in
audit_js.py. `audit-all` audits the standard states of spec 29 at each width and theme and writes
docs/design/audit/<NAME or the git branch>.md and .json; --against adds the change from an earlier run's .json.

Chrome: the CHROME variable, else google-chrome / chromium on PATH, else the Windows install path. CHROME_FLAGS adds
launch flags (a Linux container needs "--no-sandbox --disable-dev-shm-usage").
A persistent profile (in the system temp dir, outside the repo) keeps the session cookie between calls.
Expects the web app on :3000 and the backend on :8000. `eval`, `--login` and `audit-all` sign in the local test account
desk-check@example.test (a fake address; audit-all creates it if it is missing). Needs `websockets` (in the backend
.venv) and axe-core (`npm install` in web/).
"""

import argparse
import base64
import datetime
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_js  # noqa: E402
import citizen_js  # noqa: E402

WINDOWS_CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME = os.environ.get("CHROME") or next(
    (p for p in map(shutil.which, ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")) if p), WINDOWS_CHROME)
CHROME_FLAGS = shlex.split(os.environ.get("CHROME_FLAGS", ""))
PROFILE = Path(tempfile.gettempdir()) / "jukti-shot-profile"
PORT = int(os.environ.get("JUKTI_CDP_PORT", "9333"))
ORIGIN = os.environ.get("JUKTI_ORIGIN", "http://localhost:3000")  # another port: also add it to AIN_CORS
API = os.environ.get("JUKTI_API", "http://localhost:8000")
AXE = HERE.parents[1] / "node_modules" / "axe-core" / "axe.min.js"
AUDIT_DIR = HERE.parents[2] / "docs" / "design" / "audit"
CREDS = "JSON.stringify({email: 'desk-check@example.test', password: 'desk-check-pass-2026'})"
def auth_js(action: str) -> str:
    return (f"fetch('{API}/api/auth/{action}', {{method: 'POST', credentials: 'include', headers: {{'Content-Type': 'application/json'}},"
            f" body: {CREDS}}}).then(r => r.status)")


LOGIN = auth_js("login")


class Tab:
    def __init__(self, ws):
        self.ws, self.n = ws, 0
        self.res: dict[str, dict] = {}  # requestId -> type, url, wire and decoded bytes (Network events)

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            if "method" in msg:
                self._event(msg["method"], msg.get("params", {}))

    def _event(self, method, p):
        if method == "Network.responseReceived":
            self.res[p["requestId"]] = {"type": p["type"], "url": p["response"]["url"], "wire": 0, "decoded": 0}
        elif method == "Network.dataReceived" and p["requestId"] in self.res:
            self.res[p["requestId"]]["decoded"] += p["dataLength"]
        elif method == "Network.loadingFinished" and p["requestId"] in self.res:
            self.res[p["requestId"]]["wire"] = p["encodedDataLength"]

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=f"(async () => {{ return {expr}; }})()", awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:800])
        return r["result"].get("value")

    def goto(self, url, wait_ms):
        self.res.clear()
        self.call("Page.navigate", url=url)
        time.sleep(wait_ms / 1000)

    def bytes(self):
        """font and CSS bytes since the last goto (call after the page settles: it drains the pending events)"""
        self.call("Runtime.evaluate", expression="0")
        out = {"font_decoded": 0, "font_wire": 0, "css_decoded": 0, "css_wire": 0, "fonts": [], "css": []}
        for r in self.res.values():
            kind = {"Font": "font", "Stylesheet": "css"}.get(r["type"])
            if kind and not r["url"].startswith("data:"):
                out[f"{kind}_decoded"] += r["decoded"]
                out[f"{kind}_wire"] += r["wire"]
                out["fonts" if kind == "font" else "css"].append([r["url"].rsplit("/", 1)[-1].split("?")[0], r["decoded"]])
        return out


def launch():
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
                             "--no-first-run", "--hide-scrollbars", "--force-device-scale-factor=1", *CHROME_FLAGS, "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
            page = next(t for t in targets if t["type"] == "page")
            return proc, page["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit(f"chrome did not start ({CHROME})")


def chrome_version():
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version"))["Browser"]
    except Exception:
        return "?"


# ---------------------------------------------------------------- audit

def set_width(tab, width, height=900):
    tab.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=width < 600)


def measure(tab, width, axe=True):
    """axe-core + audit_js metrics + bytes on the page as it is now"""
    m = tab.js(audit_js.metrics(width))
    if axe:
        if not tab.js("typeof axe !== 'undefined'"):
            if not AXE.exists():
                raise SystemExit(f"axe-core not found at {AXE}: run `npm install` in web/")
            tab.call("Runtime.evaluate", expression=AXE.read_text(encoding="utf-8"))
        m["axe"] = tab.js(audit_js.AXE_RUN)
    m["bytes"] = tab.bytes()
    return m


def screenshot(tab, width, out: Path):
    h = int(tab.js("Math.ceil(document.documentElement.scrollHeight)"))
    set_width(tab, width, min(h, 16000))
    time.sleep(0.6)
    out.write_bytes(base64.b64decode(tab.call("Page.captureScreenshot", format="png")["data"]))
    set_width(tab, width)


def sign_in(tab):
    """sign the test account in on the current page; create it on first use"""
    if tab.js(LOGIN) != 200 and tab.js(auth_js("signup")) != 200:
        raise SystemExit("could not sign in or create desk-check@example.test (is the backend on :8000?)")


HELPERS = citizen_js.WAIT + citizen_js.CLICK_TEXT
SLEEP = "await new Promise(r => setTimeout(r, {0}));"


def drive(body):
    """an async driver with until()/clickText() in scope"""
    return f"(async () => {{ {HELPERS} {body} }})()"


def start_job(tab, sample):
    jid = tab.js(f"""(async () => {{ const f = new FormData(); f.append('sample_id', '{sample}');
        const r = await fetch('{API}/api/analyze', {{method: 'POST', body: f, credentials: 'include'}});
        if (!r.ok) throw new Error('analyze ' + r.status); return (await r.json()).job_id; }})()""")
    return jid


def wait_job(tab, jid, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = tab.js(f"fetch('{API}/api/jobs/{jid}', {{credentials: 'include'}}).then(r => r.json()).then(j => j.status)")
        if st in ("done", "error"):
            return st
        time.sleep(1)
    raise SystemExit(f"job {jid} did not finish in {timeout}s")


class Skip(Exception):
    pass


# Each state: (key, title, run). run(tab, ctx) navigates and drives the page; it returns a short note or raises Skip.
def _citizen(path, body="", wait=2500):
    def run(tab, ctx):
        tab.goto(ORIGIN + path.format(**ctx), wait)
        return tab.js(drive(body + citizen_js.GROW + SLEEP.format(500) + "return document.querySelector('h1,h2')?.textContent || '';"))
    return run


def _citizen_result(lang):
    def run(tab, ctx):
        if lang == "bn":  # a finished result opened from its link shows at once
            tab.goto(f"{ORIGIN}/r/{ctx['job']}", 2500)
            return tab.js(drive("await until(() => document.querySelector('[class*=resultScroll]'), 30000);" + SLEEP.format(600)
                                + citizen_js.GROW + "return document.querySelector('h2')?.textContent || '';"))
        tab.goto(ORIGIN + "/", 2000)  # the EN switch is on the home screen only, so English runs the sample from home
        return tab.js(citizen_js.to_result(ctx["sample_index"], "en", True))
    return run


def _salary_check(tab, ctx):
    tab.goto(ORIGIN + "/", 2000)
    return tab.js(drive(f"""
      const btns = await until(() => {{ const l = [...document.querySelectorAll('button')].filter(b => b.className.includes('sampleBtn')); return l.length ? l : null; }});
      btns[{ctx['photo_index']}].click();
      await until(() => document.getElementById('ocr-title'), 60000);
      {SLEEP.format(500)} {citizen_js.GROW}
      return document.getElementById('ocr-title').textContent;"""))


def _promise_form(tab, ctx):
    """the "what did the agent tell you?" form, opened (a sample with promises shows "change answers" instead)"""
    tab.goto(f"{ORIGIN}/r/{ctx['job']}", 2500)
    found = tab.js(drive("await until(() => document.querySelector('[class*=resultScroll]'), 30000);" + SLEEP.format(600)
                         + "return Boolean(document.getElementById('title-promise'));"))
    ctx["ledger"] = bool(found)
    if not found:
        raise Skip("ledger off: no promise step on the result")
    return tab.js(drive("""
      const open = [...document.querySelectorAll('button')].find(x => !x.disabled && /উত্তর দিন|উত্তর বদলান/.test(x.textContent));
      open.click();
      await until(() => document.getElementById('ps-salary'));
      """ + SLEEP.format(400) + citizen_js.GROW + """
      document.getElementById('title-promise').scrollIntoView({block: 'start'});
      return open.textContent.trim();"""))


def _upload_error(tab, ctx):
    tab.goto(ORIGIN + "/", 2000)
    tab.js("""(async () => { const i = document.querySelector('input[type=file]'); const dt = new DataTransfer();
      dt.items.add(new File(['not a contract'], 'contract.xyz', {type: 'application/octet-stream'}));
      i.files = dt.files; i.dispatchEvent(new Event('change', {bubbles: true})); return true; })()""")
    time.sleep(4)
    return tab.js(drive(citizen_js.GROW + "return document.querySelector('h1')?.textContent || '';"))


def _counsel(view=None, desk_lang=None, ask=False):
    def run(tab, ctx):
        tab.goto(f"{ORIGIN}/counsel/{ctx['job']}", 2500)
        body = "await until(() => document.querySelector('[class*=viewTab]'), 30000);"
        if view:
            body += f"await until(() => [...document.querySelectorAll('[class*=viewTab]')].find(b => b.textContent.includes('{view}'))).then(b => b.click());"
        if desk_lang:
            body += f"await until(() => document.querySelector('[class*=langToggle] button[lang={desk_lang}]')).then(b => b.click());"
        if ask:
            body += """
              const ta = await until(() => [...document.querySelectorAll('textarea')].find(t => t.offsetParent));
              Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(ta, 'Is the recruitment fee in this contract legal?');
              ta.dispatchEvent(new Event('input', {bubbles: true}));
              await new Promise(r => setTimeout(r, 200));
              ta.closest('form').requestSubmit();
              await until(() => document.querySelectorAll('article[data-persona]').length, 90000);
              let n = -1; while (n !== document.querySelectorAll('article[data-persona]').length) { n = document.querySelectorAll('article[data-persona]').length; await new Promise(r => setTimeout(r, 2000)); }"""
        body += SLEEP.format(800) + "return document.querySelector('[aria-current=page]')?.textContent || '';"
        return tab.js(drive(body))
    return run


def _running(tab, ctx):
    """the photo sample pauses for its salary check (up to 10 minutes), so this progress screen holds still"""
    jid = start_job(tab, ctx["photo_sample"])
    tab.goto(f"{ORIGIN}/counsel/{jid}", 1500)
    return tab.js(drive("await until(() => document.body.innerText.includes('Waiting for the salary figure'), 60000);"
                        + SLEEP.format(500) + "return 'running, paused at the salary check';"))


def _plain(path):
    def run(tab, ctx):
        tab.goto(ORIGIN + path, 2500)
        return tab.js("document.querySelector('h1')?.textContent || ''")
    return run


def _login(tab, ctx):
    tab.call("Network.clearBrowserCookies")
    tab.goto(ORIGIN + "/login", 2500)
    ctx["relogin"] = True
    return tab.js("document.querySelector('h1')?.textContent || ''")


STATES = [
    ("citizen-home", "Citizen · home", _plain("/")),
    ("citizen-salary-check", "Citizen · salary check (photo OCR confirm)", _salary_check),
    ("citizen-promise-form", "Citizen · promise form", _promise_form),
    ("citizen-result-bn", "Citizen · result (bn)", _citizen_result("bn")),
    ("citizen-result-en", "Citizen · result (en)", _citizen_result("en")),
    ("citizen-result-gone", "Citizen · result gone", _citizen("/r/audit-no-such-job", "await until(() => document.querySelector('h1'), 20000);")),
    ("citizen-upload-error", "Citizen · upload error", _upload_error),
    ("counsel-start", "Counsel · start", _plain("/counsel")),
    ("counsel-running", "Counsel · running", _running),
    ("desk-bn", "Counsel · Case Desk (bn)", _counsel()),
    ("desk-en", "Counsel · Case Desk (en)", _counsel(desk_lang="en")),
    ("memo", "Counsel · Memo", _counsel("Memo")),
    ("council", "Counsel · Council after a question", _counsel("Council", ask=True)),
    ("checks", "Counsel · Checks", _counsel("Checks")),
    ("docs", "/docs", _plain("/docs")),
    ("login", "/login", _login),
]
CITIZEN = {k for k, *_ in STATES if k.startswith("citizen")}


def git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=HERE, check=True).stdout.strip()
    except Exception:
        return "?"


def audit_all(tab, a):
    widths = [int(w) for w in a.widths.split(",")]
    themes = a.themes.split(",")
    only = set(a.only.split(",")) if a.only else None
    states = [s for s in STATES if not only or s[0] in only]
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    set_width(tab, 1440)
    tab.goto(ORIGIN + "/login", 2000)
    sign_in(tab)
    samples = tab.js(f"fetch('{API}/api/samples', {{credentials: 'include'}}).then(r => r.json())")
    ids = [s["id"] for s in samples]
    health = tab.js(f"fetch('{API}/api/health').then(r => r.json())")
    ctx = {"sample": a.sample, "sample_index": ids.index(a.sample),
           "photo_index": next(i for i, s in enumerate(samples) if s.get("kind") == "image")}
    ctx["photo_sample"] = ids[ctx["photo_index"]]
    ctx["job"] = start_job(tab, a.sample)
    print("job", ctx["job"], wait_job(tab, ctx["job"]), flush=True)

    rows, theme_script = [], None
    for theme in themes:
        if theme_script:
            tab.call("Page.removeScriptToEvaluateOnNewDocument", identifier=theme_script)
        theme_script = tab.call("Page.addScriptToEvaluateOnNewDocument",
                                source=f"try{{localStorage.setItem('jukti-theme','{theme}')}}catch(e){{}}")["identifier"]
        for width in widths:
            set_width(tab, width)
            for key, title, run in states:
                row = {"state": key, "title": title, "width": width, "theme": theme}
                t0 = time.time()
                try:
                    row["note"] = str(run(tab, ctx) or "").strip()[:80]
                    if shots:  # first, so a page that is still changing ("running") shows what was measured
                        screenshot(tab, width, shots / f"{key}-{width}-{theme}.png")
                    row.update(measure(tab, width))
                except Skip as e:
                    row["skipped"] = str(e)
                except Exception as e:  # one broken state must not lose the rest of the run
                    row["error"] = f"{type(e).__name__}: {str(e)[:300]}"
                if ctx.pop("relogin", False):
                    tab.goto(ORIGIN + "/login", 1500)
                    sign_in(tab)
                rows.append(row)
                print(f"{key:22} {width:5} {theme:5} {time.time() - t0:5.1f}s",
                      row.get("skipped") or row.get("error") or f"axe {len(row['axe'])} h {row['height']}", flush=True)

    meta = {"commit": git("rev-parse", "--short", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "llm_mode": health.get("llm_mode"),
            "dense_retrieval": health.get("dense_retrieval"), "ledger": ctx.get("ledger"), "sample": a.sample,
            "chrome": chrome_version(), "origin": ORIGIN}
    name = a.out or meta["branch"].replace("/", "-")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / f"{name}.json").write_text(dump(meta, rows), encoding="utf-8")
    before = None
    if a.against:
        before = {(r["state"], r["width"], r["theme"]): r for r in
                  json.loads((AUDIT_DIR / f"{a.against}.json").read_text(encoding="utf-8"))["rows"]}
    (AUDIT_DIR / f"{name}.md").write_text(report(meta, rows, before, a.against), encoding="utf-8")
    print("wrote", AUDIT_DIR / f"{name}.md")


# ---------------------------------------------------------------- report

def dump(meta, rows):
    """one row per line: small, and a later run's diff shows which states moved"""
    lines = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows)
    return f'{{"meta": {json.dumps(meta, ensure_ascii=False)},\n"rows": [\n{lines}\n]}}\n'

COLS = [  # (heading, value from a row)
    ("axe", lambda r: len(r["axe"])),
    ("axe nodes", lambda r: sum(v["nodes"] for v in r["axe"])),
    ("targets <24", lambda r: r["targets"]["lt24"]),
    ("<44 (phone)", lambda r: r["targets"]["lt44"] if r["width"] < 600 else None),
    ("inline links <24", lambda r: r["targets"]["inline_lt24"]),
    ("text <14", lambda r: r["text"].get("any_lt14")),
    ("Latin <14", lambda r: r["text"]["latin_lt14"]),
    ("Bangla <16", lambda r: r["text"]["bangla_lt16"]),
    ("Bangla <14", lambda r: r["text"]["bangla_lt14"]),
    ("sideways", lambda r: "yes" if r["sideways"] else ""),
    ("height", lambda r: r["height"]),
    ("fonts KB", lambda r: round(r["bytes"]["font_decoded"] / 1024)),
    ("fonts KB wire", lambda r: round(r["bytes"]["font_wire"] / 1024)),
    ("CSS KB", lambda r: round(r["bytes"]["css_decoded"] / 1024)),
    ("CSS KB wire", lambda r: round(r["bytes"]["css_wire"] / 1024)),
]
DELTA = {"axe", "targets <24", "text <14", "Latin <14", "Bangla <16", "height", "fonts KB", "CSS KB"}


def cell(v):
    return "" if v is None else f"{v:,}" if isinstance(v, int) else str(v)


def report(meta, rows, before=None, against=None):
    out = [f"# UI audit: {meta['branch']} @ {meta['commit']}", "",
           f"`python web/scripts/check/shot.py audit-all` · {meta['date']} · llm_mode `{meta['llm_mode']}` · "
           f"dense retrieval `{meta['dense_retrieval']}` · Four Ledgers `{'on' if meta['ledger'] else 'off' if meta['ledger'] is False else '?'}` · "
           f"sample `{meta['sample']}` · {meta['chrome']} · {meta['origin']}", "",
           "Rules: `web/scripts/check/audit_js.py`. Bytes are a first visit (cache off), since the page was opened, "
           "decoded and on the wire. axe-core: WCAG 2.0/2.1/2.2 A + AA tags. \"Running\" is the photo sample paused at "
           "its salary check." +
           (f" Δ is the change from `{against}`." if before else "") + (f" Note: {meta['note']}." if meta.get("note") else ""), ""]
    heads = [h for h, _ in COLS]
    if before:
        heads = [x for h in heads for x in ((h, "Δ") if h in DELTA else (h,))]
    out += ["| state | width | theme | " + " | ".join(heads) + " |", "|---|---|---|" + "---|" * len(heads)]
    for r in rows:
        lead = f"| {r['title']} | {r['width']} | {r['theme']} | "
        if "error" in r or "skipped" in r:
            out.append(lead + ("**error**: " + r["error"] if "error" in r else "skipped: " + r["skipped"]).replace("|", "/")
                       + " |" * len(heads))
            continue
        b = before.get((r["state"], r["width"], r["theme"])) if before else None
        cells = []
        for h, f in COLS:
            v = f(r)
            cells.append(cell(v))
            if before and h in DELTA:
                try:
                    d = v - f(b) if b and "error" not in b and "skipped" not in b and v is not None else None
                except (KeyError, TypeError):
                    d = None
                cells.append("" if not d else f"{d:+,}")
        out.append(lead + " | ".join(cells) + " |")

    ok = [r for r in rows if "axe" in r]
    out += ["", "## axe violations", ""]
    by_id: dict[str, list] = {}
    for r in ok:
        for v in r["axe"]:
            by_id.setdefault(v["id"], []).append((r, v))
    if not by_id:
        out.append("None.")
    for vid, hits in sorted(by_id.items()):
        v0 = hits[0][1]
        out.append(f"- **{vid}** ({v0['impact']}): {v0['help']}. In {len(hits)} of {len(ok)} audited pages, e.g. "
                   f"`{', '.join(v0['target'][:2])}`. {v0['summary']}")
        states = sorted({r["title"] for r, _ in hits})
        out.append(f"  - states: {'; '.join(states)}")

    out += ["", "## Examples (widest light run of each state)", ""]
    widest = {}
    for r in ok:
        k = r["state"]
        if r["theme"] == rows[0]["theme"] and r["width"] >= widest.get(k, {}).get("width", 0):
            widest[k] = r
    for k, r in widest.items():
        out.append(f"### {r['title']} · {r['width']}")
        if r.get("note"):
            out.append(f"Reached: {r['note']}")
        sizes = lambda d: ", ".join(f"{s}px×{n}" for s, n in sorted(d.items(), key=lambda x: float(x[0])))
        out.append(f"- Latin sizes: {sizes(r['text']['latin_sizes']) or '–'}")
        out.append(f"- Bangla sizes: {sizes(r['text']['bangla_sizes']) or '–'}")
        out += [f"- small text: {e}" for e in r["text"]["examples"][:5]]
        out += [f"- small target: {e}" for e in r["targets"]["examples"][:5]]
        css = ", ".join(f"{n} ({round(s / 1024)} KB)" for n, s in sorted(r["bytes"]["css"], key=lambda x: -x[1]))
        fs = sorted((s for _, s in r["bytes"]["fonts"]), reverse=True)
        fonts = f"{len(fs)} files: " + ", ".join(str(round(s / 1024)) for s in fs) + " KB" if fs else ""
        out.append(f"- CSS: {css or '–'}")
        out.append(f"- fonts: {fonts or '–'}")
        out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["eval", "snap", "audit", "audit-all"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--wait", type=int, default=2500)
    ap.add_argument("--js", default=None)
    ap.add_argument("--pre", default=None, help="file of JS to run before every page script")
    ap.add_argument("--login", action="store_true", help="sign in the local test account first")
    ap.add_argument("--theme", choices=["light", "dark"], default=None)
    ap.add_argument("--print", dest="pdf", default=None, help="emulate print media and save the page as this PDF")
    ap.add_argument("--clear-cookies", action="store_true", help="start with no cookies: another device opening a link")
    ap.add_argument("--reload", action="store_true", help="after --js, reload the page in the same browser session (cookies kept)")
    ap.add_argument("--json", action="store_true", help="audit: print the full measures as JSON")
    ap.add_argument("--sample", default="migrant_text", help="audit-all: the sample behind the result and Counsel states")
    ap.add_argument("--widths", default="390,820,1440")
    ap.add_argument("--themes", default="light,dark")
    ap.add_argument("--only", default=None, help="audit-all: comma-separated state keys")
    ap.add_argument("--out", default=None, help="audit-all: report name (default: the git branch)")
    ap.add_argument("--against", default=None, help="audit-all: an earlier report name to diff against, e.g. baseline")
    ap.add_argument("--shots", default=None, help="audit-all: save a full-page screenshot of every state here")
    a = ap.parse_args()
    proc, ws_url = launch()
    try:
        with connect(ws_url, max_size=None, open_timeout=20) as ws:
            tab = Tab(ws)
            tab.call("Page.enable")
            tab.call("Runtime.enable")
            if a.cmd in ("audit", "audit-all"):
                tab.call("Network.enable")
                tab.call("Network.setCacheDisabled", cacheDisabled=True)
            if a.cmd == "eval":
                tab.goto(ORIGIN + "/", 1500)
                tab.js(LOGIN)
                print(json.dumps(tab.js(a.args[0]), ensure_ascii=False, indent=1))
                return
            if a.cmd == "audit-all":
                audit_all(tab, a)
                return
            path, width = a.args[0], int(a.args[1])
            mobile = width < 600
            set_width(tab, width, a.height)
            if a.clear_cookies:
                tab.call("Network.clearBrowserCookies")
            if a.login:
                tab.goto(ORIGIN + "/login", 1500)
                tab.js(LOGIN)
            if a.pre:
                tab.call("Page.addScriptToEvaluateOnNewDocument", source=Path(a.pre).read_text(encoding="utf-8"))
            if a.theme:
                tab.call("Page.addScriptToEvaluateOnNewDocument", source=f"try{{localStorage.setItem('jukti-theme','{a.theme}')}}catch(e){{}}")
            url = path if "://" in path else ORIGIN + path
            tab.goto(url, a.wait)
            if a.js:
                print(json.dumps(tab.js(a.js), ensure_ascii=False))
                time.sleep(1.2)
            if a.cmd == "audit":
                m = measure(tab, width)
                if a.json:
                    print(json.dumps(m, ensure_ascii=False, indent=1))
                else:
                    row = {"state": path, "title": path, "width": width, "theme": a.theme or "light", **m}
                    print("\n".join(report({"branch": "audit", "commit": git("rev-parse", "--short", "HEAD"), "date": "",
                                            "llm_mode": "", "dense_retrieval": "", "ledger": None, "sample": "", "chrome": chrome_version(),
                                            "origin": ORIGIN}, [row]).splitlines()[6:]))
                return
            out = Path(a.args[2])
            if a.reload:  # Chrome writes cookies to the profile lazily, so a reload must happen in this session
                tab.call("Page.reload")
                time.sleep(a.wait / 1000)
                print("after reload:", tab.js("location.pathname + location.search"))
            if a.pdf:
                tab.call("Emulation.setEmulatedMedia", media="print")
                time.sleep(0.5)
                pdf = tab.call("Page.printToPDF", printBackground=True, paperWidth=8.27, paperHeight=11.69, preferCSSPageSize=True)
                Path(a.pdf).write_bytes(base64.b64decode(pdf["data"]))
                print("saved", a.pdf)
            if a.full:
                h = int(tab.js("Math.ceil(document.documentElement.scrollHeight)"))
                tab.call("Emulation.setDeviceMetricsOverride", width=width, height=h, deviceScaleFactor=1, mobile=mobile)
                time.sleep(0.8)
            shot = tab.call("Page.captureScreenshot", format="png")
            out.write_bytes(base64.b64decode(shot["data"]))
            print("saved", out)
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
