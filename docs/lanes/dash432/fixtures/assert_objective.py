#!/usr/bin/env python3
"""The owner's objective (#432), asserted on a page rendered from the 16:24 fixture.

    assert_objective.py <out dir> [check]      # every check, or one; exit 1 on any FAIL

<out dir> is run_fixture.sh's: index.html is read as a reader sees it (tags
stripped, entities decoded). Each check names the owner's question it
answers. They are written to fail on the pre-change page (see NOTES.md,
"Proof"), so each must find the POSITIVE form of what the owner asked for,
never merely the absence of the old defect.
"""
import html, json, os, re, sys

OUT = sys.argv[1]
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1624", "src")
PAGE = open(os.path.join(OUT, "index.html"), encoding="utf-8").read()
FIRST = PAGE[:PAGE.find('<div class="fold">')] if '<div class="fold">' in PAGE else PAGE


def text(h):
    h = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", h)
    h = re.sub(r"<(br|/p|/li|/tr|/td|/th|/div|/h\d)\b[^>]*>", "\n", h)
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def cells(row_html):
    return [text(c).strip() for c in re.findall(r"(?s)<td\b[^>]*>(.*?)</td>", row_html)]


def section(id_):
    m = re.search(r'(?s)<section class="q" id="%s">(.*?)</section>' % id_, PAGE)
    return m.group(1) if m else ""


def items(block):
    return [" ".join(text(li).split()) for li in re.findall(r"(?s)<li\b[^>]*>(.*?)</li>", block)]


ESC = []
for l in open(os.path.join(FIX, "work/host-tools/escalations.md"), encoding="utf-8"):
    l = l.strip()
    if l and "RESOLVED" not in l:
        ESC.append(re.sub(r"^.*?\)\s*:\s*", "", l))
PASS1 = [r["title"] for r in json.load(open(os.path.join(os.path.dirname(FIX), "..", "..", "pass1-backfill.json")))["rows"]]


def c_held():
    """Q1/Q4: no bare "held"; each handheld is running, in use by X (purpose, end), or idle."""
    bare = re.findall(r">\s*held\s*<", FIRST, re.I)
    if bare:
        return False, "a device state reads a bare 'held' (%d)" % len(bare)
    devs = [" ".join(text(d).split()) for d in re.findall(r'(?s)<div class="dev">(.*?)</div>', section("q4"))]
    got = {}
    for d in devs:
        m = re.match(r"(Thor|Nova)\s*(.*)", d)
        if m:
            got[m.group(1)] = m.group(2)
    if set(got) != {"Thor", "Nova"}:
        return False, "no device line for %s" % ", ".join(sorted({"Thor", "Nova"} - set(got)))
    for k, v in got.items():
        if not (re.match(r"running .+ for .+ since", v) or re.match(r"in use by \S+: .+ Since \d\d:\d\d, until (\d\d:\d\d|no end time stated)", v)
                or re.match(r"idle\b", v)):
            return False, "%s line names no holder, purpose and end: %r" % (k, v[:120])
    return True, "; ".join("%s: %s" % kv for kv in sorted(got.items()))


def c_person():
    """Q3: exactly the six escalations and the stranded perfregimen; nothing in flight, parked, or the queue."""
    blk = section("q3") or (re.search(r'(?s)<div class="att">(.*?)</div>', PAGE) or [None, ""])[1]
    its = items(blk)
    if not its:
        return False, "no 'needs a person' list"
    banned = [w for w in ("blinx372d", "flatlm13", "forza414", "fmv303c", "queued over") if any(w in i for i in its)]
    if banned:
        return False, "lists %s" % ", ".join(banned)
    miss = [e[:50] for e in ESC if not any(" ".join(e.split()) in i for i in its)]
    if miss:
        return False, "missing %d escalation(s): %s" % (len(miss), "; ".join(miss))
    strand = [i for i in its if "perfregimen" in i]
    if len(strand) != 1:
        return False, "the stranded perfregimen is listed %d times" % len(strand)
    if len(its) != len(ESC) + 1:
        return False, "%d items, want %d (the escalations and perfregimen)" % (len(its), len(ESC) + 1)
    return True, "%d items: %d escalations and lane.perfregimen" % (len(its), len(ESC))


