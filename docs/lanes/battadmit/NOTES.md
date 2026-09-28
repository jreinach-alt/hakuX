# lane.battadmit (#507): per-run battery admission

Owner, 2026-09-28 ~13:10 PDT: *"the dispatcher can put the Nova back into
service once it's charged enough to not trip the 15% based on the drain rate
and length of the run with about 5% wiggle room."*

## What changed

- `docs/testing/battery_admit.py` (new, shipped in the worker snapshot and
  in `SCRIPT_DEPS`). `check` decides one request; `learn` prints what it
  learned and from which result dirs.
- `docs/testing/dispatcher.sh`:
  - `battery_level`: reads `dumpsys battery`'s `level:`, cached at most 60 s
    in `$D/.battery_level.<label>`, one try with no retries (`ADB_RETRIES=0`).
  - `battery_admit`: called from `serve_one` after the affinity check and
    before the claim. If it refuses, `serve_one` returns 1 and the walk goes on
    to the next request.
  - `serve_queue`: the worker loop's queue walk, now a function so the head
    (`BATT_HEAD`) is reset on each walk.
  - `$rdir/battery.json` is written at the claim, and `t_device` is stamped
    into it just before `adb install`. Both `result.json` writers carry it as
    `battery` (`battery_start`, `need`, `rate`, `rate_src`, `rate_n`,
    `overhead_s`, `kind`, `runs`, `seconds`, `floor`, `margin`, `t_admit`,
    `t_device`, and `backfill_for` when it was a backfill).
- `docs/testing/jobs/selftest.d/99-battery-admit.sh`: 23 checks and 8 mutants,
  all green, and every mutant turns its case red (below).

## The rule

    need = 15 + 5 + rate(D, kind) x runs x (seconds + overhead_s) / 3600
    admit iff level >= need     (need rounded up to 0.1)

- **kind** is `soak` when the request has a title, and `pgraph` otherwise.
- **rate** is the p75 of D's last 10 results of that kind. Each result's rate
  is the fall in `pw.battery.capacity` from its first `thermal.jsonl` sample
  to its last, over the time between them, in %/h. Two kinds of run are
  excluded:
  - runs shorter than 180 s, because capacity is an integer: 1 % in 2 min
    reads as 30 %/h.
  - runs that started above 60 % (`BATTERY_LEARN_BELOW`). This exclusion is
    not in the brief. I added it after measuring. The Thor's last ten soaks
    today all ran at 77-85 % and all read **0 %/h**: plugged in near its
    charge limit, it holds its level. So an unfiltered p75 would teach
    rate 0, and at 20 % the Thor would admit a 36-minute soak. The same Thor
    went from 18 % to 5 % in one 36-minute soak today
    (`1-1790593205-lane.sustain507-3238469`). Admission only matters at low
    charge, so only low-charge runs set the rate.
- **overhead_s** is the p75 over the same last 10, per run, of
  `(DONE mtime - start) / runs - seconds`. `start` is the first of these that
  exists:
  1. `battery.json`'s `t_device` (runs from now on);
  2. the first thermal sample (older soaks: this misses the install, tens of
     seconds);
  3. the earliest file the run wrote (older disc runs: `suites.txt`, which is
     written after the build).
- **Fallback** when fewer than 3 results are usable: soak 21 %/h on the Nova
  and 10 %/h on the Thor (devwatch), a test disc at half that; overhead 120 s
  for a soak and 300 s for a disc. A disc run writes no `thermal.jsonl`, so
  **the pgraph rate is always the fallback** (10.5 / 5 %/h) until disc runs
  record battery samples. That is follow-up work, not done here.
- **Unreadable level** (adb transient, or the device is off adb): the request
  is admitted unchecked, and the log line and `battery.json` say so. An absent
  device is already requeued by `serve_one`'s own `device_present`, and the
  15 % hold stays underneath as the floor.

## The head is not starved

When the first request this device may serve (the head) does not fit, the
requests behind it that do fit are claimed as backfill, and each claim is
logged as `BATTERY: skip <id>: level L < need N (...)`. Backfill is allowed
only for `BATTERY_HEAD_WAIT_S` (1800 s) after the head was first refused.
After that the head reserves the device: nothing behind it is admitted
(`BATTERY: hold for head <id> ...`), the device charges, and the head is
claimed on the first walk at which `level >= need`, at most 60 s after it
fits because of the level cache.

Without that limit, every short run would take the charge the head is
waiting for. The level would then hover at the short runs' need (about 24 %)
and never reach the head's. The reservation is `$D/.battery_head.<label>`
(`{id, since}`). A different head starts a new clock, and the file is removed
when the head is admitted.

What a long run can wait: 30 min of backfill, plus the charge time from
there to its need. On the 500 mA port that charge time is long. The Nova at
its 36-min sustain soak needs 20 + 32.4 x 0.61 = 40 %.

## Drain rates learned from today's real results (2026-09-28)

`python3 docs/testing/battery_admit.py learn /home/justin/hakux-work/dispatch <label> <kind>`, run about 14:30 PDT:

| device | kind | rate %/h | n | overhead s | n |
|---|---|---|---|---|---|
| nova | soak | **32.4** (learned, p75) | 10 | 15.3 | 10 |
| thor | soak | **22.5** (learned, p75) | 10 | 22.0 | 10 |
| nova | pgraph | 10.5 (fallback) | 0 | 592.8 per run | 10 |
| thor | pgraph | 5.0 (fallback) | 0 | 393.0 per run | 10 |

Nova soak per-run rates, %/h:

