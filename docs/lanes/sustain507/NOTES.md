# lane.sustain507 -- MAX vs the device defaults over 30 minutes (#507), and #424's Thor leg

Base: master @ f82e7e87fe (PR #533 folded). This lane measures and changes no code.

## 0. State of the instruments, 2026-09-28 03:15Z

- The dispatcher's snapshot (`dispatch/bin/soak_title.sh`) accepts `PERF_REGIMEN=default`
  (`case ... max|rest|off|default`). The first read, a few minutes earlier, found only
  `max|rest|off`: the update window fast-forwarded it in between. So #533 is live.
- On the Thor, MAX is performance_mode 2 with fan_mode 4 (SMART), and REST and the defaults
  are perf 0 / fan 4 (`perf_regimen.json` of `0-0-x-1790557233-hostops-810152`). **On the
  Thor, MAX and the defaults differ in performance_mode only.** The fan is SMART in both.
- The thermal samples (every 30 s) carry battery current, voltage and capacity %, and USB
  current and voltage. They do not carry `charge_full`, and it is recorded nowhere on the
  host, so the Thor's battery capacity is unknown to this lane (section 3).

## 1. The prediction and the reader

- `docs/testing/predictions/sustain507-regimen.json`, registered before any run. Arms: the same
  apk (f82e7e87fe), `--env PERF_REGIMEN=max` against `--env PERF_REGIMEN=default`. Legs: L0
  (instrument), P1 (power cut 0.5-1.5 W over the same span), P2 (Crimson and MechAssault 2 lose
  no fps), P3 (GTA: MAX pauses and collapses, the defaults do not pause and hold stability >= 0.90).
  The repeat rule and the refuting results are in the file.
- `regimen_read.py` (this dir) is the reader. It reuses title_verdict.py's logcat parser and
  thermal_state.py's pause and power functions, and does not void the windows after a MAX pause.
- MechAssault 2 is in P2 as content-capped because of one run on disk: at MAX over 24 min,
  `hostops-810152` read median 30.0 and p10 30.0 with no pause, xo-therm max 74.2 C, and a
  plateau from 6.9 min. That run is why "MAX trips in 5-9 min" is not universal: it depends on
  the title's load.

## 2. Plan and pilot

- The pilot gate: one 1800 s run is ~36 min estimated, over the 30 min unreviewed limit on its
  own. First batch (30 min exactly): Part B's first Thor pair (2 x 630 s) and a 450 s GTA run at
  `default` as Part A's pilot. The pilot checks the regimen read-back, the gate, the mark and the
  power fields.
- Then the six Part A runs in the registered order: Crimson A->B, GTA B->A, MechAssault 2 A->B,
  and Part B's second pair.

## 3. Battery capacity

Not assumed. regimen_read.py pools the battery's energy (the integral of battery_w) over the
capacity % it cost. On hostops-810152 this gives 1.27 Wh for 1 %, which bounds the pack at 64-127 Wh.
That is implausible for a handheld, so either the gauge's % lags or the 30 s current samples
are biased. Hours stay blank unless the pooled range is narrow. The clean answer is one read of
`/sys/class/power_supply/battery/charge_full` (and `charge_full_design`, `energy_full` if
present) on the Thor, asked of the host on #507.

## Part B: #424's Thor leg

- The live registration is `tbflip424-blinx2.json` (00c2840810, which replaced tbflip424-blinx.json
  and names it). Blinx, `--route survey`, 540 s, Thor, A = no env, B = `HAKUX_TCG424_RANGE=1`, three
  runs per arm. The Thor already has r1 (A `1-1790517344-...-1425036` 19 gfps, B `...-1433200`
  17.0). tbflip424's section 10 says two more Thor pairs complete it as written.
- Regimen: r1 ran at MAX (`PERF: regimen=max`, before the #533 change, when max was the only
  default). The registration names no regimen, so these pairs run at the default, max, with no env
  beyond the registered one. The reader's window runs from `mark play` (~257 s) + 30 s to 540 s,
  and MAX trips in 5-9 min from cool. **A pause before 540 s voids the run.** It is not read.

## 4. Queued, 2026-09-28 03:25Z (session 1 ends on a wait)

| request | what |
|---|---|
| `1-1790565669-lane.sustain507-1255824` | #424 Blinx r2 A, 00c2840810, no env, 540 s, MAX |
| `1-1790565676-lane.sustain507-1257645` | #424 Blinx r2 B, `HAKUX_TCG424_RANGE=1` |
| `1-1790565677-lane.sustain507-1257857` | #507 pilot: GTA SA at `default`, 450 s, f82e7e87fe (not scored) |

About seven Thor requests are ahead (titleroutes, forza414, arms-pacing), and lane.titleroutes holds
a <=30 min nav session. Posted on #507 (issuecomment-5862704287, which includes the charge_full ask) and #424.

### On resume

1. Pilot: `python3 docs/lanes/sustain507/regimen_read.py --json 1257857`. Check that perf_regimen reads
   default / perf 0 / fan 4, COOLDOWN is present, `mark gameplay` is present, power is measured, and
   the gameplay frame shows CJ on foot. Write `pilots/lane.sustain507.ok` with python3.
2. Queue Part A in the registered order, `HAKUX_RELEASE_PRIO=1`, `--device thor --ref f82e7e87fe
   --expect docs/testing/predictions/sustain507-regimen.json`: Crimson (1950 s, route crimson-skies)
   max then default; GTA (2100 s, gta-sa) default then max; MechAssault 2 (2100 s, mechassault-2)
   max then default. Then #424's r3 pair.
3. #424 r2: `python3 docs/lanes/tbflip424/playread.py 1255824 1257645`, plus each run's
   verdict-style first pause (`regimen_read.py --json` has `pause_from_start`). A pause before 540 s
   voids the run.

## 5. Session 2, 2026-09-28 05:10Z

**Why session 1 did not finish.** It ended on a wait, as section 4 says: the pilot and #424's r2
pair were queued behind about seven Thor requests, and a lane session cannot outlast them. It was
not a failure. handback.sh resumed this lane once all three were DONE.

### Pilot (`0-0-x-1790565677-lane.sustain507-1257857`, GTA SA, default, 450 s): clean

| check | read |
|---|---|
| regimen | `PERF: regimen=default before=[2 4] running=[0 4]`, restored |
| gate | `COOLDOWN: waited 0 s, xo 57.4 C < 65 C` |
| mark | `mark gameplay` at 234 s from start; `220152-gameplay.png` shows CJ on foot, HUD up |
| power | battery 3.44 W + usb 2.13 W = net 5.57 W; j/frame 0.245 |
| fps (226 s window) | median 22.4, p10 19.1; no pause, no mitigation, xo max 74.4 C |

The pilot verdict is in `pilots/lane.sustain507.ok`. Battery: 2 % of capacity for 0.216 Wh pools
to a 7.2-21.6 Wh pack. The range is too wide, so the hours column stays blank. charge_full is still the ask.

### #424 r2 (MAX, 00c2840810): valid, no pause in either run

| run | arm | gate | mark play | ng | rt | m50 | gfps | churn% | di/s | slow/s | pause |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `...-1255824` | A | 61.6 C, 0 s | yes | 81 | 0 | 31 | 19 | 1.7 | 522.6 | 1217 | none (19 samples) |
| `...-1257645` | B | 70.3 -> 63.9 C, 78 s | yes | 79 | 1 | 29 | 19 | 0.0 | 0.0 | 34503 | none (22 samples) |

M0 holds on both runs. The legs are per-arm medians of three runs, so they are not judged on two.
r1 (A 19, B 17.0) + r2 (A 19, B 19) is two of three. r3 is queued. regimen_read.py does not read
these runs ("no mark gameplay": the survey route marks `play`), so the pause was read from run.log's
THERMAL line.

### Queued, 2026-09-28 05:14Z (`queue_part_a.sh`, HAKUX_RELEASE_PRIO=1, Thor)

| request | what |
|---|---|
| `1-1790572030-lane.sustain507-4130828` | Crimson A (max), 1950 s |
| `1-1790572031-lane.sustain507-4130875` | Crimson B (default), 1950 s |
| `1-1790572031-lane.sustain507-4130912` | GTA SA B (default), 2100 s |
| `1-1790572031-lane.sustain507-4130959` | GTA SA A (max), 2100 s |
| `1-1790572031-lane.sustain507-4130999` | MechAssault 2 A (max), 2100 s |
| `1-1790572031-lane.sustain507-4131051` | MechAssault 2 B (default), 2100 s |
| `1-1790572032-lane.sustain507-4131088` | #424 Blinx r3 A, 00c2840810, 540 s |
| `1-1790572032-lane.sustain507-4131123` | #424 Blinx r3 B, `HAKUX_TCG424_RANGE=1` |

About 4 h of Thor time. The Thor was under the owner's top-up hold at queue time.

### On resume

1. Part A: `regimen_read.py --json <6 full ids>` (the `1-` names are symlinks, so pass the full
   `0-0-x-` id; a short id matches two dirs), then `--pair` per title for P1. Apply the repeat rule
   (|dfps| <= 1.0 or |cut| <= 0.3 W: one more pair, reverse order). Post the table on #507 and a
   summary on #433.
2. #424 r3: `playread.py` on all six runs (r1 ids are in tbflip424's NOTES), with the pause read from
   run.log. Judge M0/M1/M4' on the per-arm medians and post on #424.

## 6. Session 3, 2026-09-28 10:45Z: Part A and #424 r3 read

**Why session 2 did not finish.** Like session 1, it ended on a wait, as section 5 says. The six
Part A runs and #424's r3 pair were about 4 h of Thor time, queued behind other work. A lane
session cannot outlast that. handback.sh resumed the lane once all eight were DONE.

### Headline: both regimens pause, on every title, in 5-8 minutes

On the Thor, from the starts the #519 gate admits (xo-therm 58-65 C), **every run paused, at MAX
and at the defaults alike**. Each first pause came 4.8-7.4 min after the run's start and 0.7-4.7
min after `mark gameplay`. After that, both regimens settle into the same limit cycle:
thermal-pause-F8 holds for ~8-15 min, clears for ~2-3 min, and trips again. xo-therm is pinned at
78 C, and **60-76 % of every run is spent paused**. On the Thor, `performance_mode` 0 vs 2 does not
change whether a title can be sustained: neither regimen sustains any of these three titles.

### Per run (`regimen_read.py`, window = mark + 1800 s, not voided after a pause)

| run | title | reg | order | xo start | fps med | p10 | clean med (span) | m2-10 | m20-30 | stab | 1st pause from start | xo max | paused | net W | J/frame |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `...4130828` | Crimson | max | 1st | 63.8 | 7.6 | 5.0 | 29.6 (242 s) | 9.2 | 7.1 | 0.77 | 364-399 s | 78.0 | 68 % | 3.90 | 0.322 |
| `...4130875` | Crimson | default | 2nd | 62.2 | 8.2 | 4.8 | 29.7 (281 s) | 11.2 | 7.2 | 0.64 | 444-478 s | 78.0 | 62 % | 3.96 | 0.308 |
| `...4130912` | GTA SA | default | 1st | 61.9 | 4.8 | 3.5 | 23.7 (138 s) | 4.2 | 4.8 | 1.15 | 355-387 s | 78.0 | 63 % | 4.00 | 0.409 |
| `...4130959` | GTA SA | max | 2nd | 63.5 | 4.2 | 3.4 | 25.0 (71 s) | 4.1 | 4.9 | 1.21 | 288-321 s | 78.0 | 76 % | 3.64 | 0.532 |
| `...4130999` | MechAssault 2 | max | 1st | 64.8 (25 s wait) | 5.2 | 3.6 | 2.1 (45 s, loading) | 6.0 | 4.8 | 0.79 | 286-318 s | 78.0 | 63 % | 3.77 | 0.434 |
| `...4131051` | MechAssault 2 | default | 2nd | 58.3 | 5.9 | 3.9 | 23.7 (144 s) | 5.8 | 6.3 | 1.09 | 386-418 s | 77.9 | 60 % | 3.87 | 0.327 |

The full ids are `1-179057203{0,1}-lane.sustain507-<n>`. In every run, the first mitigation event
is the pause itself, with kgsl devfreq in the same sample. So mitigation and pause share one
number. "paused" is the share of thermal.jsonl samples with the pause set. Whole-window net_w is
3.6-4.0 W: it is the paused draw, and not a regimen property. A stability over 1.0 means minutes
2-10 were already paused. Battery hours: the pool over these six plus the pilot is 16.9-30.1 Wh
(max/min 1.78 > 1.3), so the column stays blank as registered. charge_full is still unread.

### The legs, as registered

| leg | result |
|---|---|
| L0 | **holds** on all six: read-backs max 2/4 and default 0/4, mark present, window 1800 s, coverage None, sign_suspect 0, gate xo < 65 C |
| P1 (cut 0.5-1.5 W) | **not judgeable**. GTA and MechAssault 2 are unreadable: MAX's clean span is 71 s and 45 s, under 120 s. The one readable title, Crimson, over its 242 s span: MAX 5.36 W, default 5.70 W, **cut -0.34 W**. That is the refuting direction: the defaults do not draw less. |
| P2 Crimson | **REFUTED as written**: B's window median is 8.2, against A's clean 29.6 - 1. The named world ("MAX bought frames") is not the cause, though: before the pause B ran 29.7 against A's 29.6. The cause is B's own pause. |
| P2 MechAssault 2 | passes as written (5.9 >= 2.1 - 1). **Not counted**, because A's clean span is 45 s of loading at 2.1 fps, not a gameplay rate |
| P3 GTA | **REFUTED** by its named world: B paused at 355-387 s, inside 30 min. (a) holds: A paused, 4.2 <= 25.0/3. (b) fails: B paused, stability 1.15 over a paused baseline. (c) fails: B 4.8 vs A 4.9 in minutes 20-30. |
| M plateau at B | none below the trip. Wherever xo "plateaus" (Crimson B 24.7 min), it is pinned at 78 C by the pause cycle, so the plateau cannot set a confirmation length |

**The repeat rule fired and was not run.** All three pairs have |Δ median fps| <= 1.0 (0.6, 0.6,
0.7). A repeat pair would cost ~3.7 h of Thor time at priority 1. It could not change P3: one B
pause refutes it, and all three B runs paused. It could not change P2 Crimson either: that leg fails
by 21 fps, through the pause. The small Δ is the signature of two arms held in the same pause limit
cycle, not noise around a real difference. This departs from the registered rule, and the
departure is on purpose.

### What does differ: the first pause, and the start temperature (confounded)

- In all three pairs, the defaults paused 80-100 s later: 444 vs 364, 355 vs 288, and 386 vs 286 s.
  But in all three pairs the default run also started cooler (62.2/63.8, 61.9/63.5, 58.3/64.8 C).
  The alternating order did not decorrelate this, so the delay is not attributable to the regimen.
- **Start temperature is the stronger lever on this data.** The one MechAssault 2 MAX run on disk that
  never paused (`0-0-x-1790557233-hostops-810152`, 24 min, xo max 74.2 C) started at xo **46.9 C**,
  battery zone 34 C. Tonight's MechAssault 2 MAX run started at 64.8 C, battery 40 C, and paused at
  286 s. The pilot (GTA default, 57.4 C start) did not pause in 450 s. The gate's 65 C admits a
  heat-soaked chassis: the battery zone reads 38-40 C at every start tonight. Ambient is not
  recorded, so a warmer room is not excluded.

### What this means for #433 and #519 (proposals, not measured)

- Moving confirmations to the defaults costs no fps on this data before the pause (Crimson clean
  29.7 vs 29.6). By itself, it also buys no sustained play on the Thor.
- Under #533's rule (a pause fails a defaults run), **every one of these titles fails any
  confirmation longer than ~8 min from a 58-65 C start.** The length question therefore reduces
  to the start condition. The next measurement is the same defaults soak from a truly cool start
  (xo <= 50 C, battery zone <= 35 C), on one title: does it reach an equilibrium under 78 C, as
  hostops-810152 did at MAX?
- For #519: gate on the battery zone (the slow sensor), not only on xo-therm, which recovers in
  minutes while the chassis stays soaked.

### #424 r3: both runs VOID

| run | arm | gate | first pause from start |
|---|---|---|---|
| `1-1790572032-lane.sustain507-4131088` | A | 60.5 C, 0 s | 443-475 s, before 540 s: **VOID** |
| `1-1790572032-lane.sustain507-4131123` | B | 63.1 C, 0 s | 411-444 s, before 540 s: **VOID** |

Not read, per the brief. The valid Thor pairs are r1 (A 19, B 17.0 gfps) and r2 (A 19, B 19). The legs
are per-arm medians of three runs, so **M0/M1/M4' are not judged**. One more valid pair judges
them. At MAX, 2 of the 4 Thor Blinx runs since r1 voided. The route's `mark play` lands at ~3 min,
so the window ends at 9 min, which is right where these starts trip the pause. The next pair
wants a start well under the gate (see above).

### Next lane should not repeat

- Do not run MAX vs defaults on the Thor again from gate-admitted starts. The regimen is not the
  variable that matters there.
- A Thor soak's `mark gameplay` lands 2-4 min into the run. A "30 minutes after the mark" window
  at these starts is 60-76 % paused, whatever the regimen.

## 7. Session 4, 2026-09-28 11:00Z: Part C, the idle halt from a cold start

**Why the previous attempt did not finish.** It did finish its brief. Session 3 read Part A and
#424 r3, posted on #507, #433 and #424, and marked #537 ready. #537 folded as 9d777502fa. The
brief then gained Part C (lane.local, 04:05 PDT), and this session is that new work. It goes on
a second branch, `lane/sustain507-levers`, off master, because #537 had already folded.

### Instruments

- **The #519 gate cannot be lowered from a request.** `THERMAL_COOL_C` is a shell variable of
  `soak_title.sh`. A request's `--env` goes to the app's `env_vars` pref (dispatcher.sh
  `apply_env_pref`). Only `PERF_REGIMEN` is read back from the request, by name. So, as the
  brief's fallback says: the runs must be the first on each device after a cold period. The
  start temperatures are read from thermal.jsonl, and a warm start is reported, not scored.
- Both handhelds name the battery sensor `battery` in `tz`, beside `xo-therm`. Both expose the
  same `thermal-pause-*` cooling devices, so a Nova pause is visible. `pause_census.py`: 0 of 42
  Nova soaks with a thermal.jsonl have paused, against 12 of 35 on the Thor.
- The halt logs `[idlehalt] w=.. on=<0|1> span_us run_us rq_us halts=..` every 2 s, under tag
  `hakuX` at W. `hakuX:W` is in the soak's default LOGCAT_SPEC, so no `--perflog` is needed.
- `regimen_read.py` gained `--mark play` (the survey route, which is all Blinx and AUF have),
  `battery_start_c`, the halt read-back (`ih_on`, `ih_halts`, `ih_run_pct`) and `--halt ON OFF`
  (net_w over the span before either run paused). It reproduces #525's AUF pair (4.75 vs
  7.02 W) and Part A's Crimson cut (-0.338 W).

