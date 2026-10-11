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

Pilot batch (OFF1, ON1) queued first per the 30-min device-time gate; read,
then `pilots/fastpaths1010.ok` written before queuing the rest (ON2, OFF2),
giving the registered OFF,ON,ON,OFF order.

| run | arm | result id | warm countdown (ms) | marks | valid starts | on-lines (4) |
|---|---|---|---|---|---|---|
| 1 | OFF | `1-1791693697-fastpaths1010-2485559` | 44.58 | 12 | 12 | 0/4 (correct) |
| 2 | ON  | `1-1791693739-fastpaths1010-2489599` | 34.36 | 12 | 12 | 4/4 (correct) |
| 3 | ON  | `1-1791695098-fastpaths1010-2835211` | 34.06 | 12 | 12 | 4/4 (correct) |
| 4 | OFF | `1-1791695102-fastpaths1010-2836733` | 43.89 | 12 | 12 | 0/4 (correct) |

Arm means (`fpread.py`'s `period()`, mean of each run's own period): **ON 34.22
ms**, **OFF 44.23 ms**, D = +10.01 ms. Every run's `request.json` `env` field
matched its intended arm exactly; every run showed the arm's four on-lines
(`[reportasync] on`, `[texscan] on`, `[drawrec1010] drawrec=1 vtx=1 shc=1`,
`[perdraw433] bulk=1 ubercache=1 fogcache=1`) when ON and none of them when
OFF -- checked against `fpread.py`'s exact `LOGS_ON` regexes, not a looser
grep (an early looser grep on OFF1 matched the all-zero diagnostic lines,
e.g. `[perdraw433] bulk=0 ubercache=0 fogcache=0`, which is a different line
and does not trip the strict check).

One `hakuX-build` line is odd and worth naming, though it is not a failure:
every run, ON and OFF alike, logs `fastpaths: ON (#433)`, because that line
is `MainActivity`'s own read of the app pref (default `true`, untouched by
`--env`), printed before `env_vars` is applied by `xemu_android.cpp`. The
OFF arm's actual override still lands -- proven by the all-zero native
diagnostic lines and the absent on-lines above -- the same separation
surfgpudefault1009's own device proof relied on (it logged `surfgpu: ON`
then a separate `env:` line ~48 ms later, same PID). Not fixed here (no
native/`MainActivity` logic change beyond what step 1 already made; the log
text reads the switch, not the resolved env, same as surfgpudefault1009's).

`s11-g11.png` (one of the 12 warm-window frames) checked by eye for one ON
and one OFF run: car present and moving (different road position, different
speedometer reading, different split time between the two), flare decals
render the same way in both, no missing geometry or black frames.

`python3 docs/lanes/fastpaths1010/fpread.py <OFF1> <ON1> <ON2> <OFF2> --expect
docs/testing/predictions/fastpaths1010-nfs.json` -- **VERDICT: PASS**, 2 of 2
non-validity checks hold (W: ON 34.22 <= 36.0; D: +10.01 >= 5.0), all V legs
pass.

## 4. Step 3: Playable-title screen

(not started)
