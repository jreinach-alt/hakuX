#!/usr/bin/env python3
"""Apply lane.blit83b's board requests 1-4 to nv2a_issues.toml.

Line-oriented: every value in this file is one line. Parse in memory, assert
the result, refuse to write on any mismatch.
"""
import io
import tomllib

P = "/home/justin/hakux-work/board-wt/.boardtree/nv2a_issues.toml"
src = open(P, encoding="utf-8").read()
lines = src.split("\n")

TITLE83 = (
    "Image_blit: the eight Overlap_* captures' residual is interpolated vertex "
    "colour, not the blit (CLOSED -- measured on device, the blit rect is byte-exact)"
)

NOTE83 = (
    "CLOSED 2026-09-19 AS A DUPLICATE OF #38 MECHANISM 1, ON A MEASUREMENT AND NOT ON A "
    "RE-READING. THE PREMISE WAS A COLUMN MISREAD: 'each differ from the golden by exactly 1 px' "
    "was the max_rgb column of scoreboard rows whose differing column read 1,650 (1,649 for "
    "BL_Inside), and every counted measurement on disk agrees -- 1,573 at ccad2844d4 on Nova, "
    "1,650 at two device refs, 1,701 on desktop GL and VK. The scoreboard header is "
    "suite/test/solo/status/differing/max_rgb/max_a/pixels/off_by_one; the 1 is a channel delta. "
    "It propagated through this title, blit38-blend-and-divide.json, 24a75d6e3c's commit message "
    "and image-blit-blend-divide.md:122 without once being re-derived from a scored row. THE "
    "FALSIFIER THAT CLOSED IT, named by the first pass and run by the second: if the surviving "
    "pixel sat at the blit destination coordinate, the boundary/inclusivity reading was right. "
    "It does not. 0 of 8 blitted destination pixels differ at 71c7bd1d7d and 24a75d6e3c on device "
    "thor (captures 2026-09-18 12:12-12:32, five proven runs each, goldens 2026-09-09); all eight "
    "read 255,255,0,255 against 255,255,0,255. The one differing pixel is (176,180), B channel, "
    "ours 227 golden 228 -- THE SAME PIXEL in all eight captures and all ten runs, while the blit "
    "destination varies over eight distinct coordinates. A copy defect cannot be independent of "
    "where it copies to. IT IS ALSO IMPOSSIBLE AT THE ORIGINAL MAGNITUDE: TestOverlapBarelyInclusive "
    "(image_blit_tests.cpp:654) blits width 1 height 1, so one pixel is the ceiling on any "
    "copy-extent, coordinate-truncation or copy-direction defect in these captures, and the "
    "residual was three orders of magnitude above it. And every capture that does exercise a copy "
    "extent reads exactly 0: all seven ImgBlt_Clip_* and all three ImgBlt_SRCCOPY_* score "
    "0 0 0 307200 0, on goldens that provably discriminate (all 21 golden pairs differ, the "
    "tightest by 81 px). THE REMAINING PIXEL'S OWNER IS #38 MECHANISM 1 -- silicon quantises the "
    "vertex colour to its byte before the interpolator -- and the anatomy in "
    "docs/investigations/image-blit-residual-is-not-the-blit.md decomposes the desktop residual "
    "the same way: big Gouraud quad 1,695, small quad 6, ELSEWHERE 0, alpha byte-exact (max_a = 0 "
    "in every scored row, it comes from a constant SRC_ZERO combiner). NOTE WHAT IS NOT CLAIMED: "
    "the drop from ~1,573 to 1 is NOT attributed to dca3c94b98 here. That window is Nova->Thor and "
    "contains real blit-path work on the same rows (BlitBeyondWidth 284,628 -> 0, "
    "ImgBlt_Clip_320_240_1_1 16,383 -> 0); the attribution lives with #38 and this issue never "
    "needed it, only the coordinate. Reported by lane.blit83b, issuecomment-5737991240. "
    "DISPOSITION STAYS 'defect' because the vocabulary has no not-in-this-component value and #75 "
    "was closed the same way -- the defect is real, it is #38's, and it is not in vk/blit.c."
)

BLOCKED83 = (
    "Nothing to do on this issue; it is closed into #38. WITHDRAWN 2026-09-19, on lane.blit83b's "
    "board request 2 and 3: this field used to say the eight held at 1 px unmoved across the "
    "BLEND_AND arm, 'so the blend fix demonstrably does not reach them, which is what this issue "
    "asserted and is NOW MEASURED RATHER THAN ARGUED'. AN INERT CONTROL PASSING IS NOT A "
    "MEASUREMENT. The claim was true and held BY CONSTRUCTION the whole time, which is what "
    "blocker_tested said originally and correctly. #38's PASS is unaffected and is NOT to be "
    "re-opened: it rests on 21 live expect-values (every ImgBlt_BLENDAND_* and BlitRenderBlit to "
    "0, 16 better 0 worse). No file was ever granted for this issue and none is needed now -- "
    "vk/blit.c stays lane.blitsafe's, and both passes declined to ask for it."
)