### Prediction and queue

`docs/testing/predictions/sustain507-levers.json` (sha256 4c5b3f7b...), registered before
queueing. Legs: L0, H1 (ON pauses later or never), H2 (a Thor ON plateau at 70-77 C by min 15),
H3 (ON 2 C cooler at min 10), P (pre-pause cut >= 1.5 W), F (reported), and a falsifier.
Admission: xo <= 50 C and battery <= 36 C at the start sample.

| request | what |
|---|---|
| `1-1790593205-lane.sustain507-3238469` | Thor Blinx, halt ON, default, 2160 s (first) |
| `1-1790593205-lane.sustain507-3238578` | Thor Blinx, halt OFF, default (second) |
| `1-1790593206-lane.sustain507-3238659` | Nova AUF, halt OFF, default (first) |
| `1-1790593206-lane.sustain507-3238806` | Nova AUF, halt ON, default (second) |

All four on 9d777502fa (`queue_part_c.sh`). The pilot file has a Part C addendum. Each
run needs its own cold slot, and the second of a pair cannot follow the first directly. hostops
was asked on #507 to place them. The session ends on that wait.

### On resume

1. `python3 docs/lanes/sustain507/regimen_read.py --mark play --json 1-1790593205-lane.sustain507-3238469
   1-1790593205-lane.sustain507-3238578 1-1790593206-lane.sustain507-3238659 1-1790593206-lane.sustain507-3238806`.
   Check admission first (xo_start_c, battery_start_c), then L0.
