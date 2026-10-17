# HAKUX_FIST_ROUND on by default for 0.5.1 (#939 (b))

State: ready

Lane: fistdefault1016          Issue: #939 [#433]
Base: master @ fb6ebcff40
Files: tcg/aarch64/tcg-target.c.inc, docs/lanes/fistdefault1016/NOTES.md, docs/lanes/fistdefault1016/PR.md, docs/testing/predictions/fistdefault1016-fistround.json
Prediction: docs/testing/predictions/fistdefault1016-fistround.json @ b2d162e4da115b8165a9917795af3cf6baedf30b7fd4afc28864ec833ea89bf3
Needs device: yes (Nova)    Needs NDK: yes

Flips `hakux_fist_round` (`tcg/aarch64/tcg-target.c.inc`) from default-false to default-true.
`HAKUX_FIST_ROUND=0` is now the escape hatch; any other value, or unset, is ON. The `hb_log`
line now says which way it was decided: `fist round=ON (default)`, `fist round=ON (env)`, or
`fist round=OFF (env HAKUX_FIST_ROUND=0)`.

lane.x1port1012 root-caused #939 (b) (the ring's lit side toggling in bursts) to aarch64's
bare `FCVTZS` on inline x87 FIST/FISTP truncating instead of rounding per the guest's RC, and
verified the fix on the Nova (run 13, `docs/lanes/x1port1012/PR.md`/NOTES.md). The owner's word
(10-16 ~19:00 PDT) is to ship it ON in 0.5.1. This lane only flips the default; no change to the
FRINTI emission, the x86_64 backend (already rounds), or any other switch.

This is emulator code (`tcg/`): the fold runs the device-run gate (Forza, 120 s, Nova), and the
owner will run a regression sweep on the resulting build separately.

Release note (rendering): Halo's menu ring no longer jumps back in bursts; float-to-integer
stores round as on the Xbox.

NOTES.md has the full evidence: the arithmetic cost (one extra, fully-pipelined FP instruction
per inline FIST/FISTP site, no measurement in the repo to cite), the trace from the guest's x87
RC through `gen_flcr` to aarch64's `FPCR.RMode` (including why round-toward-zero still truncates
with the switch on), and a grep showing no living doc (`docs/testing/*.md`, Android settings)
claims the switch is default-off -- only the history files in `docs/lanes/x1port1012/` do, and
those are left alone per the brief.

NDK/Android compile check: `android/gradlew --no-daemon assembleDebug` (JDK 21,
`arm64-v8a`), run in the foreground (background work does not survive this headless session).
`BUILD SUCCESSFUL in 8m 43s`, `GRADLE_EXIT=0`. The native build log confirms
`tcg/aarch64/tcg-target.c.inc` was actually recompiled (warnings at its existing lines 1678-1817,
unrelated to this change).

Prediction `docs/testing/predictions/fistdefault1016-fistround.json`: V and R are judged against
the fold's own device-run gate run (Forza, 120 s, Nova) -- this lane queues no device run of its
own, per the brief. T (round-toward-zero RC still truncates with the switch on) is a code-reading
leg, already answered in NOTES.md, with no device run needed. Not an A/B arm; the arms job skips
it, same as lane.x1port1012's own non-arm prediction for this switch.

`preflight.sh`'s `territory` gate FAILs: `docs/testing/nv2a_index.json is claimed by both
x1port1012 and fistdefault1016`. `[lane.x1port1012]` on `origin/board`'s `territory.toml` still
lists that file even though the lane already folded (`56fdef2c85`); a prior board update moved
`tcg/aarch64/tcg-target.c.inc` off that row onto this one but missed releasing `nv2a_index.json`
too. `territory.toml` is barred to lanes (AGENTS.md, "A lane cannot satisfy a gate it is barred
from fixing"), so filed `$DISPATCH_DIR/board-requests/fistdefault1016.md` asking the board to
release it from the folded lane (or drop it from this lane's own row instead -- this lane never
touches the file, so either side clears the gate). Every other preflight gate passes. NOTES.md
has the full trace. Marking this PR ready regardless, per AGENTS.md: a lane "must never be
blamed for a gate it cannot reach."

🤖 Generated with [Claude Code](https://claude.com/claude-code)
