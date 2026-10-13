# hangwatch: catch a frozen title that starves the GPU, spins the vCPU and silences the disc, even with non-flat audio

State: ready

Lane: hangstall1013            Issue: #433
Base: master @ 93cd7ca1be (merged into lane/hangstall1013, no rebase)
Files: docs/testing/hangwatch.py, docs/lanes/hangstall1013/**
Prediction: none: analysis-only
Needs device: no    Needs NDK: no
Release note (none): offline test-harness change to the hang detector used by pathfind's held runs; no player-visible effect.

`hangwatch.py` missed two real Nova freezes (Voodoo Vince, Die Hard: Vendetta, #973 class) because its one HANG
rule required quiet audio, and a frozen title can keep driving the APU with a non-flat hum or ambience forever, and
because Die Hard's busy loop was spread across too many PCs for the pc-share pin test to hold.

Adds a second detection arm, `stalled`: still frames + GPU unfed (fifoskew kicks=0) + vCPU never idle (idle_us, the
same idle half the existing `pinned` test already used) + disc silent (pic14 raise=0), all held for HANG_S (90 s,
unchanged). The existing `pinned` arm (still+quiet+pinned) is untouched and still catches the Whiteout calibration
case. A signal whose log lines are entirely absent (no fifoskew, no pic14) can never confirm `stalled`, consistent
with how `quiet`/`pinned` already treat missing telemetry. `start()/look()/close()` keep their signatures;
`pathfind.py`'s three call sites need no change. `scan()` keeps its `pinned`/`quiet`/`pinned+quiet` keys
(`docs/lanes/hangwatch/calibrate.py` depends on them) and adds `stalled` alongside. `look()`'s `reason` string now
names which arm fired. Docstrings corrected: "quiet" means no new non-flat audio window, not no sound.

Measured the new `scan` against all three logs the brief names (matches its table); against all 40 Nova
screen-logcats from 10-11 to 10-13 and every banked Playable run with a kept logcat (81 unique files after dedup):
only the two known freezes reach 30 s or more on `stalled` (Voodoo Vince 2035 s, Die Hard 261 s); the largest
non-freeze stretch is 18 s (an ordinary loading/cutscene pause in a run banked as "gameplay", not a hang). Margin
to HANG_S=90 s is 72 s (~5x); HANG_S does not need to change. No banked Playable reaches HANG_S on `stalled`, so
there is no WAITING stop.

Selftest (`docs/testing/jobs/selftest.d/59-hangwatch.sh`, unchanged) extended with real-line-shaped fixtures (never
linked to actual run folders) for: Voodoo Vince's shape (HANG on `stalled`), Die Hard's shape (HANG on `stalled`
despite low pin share), KOTOR II's load shape (not a HANG — disc keeps interrupting), missing-fifoskew and
missing-pic14 cases (`stalled` never fires). All pre-existing cases, including the Whiteout `pinned` HANG, still
pass. 27 checks total, all green, including through the harness's own `selftest.sh`.

Two required mutants run against temp copies (not committed): dropping the disc test fails the KOTOR II case;
dropping the `stalled` arm entirely (today's code) fails both the Voodoo Vince and Die Hard cases. Full writeup,
including the per-file figures and the fixture/mutant details, is in `docs/lanes/hangstall1013/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
