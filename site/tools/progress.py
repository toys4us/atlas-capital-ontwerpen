# -*- coding: utf-8 -*-
"""Render atlas-designs/progress.html from _progress/*.json.

    python tools/progress.py

One row per piece: title, wave, round, last result (WIN / LOSS / GATE FAIL),
scores ours vs ref, wowed?, the biggest gap the judge named, updated-at, and
the latest thumbnail _progress/<id>.webp when there is one (linked to the full
png next to it). Dark, plain HTML+CSS, no external resources, refreshes itself
every 45 seconds.

Piece JSON (written by the orchestrator):
  {"id","title","wave","round","status","history":[...],
   optional: "last":{"result","ours","ref","wowed","gap","at"},
             "updated_at","thumb","shot"}
When "last" is missing the newest history entry is used, and each of its
fields is read leniently (result/outcome, ours/score, ref/ref_score,
wowed, gap/biggest_gap, at/time/updated_at).
"""
import glob
import html
import io
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
PROG = os.path.join(ROOT, "_progress")
OUT = os.path.join(ROOT, "progress.html")
LIVE = "https://toys4us.github.io/atlas-capital-ontwerpen/site/"

ORDER = ["header", "hero", "founder", "education", "channels",
         "markets", "material", "trackrecord", "access", "closer"]


def pick(d, *keys, default=""):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def load():
    pieces = []
    for p in sorted(glob.glob(os.path.join(PROG, "*.json"))):
        try:
            with io.open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as ex:
            d = {"id": os.path.splitext(os.path.basename(p))[0], "title": "(unreadable json)",
                 "status": "error", "history": [], "_err": str(ex)}
        d.setdefault("id", os.path.splitext(os.path.basename(p))[0])
        pieces.append(d)
    pieces.sort(key=lambda d: (ORDER.index(d["id"]) if d["id"] in ORDER else 99, d["id"]))
    return pieces


def last_of(d):
    last = d.get("last")
    if not isinstance(last, dict):
        hist = d.get("history") or []
        last = hist[-1] if hist and isinstance(hist[-1], dict) else {}
    return last


def fmt_time(v):
    if not v:
        return ""
    if isinstance(v, (int, float)):
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(v))
    return str(v)


def result_class(r):
    r = (r or "").upper()
    if "GATE" in r:
        return "gate"
    if r.startswith("WIN"):
        return "win"
    if r.startswith("LOSS") or r.startswith("LOSE"):
        return "loss"
    return "none"


