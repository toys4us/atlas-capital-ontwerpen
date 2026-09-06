# -*- coding: utf-8 -*-
"""The whole page, as motion and as two full sheets.

    python tools/pagemotion.py --out <dir> [--lang nl]

Writes into <dir>:
    motion.png      how the top of the page arrives: six 1440x900 frames
                    captured while scrolling from the top through the first
                    three viewports in five equal steps, 180ms apart, tiled
                    2 across x 3 down at 50%. Shot from a cold page, before
                    anything else is measured, so the frames show the reveal
                    sequence the way a visitor gets it.
    full-desk.png   the whole page at 1440
    full-mob.png    the whole page at 390, deviceScaleFactor 2

For every capture: document.fonts.ready is awaited, loading="lazy" is
switched off, and every <img> is decoded, so nothing below the fold is
missing or half-drawn. The full sheets are taken after one scroll pass, so
every .reveal has had its turn and the page is shown finished.

Prints the files written; exit status is non-zero if index.html is missing.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
INDEX = os.path.join(SITE, "index.html")

DESK = (1440, 900, 1)
MOB = (390, 844, 2)

FRAMES = 6          # 6 frames = 5 steps
VIEWPORTS = 3       # the frames span the first three viewports
GAP = 180           # ms between frames
TILE = 0.5          # the sheet is tiled at half size

PREP = """async () => {
  document.querySelectorAll('img[loading]').forEach(i => { i.loading = 'eager'; });
  try { await document.fonts.ready; } catch (e) {}
  await Promise.all([...document.querySelectorAll('img')].map(i => i.decode().catch(() => {})));
  return true;
}"""


def open_page(browser, width, height, dsf, lang):
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              device_scale_factor=dsf)
    ctx.add_init_script("try{localStorage.setItem('atlas.lang','%s')}catch(e){}" % lang)
    pg = ctx.new_page()
    pg.goto("file:///" + INDEX.replace("\\", "/"), wait_until="load", timeout=60000)
    pg.evaluate(PREP)
    return ctx, pg


def settle(pg):
    """One pass down the page so every .reveal has been seen, then back to
    the top: a full sheet must show the finished state, not a page caught
    mid-arrival."""
    y = 0
    while True:
        total = pg.evaluate("() => document.documentElement.scrollHeight")
        if y >= total:
            break
        y = min(y + 600, total)
        pg.evaluate("y => window.scrollTo(0, y)", y)
        pg.wait_for_timeout(70)
    pg.wait_for_timeout(900)
    pg.evaluate("() => window.scrollTo(0, 0)")
    pg.wait_for_timeout(200)


def motion_sheet(pg, vh, out_dir):
    """Six viewport frames down the first three viewports, tiled 2x3."""
    from PIL import Image
    maxy = max(0, pg.evaluate("() => document.documentElement.scrollHeight") - vh)
    end = min(vh * (VIEWPORTS - 1), maxy)
    pg.evaluate("() => window.scrollTo(0, 0)")
    pg.wait_for_timeout(120)
    frames = []
    for i in range(FRAMES):
        pg.evaluate("y => window.scrollTo(0, y)", end * i / float(FRAMES - 1))
        pg.wait_for_timeout(GAP)
        p = os.path.join(out_dir, "_frame%d.png" % i)
        pg.screenshot(path=p)
        frames.append(p)
    ims = [Image.open(p).convert("RGB") for p in frames]
    w, h = ims[0].size
    tw, th = int(w * TILE), int(h * TILE)
    sheet = Image.new("RGB", (tw * 2 + 8, th * 3 + 16), (8, 9, 11))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((tw, th), Image.LANCZOS),
                    ((i % 2) * (tw + 8), (i // 2) * (th + 8)))
    for im in ims:
        im.close()
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
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="nl", choices=("nl", "en"))
    a = ap.parse_args(argv)
    if not os.path.isfile(INDEX):
        print("no index.html -- run build.py first", file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)
    from playwright.sync_api import sync_playwright
    written = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()

        w, h, dsf = DESK
        ctx, pg = open_page(br, w, h, dsf, a.lang)
        written.append(motion_sheet(pg, h, a.out))     # cold page first
        settle(pg)
        p = os.path.join(a.out, "full-desk.png")
        pg.screenshot(path=p, full_page=True)
        written.append(p)
        ctx.close()

        w, h, dsf = MOB
        ctx, pg = open_page(br, w, h, dsf, a.lang)
        settle(pg)
        p = os.path.join(a.out, "full-mob.png")
        pg.screenshot(path=p, full_page=True)
        written.append(p)
        ctx.close()

        br.close()
    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
