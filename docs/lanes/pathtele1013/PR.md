# pathtele1013: an opt-in perflog telemetry hold for pathfind; KOTOR II and Splinter Cell Double Agent read as guest-vCPU-bound (#433)

Lane: pathtele1013      Issue: #433
Base: master @ 3c2338eb2b
Files: docs/lanes/pathtele1013/**, docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py
Prediction: none: harness/analysis-only, no device arm of mine
Needs device: no (Part C, not mine)    Needs NDK: no
Release note (none): harness-only -- adds an opt-in `--perflog` telemetry hold to the pathfind tool; off by
default, never banked as a Playable result.
State: ready

## What this is

Part A (offline attribution) and Part B (`pathfind.py --perflog`) of the brief, both done; Part C is lane.local's,
command lines below. Full writeup: `docs/lanes/pathtele1013/NOTES.md`. One-line digest: `OUTBOX.md`.

**Part A.** KOTOR II (4C410014) and Splinter Cell Double Agent (5553005E) are both guest-vCPU-bound (class L5 in
fpsbelow1012's lever table; no lever in L1-L4 applies to either -- those all need the render thread or GPU to be
the bottleneck, and here the vCPU is 84.6%/56.8% of wall against a render thread at only 14.3%/20.1%). KOTOR II
reads as locked at 30 fps and dropping to 20 on a fifth of flips, confirmed quantitatively: `hakuX-pace`'s v2
share (0.661, a clean 2-vblank flip) lands within 0.0015 of fps_ok_share (0.6595) measured independently from the
perf-line frame times. SC Double Agent oscillates almost evenly between 30 and 20 fps (pace v2 0.451/v3 0.520)
via the same nv2a-ERROR-callback wake-key class (`33.44`, 90.9% of busy) M:I's own reading used; KOTOR II's
dominant wake key (`30.00`, 93.7% of busy) is NOT that class, read here as general compute rather than one
blocking callback -- flagged as an inference from the shape of the data, not a decode, in NOTES.md section 3.

**Part B.** `pathfind.py --perflog` installs master's `-Pperflog=true` build (via `dispatcher.sh`'s own
`build_ref`/cache, sourced rather than reimplemented -- no second build path), `adb install -r` only, verifies
the versionName via `version_stamp.sh`'s convention, passes `--env` through `dispatcher.sh`'s own
`apply_env_pref`, and restores master in `main()`'s existing `finally`. A guard (`perflog_start`) refuses any
non-`--perflog` run while a perflog build is still installed, so a crash between an earlier hold's install and
its restore can't silently poison the next scored run. `result.json` always carries `"build": "perflog"` and
`"env": [...]` when used. Offline tests in `pathfind_selftest.py` (`_FakeDevice` + a faked
`pathfind._dispatcher_call`, no adb, no device) cover the install order, the leftover-build refusal, a setup
failure exiting rather than running silently, and restore-on-exception; full suite run (`python3
docs/testing/titles/pathfind_selftest.py`): `pathfind_selftest: all ok`.

**WAITING: a grant for `docs/testing/title_verdict.py`** (not in this lane's territory) to complete "never
banked" for verdict.json/the registry/the sweep list -- the exact patch is in NOTES.md section 4. Until granted,
`pathfind.py`'s own side (this PR) is complete and safe on its own: every perflog run's `result.json` already
carries `"build": "perflog"` for any reader, human or automated, to exclude it by hand.

## Part C -- for lane.local, after this branch folds, on the Nova

One 3-minute telemetry hold each, per the owner's `below_bar_refusal` rule ("one 3-min perflog run on a title
that has shown it will not clear"):

```
PATHFIND_BELOW_BAR=1 python3 docs/testing/titles/pathfind.py 4C410014 \
  --device nova --out docs/lanes/pathfind/runs/n-4C410014-perflog-1013 \
  --hold-s 180 --perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1

PATHFIND_BELOW_BAR=1 python3 docs/testing/titles/pathfind.py 5553005E \
  --device nova --out docs/lanes/pathfind/runs/n-5553005E-perflog-1013 \
  --hold-s 180 --perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1

PATHFIND_BELOW_BAR=1 python3 docs/testing/titles/pathfind.py 4947001F \
  --device nova --out docs/lanes/pathfind/runs/n-4947001F-perflog-1013 \
  --hold-s 180 --perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1
```

Each installs master's perflog build, holds 180 s on the title's known path, records `logcat.txt` with the
`hakuX-phase`/`[sdcall]` lines this lane's Part A reading didn't have, and restores master afterward (verify the
restore message printed by the run, per `pathfind.py`'s own `restore_master`). None of the three is ever a
Playable candidate (see the WAITING item above for why that still needs the grant to be automatic).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
