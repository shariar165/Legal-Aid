"""Headless Chrome over CDP: run JS in the app's origin and save screenshots (spec 20 browser checks).

  python shot.py eval "<async js expression>"
  python shot.py snap <path> <width> <out.png> [--height 900] [--full] [--wait 2500] [--js "<js before snap>"]

A persistent profile (in the system temp dir, outside the repo) keeps the session cookie between calls.
Expects the web app on :3000 and the backend on :8000. `eval` and `--login` sign in the local test account
desk-check@example.test (a fake address: create it once on /login). Needs `websockets` (in the backend .venv).
Pair with citizen_js.py to drive the Citizen page, e.g. `python shot.py eval "$(python citizen_js.py 0)"`.
"""

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = Path(tempfile.gettempdir()) / "jukti-shot-profile"
PORT = 9333
ORIGIN = "http://localhost:3000"
LOGIN = ("fetch('http://localhost:8000/api/auth/login', {method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'},"
         " body: JSON.stringify({email: 'desk-check@example.test', password: 'desk-check-pass-2026'})}).then(r => r.status)")


class Tab:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=f"(async () => {{ return {expr}; }})()", awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:800])
        return r["result"].get("value")

    def goto(self, url, wait_ms):
        self.call("Page.navigate", url=url)
        time.sleep(wait_ms / 1000)


def launch():
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
                             "--no-first-run", "--hide-scrollbars", "--force-device-scale-factor=1", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
            page = next(t for t in targets if t["type"] == "page")
            return proc, page["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit("chrome did not start")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["eval", "snap"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--wait", type=int, default=2500)
    ap.add_argument("--js", default=None)
    ap.add_argument("--pre", default=None, help="file of JS to run before every page script")
    ap.add_argument("--login", action="store_true", help="sign in the local test account first")
    a = ap.parse_args()
    proc, ws_url = launch()
    try:
        with connect(ws_url, max_size=None, open_timeout=20) as ws:
            tab = Tab(ws)
            tab.call("Page.enable")
            tab.call("Runtime.enable")
            if a.cmd == "eval":
                tab.goto(ORIGIN + "/", 1500)
                tab.js(LOGIN)
                print(json.dumps(tab.js(a.args[0]), ensure_ascii=False, indent=1))
                return
            path, width, out = a.args[0], int(a.args[1]), Path(a.args[2])
            mobile = width < 600
            tab.call("Emulation.setDeviceMetricsOverride", width=width, height=a.height, deviceScaleFactor=1, mobile=mobile)
            if a.login:
                tab.goto(ORIGIN + "/login", 1500)
                tab.js(LOGIN)
            if a.pre:
                tab.call("Page.addScriptToEvaluateOnNewDocument", source=Path(a.pre).read_text(encoding="utf-8"))
            tab.goto(ORIGIN + path, a.wait)
            if a.js:
                print(json.dumps(tab.js(a.js), ensure_ascii=False))
                time.sleep(1.2)
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