2. `--mark play --halt <ON> <OFF>` per device for P. Judge H1-H3 as registered.
3. Post the Part A-style table, with the start xo and battery, on #507 and #525.
4. #424's Thor leg continues as registered: it wants one more valid pair, from a cold start.

## 8. Session 5, 2026-09-28 14:25Z: Part C read, and Part D.1/D.2

**Why the previous attempt did not finish.** It ended on purpose, waiting. The four Part C runs
each needed a cold slot, which only hostops could give (section 7). Two of them were still
running when this session started.

### Part C runs (`regimen_read.py --mark play`, window = mark + 1800 s, `partc-read.json`)

Each result dir is `0-0-s-1-179059320{5,6}-lane.sustain507-<n>`, restored by hostops' cold slots. All
runs are at the defaults (read-back 0/4, fan SMART).

| run | dev | halt | order | xo start | bat start | admitted | fps med | p10 | stab | 1st pause from mark | xo max | xo min 10 | plateau (min, C) | net W | J/frame | capacity % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `3238469` | Thor | ON | 1st | **53.8** | 36.0 | **no** (xo > 50) | 16.5 | 5.6 | 0.76 | 1462-1494 s | 78.0 | 74.8 | none | 4.64 | 0.288 | 18 -> 5 |
| `3238578` | Thor | OFF | 2nd | 43.5 | 36.0 | yes | 17.9 | 14.3 | 1.05 | **none** | 75.2 | 73.4 | 9.4, 74.7 | 4.99 | 0.262 | 85 -> 84 |
| `3238659` | Nova | OFF | 1st | 34.2 | 30.0 | yes | 22.1 | 21.0 | 1.00 | none | 49.4 | 48.7 | 4.0, 49.3 | 6.52 | 0.297 | 80 -> 75 |
| `3238806` | Nova | ON | 2nd | 44.8 | 36.0 | yes | 22.3 | 21.9 | 1.00 | none | 51.5 | 46.8 | from the mark, 46.7 | 5.94 | 0.267 | 70 -> 64 |

