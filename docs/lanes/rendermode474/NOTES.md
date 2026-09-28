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
