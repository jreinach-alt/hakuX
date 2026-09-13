#!/usr/bin/env python3
"""Enumerate the corpus draws that could exhibit #38 mechanism 2's pair rule.

#38 mechanism 2 is established as a rule -- silicon holds the interpolated
colour constant across the even-aligned pixel pair and evaluates it at the
pair's right edge -- but *what selects the draws it applies to* is not.  The
surviving candidate is a conjunction, "immediate mode and `w = 1`", fitted to
two positives, and the previous lane recorded that it did not believe it.

This script exists to turn "two positives is thin" into a checkable claim about
the corpus: **the class has exactly two members, so the positive cell cannot be
subdivided.**  The conjunction itself is well supported -- the 2x2 of
(immediate | arrays) x (perspective divide | not) is filled and the other three
cells are negative -- but with only two captures in the positive cell the
precondition sits in a four-way tie with everything those two happen to share:
QUADS/POLYGON rather than a triangle form, >= 512 px wide, and SET_VERTEX4F.
Each would give a different blast radius.  That is a blocker, and a blocker
needs the same evidence as a fix, so it has to be runnable rather than asserted.

Class membership needs all three, per DRAW:

  A  screen space with no perspective divide   -- a PassthroughVertexShader
  B  immediate-mode vertices                   -- SetVertex inside Begin/End,
                                                  EITHER SET_VERTEX3F or 4F
  C  a per-vertex diffuse GRADIENT             -- >= 2 distinct SetDiffuse
                                                  inside one Begin/End

and then, to be evidence either way, the capture must be MEASURABLE, which is
one criterion stated once and applied to every row rather than a reason per
exception:

  i   the qualifying pixels come from the DRAW, not from a texture or a
      background that happens to carry a shallow gradient;
  ii  the fragment-to-framebuffer x mapping is the identity -- no 2x-width
      antialiased surface, no resolve, no blit.

Applied uniformly that admits Alpha_func and Context_switch (paired) and
High_vertex_count and Shade_model's untextured variants (unpaired, and the
negatives the 2x2 rests on); it excludes Smoothing_control and Swath_width by
(i) and (ii), and Image_blit/BlitBeyondWidth by (ii) -- which is why that last
one shows paired rows in the census and is nonetheless not evidence here.

NOTE on the register: SET_VERTEX3F is immediate mode as much as SET_VERTEX4F
is, so a 3F suite is IN the class.  "4F rather than 3F" was offered as a
candidate selector and is refuted -- Shade_model's Fixed_* variants submit 4F
at w = 1.0 in an immediate-mode gradient block and do not pair.

C is the discriminator that most suites fail, and it is why the corpus is so
thin here: a suite can have hundreds of immediate-mode screen-space vertices
and still set one flat colour per primitive, which carries no interpolant to
sample.  `Color_mask_blend` is the worked example -- 8 four-argument
`SetVertex` calls under a passthrough shader, and one `SetDiffuse` per quad.

HOW MUCH OF THIS IS AUTOMATIC, said plainly because the answer is "not all of
it".  A and C are decided here by reading the source.  Two things are NOT, and
both need a human to open the file:

  * **which shader is live for a given Begin/End block.**  A file can create a
    PassthroughVertexShader in one test and call
    `SetVertexShaderProgram(nullptr)` in another; this script only sees that
    both appear.  `w_param_tests.cpp` and `texture_perspective_tests.cpp` both
    trip this -- their gradient blocks are fixed-function, not passthrough.
  * **whether every vertex of the gradient block is at `w = 1`.**  The literal
    is reported per block, but `texture_perspective_tests.cpp` mixes w = 0.3
    and w = 1.0 in one quad, and a count cannot see that.

So this prints the candidates and the evidence, and the last column says
whether a human confirmed it.  The confirmations below are from reading the
five files on 2026-09-13; re-read them rather than trusting the row if the
corpus has changed.

The other half of the claim is the per-row census in
`docs/testing/interpolator_phase.py`, which is what says whether a candidate
actually pairs.  Read the two together: a suite in the class that the census
calls unpaired *on its own draw's pixels* refutes the conjunction.  Beware that
the census's row metric qualifies any shallow gradient, including a textured
background -- `Smoothing_control`'s 365 "measurable" rows are a tiled texture
and its own shapes are too small to measure, so it is unmeasured rather than
unpaired.  See docs/investigations/issue57-is-issue38-mech2.md.

Run:  python3 docs/testing/pair_rule_candidates.py [TESTS_SRC_DIR]
"""

import os
import re
import sys

DEFAULT_SRC = "/home/justin/nxdk_pgraph_tests/src/tests"

