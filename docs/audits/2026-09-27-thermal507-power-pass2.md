# Audit pass 2: PR #523, lane thermal507 (power per frame, cool-down gate)

Head verified: `20502ec594` (remediation `ea4675ae72` and `fe5940a6e2`, then a
merge of master). Each pass-1 scenario was re-run against this head, not
checked off by commit message.

Result: **clean.** None of the pass-1 scenarios can still occur. Goes to
`fold-ready`.

## M1. `first_pause_s` reported the cool-down gate's pause: fixed

`first_pause()` now keeps only episodes with `before` None or after
`origin(ok)`, and a pause still set at `start` returns `(None, 0.0)`.
Pass 1's reproduction, re-run on this head (`cool` samples paused at 0 s
and 20 s, clean at 40 s, `start` at 41 s, clean holds to +240 s, paused
from +270 s):

    first_pause: (240.0, 270.0)
    THERMAL: pause thermal-pause-F8 1/1 began by -41 s (paused in the first reading) ...;
      cleared by -1 s [in the cool-down, over before the start] | thermal-pause-F8 1/1
      began after +240 s and by +270 s ...

Expected `{after: 240, by: 270}` is what it gives now. The `+-41 s` offset is
gone, and the pre-start episode is labelled as being in the cool-down.
Two more cases: only a cool-down pause gives `None`, and a pause still set at
`start` gives `(None, 0.0)`. The selftest leg `waited-out` in
`99-thermal-pause.sh` covers this with `cool` samples before `start`, which
the old `void` fixture lacked.

## L1. Two origins: fixed

`title_verdict.py`'s `pauses` list uses `thermal_state.origin(read)` when
there is no mark, not `min(dev_ts)`. `--power` builds its origin from the same
`paused(r) is not None and dev_ts(r) is not None` set as `--summary`,
`--window` and `first_pause`. All four readouts now share one `origin()`.

## L2. `COOLDOWN: waited N s` counted sleeps: fixed

`cool_waited=$((SECONDS - cool_t0))` is wall time, taken before each read, so
the reported wait and the `THERMAL_COOL_MAX_S` cap include the adb and
python3 time.

## L3. Mixed USB provenance averaged silently: fixed

`power_over` sets `usb_bound` true when any sample behind the USB average
has only the `input_current_limit` bound, so a part-bounded `net_w` is
labelled a bound. The `mixed` leg (one bounded sample in six gives true) and
the `measured` leg (six measured samples give false) in
`99-power-per-frame.sh` separate the two cases. The set is taken over every
readable sample, including those held flat at the window's edges. That is
right, because `mean_over` uses those samples too.

## Tests

`99-power-per-frame.sh` and `99-thermal-pause.sh`, sourced locally with
`TESTING` set: 28 passed, 0 failed, both mutant legs included. The full
selftest was not run locally. On this head CI `build` is green and
`selftest` was still pending when this was written. Pass 1 recorded a
`76-pr-sweep.sh` failure in a file this PR does not touch. The fold needs
that job green, and the fold job checks it.