| rate | result dir |
|---|---|
| 32.5 | `1-1790618696-lane.idlehaltdefault-845673` (15->11) |
| 28.1 | `1-1790606270-lane.dirtytlb-480001` |
| 42.5 | `1-1790606270-lane.dirtytlb-479942` |
| 33.5 | `1-1790582080-idlehalt-2124441` (24->20) |
| 16.7 | `1-1790582080-idlehalt-2124356` |
| 16.9 | `1-1790582079-idlehalt-2124275` |
| 25.1 | `1-1790582079-idlehalt-2124199` |
| 16.6 | `1-1790582078-idlehalt-2124125` |
| 16.8 | `1-1790582078-idlehalt-2124008` |
| 31.9 | `1-1790579572-pipeline413-1715785` |

Thor soak per-run rates, %/h. All started at or below 60 %. The ten newest
Thor soaks, at 77-85 %, read 0 and are excluded:

| rate | result dir |
|---|---|
| 21.5 | `1-1790593205-lane.sustain507-3238469` (18->5, 36 min) |
| 22.9 | `1-1790575472-rendermode474-965903` |
| 27.1 | `1-1790572033-lane.pacing-1078761` |
| 12.5 | `1-1790572033-lane.pacing-1078684` |
| 42.9 | `1-1790572033-adpf-2928981` |
| 19.1 | `1-1790572032-lane.sustain507-4131123` |
| 19.2 | `1-1790572032-lane.sustain507-4131088` |
| 15.4 | `1-1790572031-lane.sustain507-4131051` |
| 12.1 | `1-1790572031-lane.sustain507-4130999` |
| 10.2 | `1-1790572031-lane.sustain507-4130959` |

Both learned rates are above the devwatch fallbacks: 32 vs 21 on the Nova and
22 vs 10 on the Thor. At low charge the drain is steeper. Short runs also
quantize badly: a 4-min run that loses 3 % reads 42 %/h.

What this admits on the Nova today, overhead 15 s:

| run | need |
|---|---|
| 4-min soak | 20 + 32.4 x 255 / 3600 = **22.3** |
| 7-min soak | **23.9** |
| 36-min sustain soak | **39.6** |

So the Nova at 24 % would have served the 6-8 min queue it sat behind from
11:10 PDT, which is the owner's case.

## Proof (selftest 99-battery-admit)

The fixture history teaches rate 27 %/h and overhead 340 s exactly: four
low-charge Nova soaks at 12/18/24/36 %/h, plus one full-battery run, one Thor
run and one disc run that must not count toward the rate.

| case | check | mutant, red |
|---|---|---|
| learn | rate 27 learned n=4, overhead 340 n=5 | median instead of p75; LEARN_BELOW filter removed; label filter removed |
| fits | level 50 >= 38.3: claimed; battery.json 50/38.3/27; the log line names the inputs | FLOOR 50 |
| skip | level 30: long head stays queued, 300 s soak (need 24.8) claimed, `BATTERY: skip 0-long: level 30 < need 38.3` logged | a refusal ends the walk (`return 0`) |
| none | level 22: nothing claimed, walk=1 | admission call removed |
| starve | head refused 2000 s: the fitting short soak is held; at 39 the head is claimed and the reservation cleared | reservation check disabled |
| cache | two walks inside 60 s: one dumpsys | cache never trusted |
| result.json | both writers read battery.json | (the extraction runs the shipped code) |

I also ran, alone and green: 56-desktop-worker, 57-vsh-disc, 95-affinity,
97-dispatch-deploy (the snapshot and `SCRIPT_DEPS` closure include
battery_admit.py), 97-dispatch-snapshot-rename and 98-dispatch-late-device.
51-dispatch-hardening run alone: C, D, F, G, H and I (the serve_one paths)
are green. E and E2 fail alone only because they need the 10..50 chain's
functions (`clear_markers`, `finish_queue`). CI runs them in their shard.

## Host side: the exact change for lane.local (not applied here)

In `host-tools/device_reality.sh` (hostops's tool, lines ~109-146), the
battery hold's LIFT threshold changes from 80 to 20. The PLACE threshold stays
at 15. Concretely: wherever the script compares the level against `80` to
remove `hold/<dev>` (the `battery-hostops` hold), compare against `20`, and
update the hold's text from `device_reality lifts it at >= 80%` to
`device_reality lifts it at >= 20%; the dispatcher's per-run battery admission
governs above that`. Below 15 % nothing changes: the hold is placed, and
nothing claims. From 20 % up, `battery_admit` decides each run. Between 15
and 20 the hold, once placed, stays. That gap keeps the hold from flapping
on and off at 15.

Apply it in the same update window that makes this dispatcher live (a worker
re-execs on the `SCRIPT_DEPS` hash change). If the host tool changes first,
the Nova would come back at 20 % with no per-run check.

## Knobs (environment of the worker)

`BATTERY_ADMIT=off` turns it off. The others are `BATTERY_FLOOR` (15),
`BATTERY_MARGIN` (5), `BATTERY_HEAD_WAIT_S` (1800), `BATTERY_LEARN_BELOW`
(60), `BATTERY_CACHE_S` (60) and `BATTERY_RATES_TTL_S` (300, the learned-rate
cache in `$D/.battery_rates.<label>.<kind>.json`).

## For the next lane

- Do not learn the rate from high-charge runs (see above).
- The pgraph rate is the fallback until disc runs sample the battery.
  `run_disc.sh` could write the same `thermal.jsonl`.
- After this is live, `result.json`'s `battery.battery_start` lets a check ask
  whether low-charge runs measured differently.
