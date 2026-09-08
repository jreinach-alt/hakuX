# Working on this repository

Instructions for coding agents. `CLAUDE.md` points here; keep this file
canonical so the two cannot drift.

## What this is

An original Xbox emulator for Android — QEMU-derived, via
`xemu → izzy2lost/xemu (X1 BOX) → rfandango/hakuX → this fork`. The emulator,
the Android port and the Adreno work are upstream; this fork started by fixing
frontend launching and is now working on correctness.

It is in rough shape. A handful of games boot, with visible graphical faults.
Read [`ROADMAP.md`](ROADMAP.md) before deciding what to work on — particularly
"What done looks like", which explains why *making every test pass is not the
goal*.

## Start here

```bash
# 1. What the project is trying to be, and in what order
cat ROADMAP.md

# 2. What is actually broken, with measured evidence
gh issue list --repo jreinach-alt/hakuX --limit 30

# 3. How correctness is measured at all
cat docs/testing/pgraph-harness.md

# 4. Ground already covered — read before re-deriving it
ls docs/investigations/
```

Then pick an issue. Every accuracy issue carries which suites fail, how many
tests, the median pixel delta, and what has already been ruled out. Do not start
by reading source; start by reproducing the measurement.

## Non-negotiables

**Build before you claim.** The native build takes ~20s incremental once warm.
An unbuilt change is a hypothesis. This has bitten repeatedly: a fix that looked
obviously correct failed to compile, and another compiled but hung the emulator
on boot.

**Measure before you claim.** "This should fix it" is worth nothing here. The
pgraph suite exists precisely so that claims are checkable. Run it.

**Change one thing at a time.** A batch of four plausible changes landed together
once; one of them broke boot and all four looked suspect for an hour. Bisecting
cost more than testing each would have.

**Commit as you go.** Do not end a turn with a dirty working tree. Each commit
should be one coherent change with a message explaining *why*, so that a
bisect lands on something meaningful and a reviewer can follow the reasoning.
Group by story, not by file: a fix and the test that proves it belong together;
a fix and an unrelated doc change do not. Push only when asked.

**Instrumentation is not free.** A `syscall(SYS_gettid)` added to the pushbuffer
inner loop — 144,712 calls in a few seconds — throttled the emulator so badly it
presented as a renderer deadlock, and the side-effects were investigated as
emulator bugs. Profile-grade tracing belongs behind a flag, and thread IDs belong
in a thread-local.

**Distinguish the fork from upstream.** Fork boundary is **2026-01-29** (first
Android commit). Much of the Vulkan renderer has been rewritten since:
`vk/texture.c` 40 of 65 commits are post-fork, `vk/surface.c` 34 of 53. Do not
assume a defect in an upstream-origin file is an upstream defect.

```bash
git log --format="%ad" --date=short -S "<symbol>" -- . | tail -1   # when it appeared
```

## Building

Prerequisites are in [`android/README.md`](android/README.md). Two are missing
from most setups and fail obscurely: **meson**, and **ninja on `PATH`**.

```bash
export JAVA_HOME=/path/to/jdk21          # 21, not 25
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
export PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmake/3.30.3/bin:$HOME/.local/bin:$PATH"
cd android && ./gradlew --no-daemon assembleDebug
```

Debug builds install as `com.jreinach.hakux.debug`, labelled **hakuX (debug)**,
alongside a release install. They keep separate settings, HDD images and save
data.

## Working with a device

Debug builds are debuggable, so `run-as` can read and write app private data —
which means the setup wizard can be skipped by writing `x1box_prefs.xml`
directly. Only the games-folder SAF grant needs real UI interaction.

Hard-won operational facts, each of which cost real time:

| fact | consequence |
|---|---|
| `adb shell input keyevent 96` **terminates the emulator** | It arrives with a non-gamepad source and the app treats it as an exit. Inject at the evdev layer instead: `sendevent /dev/input/eventN 1 304 1` (BTN_SOUTH), then `0 0 0` to sync. `shell` is already in the `input` group. |
| A sleeping screen minimises the app ~2s after launch | Send `input keyevent KEYCODE_WAKEUP` before launching or the run is void and looks like a crash. |
| `pidof <pkg>:xemu` matches nothing | Use `ps -A -o NAME \| grep -x '<pkg>:xemu'`. |
| ISO filenames contain spaces and parentheses | The device-side shell re-parses adb arguments; quote for *that* shell too. |
| `e:\nxdk_pgraph_tests` accumulates across runs | Use `extract_results.py --newer-than`, with a cutoff taken from the image's own newest timestamp — the guest clock is offset from host time. |
| Emulator `stderr` reaches logcat under tag `hakuX-stderr` | nv2a prints the offending value before aborting. Read the log before reaching for a disassembler. |

## Verifying a change

```bash
# 1. Does it still boot?  (~25s)
docs/testing/boot-test.sh mylabel

# 2. Does the suite still agree with silicon?
#    Build a disc for the affected suites, run it, extract, compare.
python3 docs/testing/make_test_iso.py pgraph-smoke.iso -o probe.iso --config cfg.json
python3 docs/testing/extract_results.py hdd.img -o out --newer-than <cutoff>
python3 docs/testing/collect_results.py out -o local/results --run-id <label>
```

**Regression-test one suite at a time, not the full sweep.** Some pgraph tests
are order-dependent (issue #15): a test can pass in one sweep and fail in the
next with no code change. A full-sweep diff will show regressions that are not
real. Confirm any single-test delta by running that suite in isolation on both
builds.

## Conventions

- Defects live in GitHub issues, grouped by likely shared cause, each carrying
  measured evidence.
- `docs/investigations/` holds long-form records of bugs chased in depth.
  Read the relevant one before re-deriving it.
- `docs/archive/` is superseded material. Nothing there should inform decisions.
- Commit messages follow the existing `area: summary` style — `git log` is the
  reference.
