# -*- coding: utf-8 -*-
"""The truth gate for site/index.html.

    python tools/gate.py            run everything; exit 0 only if ALL pass
    python tools/gate.py --json     also print a JSON summary (last line)
    python tools/gate.py --static   skip the browser checks (quick, partial)
    python tools/gate.py --file X   gate another built page instead of index.html

Every failure is printed on its own line, prefixed by the section it lives in
(header, hero, production, ... closer), or "page" for things that belong to
the document as a whole. Sections are found through the build markers
<!-- section:id --> ... <!-- /section:id --> and, in CSS, the comment
/* ---- section:id ---- */ that build.py writes.

What is checked
  static  the hard rules of qa100.py (no invented numbers, no guarantees,
          no member/review counts, no scarcity or countdowns, MONEY needs
          the three DISCLOSURE lines), title carries "Atlas Capital",
          the Discord invite at least three times, TikTok present, the
          risk line, the external-resource allowlist, and the reveal contract:
          opacity:0 / visibility:hidden outside @keyframes only on selectors
          that contain ".reveal" and sit under a ".js" ancestor.
  browser bilingual at 1440 and 390 (the toggle swaps, no NL visible in EN
          and vice versa, no horizontal overflow > 2px in either language), and
          VISIBILITY: 1500ms after load the hero's first heading/logo is on
          screen; after scrolling to the bottom in 600px steps (150ms waits)
          no .reveal is left below 0.9 opacity and no element with text is at
          opacity 0 unless it sits inside a closed <dialog>.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
INDEX = os.path.join(SITE, "index.html")

SECTION_IDS = ["header", "hero", "production", "founder", "education", "channels",
               "markets", "material", "trackrecord", "access", "closer"]

DISCORD = "https://discord.gg/78Ff2GuSfW"
TIKTOK = "tiktok.com/@atlascapitalbv"

RESOURCE_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com",
                  "cdnjs.cloudflare.com", "cdn.jsdelivr.net")
LINK_HOSTS = ("discord.gg", "discord.com", "tiktok.com", "www.w3.org")

STYLE_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
KEYFRAMES_RE = re.compile(r"@(?:-webkit-)?keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", re.S | re.I)
ENTITY_RE = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
MARK_RE = re.compile(r"<!-- section:([a-z]+) -->(.*?)<!-- /section:\1 -->", re.S)
CSS_MARK_RE = re.compile(r"/\* ---- section:([a-z]+) ---- \*/")

# --- text-level bans (verbatim from qa100.py) ------------------------------
HARD_TEXT = [
    (re.compile(r"\d+([.,]\d+)?\s*%"),                     "percentage in text"),
    (re.compile(r"\b\d+\s*R\b"),                           "R multiple"),
    (re.compile(r"\b\d[\d.,]*\s*(pips?|ticks?|punten)\b", re.I), "pips/points figure"),
    (re.compile(r"\bwin\s*rate\b", re.I),                  "win rate"),
    (re.compile(r"winstpercentage|slagingspercentage|rendement\s*van", re.I), "performance claim"),
    (re.compile(r"gegarandeer|garantie op winst|verzekerd van winst", re.I), "guarantee"),
    (re.compile(r"\b\d[\d.,]*\s*(leden|members|traders)\b", re.I), "member count"),
    (re.compile(r"\b\d[\d.,]*\s*(reviews|beoordelingen|sterren)\b", re.I), "review count"),
    (re.compile(r"nog\s+\d+\s+(plekken|plaatsen|spots)", re.I), "fake scarcity"),
    (re.compile(r"aftelklok|countdown|verloopt\s+over", re.I), "countdown"),
    (re.compile(r"\bper\s+maand\b|\bp/m\b|\bmaandelijks\s+€", re.I), "price framing"),
]
SOFT_TEXT = [
    (re.compile(r"\b\d{1,3}[.,]\d{3}\b"),   "thousand-separated number"),
    (re.compile(r"\b\d{5,}\b"),             "long number"),
]
# Money on the page is not itself the problem -- the rule was always "no
# INVENTED numbers", and a regex cannot tell a fabricated figure from one read
# off a certificate that carries a verification code. What it can enforce is
# that the framing which makes a real figure honest travels with it: whose
# results these are, that payouts are gross, and that the past is not a
# forecast. A page showing money without all three fails.
MONEY = [
    (re.compile(r"[€$£]\s*\d"),                                 "currency amount"),
    (re.compile(r"\d[\d.,]*\s*(euro|dollar|usd|eur)\b", re.I),  "currency amount"),
]
DISCLOSURE = [
    (re.compile(r"resultaten van .{0,14}handelaar|one trader's results", re.I),
     "attribution to one named trader"),
    (re.compile(r"zijn bruto|are gross", re.I),
     "payouts stated gross of fees"),
    (re.compile(r"verleden bieden geen garantie|past results are no guarantee", re.I),
     "past-performance disclaimer"),
]


class Report(object):
    def __init__(self):
        self.fail = []
        self.warn = []
        self.checks = {}

    def f(self, section, msg):
        self.fail.append((section, msg))

    def w(self, section, msg):
        self.warn.append((section, msg))


# ---------------------------------------------------------------- helpers ---
def strip_keyframes(css):
    prev = None
    while prev != css:
        prev = css
        css = KEYFRAMES_RE.sub(" ", css)
    return css


def text_of(src):
    s = STYLE_RE.sub(" ", src)
    s = SCRIPT_RE.sub(" ", s)
    s = TAG_RE.sub(" ", s)
    s = ENTITY_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s)


def sections_of(src):
    """[(id, start, end, chunk)] in document order."""
    out = []
    for m in MARK_RE.finditer(src):
        out.append((m.group(1), m.start(), m.end(), m.group(2)))
    return out


def section_at(secs, pos):
    for sid, a, b, _ in secs:
        if a <= pos < b:
            return sid
    return "page"


def host_of(url):
    try:
        return url.split("/")[2].lower()
    except IndexError:
        return ""


def allowed(host, hosts):
    return any(host == h or host.endswith("." + h) for h in hosts)


def iter_rules(css):
    """Yield (selector, declarations, [enclosing at-rules]) for every block
    that carries declarations, walking into @media and friends."""
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    css = strip_keyframes(css)
    stack, buf = [], []
    for ch in css:
        if ch == "{":
            stack.append("".join(buf).strip())
            buf = []
        elif ch == "}":
            sel = stack.pop() if stack else ""
            decl = "".join(buf)
            if decl.strip() and not sel.startswith("@"):
                yield sel, decl, list(stack)
            buf = []
        else:
            buf.append(ch)


# ------------------------------------------------------------ static gate ---
def static_checks(rep):
    if not os.path.isfile(INDEX):
        rep.f("page", "index.html missing -- run build.py first")
        return None
    raw = io.open(INDEX, "rb").read()
    src = raw.decode("utf-8", "replace")
    low = src.lower()
    secs = sections_of(src)
    found = [s[0] for s in secs]
    for sid in SECTION_IDS:
        if sid not in found:
            rep.f("page", "section marker missing: %s" % sid)
    if found != [s for s in SECTION_IDS if s in found]:
        rep.f("page", "sections out of order: %s" % ", ".join(found))
    for sid in found:
        # the root element must carry id="<sid>" (closer: section#closer + footer)
        chunk = [s for s in secs if s[0] == sid][0][3]
        if not re.search(r'<(header|section)\b[^>]*\bid="%s"' % sid, chunk):
            rep.f(sid, 'section root lacks id="%s"' % sid)

    if len(raw) < 9000:
        rep.f("page", "only %d bytes" % len(raw))
    if "<!doctype html" not in low:
        rep.f("page", "no doctype")
    if 'lang="nl"' not in low[:400]:
        rep.f("page", "html not lang=nl")
    if 'name="viewport"' not in low and "name='viewport'" not in low:
        rep.f("page", "no viewport meta")

    m = re.search(r"<title>(.*?)</title>", src, re.S | re.I)
    if not m:
        rep.f("page", "no title")
    elif "atlas capital" not in m.group(1).lower():
        rep.f("page", "title missing 'Atlas Capital': %r" % m.group(1)[:60])

    n_cta = src.count("discord.gg/78Ff2GuSfW")
    if DISCORD not in src:
        rep.f("page", "discord invite missing or wrong (need %s)" % DISCORD)
    if n_cta < 3:
        rep.f("page", "discord invite only %d times (need >= 3)" % n_cta)
    if TIKTOK not in src:
        rep.f("page", "tiktok link missing (%s)" % TIKTOK)
    rep.checks["discord_links"] = n_cta

    # --- external resources ------------------------------------------------
    for mm in re.finditer(r"<(link|script|img|source|iframe|video|audio|embed|object)\b[^>]*>", src, re.I):
        tag = mm.group(1).lower()
        attrs = mm.group(0)
        sid = section_at(secs, mm.start())
        for am in re.finditer(r"""\b(src|href|srcset|data)\s*=\s*["']([^"']*)""", attrs, re.I):
            val = am.group(2).strip()
            if re.match(r"https?://", val, re.I):
                h = host_of(val)
                if not allowed(h, RESOURCE_HOSTS):
                    rep.f(sid, "external resource not on allowlist: <%s> %s" % (tag, h))
            elif val.startswith("//"):
                rep.f(sid, "protocol-relative resource: <%s> %s" % (tag, val[:50]))
            elif val.startswith("data:") or val.startswith("#") or val == "":
                pass
            elif tag == "img" or tag == "source" or tag == "video" or tag == "audio":
                if not re.match(r"assets/[A-Za-z0-9_./-]+$", val):
                    rep.f(sid, "<%s> src must be assets/<file> or data:, got %s" % (tag, val[:50]))
        if tag == "img" and not re.search(r"\bsrc\s*=", attrs, re.I):
            rep.f(sid, "<img> with no src")
    for mm in re.finditer(r"<a\b[^>]*\bhref\s*=\s*[\"'](https?://[^\"']+)", src, re.I):
        h = host_of(mm.group(1))
        if not allowed(h, LINK_HOSTS):
            rep.f(section_at(secs, mm.start()), "external link to %s" % h)

    # --- CSS ---------------------------------------------------------------
    styles = list(STYLE_RE.finditer(src))
    css_all = " ".join(s.group(1) for s in styles)
    for um in re.finditer(r"""url\(\s*["']?([^"')]+)""", css_all, re.I):
        v = um.group(1).strip()
        if v.startswith("data:") or v.startswith("#"):
            continue
        if re.match(r"https?://", v, re.I):
            if not allowed(host_of(v), RESOURCE_HOSTS):
                rep.f("page", "css url() to %s" % host_of(v))
        elif not re.match(r"assets/[A-Za-z0-9_./-]+$", v):
            rep.f("page", "css url() must be assets/<file>: %s" % v[:50])
    for im in re.finditer(r"@import\b[^;]*;", css_all, re.I):
        rep.f("page", "css @import: %s" % im.group(0)[:60])

    # reveal contract: opacity:0 / visibility:hidden outside @keyframes only
    # on selectors carrying .reveal, under a .js ancestor
    for sm in styles:
        css = sm.group(1)
        pieces = CSS_MARK_RE.split(css)          # [base, id, css, id, css ...]
        labelled = [("base", pieces[0])]
        for i in range(1, len(pieces), 2):
            labelled.append((pieces[i], pieces[i + 1]))
        for label, chunk in labelled:
            for sel, decl, ctx in iter_rules(chunk):
                bad = []
                if re.search(r"opacity\s*:\s*0(?![.\d%])", decl, re.I):
                    bad.append("opacity:0")
                if re.search(r"visibility\s*:\s*hidden", decl, re.I):
                    bad.append("visibility:hidden")
                if not bad:
                    continue
                for one in sel.split(","):
                    one = one.strip()
                    if ".reveal" not in one or not re.search(r"\.js(?![\w-]).*\.reveal", one):
                        rep.f(label, "%s on '%s' -- only allowed on .reveal under a .js ancestor"
                              % ("/".join(bad), one[:60]))
        if re.search(r"position\s*:\s*fixed", strip_keyframes(css), re.I):
            rep.w("page", "position:fixed in CSS")
    for mm in re.finditer(r"""style\s*=\s*["'][^"']*(opacity\s*:\s*0(?![.\d%])|visibility\s*:\s*hidden)""", src, re.I):
        rep.f(section_at(secs, mm.start()), "inline %s" % mm.group(1))

    # --- risk line ---------------------------------------------------------
    if "geen financieel advies" not in low:
        rep.f("page", "risk line missing ('geen financieel advies')")

    # --- text rules, per section so the failure names its section ----------
    page_txt = text_of(src)
    money_hits = []
    for sid, a, b, chunk in secs:
        txt = text_of(chunk)
        for pat, label in HARD_TEXT:
            mm = pat.search(txt)
            if mm:
                rep.f(sid, "%s: %r" % (label, mm.group(0)[:40]))
        for pat, _ in MONEY:
            mm = pat.search(txt)
            if mm:
                money_hits.append((sid, mm.group(0)))
                break
    rep.checks["money_sections"] = sorted(set(s for s, _ in money_hits))
    if money_hits:
        for pat, label in DISCLOSURE:
            if not pat.search(page_txt):
                sid, hit = money_hits[0]
                rep.f(sid, "money (%r) on the page without %s" % (hit[:20], label))
    if not money_hits:
        for pat, label in SOFT_TEXT:
            mm = pat.search(page_txt)
            if mm:
                rep.w("page", "%s: %r" % (label, mm.group(0)[:40]))
    # anything in the template outside the sections gets the plain rules too
    outside = MARK_RE.sub(" ", src)
    for pat, label in HARD_TEXT:
        mm = pat.search(text_of(outside))
        if mm:
            rep.f("page", "%s outside sections: %r" % (label, mm.group(0)[:40]))
    return src


# ----------------------------------------------------------- browser gate ---
PROBE_LANG = """(sel) => {
  const de = document.documentElement, vw = window.innerWidth;
  const vis = [];
  document.querySelectorAll('[lang="nl"],[lang="en"]').forEach(el => {
    if (el.offsetParent !== null || el.getClientRects().length) vis.push(el.lang);
  });
  const secOf = el => { const s = el.closest(sel); return s ? (s.tagName === 'FOOTER' ? 'closer' : s.id) : 'page'; };
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : '');
  // The page clips itself (.page{overflow:hidden}) so scrollWidth cannot grow;
  // what matters is content that ends up outside the viewport. Measure every
  // element that carries text or is an image, plus every text run, and skip
  // decoration (aria-hidden, no text, pointer-events:none).
  let worst = null, worstR = vw, worstL = 0;
  document.querySelectorAll('body *').forEach(el => {
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return;
    if (el.closest('[aria-hidden="true"]')) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.pointerEvents === 'none') return;
    const isMedia = /^(IMG|VIDEO|CANVAS|PICTURE|SVG)$/.test(el.tagName);
    if (!isMedia && !(el.textContent && el.textContent.trim())) return;
    const d = el.closest('dialog'); if (d && !d.open) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.right > worstR + 0.5) { worstR = r.right; worst = el; }
    if (r.left < worstL - 0.5) { worstL = r.left; worst = el; }
  });
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    if (!n.nodeValue.trim()) continue;
    const p = n.parentElement; if (!p || p.tagName === 'SCRIPT' || p.tagName === 'STYLE') continue;
    if (p.closest('[aria-hidden="true"]')) continue;
    const d = p.closest('dialog'); if (d && !d.open) continue;
    const cs = getComputedStyle(p);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const rg = document.createRange(); rg.selectNodeContents(n);
    const r = rg.getBoundingClientRect();
    if (r.width === 0) continue;
    if (r.right > worstR + 0.5) { worstR = r.right; worst = p; }
    if (r.left < worstL - 0.5) { worstL = r.left; worst = p; }
  }
  // the paired pattern: <span lang="nl">..</span><span lang="en">..</span>
  const unpaired = [];
  document.querySelectorAll('[lang="nl"]').forEach(el => {
    if (el === de) return;
    const nx = el.nextElementSibling;
    if (!nx || nx.getAttribute('lang') !== 'en') unpaired.push({section: secOf(el), msg: 'NL run without an EN twin right after it: ' + name(el) + ' "' + el.textContent.trim().slice(0,40) + '"'});
  });
  document.querySelectorAll('[lang="en"]').forEach(el => {
    if (el === de) return;
    const pv = el.previousElementSibling;
    if (!pv || pv.getAttribute('lang') !== 'nl') unpaired.push({section: secOf(el), msg: 'EN run without an NL twin right before it: ' + name(el) + ' "' + el.textContent.trim().slice(0,40) + '"'});
  });
  return {
    lang: de.getAttribute('data-lang'),
    over: Math.max(de.scrollWidth - vw, Math.round(worstR - vw), Math.round(-worstL)),
    overWhere: worst ? secOf(worst) + ' ' + name(worst) : '',
    nlVisible: vis.filter(x => x === 'nl').length,
    enVisible: vis.filter(x => x === 'en').length,
    pairs: document.querySelectorAll('[lang="nl"]').length,
    unpaired: unpaired.slice(0, 20),
    toggle: document.querySelectorAll('.langsw button').length,
    text: (document.body.innerText || '').replace(/\\s+/g,' ').trim().length
  };
}"""

SWITCH = """(l) => {
  const b = document.querySelector('.langsw button[data-lang="' + l + '"]');
  if (b) b.click(); else document.documentElement.setAttribute('data-lang', l);
}"""

SECTION_SEL = ",".join("#" + s for s in SECTION_IDS) + ",footer"

PROBE_HERO = """() => {
  const hero = document.querySelector('#hero');
  if (!hero) return {ok:false, why:'no #hero'};
  const el = hero.querySelector('h1, h2, .filmtitle, img, svg');
  if (!el) return {ok:false, why:'no heading or logo inside #hero'};
  const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
  const vh = window.innerHeight, vw = window.innerWidth;
  const on = r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw;
  return {ok: on && parseFloat(cs.opacity) >= 0.9 && cs.visibility !== 'hidden',
          why: !on ? 'off screen' : 'opacity ' + cs.opacity + ' visibility ' + cs.visibility,
          tag: el.tagName + (el.className ? '.' + String(el.className).split(' ')[0] : '')};
}"""

PROBE_STUCK = """(sel) => {
  const out = [];
  const closedDialog = el => { const d = el.closest('dialog'); return d && !d.open; };
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : '');
  const sec = el => { const s = el.closest(sel); return s ? (s.tagName === 'FOOTER' ? 'closer' : s.id) : 'page'; };
  document.querySelectorAll('.reveal').forEach(el => {
    if (closedDialog(el)) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none') return;
    if (parseFloat(cs.opacity) < 0.9)
      out.push({section: sec(el), msg: '.reveal ended at opacity ' + cs.opacity + ': ' + name(el)});
  });
  document.querySelectorAll('body *').forEach(el => {
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return;
    if (!el.textContent || !el.textContent.trim()) return;
    if (closedDialog(el)) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none') return;
    if (parseFloat(cs.opacity) === 0 || cs.visibility === 'hidden')
      out.push({section: sec(el), msg: 'text stuck invisible (opacity ' + cs.opacity + ', visibility ' + cs.visibility + '): ' + name(el)});
  });
  return out.slice(0, 40);
}"""


def browser_checks(rep):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        rep.f("page", "playwright not installed -- browser checks cannot run")
        return
    url = "file:///" + INDEX.replace("\\", "/")
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for tag, w, h in (("1440", 1440, 900), ("390", 390, 844)):
            ctx = br.new_context(viewport={"width": w, "height": h})
            ctx.add_init_script("try{localStorage.removeItem('atlas.lang')}catch(e){}")
            pg = ctx.new_page()
            errors = []
            pg.on("pageerror", lambda x: errors.append(str(x)[:160]))
            pg.on("console", lambda m: errors.append(m.text[:160]) if m.type == "error" else None)
            try:
                pg.goto(url, wait_until="load", timeout=30000)
            except Exception as ex:
                rep.f("page", "%s: page failed to load: %s" % (tag, str(ex)[:100]))
                ctx.close()
                continue

            # ---- bilingual -------------------------------------------------
            pg.wait_for_timeout(400)
            nl = pg.evaluate(PROBE_LANG, SECTION_SEL)
            for u in nl["unpaired"]:
                rep.f(u["section"], "%s: %s" % (tag, u["msg"]))
            if nl["toggle"] != 2:
                rep.f("header", "%s: %d language buttons (need 2)" % (tag, nl["toggle"]))
            if nl["lang"] != "nl":
                rep.f("page", "%s: opens in %r, not nl" % (tag, nl["lang"]))
            if nl["enVisible"]:
                rep.f("page", "%s: %d EN runs visible in NL" % (tag, nl["enVisible"]))
            if not nl["nlVisible"]:
                rep.f("page", "%s: no NL text visible" % tag)
            if nl["over"] > 2:
                rep.f(nl["overWhere"].split(" ")[0] or "page",
                      "%s NL: horizontal overflow %dpx (%s)" % (tag, nl["over"], nl["overWhere"]))
            pg.evaluate(SWITCH, "en")
            pg.wait_for_timeout(250)
            en = pg.evaluate(PROBE_LANG, SECTION_SEL)
            if en["nlVisible"]:
                rep.f("page", "%s: %d NL runs visible in EN" % (tag, en["nlVisible"]))
            if not en["enVisible"]:
                rep.f("header", "%s: toggle did not switch to EN" % tag)
            if en["over"] > 2:
                rep.f(en["overWhere"].split(" ")[0] or "page",
                      "%s EN: horizontal overflow %dpx (%s)" % (tag, en["over"], en["overWhere"]))
            if tag == "1440" and en["text"] < 300:
                rep.f("page", "EN text only %d chars" % en["text"])
            rep.checks["lang_%s" % tag] = {"nl_pairs": nl["pairs"], "over_nl": nl["over"], "over_en": en["over"]}

            # ---- visibility, in both languages ------------------------------
            for lang in ("nl", "en"):
                pg.goto("about:blank")
                ctx.add_init_script("try{localStorage.setItem('atlas.lang','%s')}catch(e){}" % lang)
                pg.goto(url, wait_until="load", timeout=30000)
                pg.wait_for_timeout(1500)
                hero = pg.evaluate(PROBE_HERO)
                if not hero.get("ok"):
                    rep.f("hero", "%s %s: hero heading/logo not visible 1.5s after load (%s)"
                          % (tag, lang, hero.get("why")))
                # the page may grow while it is scrolled (lazy images, revealed
                # blocks), so the end is re-measured every step, not read once
                y = 0
                guard = 0
                while True:
                    total = pg.evaluate("() => document.documentElement.scrollHeight")
                    if y >= total or guard > 400:
                        break
                    y = min(y + 600, total)
                    pg.evaluate("y => window.scrollTo(0, y)", y)
                    pg.wait_for_timeout(150)
                    guard += 1
                pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
                pg.wait_for_timeout(900)   # let the last transition finish
                stuck = pg.evaluate(PROBE_STUCK, SECTION_SEL)
                for s in stuck:
                    rep.f(s["section"], "%s %s: %s" % (tag, lang, s["msg"]))
                # the init script is additive; reset the stored choice for the next lap
                pg.evaluate("() => { try { localStorage.removeItem('atlas.lang') } catch(e){} }")
            if errors:
                rep.f("page", "%s: console/page errors: %s" % (tag, errors[:2]))
            ctx.close()
        br.close()


# --------------------------------------------------------------------- main ---
def main(argv):
    global INDEX
    want_json = "--json" in argv
    static_only = "--static" in argv
    if "--file" in argv:
        INDEX = os.path.abspath(argv[argv.index("--file") + 1])
    rep = Report()
    src = static_checks(rep)
    if src is not None and not static_only:
        browser_checks(rep)

    for sid, msg in rep.warn:
        print("%s: note: %s" % (sid, msg))
    for sid, msg in rep.fail:
        print("%s: %s" % (sid, msg))
    ok = not rep.fail
    print("GATE %s  (%d failures, %d notes%s)" % ("PASS" if ok else "FAIL", len(rep.fail), len(rep.warn),
                                                  ", static only" if static_only else ""))
    if want_json:
        by = {}
        for sid, msg in rep.fail:
            by.setdefault(sid, []).append(msg)
        print(json.dumps({"pass": ok, "static_only": static_only,
                          "failures": [{"section": s, "msg": m} for s, m in rep.fail],
                          "by_section": by,
                          "notes": [{"section": s, "msg": m} for s, m in rep.warn],
                          "checks": rep.checks}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
