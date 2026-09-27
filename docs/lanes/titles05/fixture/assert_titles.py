#!/usr/bin/env python3
"""The 0.5 title table (#433), asserted on a page rendered by render.sh.

    assert_titles.py <render.sh out dir> [check ...]    # exit 1 on any FAIL

Each check is the owner's ask in its positive form, so it fails on #448's
renderer as well as on a regression (NOTES.md, "Proof", shows both runs).
"""
import html, json, os, re, sys

OUT = sys.argv[1]
PAGE = open(os.path.join(OUT, "render", "index.html"), encoding="utf-8").read()
EXPECT = json.load(open(os.path.join(OUT, "synth", "expect.json")))
WORDS = ("blocked", "Playable", "soak pending", "below 30", "inputs ready", "copied", "not copied")
BENCH = ("below 30", "soak pending", "Playable")


def text(h):
    h = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", h)
    h = re.sub(r"<(br|/p|/li|/tr|/td|/th|/div|/h\d)\b[^>]*>", "\n", h)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", h)).split())


def q1():
    m = re.search(r'(?s)<section class="q" id="q1">(.*?)</section>', PAGE)
    return m.group(1) if m else ""


def rows():
    """[(row html, [(td attrs, td html)])] of every title, both tables (the folded tail too).
    A title is one <tbody> (this renderer) or one <tr> (#448 and #458's first cut)."""
    out = []
    for t in re.findall(r'(?s)<table class="tt">(.*?)</table>', q1()):
        blocks = re.findall(r"(?s)<tbody\b[^>]*>(.*?)</tbody>", t) or re.findall(r"(?s)<tr\b[^>]*>(.*?)</tr>", t)
        for r in blocks:
            tds = re.findall(r"(?s)<td\b([^>]*)>(.*?)</td>", r)
            if tds:
                out.append((r, tds))
    return out


def status_of(tds):
    """The status cell's word and html: span.sw in this renderer, else the first cell."""
    for a, h in tds:
        m = re.search(r'<span class="sw[^"]*">((?:<span[^>]*></span>)?[^<]*)</span>', h)
        if m and "c-s" in a:
            return text(m.group(1)), m.group(1)
    return (text(tds[0][1]), tds[0][1]) if tds else ("", "")


def title_of(tds):
    for a, h in tds:
        if "c-t" in a:
            m = re.search(r"(?s)<summary>(.*?)</summary>", h)
            if m:
                return html.unescape(m.group(1)).strip()
    m = re.search(r"(?s)<summary>(.*?)</summary>", tds[1][1]) if len(tds) > 1 else None
    return html.unescape(m.group(1)).strip() if m else text(tds[1][1]) if len(tds) > 1 else ""


def css():
    return "".join(re.findall(r"(?s)<style>(.*?)</style>", PAGE))


def rule(sel, media=None):
    """The declarations of `sel` (exact selector list) in the page CSS, outside or inside `media`."""
    c = css()
    if media:
        m = re.search(r"(?s)@media %s\{(.*?)\n?\}\s*(?:\n|$)" % re.escape(media), c)
        c = m.group(1) if m else ""
    else:
        c = re.sub(r"(?s)@media[^{]*\{(?:[^{}]*\{[^}]*\})*[^{}]*\}", "", c)
    m = re.search(r"(?:^|[}\s])%s\{([^}]*)\}" % re.escape(sel), c)
    return m.group(1) if m else None


