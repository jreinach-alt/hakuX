#!/usr/bin/env python3
"""Assert on the words and marks of a page render.sh rendered.

    assert_measured.py <out dir> <check>     prints PASS/FAIL and a reason; exit 0 on PASS

checks: glance, order, bar, chart, json, copied
"""
import html, json, os, re, sys

OUT, CHECK = sys.argv[1:3]
page = open(os.path.join(OUT, "render", "index.html"), encoding="utf-8").read()
want = json.load(open(os.path.join(OUT, "synth", "measured.json")))
N = len(want)


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")


def glance():
    m = re.search(r'<div class="glance">(.*?)</div>', page, re.S)
    return text(m.group(1)) if m else ""


def c_glance():
    """the at-a-glance line leads 0.5 with Measured N / 145, N the fixture's titles with any fps reading"""
    g = glance()
    m = re.search(r"0\.5\s*:\s*Measured (\d+) / (\d+) · Benchmarked (\d+) / (\d+) · Playable (\d+) / (\d+)", g)
    if not m:
        return False, "no '0.5: Measured N / 145 · Benchmarked M / 145 · Playable K / 50' in: %s" % g[:200]
    got = int(m.group(1)), int(m.group(2))
    return got == (N, 145) and N >= 12, "Measured %s, want (%d, 145); titles %s" % (got, N, want)


def c_order():
    """Measured >= Benchmarked >= Playable, and the soak-only title lifts Measured above Benchmarked"""
    m = re.search(r"Measured (\d+) / \d+ · Benchmarked (\d+) / \d+ · Playable (\d+) / \d+", glance())
    if not m:
        return False, "no counts"
    a, b, c = (int(x) for x in m.groups())
    return a >= b >= c and a > b, "%d, %d, %d" % (a, b, c)


def c_bar():
    """How close: a Measured N / 145 bar, first, above Benchmarked and Playable"""
    q = page[page.find('id="q1"'):page.find('id="q2"')]
    labels = re.findall(r'<span class="gl">(\w+) <b>(\d+)</b> / (\d+)</span>', q)
    return [l[0] for l in labels] == ["Measured", "Benchmarked", "Playable"] and labels[0][1:] == (str(N), "145"), str(labels)


def c_chart():
    """the chart is inline SVG in How close, below the bars; its Measured series ends at N; lines differ by dash"""
    q = page[page.find('id="q1"'):page.find('id="q2"')]
    s = q.find('<svg class="chart"')
    if s < 0 or s < q.rfind('class="goal"'):
        return False, "no <svg class=\"chart\"> under the bars"
    svg = q[s:q.find("</svg>", s)]
    ends = dict(re.findall(r'data-series="(\w+)" data-end="(\d+)"', svg))
    dashes = re.findall(r'data-series="\w+" data-end="\d+" style="[^"]*?(stroke-dasharray:[\d ]+)?"', svg)
    ok = (ends.get("measured") == str(N) and set(ends) == {"measured", "benchmarked", "playable"}
          and "Measured %d" % N in text(svg) and "target 145" in text(svg) and "50 Playable" in text(svg)
          and len(set(dashes)) == 3 and "http" not in svg.replace("http://www.w3.org", ""))
    return ok, "ends %s, dashes %s" % (ends, dashes)


def c_json():
    """status.json carries the three series, Measured ending at N"""
    j = json.load(open(os.path.join(OUT, "render", "status.json"), encoding="utf-8"))
    se = (((j.get("first") or {}).get("titles") or {}).get("series")) or {}
    ms = se.get("measured") or []
    return bool(ms) and ms[-1][1] == N and set(se) == {"measured", "benchmarked", "playable"}, "measured %s" % ms[-3:]


def copied_cells():
    """{title: (stage, Copied mark, Copied hover)} for every table row."""
    rows = {}
    for m in re.finditer(r'<tbody class="st-(\w+)"><tr class="a"><td class="c-t" colspan="6">(.*?)</td></tr>(.*?)</tbody>', page, re.S):
        c = re.search(r'<td class="c-m[^"]*" title="Copied: ([^"]*)">([^<]*)</td>', m.group(3))
        s = re.search(r"<summary>(.*?)</summary>", m.group(2), re.S)
        t = text(s.group(1) if s else m.group(2)).strip()
        rows[t] = (m.group(1), html.unescape(c.group(2)) if c else None, html.unescape(c.group(1)) if c else None)
    return rows


def c_copied():
    """one handheld is enough: a title on one handheld is a tick naming that handheld and is not
    'not copied'; no half mark in the Copied column; no 'copied to both handhelds' anywhere"""
    rows = copied_cells()
    bad = []
    one = {t: r for t, r in rows.items() if r[2] and re.fullmatch(r"on the (Thor|Nova)", r[2])}
    if not one:
        bad.append("no row whose Copied hover names exactly one handheld")
    for t, (st, mark, say) in one.items():
        if mark != "✓" or st == "none":
            bad.append("%s: %s %r (%s)" % (t, st, mark, say))
    halves = [t for t, r in rows.items() if r[1] == "½"]
    if halves:
        bad.append("half marks in Copied: %s" % halves[:3])
    if "copied to both handhelds" in text(page).lower() or "one handheld of two" in text(page).lower():
        bad.append("the page still says 'copied to both handhelds' or 'one handheld of two'")
    return not bad, ("%d one-handheld rows, all ticks: %s" % (len(one), sorted(one)[:4]) if not bad else "; ".join(bad[:4]))


ok, why = globals()["c_" + CHECK]()
print("%s %s: %s" % ("PASS" if ok else "FAIL", CHECK, why))
sys.exit(0 if ok else 1)
