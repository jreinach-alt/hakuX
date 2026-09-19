"""Board tick 2026-09-19T01:0xZ -- wave 97.

Three things, all of them by rule, all validated in memory before any write.

1. [issue.83] CLOSED. lane.blit83b's board request, second pass: the
   pre-registered falsifier came out NEGATIVE for the blit on a device capture
   at a ref carrying dca3c94b98, so the issue's own premise is refuted and the
   surviving pixel's owner is #38 mechanism 1, which is open.
2. [issue.38] one line on status_note, request 4: what mechanism 1's residue
   measures on Image blit at 24a75d6e3c.
3. territory.toml: retire lane.blit83b (reported), lane.stencil99 (#99 closed)
   and lane.tier81fix (#81, #90 closed), release tier81fix's two accel/tcg
   files to [free], and bump the wave.

Everything is text-edited, parsed with tomllib in memory, cross-checked, and
only then written. Three board-file breakages came from string-slicing a
structured file and writing it unparsed.
"""
import tomllib, sys

BT = "/home/justin/hakux-work/board-wt/.boardtree/"
NOW = "2026-09-19T01:05:00Z"

# ---- 1 + 2. the tracker --------------------------------------------------
p = BT + "nv2a_issues.toml"
text = open(p, encoding="utf-8").read()
before = tomllib.loads(text)

CLOSED83 = (
    " CLOSED 2026-09-19 BY THE BOARD ON lane.blit83b's REQUEST, AND THE FALSIFIER IS WHY."
    " The second pass measured the one thing reading could not settle -- WHICH pixels differ on a"
    " DEVICE capture at a ref carrying dca3c94b98 -- against captures already on disk:"
    " 1789758697-lane.arms-blit38A-2228233 (ref 71c7bd1d7d, apk 7064ef90460a) and"
    " 1789758704-lane.arms-blit38B-2230198 (ref 24a75d6e3c, apk dc3dc7c38b55), device thor"
    " bdc158a5, captures written 2026-09-18 12:12-12:32, 5 proven runs each, goldens 2026-09-09"
    " and so NINE DAYS OLDER than the run. dca3c94b98 is an ancestor of both refs and is NOT an"
    " ancestor of b9d845d316, the desktop set every earlier 'which pixels' datum came from, so the"
    " desktop/device confound is removed rather than papered over. THE BRIEF'S FALSIFIER --"
    " 'if the differing pixels fall INSIDE the 1x1 blit rect, not-the-blit is refuted' -- came out"
    " NEGATIVE: 0 of 8 blitted destination pixels differ, all eight (255,255,0,255) against"
    " (255,255,0,255). The single differing pixel is (176,180), B channel, ours 227 / golden 228,"
    " THE SAME PIXEL IN ALL EIGHT CAPTURES AND ALL TEN RUNS OF TWO DISTINCT BINARIES, while the"
    " blit destination takes eight different values -- offsets from it range (-16,-11) to"
    " (+113,+116). A copy defect is defined relative to where it copies; this one is nailed to the"
    " geometry, and it sits on a colour ramp whose B quantisation step edge is displaced by one"
    " pixel (1 of 7,301 step edges in the quad, 16,383 of 16,384 quad B pixels byte-exact). All"
    " seven ImgBlt_Clip_* and BlitBeyondWidth read 0 differing at both arms. THE OWNER OF THE"
    " REMAINING PIXEL IS #38 (fixed-part, mechanism 1: silicon quantises the vertex colour to its"
    " byte before the interpolator, colorPrecision in glsl/vsh.c plus dca3c94b98), which is OPEN --"
    " verified open on GitHub at close time, so the mechanism keeps a row. status is"
    " closed-duplicate FOR #38 rather than a new disposition value: the lane asked for disposition"
    " = 'not a defect in the claimed component' and that field is an enum of five values with no"
    " such member, while the surviving pixel IS a defect -- just not this component's. The title"
    " was corrected on GitHub at the same time so a closed row stops asserting the misread."
    " NO FILE WAS GRANTED TO ANYONE for this issue, on the lane's own request: two passes and"
    " neither wanted vk/blit.c."
)

BLOCKED83 = (
    " MOOT 2026-09-19: the issue is closed and no lane holds or wants vk/blit.c on its behalf."
    " Nothing here is a wall any more -- kept for the record because a refuted blocker and a"
    " withdrawn one read alike once the row is closed, and this one was both."
)

NOTE38 = (
    " MECHANISM 1's RESIDUE ON Image blit, MEASURED 2026-09-19 (added by the board on"
    " lane.blit83b's request 4, NOT a re-judgement of anything): at 24a75d6e3c and 71c7bd1d7d on"
    " device thor bdc158a5, 2026-09-18 captures against 2026-09-09 goldens, each of the eight"
    " ImgBlt_Overlap_* captures has EXACTLY ONE differing pixel, (176,180), B channel, ours 228-1,"
    " identical across all eight blit destinations and all ten runs -- a single displaced"
    " quantisation step edge out of 7,301 in the 128x128 quad. #83 closed into this mechanism."
)


