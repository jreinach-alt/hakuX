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
    """[(row html, [(td attrs, td html)])] of every title row, both tables (the folded tail too)."""
    out = []
    for t in re.findall(r'(?s)<table class="tt">(.*?)</table>', q1()):
        for r in re.findall(r"(?s)<tr\b[^>]*>(.*?)</tr>", t):
            tds = re.findall(r"(?s)<td\b([^>]*)>(.*?)</td>", r)
            if tds:
                out.append((r, tds))
    return out


def title_of(tds):
    m = re.search(r"(?s)<summary>(.*?)</summary>", tds[1][1]) if len(tds) > 1 else None
    return html.unescape(m.group(1)).strip() if m else text(tds[1][1]) if len(tds) > 1 else ""


def c_word():
    """every row carries exactly one status word from the scale, beside a chip, and the synthetic titles read as their stage"""
    rs = rows()
    if not rs:
        return False, "no title rows (no table.tt)"
    bad, wrong = [], []
    for r, tds in rs:
        st = text(tds[0][1])
        hits = [w for w in WORDS if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), st)]
        if st not in WORDS or 'class="chip' not in tds[0][1] or len([w for w in hits if w == st]) != 1:
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
    words = [text(tds[0][1]) for _, tds in rs]
    nb, npl = sum(w in BENCH for w in words), sum(w == "Playable" for w in words)
    t = text(q1())
    mb = re.search(r"Benchmarked (\d+) / (\d+)", t)
    mp = re.search(r"Playable (\d+) / (\d+)", t)
    if not rs or not mb or not mp:
        return False, "no rows or no 'Benchmarked N / 145' and 'Playable M / 50' header"
    got = (int(mb.group(1)), int(mb.group(2)), int(mp.group(1)), int(mp.group(2)))
    want = (nb, 145, npl, 50)
    return got == want and nb >= 3 and npl >= 1, "header %s, rows %s" % (got, want)


def c_lines():
    """no title renders as more than two lines at 400 px: every cell is on line 1 or 2, and a phone keeps each on one line"""
    rs = rows()
    if not rs:
        return False, "no title rows"
    css = "".join(re.findall(r"(?s)@media \(max-width:640px\)\{(.*?)\n\}", PAGE))
    rule = re.search(r"table\.tt td\.l1,table\.tt td\.l2\{([^}]*)\}", css)
    need = ("white-space:nowrap", "overflow:hidden", "text-overflow:ellipsis")
    if not rule or not all(n in rule.group(1) for n in need):
        return False, "no phone rule holding td.l1/td.l2 to one line each"
    if "table.tt .sub{display:none}" not in css or not re.search(r"table\.tt tr\{display:grid", css):
        return False, "the phone layout is not a two-row grid with the small lines hidden"
    bad = []
    for r, tds in rs:
        cls = [re.search(r'class="([^"]*)"', a) for a, _ in tds]
        lines = {c.group(1).split()[0] for c in cls if c}
        if len(cls) != len(tds) or not all(c and c.group(1).split()[0] in ("l1", "l2") for c in cls) or not lines <= {"l1", "l2"}:
            bad.append(title_of(tds) + ": a cell on no line")
            continue
        for a, h in tds:
            outside = re.sub(r"(?s)<details\b.*?</details>", "", h)
            outside = re.sub(r'(?s)<span class="sub">.*?</span>', "", outside)
            if re.search(r"<(br|p|div|ul|ol|table)\b", outside):
                bad.append(title_of(tds) + ": a block element outside the tap-to-open detail")
                break
        if re.search(r"<details\b[^>]*\bopen\b", r):
            bad.append(title_of(tds) + ": detail open by default")
    return not bad, ("%d rows, each two lines" % len(rs) if not bad else "; ".join(bad[:4]))


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
    inner = len(re.findall(r"<tr class=", m.group(2)))
    shown = len(re.findall(r'<tr class="st-none"', q1())) - inner
    return int(m.group(1)) == inner == 2 and shown == 10, "%s folded (%d rows), %d shown" % (m.group(1), inner, shown)


def c_order():
    """red first, then green, orange, yellow, purple, blue, grey"""
    order = ["blocked", "Playable", "soak pending", "below 30", "inputs ready", "copied", "not copied"]
    ws = [text(tds[0][1]) for _, tds in rows()]
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


CHECKS = {"word": c_word, "counts": c_counts, "lines": c_lines, "target": c_target, "nodate": c_nodate,
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