# Hand confirmations from reading the sources on 2026-09-13, keyed by file.
# value: (in_class, note)
CONFIRMED = {
    "alpha_func_tests.cpp": (
        True, "passthrough; PRIMITIVE_QUADS; all gradient vertices SET_VERTEX4F w=1.0"),
    "context_switch_tests.cpp": (
        True, "passthrough; PRIMITIVE_POLYGON; all gradient vertices SET_VERTEX4F w=1.0"),
    "texture_perspective_tests.cpp": (
        False, "gradient block runs under SetVertexShaderProgram(nullptr), w=0.3/1.0 mixed"),
    "texture_perspective_enable_tests.cpp": (
        False, "no gradient vertex at w=1.0"),
    "w_param_tests.cpp": (
        False, "gradient block is fixed-function and carries a w=0.0 vertex"),
    # NOT excluded for using SET_VERTEX3F -- 3F is immediate mode too, and the
    # 3F-vs-4F reading is refuted by Shade_model/Fixed_* (4F at w=1.0 and
    # unpaired). These two fail the MEASURABILITY criterion in the docstring.
    "swath_width_tests.cpp": (
        False, "renders into a 2x-width AA surface and composites a checkerboard:"
               " framebuffer x is not fragment x"),
    "vertex_shader_rounding_tests.cpp": (
        False, "no measurable x rows in the census (its own content is too small)"),
}

BEGIN = re.compile(r"\bBegin\s*\(")
END = re.compile(r"\bEnd\s*\(\s*\)")
SV4 = re.compile(r"SetVertex\s*\([^;]*?,[^;]*?,[^;]*?,[^;]*?\)")
SV3 = re.compile(r"SetVertex\s*\(\s*[^,;()]*(?:\([^()]*\))?[^,;()]*,[^,;()]*,[^,;()]*\)\s*;")
SD = re.compile(r"SetDiffuse\s*\(([^;]*?)\)\s*;")
W1 = re.compile(r",\s*1\.0f?\s*\)$")


def scan(path):
    src = open(path).read()
    a = "PassthroughVertexShader" in src
    grad_colours = sv4 = sv3 = w1 = 0
    for m in BEGIN.finditer(src):
        e = END.search(src, m.end())
        if not e:
            continue
        blk = src[m.end():e.start()]
        if len(blk) > 4000:          # not a single immediate-mode draw
            continue
        colours = {d.strip() for d in SD.findall(blk)}
        v4, v3 = SV4.findall(blk), SV3.findall(blk)
        if len(colours) >= 2 and (v4 or v3):
            grad_colours = max(grad_colours, len(colours))
            sv4 += len(v4)
            sv3 += len(v3)
            w1 += sum(1 for v in v4 if W1.search(v))
    return a, grad_colours, sv4, sv3, w1


def main():
    src_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.isdir(src_dir):
        raise SystemExit("no test sources at %s" % src_dir)
    print(__doc__.split("Run:")[0].rstrip())
    print("\nsources: %s\n" % src_dir)

    rows = []
    for fn in sorted(os.listdir(src_dir)):
        if fn.endswith(".cpp"):
            rows.append((fn,) + scan(os.path.join(src_dir, fn)))

    cand = [r for r in rows if r[1] and r[2] >= 2 and r[3] > 0]
    other = [r for r in rows if r[1] and r[2] >= 2 and r[3] == 0 and r[4] > 0]

    print("A (passthrough in file) AND C (per-vertex diffuse gradient) AND an")
    print("immediate-mode SET_VERTEX4F in the gradient block:\n")
    print("   %-42s %6s %5s %6s  %s" % ("source", "colours", "sv4", "w=1.0", "confirmed by reading"))
    in_class = []
    for fn, _a, g, v4, _v3, w1 in cand:
        ok, note = CONFIRMED.get(fn, (None, "NOT CONFIRMED -- open the file"))
        if ok:
            in_class.append(fn)
        print("   %-42s %6d %5d %6d  %s %s"
              % (fn, g, v4, w1, "IN " if ok else ("out" if ok is False else "??? "), note))

    print("\nSame but SET_VERTEX3F (also immediate mode, implicit w = 1, so also")
    print("IN the class -- these are set aside by measurability, not the register):\n")
    for fn, _a, g, _v4, v3, _w1 in other:
        ok, note = CONFIRMED.get(fn, (None, "NOT CONFIRMED -- open the file"))
        print("   %-42s %6d %5s %6s  %s %s"
              % (fn, g, v3, "-", "IN " if ok else ("out" if ok is False else "??? "), note))

    unconfirmed = [r[0] for r in cand + other if r[0] not in CONFIRMED]
    print("\n%d of %d test sources reach the candidate list; %d are measurable"
          " class members:" % (len(cand) + len(other), len(rows), len(in_class)))
    for fn in in_class:
        print("   %s" % fn)

    if unconfirmed:
        print("\nUNCONFIRMED candidates -- the class claim is NOT established while")
        print("these stand, because each could be a third member:")
        for fn in unconfirmed:
            print("   %s" % fn)
        print("\nOpen each and check (a) which shader is live in the gradient block")
        print("and (b) whether every vertex in it is at w = 1, then add it to")
        print("CONFIRMED. Until then treat the enumeration as incomplete.")
        return 1

    print("\nThe class has %d members and both pair. The conjunction \"immediate"
          % len(in_class))
    print("mode and w = 1\" survives a filled 2x2, but two captures cannot separate")
    print("it from what they share -- QUADS/POLYGON, >= 512 px wide, SET_VERTEX4F --")
    print("and those give different blast radii. A third class member that PAIRS")
    print("while differing in one of those would narrow it with no new geometry;")
    print("otherwise the five captures in the investigation note are what can.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