def render(pieces):
    counts = {"queued": 0, "building": 0, "winning": 0, "wowed": 0}
    rows = []
    for d in pieces:
        st = str(d.get("status", "")).lower()
        last = last_of(d)
        result = str(pick(last, "result", "outcome", default=""))
        wowed = bool(pick(last, "wowed", default=False)) or bool(d.get("wowed"))
        if st in counts:
            counts[st] += 1
        elif st in ("won", "win"):
            counts["winning"] += 1
        if wowed:
            counts["wowed"] += 1
        ours = pick(last, "ours", "score", "our_score", default="")
        ref = pick(last, "ref", "ref_score", "reference", default="")
        gap = pick(last, "gap", "biggest_gap", "judge_gap", default="")
        at = fmt_time(pick(last, "at", "time", "updated_at", default=d.get("updated_at", "")))
        thumb = os.path.join(PROG, d["id"] + ".webp")
        full = os.path.join(PROG, d["id"] + ".png")
        if os.path.isfile(thumb):
            src = "_progress/%s.webp?%d" % (d["id"], int(os.path.getmtime(thumb)))
            href = "_progress/%s.png" % d["id"] if os.path.isfile(full) else src
            img = '<a href="%s"><img src="%s" alt="%s"></a>' % (
                html.escape(href), html.escape(src), html.escape(d["id"]))
        else:
            img = '<span class="nothumb">no shot yet</span>'
        rows.append(
            '<tr class="st-%s">'
            '<td class="t"><b>%s</b><br><code>%s</code></td>'
            '<td>%s</td><td>%s</td>'
            '<td><span class="res %s">%s</span><br><small>%s</small></td>'
            '<td class="n">%s <span class="vs">vs</span> %s</td>'
            '<td class="wow">%s</td>'
            '<td class="gap">%s</td>'
            '<td class="at">%s</td>'
            '<td class="th">%s</td></tr>' % (
                html.escape(st or "none"),
                html.escape(str(d.get("title", d["id"]))), html.escape(d["id"]),
                html.escape(str(d.get("wave", ""))), html.escape(str(d.get("round", ""))),
                result_class(result), html.escape(result or "—"), html.escape(st),
                html.escape(str(ours) or "—"), html.escape(str(ref) or "—"),
                "yes" if wowed else "—",
                html.escape(str(gap)) or "—",
                html.escape(at) or "—",
                img))
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="45">
<title>Atlas Capital — progress</title>
<style>
  :root{color-scheme:dark}
  body{margin:0;background:#08090B;color:#D9D7D2;font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  header{padding:22px 28px 14px;border-bottom:1px solid rgba(215,179,100,.25)}
  h1{margin:0 0 6px;font-size:18px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:#F4F2EC}
  header a{color:#D7B364}
  .counts{display:flex;gap:26px;margin-top:10px;flex-wrap:wrap}
  .counts div{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#A5A6A8}
  .counts b{display:block;font-size:24px;font-weight:400;color:#F4F2EC;letter-spacing:0}
  .counts .wowed b{color:#D7B364}
  main{padding:14px 28px 40px;overflow-x:auto}
  table{border-collapse:collapse;width:100%;min-width:980px}
  th{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#7B7C80;text-align:left;padding:8px 10px;border-bottom:1px solid #26272B}
  td{padding:12px 10px;border-bottom:1px solid #1B1C20;vertical-align:top}
  td.t b{color:#F4F2EC;font-weight:500}
  code{font-size:11px;color:#7B7C80}
  .res{display:inline-block;padding:2px 9px;border:1px solid #26272B;font-size:11px;letter-spacing:.12em;text-transform:uppercase}
  .res.win{border-color:#65C79C;color:#65C79C}
  .res.loss{border-color:#8A8B90;color:#A5A6A8}
  .res.gate{border-color:#C9584D;color:#E4877D}
  .res.none{color:#5E5F64}
  td small{color:#5E5F64;font-size:11px;letter-spacing:.1em;text-transform:uppercase}
  td.n{white-space:nowrap;color:#F4F2EC}
  .vs{color:#5E5F64;font-size:11px}
  td.wow{color:#D7B364}
  td.gap{max-width:340px;color:#B2B0AC}
  td.at{white-space:nowrap;color:#7B7C80;font-size:12px}
  td.th img{display:block;max-width:320px;height:auto;border:1px solid rgba(215,179,100,.25);background:#15161A}
  .nothumb{color:#5E5F64;font-size:11px;letter-spacing:.1em;text-transform:uppercase}
  tr.st-building td.t b{color:#D7B364}
  footer{padding:0 28px 30px;color:#5E5F64;font-size:12px}
</style>
</head>
<body>
<header>
  <h1>Atlas Capital — progress</h1>
  <a href="@LIVE@">@LIVE@</a>
  <div class="counts">
    <div class="queued"><b>@Q@</b>queued</div>
    <div class="building"><b>@B@</b>building</div>
    <div class="winning"><b>@W@</b>winning</div>
    <div class="wowed"><b>@X@</b>wowed</div>
    <div><b>@N@</b>pieces</div>
  </div>
</header>
<main>
<table>
<thead><tr><th>Piece</th><th>Wave</th><th>Round</th><th>Last result</th><th>Ours vs ref</th><th>Wowed</th><th>Biggest gap (judge)</th><th>Updated</th><th>Latest shot</th></tr></thead>
<tbody>
@ROWS@
</tbody>
</table>
</main>
<footer>rendered @NOW@ · refreshes every 45s</footer>
</body>
</html>
"""
    reps = {"@LIVE@": LIVE, "@Q@": str(counts["queued"]), "@B@": str(counts["building"]),
            "@W@": str(counts["winning"]), "@X@": str(counts["wowed"]), "@N@": str(len(pieces)),
            "@ROWS@": "\n".join(rows) if rows else '<tr><td colspan="9">no pieces in _progress/</td></tr>',
            "@NOW@": now}
    for k, v in reps.items():
        page = page.replace(k, v)
    return page


def main():
    pieces = load()
    out = render(pieces)
    fd, tmp = tempfile.mkstemp(prefix=".progress.", suffix=".tmp", dir=ROOT)
    with io.open(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    os.replace(tmp, OUT)
    print("wrote %s (%d pieces)" % (OUT, len(pieces)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