The halt read back as registered: ON `ih_on` [1] with 396,563 and 462,340 halts, OFF [0] with 0.
Every run has `mark play` and a full 1800 s window, and `sign_suspect` is 0. Mid-run play frames
show level play. L0 holds on all four. Battery hours stay blank: the capacity steps do not fit the
integrated battery Wh on the Thor (13 % for 1.26 Wh against 1 % for 1.43 Wh), as in Part A.

### The legs, as registered

| leg | Nova (AUF) | Thor (Blinx) |
|---|---|---|
| admission | both scored | **pair not judged**: ON started at 53.8 C. Re-queued as `1-1790607334-lane.sustain507-589340`, parked in `parked/sustain507-cold-20260928/` for a cold slot (`stage_thor_on_rerun.sh`) |
| H1 | not judged: neither arm paused (the expected Nova outcome) | not judged |
| H2 | n/a (Thor leg) | not judged. OFF, not ON, plateaued: 74.7 C by min 9.4, inside the ON band 70-77 C |
| H3 | **REFUTED by 0.1 C**: ON 46.8 vs OFF 48.7 at min 10, 1.9 C < 2.0 C. ON started 10.6 C *warmer*, so the direction favours the halt | not judged (ON 74.8 vs OFF 73.4, ON started 10.3 C warmer) |
| P | **REFUTED**: cut 0.58 W (ON 5.94, OFF 6.52 W over 1800 s) < 1.5 W | not judged; unscored cut **0.05 W** over the 1462 s before ON paused (4.93 vs 4.98 W) |
| F | holds: 22.3 >= 0.9 x 22.1 | (unscored: clean 17.6 vs 17.9) |

