Lane: nightlywrap1010            Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 1878dbf06d
Files: docs/testing/nightly_build.sh, docs/testing/jobs/selftest.d/86-nightly-notes.sh, docs/lanes/nightlywrap1010/NOTES.md, docs/lanes/nightlywrap1010/PR.md
Prediction: none: harness only, no device arm
Needs device: no    Needs NDK: no
State: ready

## What this fixes

`lane_body_line()` in `docs/testing/nightly_build.sh` read a lane's `docs/lanes/<lane>/PR.md` Release note with a
single-line `sed | head -1`, so (1) a lane that wraps a long note onto following lines published only the first
line, cut mid-sentence (`docs/lanes/surfgpudefault1009/PR.md`, fixed by hand last night), and (2) an unfilled
template line whose category parenthetical still has the literal `performance|stability|rendering|other|none`
in it failed the regex outright and was dropped (`docs/lanes/restoreleak1009/PR.md`).

`lane_body_line()` is now a line-by-line loop: the category group accepts anything but `)` (so the unfilled
template's `|`s no longer break the match -- it is read as text starting with "none", which the existing
none-detection in the caller already drops), and continuation lines are joined with single spaces until a blank
line, a markdown heading, or another `Key:` line. Output shape (`category<TAB>text`) is unchanged.

Release note (none): harness only

## Verification

`SELFTEST_ONLY="86-nightly-notes.sh" bash docs/testing/jobs/selftest.sh`: 96 passed, 0 failed, foreground. New
fixtures cover a one-line note (unchanged), the 3-line wrapped note, a note immediately followed by a heading
with no blank line, and the unfilled template line -- each shown to fail against a literal copy of the replaced
function before passing against the real one. See `docs/lanes/nightlywrap1010/NOTES.md` for detail.

Full `selftest.sh` (~60 min) not re-run here; the fold runs it before folding.
