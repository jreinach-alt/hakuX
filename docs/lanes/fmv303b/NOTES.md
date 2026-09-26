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

## 4. Table: tier1 off does not move the tint (attempt 3, 2026-09-26)

Why attempt 2 did not finish: it ended correctly, waiting on the four queued
Thor requests (a device queue outside the session). The host moved them up and
all four came back `DONE`. Nothing was lost, and nothing was re-run.

The result dirs are `$DISPATCH_DIR/results/0-0-y-1790433000-<id>`. Read by
`docs/lanes/fmv303b/judge_arms.sh`, which runs `tier1_judge.py` on the four
logcats and prints each run's `tier1 threshold:` line. All four runs are
ref `4b96082573`, apk `8df7aca3bbcd`, Thor `bdc158a5`, 150 s, frames every 2 s.
Each OFF run logs `env: HAKUX_TIER1_THRESHOLD=0` and then `tier1 threshold: 0`.
Only the hunk can print that line, so the apk carries it.

| order | arm | run id | apk_sha | start (device) | tier1 logged | tint lines | lit>=100 | >0.1 | ==0 | mean | M0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| control | ON | `1790389079-fmv303-1248256` | `d8a9fc20c655` | earlier session | 64 | -- | 435 | 374 | 32 | 0.66 | -- |
| 1 | ON | `1790433154-fmv303b-2431986` | `8df7aca3bbcd` | 08:17 | 64 | 1337 | 1332 | 1215 | 104 | **0.70** | OK |
| 2 | OFF | `1790433156-fmv303b-2432129` | `8df7aca3bbcd` | 10:24 | 0 | 1822 | 1798 | 1595 | 130 | **0.68** | OK |
| 3 | ON | `1790433159-fmv303b-2432336` | `8df7aca3bbcd` | 10:26 | 64 | 1749 | 1734 | 1550 | 137 | **0.68** | OK |
| 4 | OFF | `1790433161-fmv303b-2432888` | `8df7aca3bbcd` | 10:30 | 0 | 1693 | 1675 | 1500 | 128 | **0.68** | OK |

Pooled: ON 0.688 (2 valid runs, 3066 frames), OFF 0.680 (2 valid runs, 3473
frames). |OFF - ON| = 0.008. **Verdict NOT_TIER1**, as predicted in
`fmv303b-tier1-ab.json`. The rival (OFF < 0.1) is refuted by a factor of
nearly 7.

One caveat on "same session": arm 1 ran two hours before arms 2 to 4, with
other lanes' Thor runs in between (its shader cache was cleared on the apk
change, as was arm 2's). Arms 2, 3 and 4 ran back to back within six minutes,
and arm 3 (ON) alone matches both OFF runs to two places. So the verdict does
not rest on arm 1.

What this does and does not exonerate. Tier1 off removes only the tier1
optimising tier. Every guest instruction still runs through base TCG,
including the `target/i386` MMX/SSE helpers (`ops_sse.h`: packuswb, paddsw,
pmulhw). So the base helpers are not cleared by this arm. What argues against
them is the evidence already on record: the tint switches clean/tinted within
a shot, and two runs of one binary differ. A wrong helper is a function of its
inputs, and the IDCT and colour-conversion inputs of one clip do not depend on
the host's timing. A clobber of the decoder's chroma plane by a write that
races the decoder does. So the brief's **step 2a** is selected: a DMA or
surface write-back landing in the decoder's planar buffers.

## 5. Step 2a: the next discriminator, and its hunk (board-requested)

The probe knows the ARGB output buffers (0x307d000 and 0x3163000, each
640x368x4 = 0xe6000). It does not know where Sofdec's Y/Cb/Cr planes are. So
the next arm cannot test "a write lands in the Cr plane" directly. It can
test whether any non-CPU writer lands in guest RAM near the FMV working set,
and when.

The guest-RAM writers that are not the guest CPU:

1. **nv2a surface write-back** (`hw/xbox/nv2a/pgraph/vk/surface.c`). A
   colour or zeta surface whose `vram_addr` range covers the decoder's heap
   downloads over it when a CPU access, a flush or an eviction pulls it. This
   is the prime suspect. It lands in whole-surface chunks, a GPU-side stale
   binding would explain the macroblock-aligned pattern, and it is
   timing-dependent by construction (the download fires on the next
   CPU access after a dirty draw).
2. IDE/DVD DMA of the stream (it writes the compressed bitstream, not the
   planes, so it would corrupt the decode, not zero one plane).
3. MCPX APU DMA (the ADX audio track).

Hunk (default inert, gated on the existing `HAKUX_FMV303_PROBE=1`): in
`surface.c`, at every point where a downloaded surface's bytes are copied
into `d->vram_ptr + surface->vram_addr` (`download_surface_to_buffer` at
`:994` and the staged path in `pgraph_vk_complete_staged_downloads` at
`:860`), log `[fmv303] wb addr=%08x len=%x color=%d fmt=%d` with the
display frame counter. Add one per-frame counter line, so a zero is an
observed zero and not a silent instrument. The analysis joins it to the
`tint` lines by frame. Question: does a write-back land in
`0x3000000..0x3400000` (the FMV region), and does it precede tinted frames
and not clean ones?

- Hit, and ordered before the tinted frames: the write-back is the clobber.
  The fix is in `surface.c`: which binding is stale, and why it is still dirty.
- Zero write-backs in the region over >= 100 lit tinted frames, with the
  counter showing write-backs elsewhere: surface write-back is exonerated.
  Then do the same for the APU and IDE DMA landing sites. After those, the
  next suspect is the base-TCG helpers (step 2b's per-op guest falsifier,
  run with tier1 off).

File holder: `hw/xbox/nv2a/pgraph/vk/surface.c` is held by
**lane.blinx372d** on `origin/board` `territory.toml`. Board request:
`$DISPATCH_DIR/board-requests/fmv303b.md` asks for a probe-only grant, or
for the hunk to be coordinated with blinx372d. This lane did not edit it.

## Next lane, do not repeat

- Do not queue a "tier1 off" soak with `--env` alone before the hunk lands:
  nothing reads it, and the run would be a second ON arm labelled OFF. Check
  the `tier1 threshold:` logcat line in every arm. (The hunk is `4b96082573`.
  `HAKUX_TIER1_THRESHOLD=0` now works on any apk that carries it.)
- Do not re-run the tier1 A/B. Four runs: 0.70, 0.68 | 0.68, 0.68. Tier1 is not
  the cause.
- Do not read "tier1 off" as "the JIT is exonerated": base TCG still runs.
