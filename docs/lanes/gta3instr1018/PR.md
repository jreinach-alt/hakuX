# GTA III dip frame: race-free render-pass-break counters, timed fence/copy/bind costs, and the in-car fen split

State: ready

Lane: gta3instr1018            Issue: #1049 #433
Base: master @ 2f2c11e2b3
Files: docs/lanes/gta3instr1018/FINDINGS.md, docs/lanes/gta3instr1018/NOTES.md, docs/lanes/gta3instr1018/PR.md
Prediction: none: no arm (this attempt reads already-captured logs; no new code, no pixel claim)
Selftest: none -- no code changed this attempt (the `99-dipwin-counters.sh` fragment from the earlier attempt is
already on master, via lane.gta3car1018's wholesale fold of this lane's own commits, unchanged)
Needs device: no    Needs NDK: no

Note: this branch's own `docs/lanes/gta3instr1018/PR.md`, `dipwin.h`, `draw.c`, `surface.c` and
`99-dipwin-counters.sh` commits are already ancestors of `master` (lane.gta3car1018 merged this lane's branch
wholesale, then folded). Merging `origin/master` here is therefore a no-op for all of this lane's code and
instrumentation -- `git diff origin/master -- hw/xbox/nv2a/pgraph/vk/draw.c hw/xbox/nv2a/pgraph/vk/dipwin.h
hw/xbox/nv2a/pgraph/vk/surface.c docs/testing/jobs/selftest.d/99-dipwin-counters.sh` is empty. This PR's own
diff against `master` is therefore docs-only (`docs/lanes/gta3instr1018/**`); gta3car1018's fold had to drop its
*copy* of this lane's `PR.md` to pass the exactly-one-PR.md fold gate, which silently deleted this file when
`master` merged in cleanly here (unchanged-vs-deleted resolves to deleted) -- recreated above.

## What this PR adds beyond gta3car1018's fold

Earlier commits on this branch (now shared with `master`) built `[dipwin]`: a race-free, per-60-flip
`hakuX-rpbrk` line in perflog builds, with `dipwin_read.py` to read it. First measured on foot only (blocked on
reaching the owner's in-car state through a dispatched run -- no Load verb in the route grammar, FINDINGS.md 3).

This attempt reused lane.gta3car1018's already-captured in-car logcats (`captures/gta3car1018/runs/c2-{O1,S1}`),
which ran this exact `[dipwin]` instrument in the car with `HAKUX_S2T_FB` off and on, to do the measurement the
brief's step 2(c)/(d) asked for -- no new device time was spent; the data was already on disk and unread by
this lane. FINDINGS.md section 6:

| | O1 (`HAKUX_S2T_FB` off) | S1 (`=2`) |
|---|---|---|
| ms/flip | 43.70 | 38.53 |
| render passes/flip | 90.00 | 66.11 |
| `fen` (ms/flip) | 11.92 | 7.53 |
| of which `rotfen` (real GPU fence wait) | 7.56 | 3.72 |
| of which `stale` (vertex-RAM span copy) | 3.93 | 3.47 |
| named timers summed (`fen`+`pipe`+`vsync`+`vcopy`+`sub`) | 16.68 (38%) | 11.38 (30%) |
| **untimed** | **27.02 (62%)** | **27.15 (70%)** |

Two results:
- `rotw` (the software wait for "has the render thread submitted") costs nothing in either arm, cross-checked
  against the independent, always-compiled `[rwait526]` line's own `rotate calls=... waits=0`. So the cost
  left in `fen` after `rotw` is a genuine GPU-execution wait (`rotfen`), not a software/scheduling stall; and
  `stale` is confirmed as a real, separate ~3.5-4.0 ms/flip cost (vtxstale1018's target) that does not move
  with the render-pass count the way `rotfen` does.
- The frame's largest component, in both arms, is **not** inside any `[dipwin]` timer: ~24-27 ms/flip (62-70%
  of the frame) is untimed, and it does not shrink when `HAKUX_S2T_FB` cuts the render-pass count and `fen`
  with it. FINDINGS.md 6.4 names the next timer (`draw.c`, the render-pass-begin-to-end draw-call issue path,
  not currently wrapped by any `DW_TIMERS` entry) for the next lane.

Release note (none): docs only, no code changed this attempt.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
