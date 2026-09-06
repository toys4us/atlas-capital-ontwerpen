# -*- coding: utf-8 -*-
"""Screenshots of one section of site/index.html, for judging.

    python tools/shot.py --section <id> --out <dir> [--full] [--lang en]

Writes into <dir>:
    desk.png               1440-wide clip of the section (height capped 2600)
    mob.png                390-wide clip at deviceScaleFactor 2 (capped 5000)
    motion.png             6 frames tiled 2x3 at 50%, captured while the section
                           scrolls into view: from one viewport above it to its
                           top in 5 steps, 180ms apart -- this is how the reveal
                           animation is judged
    hero only:             desk-fold.png / mob-fold.png  (the viewport at the top)
    header only:           desk-nav.png (1440x200 top strip), desk-nav-scrolled.png
                           (same strip after a 900px scroll), mob-nav.png
    --full adds            full-desk.png / full-mob.png

Waits for document.fonts.ready and for every <img> to decode; lazy loading is
switched off first so nothing below the fold is missing from a clip.
Prints the list of files written.
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
INDEX = os.path.join(SITE, "index.html")

SECTION_IDS = ["header", "hero", "founder", "education", "channels",
               "markets", "material", "trackrecord", "access", "closer"]

DESK = (1440, 900, 1)
MOB = (390, 844, 2)
CAP_DESK = 2600
CAP_MOB = 5000

PREP = """async () => {
  document.querySelectorAll('img[loading]').forEach(i => { i.loading = 'eager'; });
  try { await document.fonts.ready; } catch (e) {}
  await Promise.all([...document.querySelectorAll('img')].map(i => i.decode().catch(() => {})));
  return true;
}"""

# Document-space box of a section. closer = section#closer through the footer.
BOX = """(id) => {
  const y = window.scrollY, x = window.scrollX;
  const first = document.getElementById(id);
  if (!first) return null;
  let last = first;
  if (id === 'closer') { const f = document.querySelector('footer'); if (f) last = f; }
  const a = first.getBoundingClientRect(), b = last.getBoundingClientRect();
  const top = Math.floor(Math.min(a.top, b.top) + y), bottom = Math.ceil(Math.max(a.bottom, b.bottom) + y);
  return {top, bottom, height: bottom - top,
          docHeight: document.documentElement.scrollHeight};
}"""


def open_page(pw_browser, width, height, dsf, lang):
    ctx = pw_browser.new_context(viewport={"width": width, "height": height},
                                 device_scale_factor=dsf)
    ctx.add_init_script("try{localStorage.setItem('atlas.lang','%s')}catch(e){}" % lang)
    pg = ctx.new_page()
    pg.goto("file:///" + INDEX.replace("\\", "/"), wait_until="load", timeout=60000)
    pg.evaluate(PREP)
    pg.wait_for_timeout(250)
    return ctx, pg


def clip_shot(pg, path, top, height, width):
    """A clip in document coordinates: Playwright's full_page capture is
    taken beyond the viewport, so the sticky header stays where the document
    starts and nothing overlays the section."""
    pg.evaluate("() => window.scrollTo(0, 0)")
    pg.wait_for_timeout(100)
    pg.screenshot(path=path, full_page=True,
                  clip={"x": 0, "y": top, "width": width, "height": height})


def settle_reveals(pg):
    """Scroll through once so every .reveal has had its chance to come in, then
    back to the top -- the section clips must show the finished state."""
    total = pg.evaluate("() => document.documentElement.scrollHeight")
    y = 0
    while y < total:
        y = min(y + 600, total)
        pg.evaluate("y => window.scrollTo(0, y)", y)
        pg.wait_for_timeout(60)
    pg.wait_for_timeout(900)
    pg.evaluate("() => window.scrollTo(0, 0)")
    pg.wait_for_timeout(150)


def motion_frames(pg, box, vh, out_dir, tmp_prefix):
    """Six viewport frames while the section scrolls into view."""
    from PIL import Image
    start = max(0, box["top"] - vh)
    end = box["top"]
    maxy = max(0, box["docHeight"] - vh)
    end = min(end, maxy)
    frames = []
    # a fresh lap: the reveal state is whatever the page has right now, so go
    # to the start position first and give the observer a moment
    pg.evaluate("y => window.scrollTo(0, y)", start)
    pg.wait_for_timeout(120)
    for i in range(6):
        y = start + (end - start) * i / 5.0
        pg.evaluate("y => window.scrollTo(0, y)", y)
        pg.wait_for_timeout(180)
        p = os.path.join(out_dir, "%s-frame%d.png" % (tmp_prefix, i))
        pg.screenshot(path=p)
        frames.append(p)
    ims = [Image.open(p).convert("RGB") for p in frames]
    w, h = ims[0].size
    tw, th = w // 2, h // 2
    sheet = Image.new("RGB", (tw * 2 + 8, th * 3 + 16), (8, 9, 11))
    for i, im in enumerate(ims):
        im = im.resize((tw, th), Image.LANCZOS)
        cx, cy = i % 2, i // 2
        sheet.paste(im, (cx * (tw + 8), cy * (th + 8)))
    out = os.path.join(out_dir, "motion.png")
    sheet.save(out)
    for p in frames:
        try:
            os.unlink(p)
        except OSError:
            pass
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", required=True, choices=SECTION_IDS)
    ap.add_argument("--out", required=True)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--lang", default="nl", choices=("nl", "en"))
    a = ap.parse_args(argv)
    if not os.path.isfile(INDEX):
        print("no index.html -- run build.py first", file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)
    from playwright.sync_api import sync_playwright
    written = []
    sid = a.section
    with sync_playwright() as pw:
        br = pw.chromium.launch()

        # ---------------- desktop ----------------
        w, h, dsf = DESK
        ctx, pg = open_page(br, w, h, dsf, a.lang)
        box = pg.evaluate(BOX, sid)
        if not box:
            print("section root #%s not found in the page" % sid, file=sys.stderr)
            return 2
        # motion first, from a cold page: the reveal state has not been touched
        written.append(motion_frames(pg, box, h, a.out, "desk"))
        if sid == "hero":
            pg.evaluate("() => window.scrollTo(0, 0)")
            pg.wait_for_timeout(1500)
            p = os.path.join(a.out, "desk-fold.png"); pg.screenshot(path=p); written.append(p)
        if sid == "header":
            pg.evaluate("() => window.scrollTo(0, 0)")
            pg.wait_for_timeout(300)
            p = os.path.join(a.out, "desk-nav.png")
            pg.screenshot(path=p, clip={"x": 0, "y": 0, "width": w, "height": 200}); written.append(p)
            pg.evaluate("() => window.scrollTo(0, 900)")
            pg.wait_for_timeout(400)
            p = os.path.join(a.out, "desk-nav-scrolled.png")
            pg.screenshot(path=p, clip={"x": 0, "y": 0, "width": w, "height": 200}); written.append(p)
        settle_reveals(pg)
        box = pg.evaluate(BOX, sid)
        p = os.path.join(a.out, "desk.png")
        clip_shot(pg, p, box["top"], min(box["height"], CAP_DESK), w); written.append(p)
        if a.full:
            p = os.path.join(a.out, "full-desk.png")
            pg.evaluate("() => window.scrollTo(0, 0)")
            pg.screenshot(path=p, full_page=True); written.append(p)
        ctx.close()

        # ---------------- mobile ----------------
        w, h, dsf = MOB
        ctx, pg = open_page(br, w, h, dsf, a.lang)
        box = pg.evaluate(BOX, sid)
        if sid == "hero":
            pg.wait_for_timeout(1500)
            p = os.path.join(a.out, "mob-fold.png"); pg.screenshot(path=p); written.append(p)
        if sid == "header":
            pg.wait_for_timeout(300)
            p = os.path.join(a.out, "mob-nav.png")
            pg.screenshot(path=p, clip={"x": 0, "y": 0, "width": w, "height": 120}); written.append(p)
        settle_reveals(pg)
        box = pg.evaluate(BOX, sid)
        p = os.path.join(a.out, "mob.png")
        clip_shot(pg, p, box["top"], min(box["height"], CAP_MOB), w); written.append(p)
        if a.full:
            p = os.path.join(a.out, "full-mob.png")
            pg.evaluate("() => window.scrollTo(0, 0)")
            pg.screenshot(path=p, full_page=True); written.append(p)
        ctx.close()
        br.close()

    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
