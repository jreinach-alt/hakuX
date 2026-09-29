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
- **Unreadable level**: #587 admitted the request unchecked. Since
  `lane/battadmit-2` the dispatcher **fails closed** instead: nothing is
  claimed, and the next walk reads the level again. See "Follow-up" below.

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

## Status

2026-09-28: PR #587 folded as `2c950e0a1e`, and live since the 15:20 PDT
restart. The follow-up (lane.local's addendum, 17:00 PDT) is on
`lane/battadmit-2`.

## Follow-up (lane/battadmit-2): fail closed, and the Nova's link floor

**Why attempt 1 of this resume did not finish.** It left nothing behind: no
commit, no `lane/battadmit-2` branch, and no comment on #587 or #507. The
worktree was still on `lane/battadmit` at #587's head, 54 commits behind
master. So it ended before any work, and nothing I can read records why.
Attempt 2 cut `lane/battadmit-2` from master at `2c950e0a1e`, the #587 fold.

### 1. An unreadable level fails closed

At 16:41:17 the live log read `BATTERY: level unreadable on nova; admitting
1-1790625720-arms-litcompile569-base-3794892 unchecked`. adb.log has
`ee317437: connection terminated` at 16:41:17.813, so the link was failing,
and the run voided.

Now `battery_admit` claims nothing when `dumpsys battery` gives no level:
- The walk's other requests are refused without another read
  (`BATT_WALK_UNREAD`, reset by `serve_queue`). With the link down, a read
  costs up to `ADB_QUICK_TIMEOUT`, and it used to be paid once per queued
  request.
- One log line per episode: `BATTERY: level unreadable on <dev>; not claiming
  <id>, reading again at the next walk`. On recovery it logs `BATTERY: level
  readable again on <dev> (<L>) after <N>s unreadable`.
- A device that is off adb entirely is now refused here too, before the claim.
  Before this, `serve_one` claimed the request and then requeued it.

A single WSL-interop failure costs one walk (seconds), not a run. The helper's
own failure (exit 2, a malformed request) is still admitted unchecked. That
is a request the helper cannot parse, not a link.

Other selftests with a fake adb that reports no level now need
`BATTERY_ADMIT=off`. Among the dispatcher fragments, that was
51-dispatch-hardening's serve_one driver.

### 2. The Nova's link floor: 30

The adb.log errors hostops reported are real (`ee317437: connection
terminated: read failed`, each paired with `remote usb: N - write terminated:
Input/output error`). But **they are not a clean threshold in the level.** I
read every error on 09-26..28 in
`/mnt/c/Users/Justin/AppData/Local/Temp/adb.log` against the Nova's
`pw.battery.capacity` in the result dirs' `thermal.jsonl`, nearest sample.
`python3 docs/lanes/battadmit/link_floor.py 3` reprints the per-run table,
over the last 3 days of results.

Clusters and the Nova's level:

| time (PDT) | level | result dir at the time |
|---|---|---|
| 09-27 20:59-21:09 | 27 | `1-1790559842-lane.pacing-2277012` |
| 09-27 21:58 | 21 | `1-1790559849-idlehalt-2278164` |
| 09-27 22:30-22:32 | 63-64 | `1-1790559882-lane.pacing-2288269`, `-2288358` |
| 09-27 23:10-23:11 | 61 | `1-1790569178-idlehalt-3064707`, `-3064828` (the "frozen" Nova, restored by pnputil) |
| 09-28 00:30 | 35 | `1-1790575472-rendermode474-965991` |
| 09-28 00:40 | 29 | `1-1790575472-rendermode474-966037` |
| 09-28 01:00-01:16 | 19-13 | `1-1790575939-lane.pacing-1078282`, `-1078334` |
| 09-28 15:55-15:56 (7) | 40 | `1-1790624588-forzadecay414-3394828` |
| 09-28 16:30-16:37 (12) | 29-27 | `...-3394828-r2`, `...-3394871-r2`, `-r3` |
| 09-28 16:41-16:51 (3) | 27 or below | `1-1790625720-arms-litcompile569-base-3794892`, admitted unchecked |

Per Nova run (09-27 19:30 to 09-28 16:40, 67 runs), by the lowest level the run
reached. A run counts if adb.log has an error from 60 s before its first sample
to 120 s after its last:

| lowest level | runs | runs with a link error | run hours |
|---|---|---|---|
| 10-19 | 5 | 2 | 0.37 |
| 20-29 | 12 | 6 | 1.01 |
| 30-39 | 13 | 1 | 1.37 |
| 40-49 | 17 | 1 | 1.67 |
| 50-59 | 8 | 0 | 0.73 |
| 60-69 | 10 | 4 | 0.96 |
| 70-79 | 2 | 0 | 0.76 |

Below 30 %, **8 of 17** runs lost the link. In 30-59 %, **2 of 38** did. That
is the level the brief asked for, and `FLOOR_BY_LABEL = {"nova": 30.0}` in
`battery_admit.py` sets it. A Nova run is admitted only if it is predicted to
end at 30 plus the owner's 5 or more: `need = 30 + 5 + drain`. The Thor keeps
15. `BATTERY_FLOOR_<label>` in the worker's environment overrides the table.

What this floor does not cover, so no one reads it as a cure:
- **High-charge failures exist.** 60-69 % had 4 of 10. The 09-27 22:30-23:11
  pair of episodes both ended in a dead USB node, restored by `pnputil
  /restart-device`. That is a second cause, and it is not level-gated.
- **Low charge does not always fail.** 09-28 10:30-11:15 ran seven soaks from
  26 % to 11 % with no error (`1-1790582080-idlehalt-2124356` through
  `1-1790618696-lane.idlehaltdefault-845673`). The floor lowers a rate. It
  does not remove a threshold.
- **Every 09-28 afternoon cluster up to 16:37 fell in a forzadecay414 soak**:
  its two requests and their reruns, at 27-40 %. The two forzadecay414 soaks
  just before, at 44 and 39 %, had none. This lane does not separate whether
  the cause is Forza's load (the port's current) or the charge. `battery.battery_start` in
  `result.json` plus adb.log, over the next days, can answer it.

