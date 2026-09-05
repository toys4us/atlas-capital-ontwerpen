# -*- coding: utf-8 -*-
"""Assemble site/index.html from src/.

    python build.py            write index.html
    python build.py --list     print the sections in page order

Layout of the output:
    <head>  ... <style> base.css + sections/<id>.css (page order) </style>
    <body>  template wrapper
              <!-- section:id --> partial <!-- /section:id -->   (x11)
              the roll sections (production … access) sit inside <div class="roll">
            <script> lang.js </script><script> motion.js </script>

A partial keeps any <script> of its own inside itself. Nothing is inlined
or rewritten: partials reference assets/<file> and the output does too.
The write is atomic (temp file + os.replace) so a half-written index.html
never exists. Exit status is non-zero when a partial or its CSS is missing.
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
SEC = os.path.join(SRC, "sections")
OUT = os.path.join(HERE, "index.html")

# (order, id, inside the roll?)
SECTIONS = [
    ("01", "header",      False),
    ("02", "hero",        False),
    ("03", "production",  True),
    ("04", "founder",     True),
    ("05", "education",   True),
    ("06", "channels",    True),
    ("07", "markets",     True),
    ("08", "material",    True),
    ("09", "trackrecord", True),
    ("10", "access",      True),
    ("11", "closer",      False),
]

CSS_SLOT = "<!-- css -->"
SEC_SLOT = "<!-- sections -->"
JS_SLOT = "<!-- js -->"


def read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def html_path(num, sid):
    return os.path.join(SEC, "%s-%s.html" % (num, sid))


def css_path(sid):
    return os.path.join(SEC, "%s.css" % sid)


def check_inputs():
    missing = []
    for p in (os.path.join(SRC, "index.tpl.html"), os.path.join(SRC, "base.css"),
              os.path.join(SRC, "lang.js"), os.path.join(SRC, "motion.js")):
        if not os.path.isfile(p):
            missing.append(p)
    for num, sid, _ in SECTIONS:
        for p in (html_path(num, sid), css_path(sid)):
            if not os.path.isfile(p):
                missing.append(p)
    return missing


def build_css():
    parts = ["/* ---- base.css ---- */\n" + read(os.path.join(SRC, "base.css")).rstrip() + "\n"]
    for num, sid, _ in SECTIONS:
        parts.append("\n/* ---- section:%s ---- */\n%s\n" % (sid, read(css_path(sid)).rstrip()))
    return "<style>\n" + "".join(parts) + "</style>"


def build_sections():
    out = []
    in_roll = False
    for num, sid, roll in SECTIONS:
        if roll and not in_roll:
            out.append('<div class="roll">\n')
            in_roll = True
        if not roll and in_roll:
            out.append("</div>\n")
            in_roll = False
        body = read(html_path(num, sid)).strip("\n")
        out.append("<!-- section:%s -->\n%s\n<!-- /section:%s -->\n\n" % (sid, body, sid))
    if in_roll:
        out.append("</div>\n")
    return "".join(out).rstrip("\n") + "\n"


def build_js():
    return ("<script>\n%s\n</script>\n<script>\n%s\n</script>"
            % (read(os.path.join(SRC, "lang.js")).strip("\n"),
               read(os.path.join(SRC, "motion.js")).strip("\n")))


def build():
    tpl = read(os.path.join(SRC, "index.tpl.html"))
    for slot in (CSS_SLOT, SEC_SLOT, JS_SLOT):
        if tpl.count(slot) != 1:
            raise SystemExit("template must contain exactly one %s" % slot)
    html = (tpl.replace(CSS_SLOT, build_css())
               .replace(SEC_SLOT, build_sections())
               .replace(JS_SLOT, build_js()))
    return html


def atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(prefix=".index.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv):
    if "--list" in argv:
        for num, sid, roll in SECTIONS:
            print("%s  %-12s %s  %s" % (num, sid, "roll" if roll else "    ",
                                       os.path.relpath(html_path(num, sid), HERE)))
        return 0
    missing = check_inputs()
    if missing:
        for p in missing:
            print("missing: %s" % p, file=sys.stderr)
        return 2
    html = build()
    atomic_write(OUT, html)
    print("wrote %s (%d bytes, %d sections)" % (OUT, len(html.encode("utf-8")), len(SECTIONS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
