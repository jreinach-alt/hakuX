# lane.nan-signalling-note -- PR #202: a third explanation for `-NaNs_NaNs`

Status: done, and remediated against audit pass 1 (0 HIGH, 2 MEDIUM fixed,
3 LOW all taken). Documentation only: one file,
`docs/testing/nv2a-hardware-gap-list.md`, section B. No code, no tool, no
prediction, no device.

## The brief

`nv2a-hardware-gap-list.md` listed `Attrib_float::-NaNs_NaNs` under "behaviour
that provably differs from hardware" with two candidate causes -- a V1.1-vs-1.0
silicon difference, or a golden from a different suite build. The tests tree
names a third at `src/tests/attribute_float_tests.cpp:55-57`: the hardware's
signalling-NaN handling is nondeterministic and is sometimes converted to a
quiet NaN. Record it where the list is read.

## What changed, after remediation

The insert now says four things rather than one:

1. **The two rows carry their reclassification in the cell.**
   `gap-list-b-resolved.md` -- folded as `28531197b6`, the direct parent of
   this branch's first commit -- ran both captures against a desktop build of this tree. `TexFmt_R6G5B5`:
   the emulator is byte-identical to our console, so the golden is the outlier.
   `-NaNs_NaNs`: the emulator is 14,637 px from our console, so the large
   defect is ours and the 60 px is a residual. A reader scanning the table
   under the section heading now gets that from the row.
2. **The "Either ... or" dichotomy above is gone**, replaced by what
   `gap-list-b-resolved.md` measured per row. It was enumerating two causes ten
   lines above a paragraph saying there are three.
3. **The quote is all three sentences.** The third -- *"As pgraph operates on
   integers and does a conversion from float back to int, it may be better to
   fall back into setting raw values without doing the float conversions"* --
   is the test author's own guess at the mechanism, and it points at the
   submission path, not at the GPU. Truncating it is what made "needs a second
   console" look like the only move.
4. **The prescription is offline work, not a second Xbox.** Two of the three
   candidates are decidable with what is on disk: the suite-build candidate
   from the goldens' provenance (`6e159f15`) and a build from the XBE we ran;
   the conversion-path candidate from the XBE itself, with the same
   disassembly #74 used to classify all 61 FIST/FISTP sites in this exact XBE.
   Only the silicon-revision candidate needs another console, and it is the
   last worth buying: a 60 px residual on a capture where our own emulator is
   14,637 px out.

## What the next lane should not repeat

- **Do not prescribe hardware this project does not have without grepping for
  what the tree already measured.** The first version of this insert asked for
  a second console for a question whose two other candidates were answerable
  offline, and it did so one commit after `gap-list-b-resolved.md` reclassified
  the row. The counter-evidence was in this branch's own parent.
- **A withdrawal has to be marked where the premise is read.** The correction
  originally sat ten lines below an unmarked table row and an unmarked "Either
  ... or". A reader scanning the tables for "what differs from hardware" takes
  away the row and stops.
- **Quote the whole comment when the dropped sentence is the actionable one.**
  Sentences one and two are quotable; sentence three is what tells you where to
  look.
- **`-NaNs_NaNs` vs `-NaNq_NaNq`.** Signalling and quiet differ by one letter
  and the goldens directory holds sanitised filenames, not test names
  (`gap-list-b-resolved.md` records that trap). A comparison that mixes them
  looks plausible and means nothing.

## Not done here, deliberately

`xbox-calibration-2026-09-20.md:92-96` still carries the same two-cause reading
for both captures. It is a dated record of one run and is not this PR's file --
editing it would put this lane on a path its `Files:` line does not claim. The
gap list is what briefs are written from, and it is the one corrected.
