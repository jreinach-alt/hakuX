# lane.rendermode474 (#474): per-title Turnip render mode

PR #530. Base master `59d478911e`. Code commit `61e0edf87c`.

## What shipped

- `xemu_android.cpp`: `ApplyRenderMode`, called from `SyncSetupFiles` right
  after the DVD image is resolved and before `xemu_settings_load` (and so
  before `create_instance` in `instance.c`, where Turnip parses `TU_DEBUG`
  once, in `vkCreateInstance`). Order of precedence:
  1. the per-game `render_mode` override (`runtime_override_render_mode`):
     `auto`, `sysmem` or `gmem`;
  2. the title table `kTitleRenderModes`: `4541000D` (007: Agent Under
     Fire) and `54430006` (Dead or Alive 1 Ultimate), both `sysmem`;
  3. `auto`.
  `sysmem` appends `sysmem` to whatever `TU_DEBUG` the `env_vars` pref set
  (comma list), never replacing it. `auto` and `gmem` add nothing, which is
  the driver's choice; for the two tabled titles that choice is GMEM, which
  is what flip474's GMEM arms measured. A table default also yields to an
  env `TU_DEBUG` that already names `sysmem` or `gmem`, so
  `request.sh --env TU_DEBUG=gmem` still gives a GMEM arm on the new build.
- One start-up line on **`hakuX-build`**, on every launch, tabled or not:
  `render_mode: <mode> (<source>) title=<TID> TU_DEBUG=<value|(unset)> (#474)`.
  `hakuX-build:I` is in the dispatcher's, `run_disc.sh`'s and
  `soak_title.sh`'s logcat specs. (`hakuX:I` is not in soak_title's: it keeps
  `hakuX:W`. `xemu-vk` is in none, which is why flip474's D0 line was lost.)
- `ReadDiscTitleId`: reads the title ID from default.xbe's certificate on
  the disc (XDVDFS volume at the xiso start or the redump partition starts
  0x18300000 / 0xFD90000 / 0x2080000; the root directory tree walked in
  full; XBE cert address - base address + 8). It reads the path or the
  `/dev/fdset/0` fd, whichever `SyncSetupFiles` resolved, so a launch from
  the library, from `LauncherActivity`'s `rom_path` extra (what
  `soak_title.sh`, `run_disc.sh` and `sweep_queue.sh` use), or from a VIEW
  intent all apply it: the decision is made in the emulator process from the
  disc it is about to boot, not by a screen.
- `PerGameSettingsManager.kt`: `render_mode` added to the override keys, so
  it is stored per game and written to `runtime_override_render_mode` by
  `applyRuntimeOverridesToEditor`.

The table's IDs are from `/mnt/d/hakux-staging/xiso/manifest.csv`. In
`xemu-compat-2026-09-25.csv` no other `title_id` has either as its
`canonical_title_id`, so there are no regional twins to add. DOA 2
Ultimate is a different disc and was not measured: it is not in the table.

## Host test

`docs/lanes/rendermode474/titleid_test.sh [image=TID ...]` cuts
`ReadLe32 .. ReadDiscTitleId` out of the source, compiles it and runs it on
five synthetic images (xiso, redump offset, default.xbe only reachable to
the right, no default.xbe, missing second magic) and any real images given.
All pass; the two staged real discs read `4B4E0029` and `4B4E0037`, as their
manifest rows say. The AUF and DOA images are not on this host
(`/mnt/d/hakux-staging/xiso` holds two); their read is proved by the device
line (E0).

## Not done here, and why

- **No UI for the setting.** The per-game settings screens
  (`PerGameSettingsActivity.kt`, `SettingsActivity.kt`, their layouts and
  `strings.xml`) are not in this lane's files. The key is stored and read;
  a user cannot set it from a screen yet. `SettingsActivity` and
  `PerGameSettingsActivity` load every stored key before saving, so an
  existing `render_mode` value survives a save from those screens.
- **`LauncherActivity` does not refresh `runtime_override_*`.** Only the
  library and settings screens call `applyRuntimeOverridesToEditor`, so a
  `rom_path` launch runs with the runtime overrides of the last library
  launch, for every key. The table does not depend on this (it reads the
  disc); a user's per-game `render_mode` does. That is pre-existing and
  affects all 22 keys; fixing it needs `LauncherActivity.kt`.
- `TU_DEBUG` reaches Turnip only. On a device running the vendor driver the
  line still prints, and nothing changes.

## Predictions (registered before any arm, at `42d21359c6`)