TESTED83 = (
    "TESTED AND THE ANSWER WAS NEGATIVE FOR THE BLIT, 2026-09-18 captures read 2026-09-19. Read "
    "the falsifier above as the one that was actually run: 0 of 8 blit destination pixels differ, "
    "the single survivor is (176,180) in all eight. ALSO RECORDED, because it is the reason this "
    "row over-claimed for a day: the ORIGINAL falsifier ('the eight would move when the BLEND_AND "
    "divide lands, and they are the must-not-move control on that very arm') WAS TAUTOLOGICAL. "
    "#38's entire diff is inside else-if (operation == NV09F_SET_OPERATION_BLEND_AND); the SRCCOPY "
    "branch is a memmove at blit.c:60-65 last touched by 24087af22a on 2026-01-15; #84's guards "
    "are conjoined on the same operation. The only shared edit is a parameter push. Name the world "
    "in which that leg fails and there is none -- the arm restated the claim instead of testing "
    "it, and arm A and arm B produce the byte-identical pixel (176,180), 227 against 228, in all "
    "ten runs. That is 8 of the 20 surviving must-not-move legs on "
    "blit38-blend-and-divide.json inert by construction. FOR THE NEXT CONTROL LIST, NOT A "
    "RE-JUDGEMENT of this one."
)

FALSIFIER83 = (
    "SUPERSEDED AND DISCHARGED. The falsifier that decided this issue, named by lane.blit83's "
    "first pass and run by its second: if the single surviving differing pixel in a DEVICE capture "
    "at a ref carrying dca3c94b98 sits AT THE BLIT DESTINATION COORDINATE -- (64,64) for "
    "Overlap_TL_Inside, (63,64) for TL_Outside, and so on -- then the blit is placing or valuing "
    "its one pixel wrong and the boundary/inclusivity reading is right. It sits at (176,180) in "
    "all eight, inside the Gouraud quad, while the destination varies over eight coordinates. "
    "The earlier falsifier on this row was inert; see blocker_tested."
)

MECH38 = (
    " MECHANISM 1'S RESIDUE ON Image blit IS NOW ONE PIXEL AND IT IS THE LAST ONE, added "
    "2026-09-19 from #83's closure and NOT a re-judgement of anything here: at 24a75d6e3c on "
    "device thor, 2026-09-18, all eight ImgBlt_Overlap_* captures score differing = 1 and the "
    "pixel is (176,180), B channel, ours 227 golden 228 -- one displaced quantisation step edge "
    "out of 7,301 in the quad, identical in arm A and arm B and identical across all eight "
    "captures. R at x = 64 exactly is the documented tie: the ramp's true value at the midpoint "
    "is 127.5, hardware rounds half-up to 128 and we round down to 127, which is where 'ours is "
    "one low' came from and it is in the interpolator, not in a memmove."
)


def set_key(key, value, start, end):
    """Replace `key = "..."` inside [start,end); assert exactly one hit."""
    hits = [i for i in range(start, end) if lines[i].startswith(key + " = ")]
    assert len(hits) == 1, (key, hits)
    lines[hits[0]] = '%s = "%s"' % (key, value)
    return hits[0]


def bounds(section):
    i = lines.index("[issue.%s]" % section)
    j = i + 1
    while j < len(lines) and not lines[j].startswith("[issue."):
        j += 1
    return i, j


s83, e83 = bounds("83")
for ch in (TITLE83, NOTE83, BLOCKED83, TESTED83, FALSIFIER83, MECH38):
    assert '"' not in ch and "\\" not in ch and "\n" not in ch, ch[:60]

set_key("title", TITLE83, s83, e83)
set_key("status", "closed-duplicate", s83, e83)
set_key("status_note", NOTE83, s83, e83)
set_key("blocked_on", BLOCKED83, s83, e83)
set_key("blocker_tested", TESTED83, s83, e83)
set_key("blocker_falsifier", FALSIFIER83, s83, e83)

# #38: append one line to status_note, preserving what is there.
s38, e38 = bounds("38")
hits = [i for i in range(s38, e38) if lines[i].startswith("status_note = ")]
assert len(hits) == 1
old = lines[hits[0]]
assert old.endswith('"'), old[-40:]
assert "MECHANISM 1'S RESIDUE" not in old, "already applied"
lines[hits[0]] = old[:-1] + MECH38 + '"'

out = "\n".join(lines)

# Refuse to write unless it parses and says what it should.
d = tomllib.loads(out)["issue"]
assert d["83"]["status"] == "closed-duplicate"
assert d["83"]["title"] == TITLE83
assert d["83"]["status_note"] == NOTE83
assert d["83"]["blocked_on"] == BLOCKED83
# The sentence survives only inside its own withdrawal clause -- quoting what
# was retracted is how every other row on this board records a retraction.
assert "WITHDRAWN 2026-09-19" in d["83"]["blocked_on"]
assert "AN INERT CONTROL PASSING IS NOT A MEASUREMENT." in d["83"]["blocked_on"]
assert d["83"]["blocked_on"].count("now measured rather than argued") == 0
assert d["83"]["blocked_on"].count("NOW MEASURED RATHER THAN ARGUED") == 1
assert d["83"]["disposition"] == "defect"
assert d["38"]["status_note"].endswith(MECH38)
assert d["38"]["status"] == "fixed-part"
before = tomllib.loads(src)["issue"]
assert set(before) == set(d), "issue set changed"
unchanged = [n for n in before if n not in ("83", "38")]
assert all(before[n] == d[n] for n in unchanged), "collateral change"
assert before["38"]["blocked_on"] == d["38"]["blocked_on"]

open(P, "w", encoding="utf-8").write(out)
print("ok: 83 closed-duplicate, 38 status_note +1 clause, %d rows untouched"
      % len(unchanged))