def add(text, issue, key, addition):
    """Append to a one-line basic-string value inside [issue.<n>]."""
    anchor = "\n[issue.%s]\n" % issue
    i = text.index(anchor)
    start = text.index("\n" + key + " = ", i) + 1
    end = text.index("\n", start)
    line = text[start:end]
    assert line.endswith('"'), (issue, key, line[-40:])
    esc = addition.replace("\\", "\\\\").replace('"', '\\"')
    return text[:end - 1] + esc + text[end - 1:]


def setval(text, issue, key, value):
    anchor = "\n[issue.%s]\n" % issue
    i = text.index(anchor)
    start = text.index("\n" + key + " = ", i) + 1
    end = text.index("\n", start)
    return (text[:start] + key + ' = "'
            + value.replace("\\", "\\\\").replace('"', '\\"') + '"' + text[end:])


text = add(text, "83", "status_note", CLOSED83)
text = add(text, "83", "blocked_on", BLOCKED83)
text = setval(text, "83", "status", "closed-duplicate")
text = add(text, "38", "status_note", NOTE38)

after = tomllib.loads(text)
assert set(after["issue"]) == set(before["issue"])
changed = sorted([k for k in after["issue"] if after["issue"][k] != before["issue"][k]], key=int)
assert changed == ["38", "83"], changed
e83, e38 = after["issue"]["83"], after["issue"]["38"]
assert e83["status"] == "closed-duplicate", e83["status"]
assert "NEGATIVE" in e83["status_note"] and "(176,180)" in e83["status_note"]
assert e83["disposition"] == before["issue"]["83"]["disposition"]
assert e83["title"] == before["issue"]["83"]["title"]
assert e38["status"] == "fixed-part" == before["issue"]["38"]["status"]
assert "MECHANISM 1's RESIDUE" in e38["status_note"]
# Every other field of 83 and 38 is untouched apart from the four named.
for n, keys in (("83", {"status", "status_note", "blocked_on"}), ("38", {"status_note"})):
    for k, v in before["issue"][n].items():
        if k not in keys:
            assert after["issue"][n][k] == v, (n, k)
print("tracker: issue 83 closed-duplicate, issue 38 status_note + 1 line, 2 issues changed")
tracker_text = text

# ---- 3. territory.toml ---------------------------------------------------
q = BT + "territory.toml"
t = open(q, encoding="utf-8").read()
tbefore = tomllib.loads(t)

RET_TIER = (
    "RETIRED AT WAVE 97: BOTH ITS ISSUES ARE CLOSED. #81 and #90 were closed 2026-09-19T00:20Z by"
    " the board (the fix is folded as 7dfa94c403 via 4d3edc563d; rev-list --left-right prints"
    " 109 0), and the fleet row has read `retired` since the 00:16Z tick -- but this row still"
    " claimed two files, so fleet.py listed the lane as a claim with no agent and the files were"
    " held by nobody. accel/tcg/cpu-exec.c and accel/tcg/translate-all.c ARE RELEASED TO [free] AT"
    " THIS WAVE. The old note is kept below the retirement line because #90's second contributor"
    " (the anti-churn tier-hint restore at translate-all.c:659-688, dead preprocessor on the only"
    " platform that ships) and the tb-maint.c coordination note are still the next reader's"
    " starting point. ORIGINAL NOTE: "
)
RET_STEN = (
    "RETIRED AT WAVE 97: #99 was closed 2026-09-19T00:20Z as a duplicate of #75 (itself a"
    " duplicate of #39). The lane held no files and produced no commits, so there is nothing to"
    " fold and nothing to release; the row was the only thing left asserting coverage that does"
    " not exist. ORIGINAL NOTE: "
)
RET_83B = '''
[retired.blit83b]
issues = ["83"]
files = []
retired_utc = "%s"
note = "RETIRED AT WAVE 97, AND IT ANSWERED ITS BRIEF EXACTLY. lane.blit83b ran analysis-only with files = [] (it was told not to ask for vk/blit.c and it did not), measured the device capture the first pass could not reach, and posted issuecomment-5737991240 with the date, the ref, the count and the location relative to the blit rect -- which is what briefs/blit83b.md said DONE WHEN. THE FALSIFIER CAME OUT NEGATIVE FOR THE BLIT: 0 of 8 blitted destination pixels differ at 71c7bd1d7d and 24a75d6e3c on device thor, 2026-09-18 captures against 2026-09-09 goldens; the one differing pixel is (176,180) B ours-low-by-one, the same pixel in all eight captures and all ten runs while the blit destination varies over eight coordinates. #83 IS CLOSED into #38 mechanism 1 on that measurement. IT HAD NO FLEET ROW AND NO TERRITORY ROW while it ran -- the invisible-lane hazard fleet.py documents and cannot see, and the reason #83 read as dispatchable-and-undispatched on this tick when it had in fact just been answered. Both rows exist now. WHAT IS LEFT OF IT: PR #104, whose entire diff is a root NOTES.md the lane was never granted (files = [] means no file was its to commit) and which master does not carry. The board did not route it to fold -- the report is preserved verbatim on the issue and in this file, and moving the measurement into docs/investigations/ is a lane's write, not the board's. The PR is closed with that said on it; the branch is kept."
''' % NOW

