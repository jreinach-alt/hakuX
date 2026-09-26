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

## Runs

| run | ref | request id | median gfps 110-240 s |
|---|---|---|---:|
| A1 | 15d9406b81 | 1790455170-buildflags427-4117276 | pending |
| B1 | 6cd1a58b64 | 1790455170-buildflags427-4117310 | pending |
| A2 | 15d9406b81 | 1790455170-buildflags427-4117367 | pending |
| B2 | 6cd1a58b64 | 1790455170-buildflags427-4117403 | pending |

Baseline for scale: titleplay p1 (`0-0-y-1790433159-titleplay-p1-crimson`,
a5b5b628f2, Thor, 420 s). The 30 s bins were 29 29 29 18 20 28 23 27 22, then
6 6 2 4 6 after 270 s. The median over 110-240 s was 26 (range 14-29), and gfps
is capped at 30. The soak ends at 240 s, before that collapse.

**F1 needs the host.** The dispatcher has no simpleperf path, so the profile
leg is filed as `dispatch/board-requests/buildflags427.md`: two 30 s captures,
one per APK, on the Thor.

## State at the end of session 1 (2026-09-26 13:55 PDT)

Waiting on three things outside the session:
- the four soaks `1790455170-buildflags427-*`, with about eight Thor
  requests queued ahead of them;
- the arms job's `[job.arms]` verdict on `buildflags427-pgraph-inert.json`;
- the host's two simpleperf captures (board request).

On resume:
1. Run `ghoul311/gfps.py --from 110 --to 240` on the four soaks.
2. Run `symcheck.py` on the dispatcher-built `dispatch/builds/15d9406b81.apk`
   and `6cd1a58b64.apk` (leg F0).
3. Fill the table, merge master, and mark the PR ready.

## For the next lane

- Do not use `-fvisibility=hidden` without first marking JNI and `SDL_main`
  default. `-Bsymbolic` already takes the internal PLT to 0.
- `symcheck.py` takes about 15 s per library. Run it on the dispatcher's APK
  (`dispatch/builds/<ref10>.apk`), not only on a local build.
