"""JS snippets that drive Citizen to its result screen (it is one page, no route per result)."""
import sys

WAIT = "const until = async (f, t = 30000) => { const t0 = Date.now(); while (Date.now() - t0 < t) { const v = f(); if (v) return v; await new Promise(r => setTimeout(r, 200)); } throw new Error('timeout'); };"
# Citizen draws inside a fixed phone frame with its own scroll: this lets the page grow to its full height
GROW = "const st = document.createElement('style'); st.textContent = '[class$=_app]{height:auto!important;margin:0 auto!important;border-radius:0!important} [class$=_screen],[class$=_resultScroll]{overflow:visible!important}'; document.head.appendChild(st);"
CLICK_TEXT = "const clickText = async (txt) => { const b = await until(() => [...document.querySelectorAll('button')].find(x => !x.disabled && x.textContent.includes(txt))); b.click(); return b; };"

def to_result(sample_index: int, lang: str = "bn", full: bool = True) -> str:
    lang_js = "await clickText('EN');" if lang == "en" else ""
    see = "See result" if lang == "en" else "ফলাফল দেখুন"
    grow = GROW if full else ""
    return f"""(async () => {{ {WAIT} {CLICK_TEXT}
      {lang_js}
      const btns = await until(() => {{ const l = [...document.querySelectorAll('button')].filter(b => b.className.includes('sampleBtn')); return l.length ? l : null; }});
      btns[{sample_index}].click();
      const ocrYes = '{"Yes, correct" if lang == "en" else "হ্যাঁ, ঠিক আছে"}';
      await until(() => {{ const y = [...document.querySelectorAll('button')].find(x => !x.disabled && x.textContent.includes(ocrYes)); if (y) y.click(); return [...document.querySelectorAll('button')].find(x => !x.disabled && x.textContent.includes('{see}')); }}, 60000);
      await clickText('{see}');
      await until(() => document.querySelector('[class*=resultScroll]'));
      await new Promise(r => setTimeout(r, 600));
      {grow}
      return document.querySelector('h2')?.textContent;
    }})()"""


FILL = """
  const setVal = (el, v) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); };
  const radio = (name, value) => document.querySelector(`input[name="${name}"][value="${value}"]`).click();
"""

def form(submit: bool) -> str:
    """open the step, answer: told RM 1,800, no deductions, employer pays the ticket, the worker keeps the passport"""
    body = """await clickText('উত্তর দিন');
      const amt = await until(() => document.getElementById('ps-salary'));
      setVal(amt, '1800');
      radio('ps-noDed', 'yes'); radio('ps-ticket', 'employer'); radio('ps-passport', 'worker');
      await new Promise(r => setTimeout(r, 300));"""
    if submit:
        body += """
      await clickText('চুক্তির সঙ্গে মেলান');
      await until(() => [...document.querySelectorAll('button')].find(x => x.textContent.includes('উত্তর বদলান')), 30000);
      await new Promise(r => setTimeout(r, 500));"""
    body += """
      document.getElementById('title-promise').scrollIntoView({block: 'start'});
      return [...document.querySelectorAll('[class$=_gap]')].map(li => li.innerText.split(String.fromCharCode(10)).join(' | '));"""
    return f"(async () => {{ {WAIT} {CLICK_TEXT} {FILL} {body} }})()"

if __name__ == "__main__":
    lang = sys.argv[2] if len(sys.argv) > 2 else "bn"
    full = (sys.argv[3] if len(sys.argv) > 3 else "full") == "full"
    js = to_result(int(sys.argv[1]), lang, full)
    if len(sys.argv) > 4:
        js = f"{js}.then(() => {form(sys.argv[4] == 'submit')})"
    print(js)