**Falsifier: on the Nova at the defaults, the halt is refuted as a heat lever,** by P. It cuts
0.58 W (-9 %) and 10 % J/frame, against #525's 2.28 W at MAX on the same title. The Nova is
not near its trip at the defaults, though: 49 C against 78 C. The halt is not what keeps it
there. On the Thor the unscored ON arm cut 0.05 W, which says the same: at the defaults the heat
that reaches xo-therm is not the idle vCPU's spin. The scored Thor ON run decides it.

### What the Thor OFF run says, which matters more than the halt

**Blinx at the defaults, from a cold start (xo 43.5 C, battery 36 C), ran 30 min after the mark
with no pause.** xo-therm plateaued at **74.7 C from minute 9.4**, 3.3 C under the 78 C trip,
at 17.9 fps median, p10 14.3, 4.99 W net, 0.262 J/frame. Part A's gate-admitted starts
(58-65 C) all paused in 5-8 min. So at the defaults the Thor has a steady state under the trip for
this title, and a confirmation soak reaches it by minute ~10 **from a cold start**.

The unscored ON run started at 53.8 C, at 18 % charge falling to 5 %, and crossed the trip at
~24 min from the mark. Its plateau is not the OFF run's, so a 10 C warmer start costs the margin.
The battery at 5 % is a second difference: a low battery delivers the same watts at a higher
current.