# Retire the two lane rows: rename the header, prepend the retirement to note,
# empty the files list, and add a retired_utc.
for lane, ret in (("tier81fix", RET_TIER), ("stencil99", RET_STEN)):
    head = "\n[lane.%s]\n" % lane
    i = t.index(head)
    t = t[:i] + "\n[retired.%s]\n" % lane + t[i + len(head):]
    # note: prepend the retirement sentence
    ns = t.index('\nnote = "', i) + len('\nnote = "')
    t = t[:ns] + ret.replace("\\", "\\\\").replace('"', '\\"') + t[ns:]
    # files: release them
    fs = t.index("\nfiles = ", i) + 1
    fe = t.index("\n", fs)
    t = t[:fs] + "files = []" + t[fe:]
    # retired_utc
    ie = t.index("\nissues = ", i)
    ee = t.index("\n", ie + 1)
    t = t[:ee] + '\nretired_utc = "%s"' % NOW + t[ee:]

# Release tier81fix's files into [free].
FREED = ["accel/tcg/cpu-exec.c", "accel/tcg/translate-all.c"]
fanchor = '\n[free]\n'
fi = t.index(fanchor)
ffs = t.index("\nfiles = [", fi) + 1
t = (t[:ffs] + 'files = [\n'
     + '# RELEASED AT WAVE 97 by retiring lane.tier81fix: its two issues are closed and the\n'
       '# files were claimed by a lane with no agent. #90\'s second contributor is unimplemented\n'
       '# and lives in translate-all.c -- see [retired.tier81fix].\n'
     + "".join('    "%s",\n' % f for f in FREED)
     + t[ffs + len("files = ["):])

# blit83b's row, next to the first pass's.
r83 = t.index('\n[retired.blit83]\n')
nxt = t.index('\n[', t.index('\nnote = "', r83) + 4)
t = t[:nxt] + RET_83B.rstrip("\n") + "\n" + t[nxt:]

t = t.replace("wave = 96\n", "wave = 97\n", 1)
t = t.replace('updated_utc = "2026-09-19T00:39:00Z"', 'updated_utc = "%s"' % NOW, 1)

tafter = tomllib.loads(t)
assert tafter["wave"] == 97 and tafter["updated_utc"] == NOW
assert set(tafter["lane"]) == set(tbefore["lane"]) - {"tier81fix", "stencil99"}, sorted(tafter["lane"])
assert set(tafter["retired"]) == {"blit83", "blit83b", "tier81fix", "stencil99"}, sorted(tafter["retired"])
for lane in ("tier81fix", "stencil99"):
    r = tafter["retired"][lane]
    assert r["files"] == [] and r["retired_utc"] == NOW
    assert r["note"].startswith("RETIRED AT WAVE 97")
    assert "ORIGINAL NOTE:" in r["note"]
    assert tbefore["lane"][lane]["note"] in r["note"]
    assert r["issues"] == tbefore["lane"][lane]["issues"]
assert tafter["retired"]["blit83b"]["note"].startswith("RETIRED AT WAVE 97")
assert tafter["retired"]["blit83"] == tbefore["retired"]["blit83"]
# Nothing claimed twice, nothing both free and held -- check_territory.py's rule,
# re-run here because the checker lives on master and this file is on `board`.
owner = {}
problems = []
for lane, meta in tafter["lane"].items():
    for f in meta.get("files", []):
        if f in owner:
            problems.append("%s claimed by %s and %s" % (f, owner[f], lane))
        owner[f] = lane
for f in tafter["free"]["files"]:
    if f in owner:
        problems.append("%s FREE but claimed by %s" % (f, owner[f]))
assert not problems, problems
for f in FREED:
    assert f in tafter["free"]["files"] and f not in owner, f
# Every surviving lane row is byte-identical to before.
for lane, meta in tbefore["lane"].items():
    if lane in tafter["lane"]:
        assert tafter["lane"][lane] == meta, lane
print("territory: wave 96 -> 97, 3 lanes retired, %d files freed, %d lanes live"
      % (len(FREED), len(tafter["lane"])))

if "--write" not in sys.argv:
    print("dry run; pass --write")
    sys.exit(0)
open(p, "w", encoding="utf-8").write(tracker_text)
open(q, "w", encoding="utf-8").write(t)
print("wrote", p, "and", q)
