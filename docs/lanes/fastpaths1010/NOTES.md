# lane.fastpaths1010 -- the six renderer switches as one Graphics toggle (#433, 0.5)

## 1. Precondition: drawrec1010 is in master

`git merge-base --is-ancestor lane/drawrec1010 origin/master` passes (exit 0):
`lane/fastpaths1010` branched from `9b26a9647c`, which IS the drawrec1010 fold
commit. All six switches' native code (`HAKUX_REPORT_ASYNC`, `HAKUX_TEXSCAN`,
`HAKUX_DRAWREC`, `HAKUX_UNI_BULK`, `HAKUX_UNI_UBERCACHE`, `HAKUX_UNI_FOGCACHE`)
is present on this branch's base; confirmed by `grep getenv` in
`hw/xbox/nv2a/pgraph/vk/{reports,texture,draw,shaders}.c`. No merge of
`drawrec1010` needed -- it already folded.

## 2. Step 1: the toggle

Copied the shape of `7d574ece8b` (surfgpudefault1009), which copied `d4a02e2060`
(#569, Ubershader): a `fastpaths` boolean pref (global + per-game override,
`PerGameSettingsManager.runtimeKey`), default `true`. `MainActivity.onCreate`
sets all six env vars to `"1"`/`"0"` together right after the `HAKUX_SURFGPU`
block, from one `FASTPATHS_VARS` array, and logs one `hakuX-build` line:
`"fastpaths: ON (#433)"` or `"...OFF..."`. No native change; each switch's own
C default is still off (`getenv` returns NULL for a bare `request.sh` run with
no env and no app in front of it, e.g. selftests and desktop).

An `--env` entry for any one of the six still wins: `xemu_android.cpp` applies
the `env_vars` pref line AFTER `MainActivity`'s `nativeSetenv` calls (the same
ordering surfgpudefault1009 relied on and proved in its own device pair).

Files touched: `MainActivity.kt`, `SettingsActivity.kt`,
`PerGameSettingsManager.kt`, `PerGameSettingsActivity.kt`,
`activity_settings.xml`, `strings.xml`.

`./gradlew compileDebugKotlin --offline -q` -- exit 0, no diagnostics.

### 2.1 Why one switch, not six

The brief asks for exactly this (one Graphics toggle). A per-switch picker
set already exists in `PerGameSettingsActivity`-style per-game overrides for
the OTHER settings (ubershader, surfgpu) one at a time; six more of those
would let a per-game override turn on e.g. only `HAKUX_TEXSCAN` without
`HAKUX_REPORT_ASYNC`, which texscan1010 measured as a regression alone
(slower than both off). Keeping them as one app-level switch makes that
combination unreachable from the UI; the override is read as six, not one,
for provenance (each native `getenv` site is independent), but there is no
UI path to light only one of them. `--env` still can, for testing.

## 3. Step 2: device proof (NFS MW, `nfs-mw-quickrace`)

Prediction: `docs/testing/predictions/fastpaths1010-nfs.json`, registered
before any device run, `a_ref` = `b_ref` = this lane's step-1 commit (one
binary, env-only A/B -- the same reason texscan1010-nfs.json and
postput1010-nfsall.json used an equal pair, and the same reason their
queue_order says "arms.sh skips a_ref == b_ref": the lane queues these
itself with `request.sh`, not the automatic arms job).

Reader: `docs/lanes/fastpaths1010/fpread.py`, built on
`docs/lanes/reportasync1010/raread.py`'s parsing (marks, pace lines,
`bad_starts`, `has_log`) with its own `arm_of` (ON = request.json env holds
none of the six `=0` overrides; OFF = holds all six) and its own two legs
(`W`: ON's warm countdown <= 36.0 ms; `D`: OFF - ON >= 5.0 ms warm), plus the
log-line check for all four on-lines (`[reportasync] on`, `[texscan] on`,
`[drawrec1010] drawrec=1 vtx=1 shc=1`, `[perdraw433] bulk=1 ubercache=1
fogcache=1` -- the three UNI_* switches share one combined log line, so "each
switch's own line" is four distinct lines covering six vars) present on
every ON run and absent on every OFF run.

(fill in after the device runs: result ids, table, verdict)

## 4. Step 3: Playable-title screen

(not started)
