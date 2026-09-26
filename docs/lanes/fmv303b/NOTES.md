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

## 3. The arm (granted, registered and queued 2026-09-26)

Attempt 1 ended blocked on the grant, correctly. It posted `[lane.fmv303b]
blocked:` on #398 at 14:28 UTC, and the host granted
`xemu_android.cpp` at 14:29 UTC. The session had already ended, so nothing
picked the grant up until this resume. No device job was in flight: the
background task the resume brief mentions left no result dir and no queued
request. Attempt 2 (this one) does the rest.

- Hunk: `4b96082573`, two lines after the `tier1_threshold` pref read in
  `xemu_android.cpp`. Unset, the pref value stands.
- Prediction: `docs/testing/predictions/fmv303b-tier1-ab.json`, registered
  before any arm ran. a_ref = b_ref = `4b96082573`. The env is the only
  independent variable. Predicted NOT_TIER1.
- Judge: `docs/lanes/fmv303b/tier1_judge.py --on L1 --on L3 --off L2 --off
  L4`. M0 per run: the `tier1 threshold:` line reads 64 (ON) or 0 (OFF),
  and the run has >= 100 lit frames. Checked on the control of record: it
  reads ON 64, 435 lit, 0.66, and the same logcat passed as OFF is VOID.
- Queued by `docs/lanes/fmv303b/queue_arms.sh`, Thor, 150 s, frames every
  2 s (the control's shape, because frame capture costs frame rate and the
  tint is timing-dependent), interleaved:

| order | arm | request id |
|---|---|---|
| 1 | ON | `1790433154-fmv303b-2431986` |
| 2 | OFF | `1790433156-fmv303b-2432129` |
| 3 | ON | `1790433159-fmv303b-2432336` |
| 4 | OFF | `1790433161-fmv303b-2432888` |

- Falsifier (as briefed): an OFF mean within 0.2 of the same session's ON
  mean means the JIT tier is not the cause (step 2a: find a DMA or surface
  write-back landing in the decoder's planar buffers). An OFF mean below 0.1
  means tier1 is the cause (step 2b: bisect packuswb / paddsw / pmulhw with
  a guest-side falsifier per op). A result between the two is no verdict and
  needs more runs.

### Waiting (2026-09-26 14:40 UTC, 7:40 AM PDT)

At queue time 36 requests were ahead of these four, and about 24 of them were
Thor-pinned: hotfix041 soaks at 240 s and the titleplay p1 batch at 420 s.
That is roughly three hours of Thor before arm 1 starts. Attempt 2 stops
here, waiting on the four request ids above. Once all four have a `DONE`
in `$DISPATCH_DIR/results/<id>/`, run `tier1_judge.py` on their
`logcat.txt`s, fill section 4 (apk_sha from each `result.json`), and
choose step 2a or 2b.

Preflight on `6030723364` passes everything but `coverage`. That gate
reads #223, #262 and #266 in `nv2a_issues.toml` on origin/board: rows
marked `dispatch_state = done` whose status is still `open`. Those are
board files and not this lane's.

## 4. Table (empty until the arm runs)

| arm | run id | apk_sha | tier1 logged | tint lines | lit>=100 | mean |
|---|---|---|---|---|---|---|
| ON (control of record, earlier session) | `1790389079-fmv303-1248256` | `d8a9fc20c655` | 64 | -- | 435 | 0.66 |

## Next lane, do not repeat

- Do not queue a "tier1 off" soak with `--env` alone before the hunk lands:
  nothing reads it, and the run would be a second ON arm labelled OFF. Check
  the `tier1 threshold:` logcat line in every arm.