### Part D.1: fan_mode 6 (CUSTOM), probed on the idle Nova, 15:30-15:32Z (`fanprobe-nova.txt`)

The hold was taken ahead with `jobs/hold.sh` (tag lane.sustain507) while the Nova ran its ON arm,
and the probe ran in the idle gap after it. It took 1 min 46 s, then restored fan_mode 4 and
released the hold.

- **CUSTOM holds a fixed 25000 (50 %), the same as SPORT.** Duty went 12000 -> 25000 within 5 s
  and stayed there for 60 s, with the tach at 8700-9300 rpm. It is not a curve.
- **No settings key backs a custom curve.** Across system, global and secure, the only change
  under mode 6 was `fan_mode` itself. The quick-settings tile list names a `fan` tile. The
  packages are `de.langerhans.odintools` and Retroid's own (`com.retroidpocket.*`); no provider
  names a fan.
- **The PWM node is world-writable** (`duty`, `state` and `speed` are `-rw-rw-rw-`). The adb shell
  wrote duty 50000, and it **held 50000 for the 9 s it was read under mode 6**, with the tach at
  13800-14100 rpm (against 9000 at 25000). Restoring mode 4 put SMART's 12000 back.
- **Not measured:** whether 50000 survives for minutes under mode 6 (the OEM service might
  rewrite it), and the Thor (it was busy all session). The Thor's `speed` reads 0, so only duty
  can show it there.

