# Audit pass 1: PR #523, lane thermal507 (power per frame, cool-down gate)

Head audited: `4d8ba75b63`. Read: the diff of `soak_title.sh`,
`thermal_state.py`, `title_verdict.py`, `selftest.d/99-power-per-frame.sh`,
`selftest.d/99-thermal-pause.sh` (NOTES.md read for intent only).

Result: **1 MEDIUM, 3 LOW. No HIGH.** Goes to `needs-remediation`.

## MEDIUM

### M1. `first_pause_s` reports the cool-down gate's pause, not the run's

`thermal_state.first_pause()` takes `episodes(recs)[0]`. With this PR,
`recs` includes the `cool` samples the gate writes *before* `start`, and the
gate's own job is to wait while a pause device is set. So a gate that waited
on a pause produces an episode that ends before `start`, and `first_pause`
reports that one, with negative bounds, even when the run later paused.

Reproduced on the head (standalone script, samples in the shape
`thermal_state.py` writes): `cool` samples paused at 0 s and 20 s, clean at
40 s, `start` at 41 s, clean holds until +240 s, paused from +270 s:

    first_pause: (None, -41.0)
    THERMAL: pause thermal-pause-F8 1/1 began by +-41 s (paused in the first reading) ... | thermal-pause-F8 1/1 began after +240 s and by +270 s ...

Expected `first_pause_s` = `{after: 240, by: 270}`; the verdict writes
`{after: null, by: -41}`. `title_verdict.py`'s docstring defines the field as
"the time from the run's start ... to the first pause". This is the field the
lane's queued regimen comparison is meant to read (time to pause per
regimen). Every run that follows a hot one is exactly the case where the gate
waits on a pause, so the wrong value lands on the runs that matter most.
Bounded: the field is reported and not judged, and the void logic is not
affected (the pre-start episode's `before` is earlier than the mark, so
`in_window` does not select it).

Fix direction: take the first episode whose `before` is None or after
`origin(ok)` (a pause still set at `start` counts, with `after` None or
negative, which says "started paused"). Add a selftest leg with `cool` samples
paused before `start`. As written, the `void` leg's fixture has no `cool`
samples, so this leg can't catch it.

The `summary` line has the same shape: it describes the pre-start episode as
"began by +-41 s (paused in the first reading)". A reader of run.log gets a
`+-` offset. That part is LOW on its own, and M1's fix should cover it by
labelling or skipping episodes that ended before `start`.

## LOW

- **L1. Two origins for the same file.** `summary`, `--window`, `--power` and
  `first_pause` now measure from `origin()` (the `start` sample).
  `title_verdict.py`'s `pauses` list, when there is no mark, still uses
  `min(dev_ts(r) for r in read)`, which is now the first `cool` sample. With
  no mark, the two readouts of one run disagree by the cool-down wait.
  `--power` also filters its origin set on `not r.get("error")` where the
  others use `paused(r) is not None`. That is the same in practice, but it's
  a second definition.
- **L2. `COOLDOWN: waited N s` counts sleeps only.** `cool_waited` adds
  `THERMAL_COOL_EVERY_S` per loop. Each iteration also spends one adb call
  (now including `dumpsys -t 3`) and one python start. The reported wait and
  the cap run short of the wall-clock wait, by up to about a minute at the
  default 360 s cap. The `harness_health.py` overrun margin (+10 min) still
  holds.
- **L3. Mixed USB provenance averages silently.** `power_over` can average a
  window where some samples have a measured USB input and others only the
  `input_current_limit` bound. `usb_from` lists both, but `net_w` is then
  part-measurement, part-bound, and nothing marks it as a bound. This is rare
  (the USB `current_now` node either exists or it doesn't).

## Checked and clean

- The sign convention (`battery_w = -(i*v)/1e12`) matches the stated kernel
  convention, and the mutant leg pins it. `sign_suspect` withholds J/frame.
- A void run gets no J per frame: void runs have no fps windows, so
  `flips = 0`, and the `void` leg asserts it.
- Unread power fields are left out, never 0 (`parse_sample` requires a
  non-empty value, and `power()` requires ints).
- `mean_over`: the trapezoid over breakpoints inside the window, held flat
  outside, is correct. The weighted leg separates it from both naive means.
- Gate exits: unread and no-zone both exit 2 and break the loop, so a device
  without the zone is never held. The cap breaks and still starts the title.
  With `thermal_state.py` missing, `THERMAL_OUT` is cleared and the loop
  breaks. The gate runs before `perf_enter` and `am start`, and the selftest
  asserts that order.
- CI: `selftest` is red on this head with 2230 passed and 1 failed. The
  failure is `76-pr-sweep.sh` "a stale failure ALONGSIDE a live one is a live
  red", a file this PR does not touch. Every thermal and power section
  passes. It is not attributed to this diff, but the fold needs a green head,
  so a rerun after remediation should confirm it.
