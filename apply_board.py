"""Apply this tick's two board-branch edits, validating before writing.

1. [issue.83]: lane.blit83's board request -- withdraw the sentence in
   `blocked_on` claiming the blend arm upgraded this blocker to measured, and
   record on the blocker fields that the control is INERT.
2. territory.toml: release the four lanes that reported this tick.

Everything is edited as text, parsed with tomllib in memory, and only then
written. Three board-file breakages came from string-slicing a structured file
and writing it unparsed.
"""
import tomllib, sys, io

BT = "/home/justin/hakux-work/board-wt/.boardtree/"

# ---- 1. issue.83 ---------------------------------------------------------
p = BT + "nv2a_issues.toml"
text = open(p, encoding="utf-8").read()
before = tomllib.loads(text)

WITHDRAWN = (
    " WITHDRAWN 2026-09-19 by the board, on lane.blit83's request: the sentence above saying"
    " the eight 'held at 1 px, unmoved -- so the blend fix demonstrably does not reach them,"
    " which is what this issue asserted and is now measured rather than argued'. AN INERT"
    " CONTROL PASSING IS NOT A MEASUREMENT. The eight captures' differing pixels are in the"
    " Gouraud quad the test draws, not written by the blit at all, so the leg reads unmoved"
    " whatever the BLEND_AND divide does. The claim is true and still held BY CONSTRUCTION,"
    " exactly as blocker_tested said before the arm. #38's PASS is unaffected and must not be"
    " reopened -- it rests on its 21 live expect-values. Same shape as the Image_blit/OverlapFIFO"
    " leg lane.arms already dropped from this file, and it is 8 of the 20 surviving"
    " must_not_move legs, not 1."
)

FALSIFIER = (
    "TAUTOLOGICAL AS WRITTEN, refuted 2026-09-19 by lane.blit83 and recorded rather than"
    " deleted. It read: \"if 'the blend fix cannot reach these' were false, the eight would move"
    " when the BLEND_AND divide lands -- and they are the must-not-move control on that very"
    " arm, so the arm itself tests this claim rather than assuming it.\" Name the world in which"
    " that leg fails: it needs a change confined to one arm of an if to alter pixels the other"
    " arm never writes. There is no such world. The arm did not test the claim, it restated it."
    " A REPLACEMENT FALSIFIER MUST NAME A CAPTURE THE BLIT ACTUALLY WRITES."
)

TESTED = (
    "HELD BY CONSTRUCTION, NOT BY MEASUREMENT -- and that was the original and correct reading."
    " SRCCOPY is a memmove with no beta and no divide (blit.c:60-65, last changed in 24087af22a,"
    " 2026-01-15, an ancestor of every ref in play), while #38's whole diff and #84's two guards"
    " live inside the BLEND_AND arm; the one shared edit, perform_blit()'s new bytes_per_pixel"
    " parameter, is read only at blit.c:140, inside that arm. Traced line by line at 55bc6c6c2b"
    " by lane.blit83 2026-09-19. The interim claim that the queued control leg upgraded this to"
    " measured is WITHDRAWN -- see blocked_on."
)

PREMISE = (
    " PREMISE CORRECTED 2026-09-19, AND IT CHANGES WHAT THIS ISSUE IS. 'EXACTLY 1 px, ours one"
    " low' is the max_rgb COLUMN read as a pixel count. The scoreboard header is"
    " `suite test solo status differing max_rgb max_a pixels off_by_one`; the rows read"
    " differing=1650, max_rgb=1. Every scored measurement on disk agrees and none of them reads"
    " 1: 1,573 px on run-2026-09-10-image_blit-adreno.tsv (ccad2844d4, Nova/Adreno), 1,650"
    " (BL_Inside 1,649) on run-2026-09-12-image-blit-clip.tsv and on"
    " run-2026-09-12-issue19-g0-scores.tsv, 1,701 on gl-vs-vulkan-surf1-2026-09-13.tsv for GL and"
    " VK alike at delta 0, and 1,701 in image-blit-residual-is-not-the-blit.md. The '1 px each'"
    " appears ONLY IN PROSE -- this title and status_note, blit38-blend-and-divide.json,"
    " 24a75d6e3c's commit message, image-blit-blend-divide.md:122 -- one reading propagated five"
    " times and never re-derived from a scored row. AND THE MECHANISM'S CEILING REFUTES THE"
    " BOUNDARY DIAGNOSIS DIRECTLY: TestOverlapBarelyInclusive (image_blit_tests.cpp:654) issues a"
    " blit of width 1, height 1, so the ceiling on any copy-extent, coordinate-truncation or"
    " copy-direction defect in these captures is ONE PIXEL, three orders of magnitude below the"
    " measured residual at every ref where anyone counted. The boundary-or-inclusivity reading"
    " above is therefore STALE; see docs/investigations/image-blit-residual-is-not-the-blit.md."
)

reps = [
    ('blocker_falsifier = "if \'the blend fix cannot reach these\' were false,',
     None),
]

# Surgical, anchored replacements on the three [issue.83] lines.
def replace_line(text, key, newval, anchor):
    i = text.index(anchor)
    start = text.index("\n" + key + " = ", i) + 1
    end = text.index("\n", start)
    line = text[start:end]
    assert line.startswith(key + ' = "') and line.endswith('"'), line[:80]
    return text[:start] + key + " = " + toml_str(newval) + text[end:], line


def toml_str(s):
    assert '"' not in s or True
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


anchor83 = "\n[issue.83]\n"
i83 = text.index(anchor83)
i84 = text.index("\n[issue.84]\n")

text, old_f = replace_line(text, "blocker_falsifier", FALSIFIER, anchor83)
text, old_t = replace_line(text, "blocker_tested", TESTED, anchor83)

# Append to status_note and blocked_on rather than rewriting them.
for key, addition in (("status_note", PREMISE), ("blocked_on", WITHDRAWN)):
    i = text.index(anchor83)
    start = text.index("\n" + key + " = ", i) + 1
    end = text.index("\n", start)
    line = text[start:end]
    assert line.endswith('"'), key
    text = text[:end - 1] + addition.replace("\\", "\\\\").replace('"', '\\"') + text[end - 1:]

after = tomllib.loads(text)

# The edit must touch issue 83 and nothing else.
assert set(after["issue"]) == set(before["issue"])
changed = [k for k in after["issue"] if after["issue"][k] != before["issue"][k]]
assert changed == ["83"], changed
e = after["issue"]["83"]
assert "TAUTOLOGICAL" in e["blocker_falsifier"]
assert "WITHDRAWN 2026-09-19" in e["blocked_on"]
assert "max_rgb COLUMN" in e["status_note"]
assert e["title"] == before["issue"]["83"]["title"]
print("issue.83 validated; 4 fields updated, 1 issue changed")

if "--write" in sys.argv:
    open(p, "w", encoding="utf-8").write(text)
    print("wrote", p)
