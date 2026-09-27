# Audit pass 1: PR #435, lane buildflags427 (#427)

Head audited: `4be976969f`. Diff read: `android/app/build.gradle.kts`,
`android/app/src/main/cpp/CMakeLists.txt`, both prediction files,
`queue_soaks.sh`, and the NOTES sections the PR body cites.

**Verdict: 2 MEDIUM, 2 LOW. Needs remediation.** The three flags do what the
PR says they do: F0 reads them in the dispatcher's own APKs, and F1 shows the
vCPU-thread samples leaving emutls, the outline atomics and the PLT. The code
change is sound on the hardware it was tested on. The two MEDIUMs are a
hardware floor the change sets but does not enforce, and a FAIL verdict that
blocks the fold and was left standing.

## MEDIUM

### M1. `-march=armv8.2-a` sets a CPU floor that nothing enforces. Below it the app dies with SIGILL.

`CMakeLists.txt:12-13` puts `-march=armv8.2-a` on every target in the file,
including `xemu` and also `xiso_converter` (`:1107`), which the launcher loads
before any emulation. With it, clang emits LSE instructions (`casal`, `ldaddal`,
`swpal`) inline. Before this, it called the `__aarch64_*` helpers, which check
the CPU at run time and fall back to LL/SC. The only statement of a floor is one
line in `docs/investigations/perf-architecture.md:293` ("An SD 865-class floor
still has it"). The manifest, the README and the app have no gate.

**Failure scenario.** Take an ARMv8.0 device on Android 10 or later: Cortex-A73/A53
or A53-only parts such as the SD 835 (Pixel 2 on Android 11), SD 660/665/460 or
Helio G35. `minSdk 29` accepts it, so the APK installs. The first static
constructor or atomic in `libxemu.so` or `libxiso_converter.so` raises SIGILL
while the library loads. The process dies with no dialog and no log line of
ours. On master the same device ran, slowly. Neither golden sweep can see this,
because both devices (Thor, Nova) are ARMv8.2 or newer.

**Remedy.** Before the first `System.loadLibrary`, check for LSE in Kotlin (the
`Features` line of `/proc/cpuinfo` contains `atomics`). The check has to be in
Kotlin: any native check built from this CMakeLists would carry the flag and trap
itself. If LSE is missing, show an "unsupported CPU (needs ARMv8.2 / LSE
atomics)" screen and do not load the libraries. State the floor where users read
it (README), next to the Android 10 floor from L1.

### M2. The pgraph must-not-move prediction guards a capture family documented to drift. Its FAIL leaves the PR `regressed`, and `fold.sh` will not fold it.

`buildflags427-pgraph-inert.json` guards `Vertex_shader_rounding_tests/*` with no
exclusion. `docs/lanes/dpforce345/NOTES.md:94-95` says: "Do not guard
`Vertex_shader_rounding_tests/GeometrySuperscreen_*` in a one-run arm. It drifts
between runs of the same build, in the base arm too." The arm drifted as
documented (`GeometrySuperscreen_0.5624` better, `_1.0000` worse; the other 680
are byte-identical). `[job.arms]` judged FAIL and labelled the PR `regressed`.
NOTES says the lane expected the FAIL and chose to leave it.

The lane's reading of the two movers is well supported, and I do not dispute it.
The base arm shows the same defect, and the dpforce345 hashes show master off the
modal image on 4 of 9. The defect is in the PR's state. `fold.sh:958-970` refuses
any PR that carries an unsuperseded `regressed` verdict. It tells the lane to
re-register, and says not to remove the label by hand.

**Failure scenario.** The PR passes both audits and gets `fold-ready`. `fold.sh`
still posts "Not folded: this PR is labelled `regressed`" on every tick. Nothing
in the lane's plan supersedes the verdict, so the PR sits until a person steps in.

**Remedy.** This is dpforce345's remedy for the same case. Re-register the prediction on the
same refs with `GeometrySuperscreen_*` unguarded. Keep the rest of the suite
guarded with `Vertex_shader_rounding_tests/[!G]*`, `.../Geometry_*` and
`.../GeometrySubscreen_*`. Then let a fresh arm judge it. A dry judge against the
existing pair is not the verdict: the file postdates the arm.

## LOW

### L1. The PR body does not state the user-facing cost of `minSdk 26 -> 29`.

Android 8.0-9 devices can no longer install or update. The body justifies the
change only by the two test devices (SDK 33). One line in the body and in the
release notes covers it. This is a product decision, not a defect, but it should
be decided in the open.

### L2. The PR body reads leg F1 as a pass. As worded, it failed.

The registered leg F1 says "B: samples in `__emutls_get_address + __aarch64_*` == 0
on the vCPU thread". B has 54 such samples, all in system `libc.so`. NOTES records
"FAILS as worded" and gives the reason: the failure world the leg names would put
the samples in libxemu, and libxemu has 0. The PR body's table shows the 0.26%
but never says the leg failed as registered. A reader of the body alone sees a
clean pass. Add one clause saying so.

## Checked and not a finding

- **`-Wl,-Bsymbolic` scope.** It applies to `xemu` only. `libSDL2.so` and
  `libxiso_converter.so` are separate shared objects and are not affected. The
  exported `Java_*`/`SDL_main` table is unchanged (symcheck). In bionic, a
  dlopen'd library's own definitions come before its dependencies' in its local
  group, so a symbol libxemu defines and also imports from libSDL2 already bound
  to libxemu's copy. Binding it directly does not change which copy runs.
- **ELF TLS at API 29.** The PR's own runs show the native TLS segment working:
  four B soaks and a B profile ran with no tombstone.
- **The glib cross file.** It now carries the flag, so glib's atomics are inline
  too. Other ExternalProjects do not inherit `add_compile_options`. That costs
  only speed: mixing inline LSE with outline helpers is correct.
- **FP codegen.** `armv8.2-a` without `+fp16` or `+dotprod` adds nothing that
  scalar float code would use. 680 of 682 captures are byte-identical. That is
  consistent, and the 2 movers are M2's drift.
- **P1/P2 honesty.** The body reports the Crimson A/B as below resolution
  (both arms at the 30 fps cap) and the lever's size as a bound. That is the
  correct reading.

## What pass 2 must verify

- M1: on the head, a device without `atomics` in `/proc/cpuinfo` reaches a
  message and never reaches `System.loadLibrary`. Verify by reading the code path
  from the launcher, and also check that the order holds for `XisoConverterNative`,
  `XboxHddFormatter`, `XboxInsigniaHelper` and `XboxDashboardImporter`, which each
  load libraries themselves.
- M2: the PR no longer carries `regressed`, because a fresh arm judged a
  re-registered prediction. Removing the label by hand does not count.