**The cost.** The Nova charges idle on the 500 mA port at about 8.5 %/h. It
was at 11 % after `1-1790618696-lane.idlehaltdefault-845673` (11:15) and at
46 % at the start of `1-1790618748-lane.idlehaltdefault-846115` (15:20). From
hostops's 15 % hold, a 7-min soak now needs 30 + 5 + 32.4 x 435 / 3600 =
**38.9 %**, about 2.8 h of charge. At floor 15 it needed 23.9 %, about 1 h.
The Nova does fewer runs per charge cycle, and fewer of them void.

### Host side, updated

The change to `device_reality.sh` for lane.local is unchanged: place the hold
below 15 %, and lift it at 20 % instead of 80 %. On the Nova the dispatcher's
floor of 30 then governs from 20 up: nothing is admitted below 35 plus the
run's drain. hostops's current manual hold on the Nova ("lifts it at >= 50%")
can go once this is live.

### Proof (99-battery-admit, now 57 checks and 16 mutants)

| case | check | mutant, red |
|---|---|---|
| unreadable | dumpsys fails for two walks in one worker: nothing claimed (walk=1 twice), one `level unreadable` line, 3 dumpsys for 3 walks over 2 requests; at 50 the third walk claims the head and logs `readable again` | admit on unreadable (`return 0`); per-walk flag ignored (5 reads); log every walk |
| nova floor | no `BATTERY_FLOOR_nova`: at 50 the 2100 s soak (need 53.3) waits, the 300 s one (39.8) is claimed, `battery.json` floor 30, the line says `floor 30 + margin 5` | table emptied |
| thor floor | `check` on the thor records floor 15 | every device at 30 |

The earlier cases run the nova at `BATTERY_FLOOR_nova=15`, so their numbers
(38.3, 24.8) stand. Their FLOOR-50 mutant would now be masked by that
override, so it became MARGIN 50.

## For the next lane

- Do not learn the rate from high-charge runs (see above).
- The pgraph rate is the fallback until disc runs sample the battery.
  `run_disc.sh` could write the same `thermal.jsonl`.
- After this is live, `result.json`'s `battery.battery_start` lets a check ask
  whether low-charge runs measured differently.
