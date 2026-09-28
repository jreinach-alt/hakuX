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
