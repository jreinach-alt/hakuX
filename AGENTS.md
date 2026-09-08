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

**Stop the emulator when a run ends.** Always, including on failure and on the
paths where you gave up. A left-running emulator holds the device at full GPU
load; a handheld will not trickle-charge against that draw, so an abandoned run
flattens the battery instead of merely wasting it. This is not hypothetical — a
Nova was found looping the Crimson Skies intro long after the test that started
it had been forgotten.

```bash
trap 'adb -s "$SERIAL" shell am force-stop "$PKG"' EXIT   # in every script
```

A per-script trap is necessary but not sufficient: it says nothing about a turn
ending while a background campaign holds the device, which is how this went
wrong twice. `docs/testing/stop-emulator.sh` is wired to a **Stop hook** in
`.claude/settings.json` so the emulator is force-stopped whenever an agent
finishes responding, on every attached device.

A long-running batch that legitimately owns the device holds a lease by
touching `/tmp/hakux-device-lease` at least once every 90s; the hook then
defers and says so. The lease is deliberately short-lived, so a batch that dies
stops suppressing the hook on its own.

Note this is not only a crash-path concern — because of issue #20 a *successful*
run does not exit by itself either.

**Show the pixels, not the number.** Any comparison that is not *bit-identical*
gets surfaced as images at the end of the turn — the hardware capture, our
output, and the difference map. A figure cannot be scrutinised: "0.00 mean
error" was reported as pixel-exact on a test differing across 1,536 pixels, and
an RGB-only compare hid 1,279 differing alpha pixels. Both were caught by
looking, not by reading.

```bash
docs/testing/diff_specimen.py -o cmp.html --goldens goldens/results \
    --results out --all-differing
```

Report **differing-pixel count with max delta**, per channel group. A mean
cannot tell "this format is not decoded at all" (max 255) from "rounding"
(max 8), and that is the entire triage decision. Note also that upstream's own
criterion is `perceptualdiff` — any pixel threshold used here is ours, and
should be described as ours rather than as agreement with hardware.

**A PR that closes or downgrades a test carries the comparison.** Same tool,
attached to the pull request. Nobody should have to take "this now matches" on
trust, and a reviewer who can see the frames can catch a wrong call in seconds.

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

A distribution `java-25` package under `/usr/lib/jvm` is typically a **JRE**,
and Gradle fails on it late and obscurely:

```
Toolchain installation '/usr/lib/jvm/java-25-openjdk-amd64'
does not provide the required capabilities: [JAVA_COMPILER]
```

Check for `bin/javac`, not `bin/java`. On this machine the JDK is at
`~/toolchains/jdk21`.

```bash
export JAVA_HOME=/path/to/jdk21          # 21, not 25; must contain bin/javac
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
| Neither `--newer-than` nor the FATX mtime proves a test ran | Files that were never rewritten come through the filter, **and their mtimes advance anyway** — an image whose tests provably never executed still showed fresh timestamps. Set `enable_progress_log: true` in the disc config and read `pgraph_progress_log.txt`: it names every test the suite started and finished. That is the only trustworthy record. |
| A run cut off by your wait loop is not a completed run | The emulator does not exit on guest power-off (#20), so waiting for the process to die always hits your timeout. Confirm completion from the progress log's "Testing completed normally", never from the run's duration. |
| Emulator `stderr` reaches logcat under tag `hakuX-stderr` | nv2a prints the offending value before aborting. Read the log before reaching for a disassembler. |

## Sharing one device between a long sweep and active work

A full re-baseline is ~1,600 single-test runs, several hours of the only Nova.
`docs/testing/sweep_queue.sh` works that queue so it can be preempted:

```bash
docs/testing/sweep_queue.sh start queue.txt   # queue is one Suite::Test per line
docs/testing/sweep_queue.sh pause             # blocks until the Nova is genuinely free
docs/testing/sweep_queue.sh resume
docs/testing/sweep_queue.sh status
```

`pause` returns only once the runner has parked, so the device really is yours
before you install anything. **Every `resume` reinstalls the baseline APK**, and
each result records the APK hash that produced it — otherwise an experimental
build installed during a pause silently measures half the queue on a different
binary, and nothing in the results would show it.

The runner holds the device lease while working, so the Stop hook defers; on
pause it drops the lease, so the hook protects the device again.

Discs are built just-in-time (`make_isolation_discs.py --build-one`) because
1,591 ISOs would be ~9GB.

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

```bash
# 3. Is the test even measuring what its name says?
python3 docs/testing/crossmatch.py out --goldens goldens/results
```

**Ask what a failing test is actually rendering before you debug it.** 328 of
the 864 failures in the baseline sweep reproduce a *different test's* golden
more closely than their own — see
[`docs/investigations/cross-test-contamination.md`](docs/investigations/cross-test-contamination.md).
Days went into "the DXT decoder is wrong" before anyone asked, and the decoder
was fine.

That signature has two causes and they need opposite fixes, so **classify with a
pair/solo disc before theorising**: build one disc enabling the failing test plus
the test it impersonates, and one enabling the failing test alone.

| solo result | meaning |
|---|---|
| correct alone | contamination — earlier state leaking forward |
| still wrong alone | a state distinction we do not implement at all |

`Texture DXT` is the first, `Window clip` the second, and they looked identical
until the discs were run.

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