| file | arms | how queued |
|---|---|---|
| `rendermode474-pgraph.json` | 27 pgraph suites, A `59d478911e` vs B `61e0edf87c`, all must_not_move; ZPass is the discriminator (40960 GMEM / 65536 sysmem) | the arms job |
| `rendermode474-doa.json` | DOA, Nova, 300 s survey, window 151-288, A vs B no env: E0 line, D1 X/R, F1 gfps, T0 heat, P0 J/frame | by hand: the pilot |
| `rendermode474-auf.json` | AUF, Nova, 420 s, window 299-420, A vs B | after the pilot |
| `rendermode474-blinx.json` | Blinx, Thor, 180 s, B only: `render_mode: auto (default) title=4D530013 TU_DEBUG=(unset)` | after the pilot |
| `rendermode474-doa-frames.json` | DOA, Nova, frames every 5 s, A vs B, for the visuals in the qry lines; prices nothing | after the pilot |

## Device log

- 2026-09-28 01:5xZ: pilot queued, `--who rendermode474`:
  A `1790559549-rendermode474-2188053` (master), B
  `1790559550-rendermode474-2188203` (this branch). The rest wait for the
  pilot's verdict in `pilots/rendermode474.ok`.

## For the next session

1. Read the pilot: E0 line in B, X/R in both (flip474's
   `sysmemjudge.py` on PR #516: `git show pr/516:docs/lanes/flip474/sysmemjudge.py`),
   thermal samples. Write `pilots/rendermode474.ok` with python3.
2. Queue AUF A/B, Blinx B, DOA-frames A/B (commands in each prediction's
   `queue_order`).
3. Read the arms job's `[job.arms]` verdict for the pgraph pair, and grep
   B's logcat for the `render_mode: auto (default)` line.

## Attempt 2 (resumed 2026-09-28 06:02Z)

**Why attempt 1 did not finish:** it ended correctly on a `waiting:`, for
the DOA pilot, CI and the arms job's pgraph pair, all outside the session.
All three resolved. CI is green on `b4612beec5`. The pilot landed, and the
pgraph pair was judged FAIL (label `regressed`).

### pgraph verdict: FAIL, 13 of 1059, not attributable

The arms job queued the pair unpinned (`request.json` `device` empty). A
ran on the **thor** and B on the **nova**. `ab_compare` says so itself:
"a leg that FAILS is NOT attributable". The 13 byte movers are 6 Stencil
REPLACE/ZERO captures, 4 Vertex_shader_rounding Geometry{Sub,Super}screen
captures, Blend_tests `#spot_0_ADD`, Antialiasing
`FramebufferNotModifiedBySurfaceState` and Surface_pitch `Swizzle`. These
are the captures the prediction already named as flip474's run-to-run
band, plus known thor/nova differences. The discriminating leg holds.
None of the 78 ZPass_pixel_count captures moved, so sysmem did not engage
on a pgraph disc. B's logcat has
`render_mode: auto (default) title=FFFF0002 TU_DEBUG=(unset)`. Neither arm
has `unreadable` rows in scores1.tsv or UtilAcceptVsock in run1.log. A
same-device replicate is queued: thor, 2 runs per arm, same prediction and
composition (below).

### DOA pilot: every leg holds

`sysmemjudge.py` (PR #516) over 151-288 s, nova, no env in either arm:

| arm | line | phase lines | GPU ms | X/R | gfps median (min) |
|---|---|---:|---:|---:|---|
| A master `59d478911e` | none | 30 | 59.2 | 1.00 | 13 (12) |
| B `61e0edf87c` | `render_mode: sysmem (table) title=54430006 TU_DEBUG=sysmem` | 50 | 31.6 | 0.02 | 20 (19) |

- E0, D1 (0.02 <= 0.25, 1.00 >= 0.8) and F1 (20 >= 19 and >= 13 + 4) hold.
- M0 holds (>= 15 lines each) and H0 holds: the longest gap is 4.6 / 3.9 s,
  with no crash.
- T0 holds. No `pause-*` or `thermal-pause-*` cooling device is engaged in
  any of the 12 samples of either arm. The hottest zone peaks at
  66.8 / 67.9 C, and min/median gfps is 0.92 / 0.95. The regimen is MAX.
- P0 cannot be read: `power` is absent from both result.json files, so no
  J/frame was measured.

The pilot verdict is written to `pilots/rendermode474.ok`.

### Queued 2026-09-28 ~06:25Z, `--who rendermode474`

| id | what |
|---|---|
| `1790575471-rendermode474-965765` / `1790575472-rendermode474-965811` | AUF A / B, nova, 420 s (`rendermode474-auf.json`) |
| `1790575472-rendermode474-965903` | Blinx B, thor, 180 s (`rendermode474-blinx.json`) |
| `1790575472-rendermode474-965991` / `1790575472-rendermode474-966037` | DOA frames A / B, nova, every 5 s (`rendermode474-doa-frames.json`) |
| `1790575472-rendermode474-966088` / `1790575473-rendermode474-966130` | pgraph A / B, **thor, runs 2**, `rendermode474-pgraph.json`, same suites and skip |

Judge the pgraph replicate by hand: `ab_compare.py` on the two ids with
`--expect docs/testing/predictions/rendermode474-pgraph.json`. The arms
job's thor/nova FAIL is superseded only by this same-device pair; state
that on the PR.

## Session 3 (resumed 2026-09-28 15:17Z)

**Why the previous session did not finish:** it ended on a
`[lane.rendermode474] waiting:` for the seven requests above, which is
the correct outcome. They were slow for two reasons. Hostops promoted
them to `1-` at 06:34Z. The Nova then fell off adb, and the four Nova
runs waited for hands. All seven are done now.

### pgraph, same device: PASS

`ab_compare.py` with `--expect rendermode474-pgraph.json`, run by hand,
A `1-1790575472-rendermode474-966088` (master) against B
`0-0-x-1790575473-rendermode474-966130` (this branch). Both arms ran on
the thor with 2 runs each.

**VERDICT: PASS: all 1059 registered checks hold.** 0 better, 0 worse,
1051 same and 8 inside the noise band. Both of B's logcats have
`render_mode: auto (default) title=FFFF0002 TU_DEBUG=(unset)`. No run
has `unscored` rows, and every run has `progress_log_proof`.

The arms job cannot see a verdict read by hand. It clears a FAIL only
with a later registration on the same issue. `rendermode474-pgraph-onedev.json`
(registered 15:21Z) is that registration. It is the same prediction
and composition with `runs_per_arm: 2`. Current master's `arms.sh` pins
both arms of a pair to one device (`affinity.py --choose`), so its pair
cannot repeat the thor/nova split. The prediction text says "36 ZPass
captures", copied from the first file. The disc has 78, and none of
them moved in either pair.

### AUF, nova, 299-420 s: every leg holds

| arm | line | phase lines | GPU ms | X/R | gfps median (min) |
|---|---|---:|---:|---:|---|
| A master `-965765` | none | 35 | 40.6 | 1.00 | 17 (15) |
| B `-965811` | `render_mode: sysmem (table) title=4541000D TU_DEBUG=sysmem` | 52 | 21.5 | 0.02 | 26 (22) |

- E0 holds: one line in B, none in A, and neither arm has an
  `env: TU_DEBUG` line.
- D1 holds: 0.02 <= 0.25 and 1.00 >= 0.8.
- S2 holds: 21.5 <= 0.75 x 40.6.
- F1 holds: 26 >= 22 and 26 >= 17 + 4.
- M0 holds: at least 15 lines in each arm.
- H0 holds: the longest gap is 3.5 / 2.3 s, gfps lines run to 427 / 425 s,
  and there is no crash.
- T0 holds: no `pause`/`thermal-pause` cooling device is engaged in any
  of the 16 samples of either arm. Min/median gfps is 0.88 / 0.85, under
  the MAX regimen.
- P0 cannot be read: no `power` field in either result.json, so there is
  no J/frame.

A's absolute GPU ms (40.6) is higher than flip474's base (24.9), because
this is a different window and a later build. The ratio inside the pair
is the leg.

### Blinx, thor, B only: untouched holds

`1-1790575472-rendermode474-965903`:
`render_mode: auto (default) title=4D530013 TU_DEBUG=(unset)`. That is
the prediction's line exactly, so a title not in the table keeps the
driver's default.

### DOA frames: V0 is only partly readable

Neither arm has a `power` field.

- A (`-965991`, GMEM) **aborted at 164 s of 300**: the Nova went off adb
  mid-route (`soak aborted: not-foreground`). Its last route frame is
  truncated. A has frames only up to the pre-fight screen of stage 1.
- B (`-966037`, sysmem) logs 6 `hakuX-rpbrk` lines with `qry > 0` in
  151-288 s, in three pairs: 158.6/161.1 s (qry 44, 26), 241.8/243.3 s
  (69, 30), 285.0/286.2 s (1, 18). A logs 1 rpbrk line in the window,
  with no qry.
- For the first pair, B's frames at 004319/004325 show the stage-1 clock
  tower fight: the clock face, the sun glare at the top left and the light
  shafts. In the same run, A shows the same stage pre-fight (003044,
  003050). The pilot's GMEM arm (`-2188053`, 202304/202330) shows the
  same clock-face camera in a fight. **By eye I found no element present
  in one mode and absent in the other**: glare, light shafts, clock face,
  shadows and HUD all appear in both. The comparison is scene against
  scene, not frame against frame, because the arms' timing differs
  (13 vs 20 gfps).
- For the second and third pairs, B's play frames (004432, 004456) show
  a clean fight and a KO screen, and 004520 is back at the title screen.
  No A frame covers those moments, so V0 is VOID for them: the query
  lines occurred, and the GMEM frames did not.

Not re-queued: this is a visual leg, and the brief says to report
rather than gate. #527 (the ZPASS value) is where a real difference
would be chased.

## Waiting (2026-09-28 ~02:00Z, attempt 1)

Waiting on three things: the pilot (A `-2188053`, B `-2188203`), CI on
`e2f5c22c1b`, and the arms job's pgraph pair. Posted as
`[lane.rendermode474] waiting:` on #530.
