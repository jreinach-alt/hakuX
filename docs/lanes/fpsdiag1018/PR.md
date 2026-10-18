# fpsdiag1018: one FPS lane for GTA III, Blinx 2, Fable -- known/not/could-be and a diagnostic tool (#433)

State: ready

Lane: fpsdiag1018             Issue: #433
Base: master @ e34f8ffa77
Files: docs/lanes/fpsdiag1018/**, docs/testing/perf/fpsdiag/**, docs/testing/jobs/selftest.d/99-fpsdiag.sh
Prediction: none: analysis-only plus an offline host tool; no renderer/emulator code changes, no device arm
Needs device: no    Needs NDK: no
Release note (other): none -- a host-side analysis tool, no emulator/renderer code touched

One lane for the GTA III, Blinx 2, and Fable fps misses, replacing the separate per-title threads that had
stalled: what is known, what has been measured out, a ranked list of what is left, and a tool that answers
the ranked list directly from a capture instead of by hand.

- `docs/lanes/fpsdiag1018/FINDINGS.md`: one page of known measured fps per title; eight ruled-out causes,
  each with the measurement that ruled it out and the scope that measurement actually covers; a ranked list
  of what is left, each row naming its own confirm/refute measurement and whether an instrument for it
  already exists.
- `docs/testing/perf/fpsdiag/fpsdiag.py`: `analyze`/`gaps`/`capture`. `analyze` cuts a capture into 60-flip
  windows, classifies each against the title's own fps bar, and reports every ranked candidate as
  "supported", "refuted", or "not measured" -- never from fewer than three windows of each class, never
  "refuted" for a candidate whose tag the capture never carries, and never scoring a window that holds a
  boot/pipeline-warmup marker, a save-state load, or a frozen (zero flip advance) moment. `gaps` lists which
  candidates a given capture (or the tool in general) cannot yet measure. `capture` attaches to an
  already-running session and records logcat plus periodic host-side samples; it reads only, never launches,
  sends input, or changes a setting.
- Run against the four real captures on disk for these three titles (FINDINGS.md section 4): closes two of
  the ranked list's open scope gaps with new measurements, rules out ART GC pause as a cause in all four, and
  surfaces one open, unresolved tension between two GPU-saturation measurements that the tool cannot yet
  resolve on its own (needs a time-range split this version does not have -- named as a gap, not guessed at).
- `docs/testing/jobs/selftest.d/99-fpsdiag.sh`: synthetic-fixture selftest. A planted cause reads
  "supported" while a small measured effect reads "refuted" and a data-less candidate reads "not measured",
  together, in one run; swapping which side of the data carries the plant flips the verdict; a fixture
  missing a required tag reads "not measured", never "refuted"; a boot-marker, save-state-load, or frozen
  window is excluded from both classes and counted separately. Found and fixed two real bugs in the tool
  itself along the way (both re-checked against all four real captures afterward -- no change to anything
  already written).
- `docs/lanes/fpsdiag1018/CAPTURE.md`: what to run alongside the next time any of these three titles is
  being played, to fill in the measurements nothing on disk has yet -- not a request for a new play session.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
