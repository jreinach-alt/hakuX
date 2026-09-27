# Audit pass 2: PR #435, lane buildflags427 (#427)

Head audited: `8aa686e940`. Pass 1: `2026-09-26-buildflags427-pass1.md`,
head `4be976969f`. Remediation commit read: `8aa686e940`.

**Verdict: clean. `fold-ready`.** M1's failure scenario can no longer occur:
no native library of ours loads below the LSE floor. M2's structural defect is
fixed: a re-registered prediction now exists, and the arms job will judge it.
`regressed` stays on the PR until that verdict arrives. `fold.sh` refuses to
fold while the label is present, so fold-ready does not let the PR through
before the arm has judged it. One new LOW is recorded below.

## M1. CPU floor: fixed

Pass 1 asked two things. A device without `atomics` must reach a message and
never reach `System.loadLibrary`. The same gate must hold for the four
helpers that load libraries themselves.

- **Every load site is gated.** `grep -rn loadLibrary android/app/src` finds
  six call sites of ours. Each has `CpuSupport.requireSupported()` before it:
  - `XisoConverterNative.kt:5`, inside the `try` that already catches
    `UnsatisfiedLinkError`, so a failed check gives `isLibraryLoaded = false`
    and no load happens;
  - the `NativeBridge` `init` blocks of `XboxDashboardImporter`,
    `XboxHddFormatter` and `XboxInsigniaHelper`;
  - `MainActivity.loadLibraries()`, before `super.loadLibraries()`, the only
    route into `SDL.loadLibrary`.

  Nothing else loads a library. `HakuXApplication` has no JNI. The `external
  fun` declarations in `SettingsActivity` and `GpuDriverHelper` bind to a
  library that one of the gated sites loaded. With no library loaded, calling
  one raises a Java `UnsatisfiedLinkError`, not SIGILL.
- **The launcher reaches a message.** `LauncherActivity.onCreate` checks
  `CpuSupport.hasLse` first. On failure it shows a non-cancelable "Unsupported
  CPU" dialog and returns before it reads prefs or starts any other screen.
- **The check itself.** It passes only when every `Features` line lists
  `atomics`, which is the correct answer on big.LITTLE parts. An unreadable
  cpuinfo, or one with no `Features` line, counts as supported and is logged.
  That fails open, which is the right direction for a check that cannot read
  its input. It is Kotlin, so the `-march` flag cannot reach it.
- **README** states the Android 10 and ARMv8.2/LSE floor and the message a
  user sees below it. That also covers L1's user-facing half.

## M2. `regressed` from a documented-drift capture: fixed in the registration, verdict pending

- `buildflags427-pgraph-inert.json` is re-registered on the same refs
  (`a_ref 15d9406b81`, `b_ref 6cd1a58b64`). Both are still ancestors of the
  head: the branch took a merge, not a rebase. The file's sha256 is new, and
  `arms.sh` binds a prediction to its sha256 (`collect()`, `:219-248`), so the
  next arms tick treats it as a new registration.
- `Vertex_shader_rounding_tests/*` is replaced by `[!G]*`, `Geometry_*` and
  `GeometrySubscreen_*`. The judge matches these with `fnmatch`
  (`ab_compare.py:963`), which supports `[!G]`. The only G-prefixed families
  in the suite are `Geometry_`, `GeometrySubscreen_` and
  `GeometrySuperscreen_`, so exactly the documented-drift family is
  unguarded. A leg that matches no capture fails the judge
  (`ab_compare.py:964-967`), so a typo in any of the three legs would show up
  as a FAIL. It would not silently guard nothing.
- The prediction text records why the family is unguarded and cites
  dpforce345's NOTES. It does not downgrade the claim for the rest of the
  suite.

Pass 1 asked for the PR to lose `regressed` through a fresh arm. That has not
happened yet: the only `[job.arms]` verdict (00:28Z) is the FAIL on the old
file. It is the one item pass 2 cannot check today. Pass 1's scenario, "sits
until a person steps in", no longer holds: nothing needs a person now. The arms
job queues the new file, and a PASS clears `regressed` automatically
(`fold.sh:958-970`). If the new arm FAILs, `regressed` stays, `fold.sh` keeps
refusing, and that FAIL is a new finding for the lane. The gate that enforces
this condition is in the fold job, not in this audit.

## L1, L2 (pass 1 LOWs)

- L1: the README now states the Android 10 floor. Whether the PR body states
  it is left to the lane. LOW, not re-checked.
- L2: not re-checked. LOW.

## New LOW

### L3. On an unsupported CPU, `MainActivity` shows SDL's error dialog and then crashes on `nativeSetenv`.

`SDLActivity.onCreate` catches the `UnsatisfiedLinkError` from
`requireSupported()`, shows its "SDL Error" dialog and returns.
`MainActivity.onCreate` then goes on to call `SDLActivity.nativeSetenv`
(`MainActivity.kt:98`). No library is loaded, so this throws an uncaught
`UnsatisfiedLinkError` and the `:xemu` process crashes with a Java trace, not
SIGILL.

**Scenario:** this is reachable only if `MainActivity` starts without
`LauncherActivity` having refused first. `MainActivity` is
`exported="false"`, and every in-app route to it passes the launcher, so no
path from a fresh install reaches it. The same thing already happens on
master for any broken-library case, so this is not new with this PR. The fix
is to return from `MainActivity.onCreate` when `SDLActivity.mBrokenLibraries`
is set.

## Checked and not a finding

- `CpuSupport.hasLse` is a `lazy` per process. `MainActivity` runs in `:xemu`,
  re-reads cpuinfo there and gets the same answer.
- The remediation touches only Kotlin, README, NOTES and the prediction file.
  `CMakeLists.txt` and `build.gradle.kts` are unchanged since pass 1, so pass
  1's "checked and not a finding" items still hold.
