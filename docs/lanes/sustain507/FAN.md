# sustain507 Part D: the fan lever (#507)

A separate file from NOTES.md, so that this branch (`lane/sustain507-fan`) and
`lane/sustain507-levers` (Part C) fold without touching the same lines.

## D.2: fan duty in every soak sample (2026-09-28)

`thermal_state.py`'s one-call sample now also reads `/sys/class/gpio5_pwm2/`
`duty`, `period`, `state` and `speed`, as `"fan": {...}` in each thermal.jsonl
line. The `THERMAL:` line in run.log ends `fan duty <lo>-<hi> of <period>`.
A device without the node gives no `fan` key and no change to the line.

- Period is 50000 on both handhelds (lane.local's live read, 07:1x PDT), so
  duty/period is the share of full speed.
- `speed` is the Nova's tach rpm; the Thor's reads 0 (perfregimen NOTES).
- The selftest leg (`99-thermal-pause.sh`, `fan`) runs the real sample script
  locally, with FAN_DIR pointed at a fake node, so the shell loop's quoting
  is exercised as well as the parse.

It reaches soaks only after the dispatcher's next update window takes the
merged `docs/testing/` snapshot. It is not live on the merge.

## D.1: CUSTOM (fan_mode 6), not yet probed

Probing needs an idle device and a short held session under
`jobs/hold.sh take <dev> lane.sustain507`. At 14:30Z neither device was idle.
The Thor was held by lane.xbox for a title push, and the Nova was running
Part C's AUF OFF arm. So the probe is still open.

## D.3: not started

It is gated on D.1 finding a setting that holds more than 29000 duty.
