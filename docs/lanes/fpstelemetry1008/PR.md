# fpstelemetry1008: one cause table for the below-bar titles -- perflog + GPU xfr + frame trace on the Nova (#433)

State: ready

Lane: fpstelemetry1008      Issue: #433 (dispatched directly, no tracker issue)
Base: master @ 93fbc525fc (merged in after §3's device runs; no conflicts, no code changed)
Files: docs/lanes/fpstelemetry1008/NOTES.md, docs/lanes/fpstelemetry1008/PR.md
Prediction: none: telemetry survey, no golden, no A/B arm
Needs device: yes (Nova; 2 fresh requests this session, both DONE, see NOTES.md §3)
Needs NDK: no
Release note (none): analysis only; no emulator or Android code touched.

One cause table (NOTES.md §7) covering 11 below-bar titles: two measured fresh this
session on the Nova (MechAssault 2, Buffy — perflog + `HAKUX_GPUXFR=1` +
`HAKUX_FRAMETRACE=1`, decomposed with `decompose.py`/`xfrsurvey.py`/`sdsurvey.py`), nine
attributed from existing data at zero further device cost (NFS Most Wanted, LOTR ROTK,
Hulk UD, NHL 2K3, Spider-Man 2, Midnight Club II, Ninja Gaiden Black, Dead or Alive 3, NBA
Live 2005). 11 more titles are listed with reasons for exclusion (route/input defects,
thermal-paused figure, not actually failing fps, gameplay unconfirmed, not on the Nova) so
the below-bar count is not silently short, plus three (Pilot Down, Amped 2, Arctic
Thunder) named as reachable but not run this session (no route, or budget).

Findings worth flagging on their own: MechAssault 2 splits into two regimes (guest-CPU-bound
in most windows, render-thread-saturated in the worst decile, not explained by
surface-download finishes); `HAKUX_FRAMETRACE=1` produced no frame-trace data in either
fresh run; Buffy's fresh-run fps share (3%) disagrees sharply with its recorded verdict
(55%) because the two runs take different routes through the title, not a regression. See
NOTES.md §1 for why the brief's `prequeue.py` gate step, read literally, would skip every
below-bar title (and how that was resolved, per the owner's addendum), §2 for the full
gate/route/ISO audit, and §6 for what each instrument cannot see.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
