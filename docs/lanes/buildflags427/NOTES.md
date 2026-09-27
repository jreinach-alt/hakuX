# lane.buildflags427 -- #427 host build flags

Lever 4 of `docs/investigations/perf-architecture.md` (section 3.3): native ELF
TLS, inline LSE atomics, no intra-library PLT for `libxemu.so`.

**The lever's size is a BOUND, not a measured gain.** In the dated 09-11
Crimson simpleperf capture, 4.40% of the vCPU thread's samples and 3.73% of the
PFIFO thread's were in emutls, outline atomics, PLT stubs and pthread TLS.
Removing all of it saves at most that share. Crimson is vCPU-bound, so gfps can
rise by at most about 4.6%. Whether an A/B on a game can resolve that is itself
a question the soaks answer (leg P2).

## The change (b_ref `6cd1a58b64`, a_ref `15d9406b81` = master)

| flag | where | what it removes |
|---|---|---|
| `minSdk 26 -> 29` | `android/app/build.gradle.kts` | emulated TLS (`__emutls_get_address`, and the `pthread_getspecific` inside it) on `tcg_ctx`, `current_cpu`, `hakux_jmp_trans_armed`. AGP passes `ANDROID_PLATFORM=android-29`, and the glib cross file's `--target` follows it. |
| `-march=armv8.2-a` | `CMakeLists.txt`: `add_compile_options` before any target, and in the glib meson cross file's `c_args`/`cpp_args` | outline atomics (`__aarch64_*` helpers) |
| `-Wl,-Bsymbolic` | `target_link_options(xemu ...)` | PLT stubs for calls between functions inside `libxemu.so` |

I chose `-Bsymbolic` over `-fvisibility=hidden`. Hidden visibility would need
every JNI entry point and `SDL_main` (looked up by SDL with `dlsym`) marked
default. `-Bsymbolic` leaves the exported table as it was.

**Device OS versions** were read with `adb getprop` (read-only, 2026-09-26):
Thor `bdc158a5` and Nova `ee317437` are both SDK 33 (Android 13), so minSdk 29
is below both. No stored run metadata recorded the Thor's version.

## Symbol table, before any device run

`symcheck.py` reads a built `libxemu.so` or APK with the NDK's llvm tools and
counts call sites. A is the dispatcher's `builds/aaf01a1cef.apk` (master one
commit before the base; build files identical). B is a local debug build of
`6cd1a58b64`.

| counter | A (master) | B (flags) |
|---|---:|---:|
| `bl __emutls_get_address` call sites | 1,828 | 6 |
| `__emutls_v.*` TLS control variables | 40 | 2 |
| PT_TLS segment (native TLS) | no | yes |
| `bl __aarch64_{cas,swp,ld*}` outline-atomic call sites | 1,599 | 289 |
| outline-atomic helpers defined | 28 | 4 |
| inline LSE instructions | 28 | 1,326 |
| PLT entries (JUMP_SLOT) | 9,374 | 635 |
| of which target a symbol libxemu defines | **8,753** | **0** |
| exported dynamic symbols | 18,712 | 18,710 |
| `Java_*` exports / `SDL_main` | 44 / yes | 44 / yes |

The residue in B is all in the NDK's prebuilt `libc++_static`, which is
compiled for the generic target. Emutls is called only from `__cxa_thread_atexit`
and libc++abi's thread-local destructor manager. The 289 outline calls are in
`std::__ndk1::locale::__imp` setup and similar one-time code. `.scratch/callers.py`
(not committed) found no caller outside `std::__ndk1`/`__cxxabiv1`.
`__aarch64_swp4_acq_rel`, the brief's named example, is gone.
Removing the residue would need `c++_shared`, which gains nothing on a hot path.

The export diff is exactly the TLS variables' representation:
`__emutls_v.X`/`__emutls_t.X` became `X`.

## Predictions (registered before any device run)

