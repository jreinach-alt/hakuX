# usagemode1009: usage Low is a read-time cap, re-evaluated every tick (#433)

State: ready

Lane: usagemode1009      Issue: #433 (0.5)
Base: master @ 4f2403d076
Files: docs/testing/lane.sh, docs/testing/jobs/usage/mode.sh, docs/testing/jobs/selftest.d/89-usage-mode.sh, docs/testing/jobs/selftest.d/99-lane-model-file.sh, docs/lanes/usagemode1009/PR.md
Prediction: none: harness change, no emulator code
Needs device: no
Needs NDK: no
Release note (none): harness only.

Usage Low (jobs/usage/mode.sh) used to rewrite `LANE_MAX`, `MODEL_LANE_ESCALATED` and every
`briefs/*.model` on the way in, and restore them from a snapshot on the way out. The snapshot
was taken once, so a restore would have brought back model pins removed since it was taken.
Low also only ended when the clock passed `week_end_epoch`, a value meter.py has already moved
to the next week by the time mode.sh reads it, so Low never ended on its own.

Now:

- mode.sh only creates or removes `$WORK/usage/low-active` (plus `PATHFIND_MODEL_CALLS_MAX`,
  whose normal state is absent, and the hostops heartbeat drop-in). It rewrites no dial and
  no `.model` file, and keeps no snapshot.
- lane.sh reads `low-active` at every start and resume: `LANE_MAX` is capped at
  `USAGE_LOW_LANE_MAX` (3), and any model other than Sonnet/Haiku -- a brief's `.model` or the
  escalation model -- runs on `USAGE_LOW_MODEL` (claude-sonnet-5). An explicit `HAKUX_MODEL`
  still wins.
- Every tick re-evaluates, with no latch: Low at >= `USAGE_LOW_PCT` (80) % used or
  >= `USAGE_LOW_PROJ` (90) % projected at reset; back to Normal under 80% used and under
  `USAGE_NORMAL_PROJ` (75) % projected. A tick that changes nothing logs nothing. A mode
  file and `low-active` that disagree are reconciled on the next tick.

Selftest: 89-usage-mode.sh rewritten for the new contract (low/normal leave limits.env and
`.model` files byte-identical; hysteresis both ways; no latch; projection trigger; dial
override; self-heal). 99-lane-model-file.sh gains three Low legs and a mutant that drops the
cap (red). `SELFTEST_ONLY="89-usage-mode.sh 99-lane-model-file.sh"`: 72 passed, 0 failed.

Not covered by a selftest: the `LANE_MAX` cap under Low (lane.sh counts live systemd units).