**So the fan lever is reachable without the owner's hands:** `settings put system fan_mode 6`,
then `echo 50000 > /sys/class/gpio5_pwm2/duty`. That is up to 2x SPORT and 1.7x the most SMART
has been seen to use (29000 on a 74 C Thor).

### Part D.3 is blocked on a dispatcher knob

A request cannot set the fan. Only `PERF_REGIMEN` crosses from a request to `soak_title.sh`
(section 7), and this lane changes no code. D.3 (halt ON, 30 min at the defaults, 100 % fan vs
SMART, from cold starts) needs `soak_title.sh` to take a fan duty from the request, for example
`FAN_DUTY=50000`:
1. write mode 6 and the duty after the regimen;
2. re-write the duty at every thermal sample, in case the OEM service rewrites it;
3. restore mode 4 on exit.

The Thor OFF result says where it would matter. The Thor sits 3.3 C under the trip from a cold
start, and a warm start loses that margin. A fan at 50000 may buy it back.

### Part D.2: fan duty in every soak sample

This is PR #554 (`lane/sustain507-fan`), folded as 0f4002ebe8 at 15:20Z. `thermal_state.py` samples
`gpio5_pwm2` duty/period/state/speed, and the `THERMAL:` line ends `fan duty lo-hi of period`. It is
live once a dispatcher update window has taken that snapshot.

### Next lane should not repeat

- Do not expect the idle halt to cool a device at the defaults. It cut 0.58 W on the Nova, and
  0.05 W unscored on the Thor.
- On the Thor, the start temperature decides the run. Blinx from 43.5 C never paused, and from
  53.8 C it paused at 24 min. A confirmation soak must start cold, or it measures the chassis.

### On resume

1. When hostops has cold-slotted `1-1790607334-lane.sustain507-589340`, read it with the Thor OFF
   run (`--mark play` and `--halt <ON> <OFF>`). Check admission first, then judge H1, H2, H3 and P
   for the Thor as registered.
2. #424's Thor leg still wants one more valid pair, from a cold start (section 6).