def lane_rows():
    rows = []
    for t in re.findall(r'(?s)<table class="cards lanes">(.*?)</table>', section("q2")):
        rows += [cells(r) for r in re.findall(r"(?s)<tr>(.*?)</tr>", t)]
    return [r for r in rows if r]


def c_sessions():
    """Q2/5: the lanes table has rows for lane.xbox and lane.remote."""
    first = {r[0].split()[0] for r in lane_rows() if r}
    miss = [n for n in ("lane.xbox", "lane.remote") if n not in first]
    return (not miss), ("rows for lane.xbox and lane.remote" if not miss else "no row for " + ", ".join(miss))


def c_never():
    """Q6: "never" does not occur: not on the first screen, and never as a value anywhere."""
    # A title or a sentence quoted from GitHub may say "never" (PR #446's title
    # does); what the owner read was "never" as a TIME, a table cell of its own.
    n = re.findall(r"\bnever\b", text(FIRST), re.I)
    v = re.findall(r"(?is)<td\b[^>]*>\s*never\s*</td>", PAGE)
    return (not n and not v), ("%d on the first screen, %d cells reading 'never'" % (len(n), len(v)) if n or v else "absent")


def c_results():
    """Q6: every latest-result cell is whole: it ends a sentence, never mid-word or with '...'."""
    rows = lane_rows()
    if not rows:
        # the pre-change page's lane table: its last column is "it said"
        m = re.search(r"(?s)<tr><th>lane</th><th>state</th>.*?</table>", PAGE)
        rows = [cells(r) for r in re.findall(r"(?s)<tr>(.*?)</tr>", m.group(0))] if m else []
    bad = []
    n = 0
    for r in rows:
        if not r:
            continue
        c = re.sub(r"\s*\(PR #\d+\)$", "", r[-1]).strip()
        if c in ("", "-"):
            continue
        n += 1
        if c.endswith("...") or not re.search(r"[.!?][\"')\]`]*$", c):
            bad.append(c[-40:])
    if not n:
        return False, "no latest-result cells"
    return (not bad), ("%d cells, all whole" % n if not bad else "%d of %d cut: %s" % (len(bad), n, " | ".join(bad[:3])))


def c_titles():
    """Q1/7: the 0.5 table has pass 1's 17 titles, and its counts agree with its rows."""
    q1 = section("q1")
    m = re.search(r'(?s)<table class="[^"]*\btitles\b[^"]*">(.*?)</table>', q1)
    if not m:
        return False, "no 0.5 title table"
    rows = [cells(r) for r in re.findall(r"(?s)<tr>(.*?)</tr>", m.group(1))]
    rows = [r for r in rows if r]
    titles = {r[0] for r in rows}
    miss = [t for t in PASS1 if t not in titles]
    if miss:
        return False, "pass-1 titles missing: %s" % "; ".join(miss)
    nr = re.search(r"Not run yet \((\d+)\)", text(q1))
    listed = len(titles) + (int(nr.group(1)) if nr else 0)
    tested = sum(1 for r in rows if re.match(r"(yes|no|late)\b", r[2]))
    reached = sum(1 for r in rows if r[2] == "yes")
    playable = sum(1 for r in rows if r[6] == "Playable")
    mc = re.search(r"(\d+) titles on the handhelds; (\d+) tested; (\d+) reached gameplay; (\d+) Playable", text(q1))
    if not mc:
        return False, "no counts line"
    want = (listed, tested, reached, playable)
    got = tuple(int(x) for x in mc.groups())
    return got == want, "counts %s, rows say %s" % (got, want)


def c_no145():
    """Q1/7: the 0.5 section does not say "of 145"."""
    blk = section("q1") or PAGE
    return ("of 145" not in text(blk)), ("absent" if "of 145" not in text(blk) else "says 'of 145'")


CHECKS = {"held": c_held, "person": c_person, "sessions": c_sessions, "never": c_never,
          "results": c_results, "titles": c_titles, "no145": c_no145}

if __name__ == "__main__":
    want = sys.argv[2:] or list(CHECKS)
    fails = 0
    for k in want:
        try:
            ok, why = CHECKS[k]()
        except Exception as e:                      # a page this cannot parse is a failed check, not a pass
            ok, why = False, "error: %r" % e
        fails += not ok
        print("%s %-8s %s -- %s" % ("PASS" if ok else "FAIL", k, CHECKS[k].__doc__.split("\n")[0], why))
    sys.exit(1 if fails else 0)