def c_word():
    """every row carries exactly one status word from the scale, beside a chip, and the synthetic titles read as their stage"""
    rs = rows()
    if not rs:
        return False, "no title rows (no table.tt)"
    bad, wrong = [], []
    for r, tds in rs:
        st, sh = status_of(tds)
        hits = [w for w in WORDS if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), st)]
        if st not in WORDS or 'class="chip' not in sh or len([w for w in hits if w == st]) != 1:
            bad.append("%s: %r" % (title_of(tds), st))
        t = title_of(tds)
        if t in EXPECT and EXPECT[t] != st:
            wrong.append("%s reads %r, want %r" % (t, st, EXPECT[t]))
    seen = {title_of(tds) for _, tds in rs}
    miss = [t for t in EXPECT if t not in seen]
    ok = not bad and not wrong and not miss
    return ok, ("%d rows, one word each; the %d synthetic titles at their stages" % (len(rs), len(EXPECT)) if ok else
                "; ".join((bad[:3] + wrong[:3] + ["missing " + ", ".join(miss[:4])] if miss else bad[:3] + wrong[:3])))


def c_counts():
    """the header's Benchmarked and Playable counts equal the rows', against 145 and 50"""
    rs = rows()
    words = [status_of(tds)[0] for _, tds in rs]
    nb, npl = sum(w in BENCH for w in words), sum(w == "Playable" for w in words)
    t = text(q1())
    mb = re.search(r"Benchmarked (\d+) / (\d+)", t)
    mp = re.search(r"Playable (\d+) / (\d+)", t)
    if not rs or not mb or not mp:
        return False, "no rows or no 'Benchmarked N / 145' and 'Playable M / 50' header"
    got = (int(mb.group(1)), int(mb.group(2)), int(mp.group(1)), int(mp.group(2)))
    want = (nb, 145, npl, 50)
    return got == want and nb >= 3 and npl >= 1, "header %s, rows %s" % (got, want)


EM = 0.58          # an average glyph width in em for a sans face, lowercase-heavy; generous


