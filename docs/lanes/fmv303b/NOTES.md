# lane.fmv303b -- #303 Spikeout FMV green, the CPU-side discriminator

Continues lane.fmv303 (its NOTES sections 4 and 5). Settled there, and not
re-measured here: the green is already in the guest's ARGB buffer. The job
is to A/B the tier1 JIT tier (off vs on) on the same Thor soak, metered by
`docs/lanes/fmv303/guest_tint.py` on the probe's `tint` line.

## 1. How a soak sets tier1 off: it cannot, today (2026-09-26)

The threshold is a **pref only**, not an env var:

- `accel/tcg/cpu-exec.c:72` `xemu_set_tier1_threshold(0)` sets
  `g_tier1_threshold = 0x7FFFFFFF` (off). Values 1..7 clamp to 8.
- Its one boot-time caller is `android/app/src/main/cpp/xemu_android.cpp:974`:
  `GetPrefInt(env, activity, "tier1_threshold", 64)`. `GetPrefInt`
  (`:467`) reads `runtime_override_tier1_threshold` first, then
  `tier1_threshold`, from `x1box_prefs.xml`. The Settings screen and
  per-game settings write those keys (`SettingsActivity.kt:550`,
  `PerGameSettingsManager.kt:31`). No `getenv` reaches the threshold.
- The dispatch path writes exactly one pref, `env_vars`
  (`docs/testing/dispatcher.sh:357-433`, from `request.sh --env`). No request
  field writes any other pref. The soak launches with `am start ... --es
  rom_path` only (`soak_title.sh:160`), with no settings extras.

So a queued soak runs at whatever `tier1_threshold` the device holds. The ON
arm of record ran at 64: logcat of `1790389079-fmv303-1248256` says
`tier1 threshold: 64` at 19:52:55, beside `env: HAKUX_FMV303_PROBE=1`. A lane
must not touch a device directly, so a tier1-off arm cannot be queued.

Checked and rejected as ways round it: `--env` (nothing reads an env for
the threshold); per-game overrides (they need a write on the device); intent
extras (the soak passes none).

## 2. The unblocking hunk (board-requested, not edited)

`android/app/src/main/cpp/xemu_android.cpp`, directly after `:974`, before
the `xemu_set_tier1_threshold` call:

```c
  const char *t1env = getenv("HAKUX_TIER1_THRESHOLD");
  if (t1env && *t1env) tier1_threshold = atoi(t1env);
```

The `env_vars` pref is applied with `setenv` at `:796-810`, inside the same
`SyncSetupFiles()` and before `:974`, so a queued `--env
HAKUX_TIER1_THRESHOLD=0` reaches it. It does nothing by default (the env is
unset), and the existing `tier1 threshold: %d` log line then reports the value
the run actually used. That log line is the arm's own check that it took
effect. File holder: **free** on `origin/board` `territory.toml` (released at
wave 123 by retiring diagdump77), and no open PR lists it. Board request:
`board-requests/fmv303b.md`, which asks to grant this file to lane.fmv303b.

## 3. The arm, once granted (not registered yet: its refs do not exist)

- a_ref = the hunk commit, `--env HAKUX_FMV303_PROBE=1` (tier1 on, 64).
- b_ref = same sha, `--env HAKUX_FMV303_PROBE=1 --env HAKUX_TIER1_THRESHOLD=0`.
- Thor, Spikeout, 150 s, at least two runs per arm, interleaved in one
  session. Check `tier1 threshold: 0` in each OFF run's logcat before reading
  its tint, and `tier1 threshold: 64` in each ON run's.
- Falsifier (as briefed): OFF mean within 0.2 of the same session's ON mean
  means the JIT tier is not the cause (step 2a: find a DMA or surface
  write-back landing in the decoder's planar buffers). OFF mean below 0.1
  means tier1 is the cause (step 2b: bisect packuswb / paddsw / pmulhw with a
  guest-side falsifier per op). Between the two is no verdict and needs more
  runs. An arm with fewer than 100 lit frames, or with no `tint` lines, is no
  reading.
- The prior spread of the ON arm is 0.41-0.66 across runs of one binary
  (screen, section 4 of fmv303), so a single run per arm cannot separate
  "within 0.2" from noise. That is why two runs per arm is the minimum.

## 4. Table (empty until the arm runs)

| arm | run id | apk_sha | tier1 logged | tint lines | lit>=100 | mean |
|---|---|---|---|---|---|---|
| ON (control of record, earlier session) | `1790389079-fmv303-1248256` | `d8a9fc20c655` | 64 | -- | 435 | 0.66 |

## Next lane, do not repeat

- Do not queue a "tier1 off" soak with `--env` alone before the hunk lands:
  nothing reads it, and the run would be a second ON arm labelled OFF. Check
  the `tier1 threshold:` logcat line in every arm.