- `docs/testing/predictions/buildflags427-pgraph-inert.json`: 12 pgraph suites
  identical between arms (the owner's rule: no pgraph suite regresses). The
  arms job queues it.
- `docs/testing/predictions/buildflags427-crimson-soak.json`: Crimson Skies,
  Thor, crimson-skies route, 240 s, A1 B1 A2 B2. Legs: M0 instrument; F0 the
  symcheck counters on the dispatcher-built APKs; F1 the simpleperf counter;
  P1 gfps B/A in [0.98, 1.08]; P2 resolution.

## Results (session 2, 2026-09-26 PDT)

The hostops re-pinned all four soaks and both profiles from the Thor to the **Nova**
`ee317437`, all together, so every A/B pair stayed on one device (PR comment,
13:59 PDT). The pgraph arm also ran on the Nova. Read every number here as a Nova number.

### Soaks: Crimson Skies, crimson-skies route, 240 s

`docs/lanes/ghoul311/gfps.py --from 110 --to 240`. Every run reached `mark gameplay`,
and the route frames show flight with the HUD in both arms. `logcat` has no crash or
DEBUG lines on any run.

| run | ref | apk_sha | request id | perf lines 110-240 s | median gfps | min-max |
|---|---|---|---|---:|---:|---|
| A1 | 15d9406b81 | acb81bbaa1d1 | 1790455170-buildflags427-4117276 | 63 | 29 | 23-31 |
| B1 | 6cd1a58b64 | 460b947a4109 | 1790455170-buildflags427-4117310 | 63 | 29 | 3-31 |
| A2 | 15d9406b81 | acb81bbaa1d1 | 1790455170-buildflags427-4117367 | 62 | 29 | 10-30 |
| B2 | 6cd1a58b64 | 460b947a4109 | 1790455170-buildflags427-4117403 | 63 | 29 | 24-31 |

All four sit at 29 against Crimson's self-imposed 30 fps cap, with `G` (frame interval)
at about 33 ms throughout. **On the Nova, this route is pinned at the cap in both
arms, so gfps cannot show a gain of any size.** It can show a regression, and it shows
none. (The Thor baseline from titleplay p1 had a median of 26 with headroom. That is
the device where a gain could have shown, but these runs were not on it.)

### Profiles (leg F1): 30 s simpleperf, Crimson gameplay, Nova, same session

`/home/justin/hakux-work/perf/2026-09-26-buildflags427/{a,b}.data`, captured by the host with
`profile_guest.sh 30`. Counted with `docs/lanes/buildflags427/f1.py`, which classifies
the leaf frame of each sample on the vCPU thread (the tid whose chains run through
`mttcg_cpu_thread_fn`).

| vCPU-thread leaf samples | A (tid 20767, n=20,626) | B (tid 25062, n=20,402) |
|---|---:|---:|
| `__emutls_get_address` | 161 (0.78%) | **0** |
| `__aarch64_*` outline atomics | 230 (1.12%): 156 libxemu, 74 libc | 54 (0.26%): **0 libxemu**, 54 libc |
| `pthread_getspecific` | 80 (0.39%) | 1 (0.00%) |
| `@plt` stubs | 235 (1.14%): 213 in libxemu.so | 29 (0.14%): 21 in libxemu.so |
| **sum** | **706 (3.42%)** | **84 (0.41%)** |

The counter moved. Every remaining outline-atomic sample in B is in the platform's
`/system/lib64/libc.so`, called from bionic's `pthread_mutex_lock/unlock` and scudo's
`HybridMutex`. Those are the platform's own outline helpers, and no flag in this build
reaches them. A has 74 of the same.

### pgraph must-not-move arm (12 suites, Nova)

`1790455260-arms-buildflags427-base-4129766` (A) and `1790455261-arms-buildflags427-fix-4129802` (B).
Of 682 captures, 680 are byte-identical (sha256). Status: 66 non-ok rows in each arm, the
same rows. The two that moved are both in `Vertex_shader_rounding_tests`, one per arm, in
opposite directions:

| capture | A | B |
|---|---|---|
| `GeometrySuperscreen_0.5624` | 800 px off (max 255) | exact |
| `GeometrySuperscreen_1.0000` | exact | 570 px off (max 255) |

In both, the differing pixels are a 4-row band along the quads' top edge (y 168-172),
where the edge is part-drawn. The good captures in each arm are byte-identical to the
same test's captures in the 6 other runs on disk. The 2026-09-26 dpforce345 audit
documents that master's own base APK is off the modal GeometrySuperscreen image on 4
of 9 and 5 of 9 captures, and that different captures miss in different runs. The base
arm here fails on one of them too. **No pgraph suite regresses.**
The prediction said to rerun a moved suite once before reading it. I did not. The
base arm, with none of the flags, shows the same defect on the same test family, and that
already settles the question the rerun was meant to answer (codegen difference vs. existing
nondeterminism). A rerun of a suite known to flip would show only another draw.
At the time of writing, the arms job has not posted its `[job.arms]` verdict. As registered,
the prediction guards `Vertex_shader_rounding_tests/*` with no exclusion. It can therefore
read FAIL on these two captures, and the table above is the reading of that FAIL.

### Legs

| leg | result |
|---|---|
| M0 instrument | PASS: 62-63 perf lines in 110-240 s, and `mark gameplay` on all four |
| F0 counter in the binary | PASS on the dispatcher's own APKs (`builds/15d9406b81.apk` = acb81bbaa1d1, `6cd1a58b64.apk` = 460b947a4109, the apk_shas the soaks ran). A: emutls 1828, outline 1599, plt_internal 8753. B: tls_segment true, emutls 6, outline 289, plt_internal 0. Identical to the local builds. |
| F1 counter in the profile | A: 2.29% in emutls + outline + pthread TLS (>= 1.0%), PASS. B emutls = 0, PASS. PLT in libxemu 21 vs 213 (10%, <= 50%), PASS. B `__aarch64_*` == 0: **FAILS as worded**, with 54 samples, all in system libc. The wording did not separate the platform's own helpers from ours. In the failure world the leg names, "something on the vCPU path is not built with these flags", libxemu's count would be non-zero, and it is 0. |
| P1 gfps B/A in [0.98, 1.08] | 29 / 29 = 1.00: PASS, read only as "no regression" (see P2) |
| P2 resolution | BELOW RESOLUTION: \|B - A\| = 0, and the within-arm differences are 0. The route is at the 30 fps cap on the Nova. |
| must-not-move: pgraph | 680/682 identical. The 2 moved captures are master's documented GeometrySuperscreen nondeterminism, one in each arm. |
| must-not-move: crash | none on any B run. gfps lines were still printed at 240 s. |

### What the lever is worth

**A BOUND, not a measured gain.** In this session's A profile, 3.42% of the vCPU thread's
samples are in the four mechanisms, and B leaves 0.41%. The change removes about 3.0% of
vCPU-thread time. For a title bound by the vCPU, that bounds the frame-time saving at
about 3% (gfps at most +3%). No fps change was measured: on the Nova the only gameplay
window measured is at its cap in both arms. Measuring the gain would need a title or
device with headroom below the cap (the Thor on Crimson, median 26). That is the
next lane's A/B, if anyone wants the number rather than the bound.

## Why session 1 did not finish

It ended, correctly, waiting on three things outside the session: the four soaks
(queued behind about eight Thor requests), the pgraph arm, and the host's simpleperf
captures. It posted `[lane.buildflags427] waiting:` on the PR. All three resolved
after it ended. The profile's arm B was lost once to another session's Stop hook
force-stopping the Nova (hostops found and fixed that) and was retried. Session 2
read the results, merged master (clean; master had not touched either build file), and
marked the PR ready.

## For the next lane

- Do not use `-fvisibility=hidden` without first marking JNI and `SDL_main`
  default. `-Bsymbolic` already takes the internal PLT to 0.
- `symcheck.py` takes about 15 s per library. Run it on the dispatcher's APK
  (`dispatch/builds/<ref10>.apk`), not only on a local build.
- Do not use Crimson on the Nova for a perf A/B. On this route it sits at 29 of 30 fps
  in both arms, so a gain cannot show. Use the Thor (median 26), or a title below its cap.
- Write a helper-count leg per DSO. System `libc.so` has its own `__aarch64_*`
  helpers under pthread_mutex and scudo, and no build flag of ours removes them.
- `f1.py` reads a simpleperf file in about 4 minutes per arm (report-sample with call chains).

## Remediation after audit pass 1 (2026-09-26)

- **M1, CPU floor.** `-march=armv8.2-a` traps with SIGILL on an ARMv8.0 core
  (no LSE) the moment a library loads. `CpuSupport.kt` reads the `Features`
  lines of `/proc/cpuinfo` and requires `atomics` on every core. It is Kotlin
  because a native check built from this CMakeLists would carry the flag.
  `LauncherActivity` shows "Unsupported CPU" and exits before any screen that
  loads a library; `MainActivity.loadLibraries`, `XisoConverterNative` and the
  `NativeBridge` objects in `XboxHddFormatter`, `XboxInsigniaHelper` and
  `XboxDashboardImporter` call `CpuSupport.requireSupported()` first, which
  throws `UnsatisfiedLinkError` so their existing missing-library handling
  applies. A cpuinfo with no `Features` line is treated as supported (logged).
  The README states the Android 10 and ARMv8.2/LSE floor.
- **M2, the `regressed` verdict.** `buildflags427-pgraph-inert.json` is
  re-registered on the same refs with `GeometrySuperscreen_*` unguarded and the
  rest of `Vertex_shader_rounding_tests` guarded through `[!G]*`, `Geometry_*`
  and `GeometrySubscreen_*` (dpforce345's remedy for the same drift). A fresh
  arm judges it; do not remove `regressed` by hand.
