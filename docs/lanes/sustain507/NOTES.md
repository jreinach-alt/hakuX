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
