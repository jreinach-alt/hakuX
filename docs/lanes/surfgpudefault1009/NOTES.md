# lane.surfgpudefault1009 -- the surfgpu switch as a Graphics toggle, on by default (#433, 0.5)

Owner, 2026-10-09 23:2x PDT, verbatim: "2 changes to queue up then: make the switch a visible toggle in the Graphics
option, and set it to on by default. If we can get them into the nightly, even better." Tonight's nightly is held
for this lane's fold, up to 06:00 PDT.

## 1. Merge lane.surfgpu1009

`git merge --no-edit origin/lane/surfgpu1009` fast-forwarded `39379dafdd..31897cb197` (clean, no conflicts). That
head carries `surfgpu_enabled()` in `hw/xbox/nv2a/pgraph/vk/surface.c`: `getenv("HAKUX_SURFGPU")`, on only when the
value's first byte is `'1'`, logged once as `[surfgpu] on`. Off (unset or anything else) reproduces the shipped
behavior exactly. No native change made in this lane -- `surface.c` stays surfgpu1009's row.

## 2. Settings plumbing, copying d4a02e2060 (the Ubershader setting)

Read `d4a02e2060` (#569, "the ubershader on by default, an Ubershader setting ...") first and matched its shape:

- `MainActivity.kt`: a `surfgpuEnabled(prefs)` function (per-game override, else the global `"surfgpu"` bool pref,
  default `true`), called right after the existing `ubershaderOn` block (same place `HAKUX_GPL` is set), setting
  `HAKUX_SURFGPU` to `"1"`/`"0"` via `nativeSetenv` and logging `surfgpu: ON|OFF (#433)`. Unlike the Ubershader
  setting, this one does **not** read `env_vars` itself to decide anything -- there is no startup banner to key off
  it, and an `HAKUX_SURFGPU=` line in the `env_vars` pref still wins regardless, applied after `nativeSetenv` by
  `xemu_android.cpp`. No banner: the owner did not ask for one, and the brief says not to add one.
- `SettingsActivity.kt`: `"surfgpu" to true` in the defaults map; `setupSwitch(R.id.switch_surfgpu, "surfgpu", true)`
  right after the Ubershader switch (no native setter -- read at next launch, same as Ubershader).
- `PerGameSettingsManager.kt`: `"surfgpu"` added to the per-game override key list.
- `PerGameSettingsActivity.kt`: `addBoolPicker(container, "surfgpu", ..., globalDefault = true)` right after the
  Ubershader picker.
- `activity_settings.xml`: a `group_surfgpu` switch block, same shape as `group_ubershader`, placed right after it.
- `strings.xml`: `settings_surfgpu` = "GPU surface reuse" (label in the Ubershader string's plain-player style, not
  the internal flag name); `settings_surfgpu_desc` names the one-line tradeoff -- "Turn off only if a game shows
  stale or flickering images with it on" -- per the brief's exact failure mode to describe.

No native change: `surface.c`'s own default (`surfgpu_state` initialised from `getenv`) stays off for anything that
does not set the env var, i.e. for non-app builds and for request.sh runs that don't pass `--env`. The app always
calls `nativeSetenv("HAKUX_SURFGPU", ...)` now, so an app launch's behavior is controlled by the Settings switch, on
by default.

## 3. Build

**Attempt 1 did not finish**: it started `assembleDebug` with `run_in_background` and ended its turn to "report
back once it finishes." In `claude -p` a turn ending *is* the session ending -- nothing resumes it, and the
unit's cgroup killed the build along with the session. Lane.local's addendum 1 names the fix: run long commands
in the foreground, or background them and wait on the log in the *same* turn. The uncommitted edits (this NOTES.md
section included) survived in the worktree; nothing else was lost.

Attempt 2 (this session) merged `origin/master` (39379dafdd..96852d8144, two nightlynotes1009 commits, no
overlap with this lane's files) on top of the fast-forward to `31897cb197`, then ran the addendum's narrower
command in the foreground:

```
cd android && JAVA_HOME=/home/justin/toolchains/jdk21 ANDROID_SDK_ROOT=$HOME/Android/Sdk \
  PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmake/3.30.3/bin:$HOME/.local/bin:$PATH" \
  ./gradlew --no-daemon :app:compileDebugKotlin
```

`BUILD SUCCESSFUL`, `:app:compileDebugKotlin UP-TO-DATE` -- attempt 1's killed `assembleDebug` had already reached
and finished that task before the kill landed, so Gradle's input-hash cache shows the six changed files already
compiled clean under the current content. Not re-run from scratch, but a genuine pass: Gradle keys UP-TO-DATE on
source hashes, not timestamps, and the files on disk are the ones with the surfgpu switch in them.

## 4. Device proof (Nova)

Committed section 1-3's work as `214da4fe81`, pushed `lane/surfgpudefault1009`, then queued both arms at once
(pilot gate did not apply: two 480 s soaks is ~19 min of device time, under the 30 min that always goes through
with no `pilots/surfgpudefault1009.ok` file). Both `--ref HEAD` resolved to `214da4fe81`.

```
HAKUX_RELEASE_PRIO=1 docs/testing/request.sh --who surfgpudefault1009 \
  --purpose "surfgpudefault1009: app default (switch on, no env), NBA Live 07 A (#433)" \
  --title "454100A1-NBA_Live_07.xiso.iso" --route nbalive07 --seconds 480 --perflog \
  --device nova --ref HEAD --no-expect "settings plumbing; perf evidence is lane.surfgpu1009's"
# -> 1-1791614519-surfgpudefault1009-2139156

HAKUX_RELEASE_PRIO=1 docs/testing/request.sh --who surfgpudefault1009 \
  --purpose "surfgpudefault1009: env override (HAKUX_SURFGPU=0), NBA Live 07 B (#433)" \
  --title "454100A1-NBA_Live_07.xiso.iso" --route nbalive07 --seconds 480 --perflog \
  --device nova --ref HEAD --env HAKUX_SURFGPU=0 \
  --no-expect "settings plumbing; perf evidence is lane.surfgpu1009's"
# -> 1-1791614524-surfgpudefault1009-2139314
```

Both queued at release priority (`HAKUX_RELEASE_PRIO=1`), sat behind one running and one queued `perdraw1009`
request plus a build for this new ref, then ran in order. gfps figures below are the mean/median of every
`gfps=` sample in `logcat.txt` from the route's `mark gameplay` line to the end (the loop body, same window
lane.surfgpu1009's own NBA07 reads used).

| | A: no env (switch default) | B: `--env HAKUX_SURFGPU=0` |
|---|---|---|
| result id | `...2139156` | `...2139314` |
| `[surfgpu] on` present | yes (1x) | no (0x) |
| MainActivity log | `surfgpu: ON (#433)` | `surfgpu: ON (#433)` (the switch's own decision; see below) |
| `env: HAKUX_SURFGPU=` (xemu_android.cpp) | not set (no env passed) | `HAKUX_SURFGPU=0` |
| `[surfgpu] frames=` lines | present throughout | **0** |
| `hold=`/`frames=` (sampled) | `60/60` = 1.00/flip | n/a (surfgpu_enabled() false) |
| gfps, post-mark (n samples) | median 47.0, mean 44.9 (n=241) | median 23.0, mean 21.0 (n=114) |
| pass bar (brief) | `[surfgpu] on`, hold ~1.00/flip, gfps >= 40 | no `[surfgpu] on`, gfps ~22 | 
| verdict | **PASS** | **PASS** |

**Why B's Kotlin log still says `ON`.** `surfgpuEnabled(prefs)` in `MainActivity.kt` reports the *switch's*
decision (global default `true`, no per-game override here) and calls `nativeSetenv("HAKUX_SURFGPU", "1")`
regardless of what a queued request's `--env` will do -- by design, per the brief: the `env_vars` pref's
`HAKUX_SURFGPU=0` line is applied by `xemu_android.cpp` AFTER `nativeSetenv`, and wins. `logcat` confirms the
order: `surfgpu: ON (#433)` at 00:29:27.180, then `env: HAKUX_SURFGPU=0` at 00:29:27.228 (48 ms later, same PID).
`surfgpu_enabled()` in `surface.c` then reads the final value at first use and logs nothing (`0` occurrences of
`[surfgpu] on` or `[surfgpu] frames=` anywhere in B's `logcat.txt`) -- the native switch is off for the whole run,
exactly as it should be when the request overrides the app's own default.

This is the thing step 4 set out to show: the app's on-by-default switch reaches native code (A), and an
`--env` override still reaches native code ahead of the switch (B) -- so `request.sh --env HAKUX_SURFGPU=0/1`
remains available to any future lane working on `surface.c` itself, independent of whatever the Settings default
is at the time.

No golden/pixel check queued here (brief: "Prediction: none ... the performance evidence is lane.surfgpu1009's" --
that lane's own golden3 (9.4) and NBA07-held (9.3) reads already cover pixel safety and the `record`/`hold`
mechanics; this lane changes no native code, so there is nothing new to check pixels against).

## 5. PR.md, State: ready

Committed as `52f32bb2c8`, pushed. `Files:` lists only what this lane itself wrote; a note in PR.md flags that
the wider `git diff --stat origin/master...HEAD` also carries lane.surfgpu1009's own unfolded files, merged in
per step 1 so device proof above runs against real `HAKUX_SURFGPU` code.

## 6. Fold-head confirmation run

Step 5's commit (`52f32bb2c8`) changed the head sha again, so arm A above (on `214da4fe81`) is not built from
the fold's actual head. Queued one more run, same shape as arm A, on the new head:

```
HAKUX_RELEASE_PRIO=1 docs/testing/request.sh --who surfgpudefault1009 \
  --purpose "surfgpudefault1009: fold-head confirmation (switch default on, no env), NBA Live 07 (#433)" \
  --title "454100A1-NBA_Live_07.xiso.iso" --route nbalive07 --seconds 480 --perflog \
  --device nova --ref HEAD --no-expect "fold-head confirmation; settings plumbing, perf evidence is lane.surfgpu1009's"
# --ref HEAD resolved to 52f32bb2c8
# -> 1-1791617969-surfgpudefault1009-3278970
```

Wrote `docs/lanes/surfgpudefault1009/WAITING` naming this id and its pass bar, per the brief's step 6 and per
lane.surfgpu1009's own section 9's lesson (a PR comment is not polled offline; a `WAITING` file is what jam-duty
and lane.local's sweep actually read). Stopping here: nothing left in the brief that doesn't wait on this run's
result.