def wrap(words, width_px, px):
    """Greedy word wrap: the lines a string takes in a column (a word never breaks)."""
    per = max(1, int(width_px // (EM * px)))
    lines, cur = 1, 0
    for w in words.split():
        if cur and cur + 1 + len(w) > per:
            lines, cur = lines + 1, len(w)
        else:
            cur = cur + 1 + len(w) if cur else len(w)
    return lines


def c_lines():
    """fixed columns: at 360 px (and so at 400) no title and no next step wraps past two lines in its own column, and short tokens never wrap"""
    rs = rows()
    if not rs:
        return False, "no title rows"
    tt = rule("table.tt") or ""
    ws, wp = rule("table.tt col.w-s") or "", rule("table.tt col.w-p") or ""
    ms, mp = re.search(r"width:(\d+)px", ws), re.search(r"width:(\d+)px", wp)
    if "table-layout:fixed" not in tt or not ms or not mp or '<col class="w-s">' not in q1():
        return False, "no fixed layout: table.tt needs table-layout:fixed and a colgroup with pixel widths"
    main = 24                                   # main{padding:10px 12px}
    pad = 8                                     # a cell's 4 px each side
    out = {}
    for vw in (360, 400):
        full = vw - main
        # the title spans the row; the next step sits between the status column and the four marks
        out[vw] = (full - pad, full - int(ms.group(1)) - 4 * int(mp.group(1)) - pad)
    bad = []
    for r, tds in rs:
        t = title_of(tds)
        nxm = re.search(r'(?s)<span class="nx[^"]*">(.*?)</span>', r)
        if not nxm:
            bad.append(t + ": no next-step span")
            continue
        nx = html.unescape(nxm.group(1))
        for vw, (tw, nw) in out.items():
            if wrap(t, tw, 13) > 2:
                bad.append("%s: title is %d lines at %d px" % (t, wrap(t, tw, 13), vw))
            if wrap(nx, nw, 13) > 2:
                bad.append("%s: next step %r is %d lines at %d px" % (t, nx, wrap(nx, nw, 13), vw))
        st, _ = status_of(tds)
        if not re.search(r'<span class="sw nw">', r):
            bad.append(t + ": the status word can wrap")
        if len(st) * EM * 13 + 13 > int(ms.group(1)) - pad + 8:
            bad.append("%s: %r does not fit its column" % (t, st))
        f = [h for a, h in tds if "c-s" in a]
        if not f or not re.search(r'class="ln', f[0]):
            bad.append(t + ": the fps figures can wrap")
        if re.search(r"<details\b[^>]*\bopen\b", r):
            bad.append(t + ": detail open by default")
    return not bad, ("%d titles; title and next step at most two lines at 360 and 400 px" % len(rs) if not bad else "; ".join(bad[:4]))


def c_nocut():
    """nothing in the 0.5 section is shortened: no text-overflow:ellipsis on its tables, no ellipsis glyph, every title and next step in full"""
    c = css()
    cut = [m for m in re.findall(r"([^{}]*)\{([^}]*)\}", c) if "ellipsis" in m[1] and re.search(r"\.tt|\.lv|\.goal|\.legend|#q1", m[0])]
    if cut:
        return False, "ellipsis rule: %s" % cut[0][0].strip()
    body = q1()
    if "\u2026" in html.unescape(body) or "&hellip;" in body:
        return False, "an ellipsis glyph in the 0.5 section"
    rs = rows()
    if not rs:
        return False, "no title rows"
    st = json.load(open(os.path.join(OUT, "render", "status.json")))
    want = ((st.get("first") or {}).get("titles") or {}).get("rows") or []
    summ = [html.unescape(x) for x in re.findall(r"(?s)<summary>(.*?)</summary>", body)]
    nxs = [html.unescape(x) for x in re.findall(r'(?s)<span class="nx[^"]*">(.*?)</span>', body)]
    miss = [x["title"] for x in want if x["title"] not in summ] + [n for n in EXPECT if n not in summ]
    short = ["%s: %r" % (x["title"], x["next"]) for x in want if x["next"] not in nxs]
    ok = not miss and not short and len(want) == len(rs)
    return ok, ("%d titles and next steps in full" % len(want) if ok else
                "; ".join(["title not in full: " + m for m in miss[:3]] + ["next step not in full: " + m for m in short[:3]]) or
                "%d rows in status.json, %d on the page" % (len(want), len(rs)))


def c_pipe():
    """the pipeline is four labelled mini-columns (Copied, Inputs, Save, Bench) of ticks and dashes, with a legend; a one-route title counts as inputs ready"""
    heads = [text(h) for h in re.findall(r'(?s)<th class="v"[^>]*>(.*?)</th>', q1())]
    if heads[:4] != ["Copied", "Inputs", "Save", "Bench"]:
        return False, "headers %r" % heads[:4]
    if not re.search(r'<p class="legend">Pipeline: Copied, Inputs, Save, Bench\.', q1()):
        return False, "no legend above the table"
    bad = []
    marks = {}
    for r, tds in rows():
        m = [text(h) for a, h in tds if "c-m" in a]
        marks[title_of(tds)] = m
        if len(m) != 4 or not all(x in ("\u2713", "\u2013", "\u00bd", "n/a") for x in m):
            bad.append("%s: %r" % (title_of(tds), m))
    if 'class="pm"' in q1():
        bad.append("letter codes (span.pm) still on the page")
    one = marks.get("Zz Purple Single Route")
    if one != ["\u00bd", "\u2713", "n/a", "\u2013"]:
        bad.append("the one-route title reads %r, want half, tick, n/a, dash" % (one,))
    fr = marks.get("Zz Blue First Run: Tom Clancy's Rainbow Six 3 Black Arrow")
    if fr != ["\u00bd", "\u2713", "\u2013", "\u2013"]:
        bad.append("the first-run-only title reads %r, want half, tick, dash, dash" % (fr,))
    return not bad, ("%d rows, four marks each" % len(marks) if not bad else "; ".join(bad[:4]))


def c_target():
    """the target line says 145 and 50 and carries no date"""
    m = re.search(r'(?s)<p class="target">(.*?)</p>', q1())
    if not m:
        return False, "no target line"
    t = text(m.group(1))
    date = re.search(r"\d{4}-\d{2}-\d{2}|\b\d{1,2}-\d{2}\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d", t)
    ok = "145" in t and "50" in t and not date
    return ok, repr(t[:120])


def c_nodate():
    """'~2026-09-28' appears nowhere on the page"""
    return "~2026-09-28" not in PAGE, "absent" if "~2026-09-28" not in PAGE else "present"


def c_fold():
    """the 'not copied' tail folds after 10 rows, with its count"""
    m = re.search(r'(?s)<details class="more"><summary>(\d+) more not copied</summary>(.*?)</table></div></details>', q1())
    if not m:
        return False, "no folded tail"
    tag = "tbody" if "<tbody class=" in q1() else "tr"     # one title per tbody here, per tr before
    inner = len(re.findall(r'<%s class="st-' % tag, m.group(2)))
    shown = len(re.findall(r'<%s class="st-none"' % tag, q1())) - inner
    return int(m.group(1)) == inner == 2 and shown == 10, "%s folded (%d rows), %d shown" % (m.group(1), inner, shown)


def c_order():
    """red first, then green, orange, yellow, purple, blue, grey"""
    order = ["blocked", "Playable", "soak pending", "below 30", "inputs ready", "copied", "not copied"]
    ws = [status_of(tds)[0] for _, tds in rows()]
    idx = [order.index(w) for w in ws if w in order]
    if not idx:
        return False, "no title rows"
    return idx == sorted(idx), "in order" if idx == sorted(idx) else "out of order"


def c_forecast():
    """the header forecasts from the last 48 h rate, and says 'Ships when both are met'"""
    t = text(q1())
    m = re.search(r"Ships when both are met\. At the last 48 h rate: (about \d{4}-\d{2}-\d{2}|no rate yet[^.]*)\.", t)
    return bool(m), m.group(0) if m else "no forecast line"


def c_flight():
    """an issue shows its state and what is in flight; an open issue with nothing reads 'nothing in flight' and is an alarm"""
    q1t = text(q1())
    q3 = re.search(r'(?s)<section class="q" id="q3">(.*?)</section>', PAGE)
    ok = ("#413 open" in q1t or "#413 board" in q1t) and "lane.doa413b" in q1t and "#9901 open · nothing in flight" in q1t \
        and q3 and "#9901 (Zz Grey 01) is open with nothing in flight" in text(q3.group(1))
    return bool(ok), "issues, lanes and the alarm present" if ok else "missing an issue state, its lane, or the alarm"


def c_watch():
    """Q4 carries the watchdog's word, since, the last hour, and a stale watchdog is an alarm for lane.local"""
    q4 = re.search(r'(?s)<section class="q" id="q4">(.*?)</section>', PAGE)
    q3 = re.search(r'(?s)<section class="q" id="q3">(.*?)</section>', PAGE)
    t4 = text(q4.group(1)) if q4 else ""
    ok = ("watchdog: hands-on since 16:13 (held-idle)" in t4 and
          "last hour: 8 running, 40 hands-on, 12 waste (idle-waiting + held-idle + overdue)" in t4 and
          "last hour: 50 running, 0 hands-on, 6 waste" in t4 and
          q3 and re.search(r"lane\.local\s*the device watchdog is stale", text(q3.group(1))))
    return bool(ok), "present" if ok else "watchdog lines or alarm missing"


CHECKS = {"word": c_word, "counts": c_counts, "lines": c_lines, "nocut": c_nocut, "pipe": c_pipe, "target": c_target, "nodate": c_nodate,
          "fold": c_fold, "order": c_order, "forecast": c_forecast, "flight": c_flight, "watch": c_watch}

if __name__ == "__main__":
    want = sys.argv[2:] or list(CHECKS)
    fails = 0
    for k in want:
        try:
            ok, why = CHECKS[k]()
        except Exception as e:
            ok, why = False, "error: %r" % e
        fails += not ok
        print("%s %-8s %s -- %s" % ("PASS" if ok else "FAIL", k, CHECKS[k].__doc__.split("\n")[0], why))
    sys.exit(1 if fails else 0)
