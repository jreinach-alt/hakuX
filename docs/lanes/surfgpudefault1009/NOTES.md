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
