# collapse433: Battlefield 2 on the Nova is GPU-bound in heavy views; the Thor collapses were heat

State: ready

Lane: collapse433            Issue: #433
Base: master @ 8e3b1f2ad2
Files: docs/lanes/collapse433/PR.md, docs/lanes/collapse433/NOTES.md, docs/lanes/collapse433/OUTBOX.md, docs/lanes/collapse433/pacetab.py, docs/lanes/collapse433/joinread.py, docs/lanes/collapse433/badgood.py, docs/lanes/collapse433/modecmp.py, docs/lanes/collapse433/gpufit.py
Prediction: none: analysis-only (diagnosis; three Nova diagnosis soaks, no arm, no emulator change)
Needs device: yes (three Nova soaks, done)    Needs NDK: no

Diagnosis only. Details, citations and tools are in `NOTES.md`.

**Battlefield 2: Modern Combat (Nova) does not collapse. It is GPU-bound
whenever the view is heavy.** Perflog soak `1-1790919561-lane.collapse433-390126`
splits it by the draws in a frame:

| draws/frame | fps | GPU ms/frame | fence wait ms |
|---|---|---|---|
| 600-1200 | 27.6 | 21.8 | 1.3 |
| 1800-2400 | 18.9 | 34.9 | 11.4 |
| 2400+ | 16.0 | 40.0 | 16.8 |

At ~1,800+ draws the GPU needs more than the 33.4 ms that 30 fps allows, so
frames take 3 VBLANKs. The 514 s confirmation's 66.5% is that mix.

- **Ruled out:** heat (Nova, no pause, `throttling 0`); the PGRAPH lock
  (`[lock474]` wait is ~1.7% of wall time, the same in good and bad
  windows); shader and pipeline compiles; the UBO ring.
- **Turnip sysmem** (`-601955`): heavy-view GPU time is unchanged
  (35.5 vs 34.9 ms). Two of its frames also went near-black, unexplained.
  Not a fix.
- **Max regimen** (`-967641`): the default regimen holds the Nova's GPU at
  401 MHz. 55 default-regimen runs on disk read mostly 401; 206 max runs
  never read below 615. At 615 MHz heavy-view GPU time falls only 12-17%,
  and no heavy window reaches 30.
- **The lever:** GPU time is ~12-14 us per draw, and that cost does not
  shrink with clock or render mode. That points at a per-draw stall or
  memory fetch on the GPU, not shader work. NOTES section 8 gives the next
  lane's first measurements.

**Play was confirmed.** Frames from the soaks show the player in the level,
the view moving and ammo falling. The blind route ends facing a wall with
an empty gun, so the 514 s run's all-30 stretch after ~300 s is probably
that, not representative play.

**The Thor collapses (BF2 and Blood Wake) were heat.** Both runs used the
MAX regimen. Each fell in one step to a 5-7x lower rate 4m56s and 8m10s
after launch, with a clean VBLANK clock: the thermal-pause signature. There
is no thermal record for those runs. The Nova runs the same route offsets
without a step.

**Blood Wake (Nova, accepted Playable) was mostly not being played.**
From mark+131 s to the end (~536 of 667 s) every counter goes flat. Guest
idle is 0 in one user-mode loop, there is no new code, a third of the
vertex traffic, and texture queries fall 1200 -> 32. That is very probably
a static screen the blind route never leaves; no frame after the mark
exists to say which. **Audio burst (one sentence):** the 21-callback burst
at 10:44:51 is the transition into that state, a load-shaped code burst,
not a gameplay stall, and BF2 shows no matching pause. The run should be
re-checked with `--frames-every`.

Local checks (no CI while offline):
- `bash docs/testing/preflight.sh --allow-tracker`: passed, territory ok.
  The coverage gate did not run, because `gh` returns 403.
- No harness or emulator files changed, so `selftest.sh` and a head-build
  run are not required.
- The three soaks were built from this branch at `8b45e7c15c` (docs-only
  over master).

Release note (none): diagnosis only, no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
