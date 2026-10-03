# lane.stallmeasure569: does the shipped shader pre-build remove first-play stalls? (#569)

State: ready

Lane: stallmeasure569        Issue: #569
Base: origin/master @ dbf2ebe915
Files: docs/lanes/stallmeasure569/NOTES.md, docs/lanes/stallmeasure569/OUTBOX.md, docs/lanes/stallmeasure569/PR.md, docs/lanes/stallmeasure569/pair_hitch.py
Prediction: none: analysis-only, no code or emulator change
Needs device: no (every reading is from dispatch/results already on disk)    Needs NDK: no

Analysis-only lane, no emulator code touched. Full method, tables and citations in NOTES.md;
relayed summary in OUTBOX.md.

**Answer: no, the shipped pre-build (`shaderprebuild569`, folded `b1cea467c6`, default on) does not
remove a title's first-play compile stalls, by design** -- it has no recorded pipelines to build
from on a device's first launch of a title. Kabuki's first launch under the pre-build code (32
hitches, worst 4.80 s) reads statistically the same as a cold baseline from before the mechanism
existed (37 hitches, worst 4.99 s). Two titles run for the first time today (ToeJam & Earl III,
Tron 2.0) both still hitch on shader compiles in their first two minutes.

**It does remove most of the stall on a replay of a title already recorded**: Kabuki's second
launch, the one clean same-content pair on disk (fixed route), cut whole-window hitches 34%
(32 -> 21) and its worst single stall 86% (4.80 s -> 665 ms). What remains on replay is content the
prior launch did not happen to meet (randomised opponent/arena inside the fixed route), not engine
overhead. DOA's pair moved the same direction but is confounded by its blind route meeting a
different opponent/stage each launch (shaderprebuild569's own W1b finding; NOTES.md section 4).

**Next ubershader step, ranked:** promotes `uberspike569/BUILD.md`'s own #2 ("persist the uber
combinations and pre-build them at boot," not built there by decision, over concern for
contaminating the "cold" reading) to #1, because `shaderprebuild569` has since shipped the exact
pattern this needs **and** already solved that concern with its own cold/warm falsifier leg; this
lane's Kabuki reading is the first production evidence the pattern delivers at this size. The
successor brief (`briefs/uberpersist569.md`) is drafted in OUTBOX.md for `lane.local` to dispatch.
`uberspike569`'s own #1 (a link-cost/interpreter-cost split arm) stays a cheap, useful diagnostic,
now ranked #2 since it decides a later fix rather than removing a stall itself. `NoContraction`
(#3) and the default flip (#4, owner's decision) are unchanged from uberspike569's ranking.

**Board note, not acted on here:** the `#569` tracker row's `blocked_on` is stale (still names
`litcompile569` at its attempt cap from 09-30; that lane folded and retired the same day, and the
other three shader lanes have since folded or retired too). Flagged in OUTBOX for a board request;
this lane does not edit `nv2a_issues.toml`.

## Local checks in place of CI
- `python3 -m py_compile docs/lanes/stallmeasure569/pair_hitch.py`: OK.
- No harness file and no emulator file changed, so `selftest.sh` and a dispatch run are not
  required for the fold (analysis-only; no code to build).
- `docs/testing/preflight.sh --allow-tracker`: run below.

Release note (none): analysis only, no emulator code changed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
