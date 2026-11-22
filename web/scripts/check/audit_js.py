"""In-page measures for `shot.py audit` (spec 29 step 0.1): tap targets, small text, sideways scroll, page height.

AXE_RUN runs axe-core (injected first by shot.py) with the WCAG 2.2 AA tags. METRICS returns everything else.
Rules, so later steps compare like with like:
- a tap target is a visible a[href], button, input, select, textarea, summary, [role=button|tab|link|checkbox|radio]
  or [tabindex="0"], measured by its border box; "small" means its width or its height is under the limit
  (24 px, WCAG 2.2 SC 2.5.8; 44 px on phones). A link inside a sentence is counted apart, since 2.5.8 exempts it.
- a text node is visible text; its size is the parent's computed font-size. Bangla (U+0980–U+09FF) is flagged
  under 16 px, Latin text (a-z, no Bangla) under 14 px; any_lt14 counts every text node under 14 px. Screen-reader-only text (a 1 px box) is left out.
"""

AXE_RUN = """(async () => {
  const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']},
                                    resultTypes: ['violations']});
  return r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
                                 target: v.nodes.slice(0, 3).map(n => n.target.join(' ')),
                                 summary: (v.nodes[0]?.failureSummary || '').split('\\n').slice(0, 2).join(' ').slice(0, 200)}));
})()"""

METRICS = r"""((WIDTH) => {
  const shown = (el) => el.checkVisibility({opacityProperty: true, visibilityProperty: true});
  const label = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) return s + '#' + el.id;
    const c = [...el.classList].find(x => !/^__/.test(x));
    // the CSS-module name without its hash: "etrp1G_cardHead" (build) or "desk-module__x__lawCell" (dev) -> the last part
    if (c) s += '.' + (c.includes('__') ? c.split('__').pop() : c.slice(c.indexOf('_', 1) + 1));
    return s;
  };
  const snippet = (t) => t.replace(/\s+/g, ' ').trim().slice(0, 40);
  const phone = WIDTH < 600;  // the emulated width: innerWidth grows when a phone page scrolls sideways

  const TARGET = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=link], [role=checkbox], [role=radio], [tabindex="0"]';
  const targets = {lt24: 0, lt44: 0, inline_lt24: 0, examples: []};
  for (const el of document.querySelectorAll(TARGET)) {
    if (!shown(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const small = Math.min(r.width, r.height);
    const inline = el.tagName === 'A' && getComputedStyle(el).display === 'inline'
      && (el.parentElement?.textContent.trim().length || 0) > el.textContent.trim().length + 15;
    if (small < 24) {
      if (inline) targets.inline_lt24++;
      else {
        targets.lt24++;
        if (targets.examples.length < 8) targets.examples.push(`${label(el)} ${Math.round(r.width)}×${Math.round(r.height)} "${snippet(el.textContent || el.getAttribute('aria-label') || '')}"`);
      }
    }
    if (phone && small < 44 && !inline) targets.lt44++;
  }

  const BN = /[ঀ-৿]/, LATIN = /[A-Za-z]/;
  const text = {any_lt14: 0, latin: 0, latin_lt14: 0, bangla: 0, bangla_lt16: 0, bangla_lt14: 0, latin_sizes: {}, bangla_sizes: {}, examples: []};
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Map();
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const t = n.textContent;
    if (!t.trim()) continue;
    const el = n.parentElement;
    if (!el || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(el.tagName)) continue;
    let ok = seen.get(el);
    if (ok === undefined) {
      const r = el.getBoundingClientRect();
      ok = shown(el) && r.width > 1 && r.height > 1;
      seen.set(el, ok);
    }
    if (!ok) continue;
    const px = Math.round(parseFloat(getComputedStyle(el).fontSize) * 100) / 100;
    if (px < 14) text.any_lt14++;  // every script, numbers and symbols too
    if (BN.test(t)) {
      text.bangla++;
      text.bangla_sizes[px] = (text.bangla_sizes[px] || 0) + 1;
      if (px < 16) text.bangla_lt16++;
      if (px < 14) text.bangla_lt14++;
      if (px < 16 && text.examples.length < 10) text.examples.push(`bn ${px}px ${label(el)} "${snippet(t)}"`);
    } else if (LATIN.test(t)) {
      text.latin++;
      text.latin_sizes[px] = (text.latin_sizes[px] || 0) + 1;
      if (px < 14) {
        text.latin_lt14++;
        if (text.examples.length < 10) text.examples.push(`en ${px}px ${label(el)} "${snippet(t)}"`);
      }
    }
  }

  const doc = document.documentElement;
  return {
    url: location.pathname + location.search,
    width: WIDTH, inner_width: innerWidth,
    height: Math.ceil(doc.scrollHeight),
    sideways: doc.scrollWidth > doc.clientWidth + 1,
    scroll_width: doc.scrollWidth,
    targets, text,
  };
})(%d)"""


def metrics(width: int) -> str:
    return METRICS % width
