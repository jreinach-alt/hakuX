# lane.gmem474 (#474): Turnip render mode per title, judged by J/frame

PR #582. Base master `30695ba1a9`. Issue #474.

#530 made Turnip sysmem the per-title default for DOA Ultimate and AUF.
flip474 chose it on SPEED (AUF 16 -> 24, DOA 13 -> 21 gfps, Nova, MAX). The
critical path is now sustained fps within the heat budget, so this lane
measures each mode's **energy per frame** at the device defaults, per title,
and keeps or changes the per-title default on that.

## 1. Brief corrections (read before re-using the brief)

- **`TitleDefaults.kt` does not exist.** #530's table is `kTitleRenderModes`
  in `android/app/src/main/cpp/xemu_android.cpp` (`ApplyRenderMode`). A
  second PR that changes a title's default edits that table, not a Kotlin
  file.
- **No request can set the per-game `render_mode` override.** `request.sh`
  has `--env` (the `env_vars` pref) and nothing for `runtime_override_*`.
  On master a DOA/AUF run always gets `sysmem` from the table unless the env
  `TU_DEBUG` names `sysmem` or `gmem`, so the autotune arm (A) and the
  profiled arm (D) cannot be run on master. See section 3.
- **`forcebin` is not "one binning pass instead of two replays".**
  `tu_util.cc:344-353`: with forcebin a direction that has one tile is split
  in two (so a 1x1 pass becomes 2x2 = 4 tiles), and `binning_useful` is
  forced true (`:509-514`). Arm C is a binning pass plus up to four tiles,
  each running only the draws binned to it. Whether that beats one sysmem
  pass depends on whether DOA's heavy pass costs per draw (flip474's guess,
  section 16 of its NOTES) or per pixel.
- **Forza is not usable as the unsaturated title**: its fps decays from the
  invalid-surface list since #517 (#579, lane.forzadecay414). Crimson Skies
  on the Thor is the unsaturated title (29-30 gfps capped, GPU 5-7 ms).

## 2. The fleet driver recognises every option (step 1)

Read from the fleet's binary, `vulkan.purple.so` sha256 `1d80dfa01965...`
(18,869,912 bytes; the same file in `~/hakux-work/drv/T30`, `turnip_t30` and
the Thor backup), `PurpleVK 26.3.0-devel (git-62ac221a33)`:

| option | evidence in the binary |
|---|---|
| `TU_DEBUG=sysmem`, `gmem`, `forcebin`, `startup` | `tu_debug_options` (`.data.rel.ro` 0xdabf10) holds `startup`=0x1, `nobin`=0x4, `sysmem`=0x8, `forcebin`=0x10, `gmem`=0x1000 |
| `TU_AUTOTUNE_ALGO=profiled` | the `call_once` lambda of `tu_autotune::get_env_config()` (0x9e3ca4) reads `os_get_option("TU_AUTOTUNE_ALGO")`, and for length 8 compares the immediate 0x64656c69666f7270 (`profiled`) and sets algorithm 1. `bandwidth`, `prefer_sysmem`, `prefer_gmem` and `profiled_imm` are compared the same way; anything else logs `Unknown TU_AUTOTUNE_ALGO '%s', using default` |
| default algorithm | `bandwidth` (0) in the pinned tree (`tu_autotune.cc:102`), so `profiled` is a real arm, not the default |

That is static. Each run also proves its own mode: `TU_DEBUG=startup` makes
the driver log the parsed flag word (`TU_DEBUG=0x..`, `tu_util.cc:134`) and
`TU_AUTOTUNE_ALGO=N (name)` (`tu_autotune.cc:300`). Those go to the `TU`
tag, which the dispatcher's `LOGCAT_SPEC` drops, so every arm sets
`MESA_LOG_FILE` to a file in the app's external files dir and `--pull`s it
(Mesa's file logger `fflush`es each line, `util/log.c:312`).

## 3. How the arms are set

Measurement build `db1e8a7f12`: #530's two table rows read `"auto"`, so the
app sets no `TU_DEBUG` of its own, and the `render_mode:` line still names
the table (`render_mode: auto (table) title=54430006 TU_DEBUG=<env>`). It is
reverted by `080e976e7d` on this branch, so the PR's net diff has no
emulator code. One apk runs every arm on a device.

| arm | env (plus `PERF_REGIMEN=default`, `MESA_LOG_FILE=.../gmem474-<title>-<run>.log`) | Mesa flag word |
|---|---|---|
| A (A1, A2) | `TU_DEBUG=startup` | 0x1 |
| B | `TU_DEBUG=startup,sysmem` (the driver sees what #530 ships) | 0x9 |
| C | `TU_DEBUG=startup,gmem,forcebin` | 0x1011 |
| D | `TU_DEBUG=startup`, `TU_AUTOTUNE_ALGO=profiled` | 0x1, plus `TU_AUTOTUNE_ALGO=1 (profiled)` |

A runs twice (A1 first, A2 last) for the noise floor and the order effect.

## 4. Registered (before any run)

`gmem474_register.py db1e8a7f12` wrote:

| file | title, device | soak, window (s from soak start) | runs |
|---|---|---|---|
| `gmem474-doa.json` | DOA, Nova | survey 300 s, 151-288 (the fight) | A1 B C D A2 |
| `gmem474-auf.json` | AUF, Nova | survey 600 s, 299-590 (mission play, ~10 power samples) | A1 B C D A2 |
| `gmem474-crimson.json` | Crimson, Thor | crimson-skies 360 s, 120-350 | C D (pilot), then A1 B A2 |

The decision rule is in each file (`decision_rule`): a non-shipped arm
replaces the shipped one only if it is not VOID, loses at most 1 gfps, and
beats the shipped J/frame by more than max(noise, 5%). C and D wins are
reported, not shipped (the table cannot express them).

Reader: `gmemread.py --from F --to T <runs>`. Queue: `queue.py <key> <runs>`,
which reads everything from the prediction.

## 5. Runs

Pilot, queued 2026-09-28 ~20:30Z (13:30 PDT), Thor, release priority:
Crimson C `1-1790625696-lane.gmem474-3784417`, then Crimson D
`1-1790625696-lane.gmem474-3784577`. About 1.5 h of Thor queue is ahead of
them (lane.pacing's eight Crimson/Otogi soaks, titleroutes).

What the pilot must show before the other 13 runs are queued (pilot rule):
the Mesa log is pulled and reads `TU_DEBUG=0x1011` (C) and
`TU_AUTOTUNE_ALGO=1 (profiled)` (D); the `render_mode:` line carries the
env's `TU_DEBUG`; `gmemread.py --from 120 --to 350` prints J/frame from >= 3
power samples, GPU from hakuX-phase, and no pause; the shots show flight.
Then write `pilots/lane.gmem474.ok` and queue the Nova interleave (DOA A1,
AUF A1, DOA B, ... AUF A2) and Crimson A1, B, A2. The Nova is on
hostops' battery hold (14% at 18:10Z, lifted at >= 80%).

## 6. Waiting (2026-09-28 ~20:35Z, attempt 1)

On the two pilot requests above, outside this session. When they land:
read them with `gmemread.py --from 120 --to 350 3784417 3784577`, write the
pilot verdict, queue the rest with `queue.py`.
