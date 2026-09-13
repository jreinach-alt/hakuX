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

**Never trigger CI to check your own work.** GitHub Actions minutes here are a
finite monthly budget, and exhausting them means no CI when a release actually
needs it. CI is for full build releases, run on demand when the user asks.
Concretely: `android.yml`, `desktop.yml` and `nv2a-index.yml` fire on
`push: branches: [master]` and on `pull_request:`, so a push costs runs only if
the branch has an open PR. `claude/es-de-launcher-disc-error-ojnl14` has no PR
-- **do not open one for it**. Put `[skip ci]` in the commit subject for
anything that may reach a PR-backed branch, and never use `gh workflow run`.

The obligation that replaces it is local: **build both Android and desktop.**
The Android build cannot catch a desktop link error, because the same core
sources compile for both and an Android-only symbol resolves on one and not the
other. That is not hypothetical -- it broke the desktop gate on 2026-09-12 and
cost the other lane a CI run. `docs/testing/check_android_guards.py` catches
that specific class with no toolchain and no CI; run it before pushing. A local
desktop build additionally needs one system package
(`dependency('libcurl')` is unconditional in this fork and falls back to a
subproject requiring openssl), so ask rather than assume it works.

**Build before you claim, and build the COMMITTED state.** The native build
takes ~20s incremental once warm. An unbuilt change is a hypothesis. This has
bitten repeatedly: a fix that looked obviously correct failed to compile, and
another compiled but hung the emulator on boot.

And a green build of a dirty tree proves nothing about any commit -- it is a
worse signal than a red one, because it reads as verified. On 2026-09-12 a
cherry-pick conflict was resolved badly, committed broken, then repaired in the
working tree; the repair was never committed, the Android build said BUILD
SUCCESSFUL, and a device A/B was queued against a commit with twelve compiler
errors in it. The dispatcher caught it by refusing to build a dirty tree, which
is the only reason it did not reach the device. Check `git status` is clean
before you believe a build.

**Measure before you claim.** "This should fix it" is worth nothing here. The
pgraph suite exists precisely so that claims are checkable. Run it.

**Change one thing at a time.** A batch of four plausible changes landed together
once; one of them broke boot and all four looked suspect for an hour. Bisecting
cost more than testing each would have.

**Disposition an item, update its issue.** The issue log is the project's
memory; a finding that lives only in a commit message, a doc or a PR thread is
one nobody will find before re-deriving it. Whenever you land a fix, revert one,
kill a hypothesis, or re-rank an entry, say so on the issue that owns it, and
open one if none does.

This is not bookkeeping. #41 recorded, four days before the fact, both the
measurement for the radial fog cell and the argument against implementing it.
I did not read it, spent an afternoon deriving a worse answer, shipped it and
reverted it. The largest entry on the board -- the `Blend_tests` fifth quad, 6.5M
structural channels and five dead mechanisms -- existed only as prose in a PR
thread, which is why the same mechanisms were proposed twice from two lanes.

Two habits follow from it:

- **Read the issue before deriving a mechanism.** Search the log for the suite
  and the register first. It costs a minute against an afternoon.
- **Record negatives, not just fixes.** A mechanism that measured zero is worth
  more than silence: it stops the next person spending a build on it. Say what
  was tried, what it moved, and against which oracle.

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

**`pgrep qemu-system-i386` never matches, and the false negative is dangerous.**
Linux truncates a process's `comm` to fifteen characters, so the desktop
emulator appears as `qemu-system-i38`. `pgrep -c qemu-system-i386` therefore
returns 0 while a run is in full flight, which reads as "the emulator is free"
and invites starting a second one on top of the first. Match the truncated name,
or check with `ps -eo comm= | grep qemu`. (This is a different trap from the
`pgrep -f` one in `CLAUDE.md`, which matches your own shell; both bite.)

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

**This fires on a person's session too, and that is easy to miss.** The hook
runs at the end of *every* turn, so replying to someone who is mid-game kills
their game. It cost several Galleon sessions in one evening, each behind an
unskippable two-minute intro, before anyone noticed the pattern -- from the
outside it looks exactly like the emulator crashing, and the log line to look
for is `Killing <pid>:<pkg>:xemu ... stop <pkg> due to from pid N`, which is a
force-stop request and not a fault. Before handing the device to someone to
drive, start `docs/testing/hold_device.sh <minutes>` in the background, and
`hold_device.sh release` when they are done.

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

**Every surfaced page carries its build identity.** Commit SHA in the filename,
in the `<title>`, and in a header block alongside the device serial, the results
directory and the time. Two comparisons that differ only in content are
indistinguishable at a glance otherwise, and a client that keys on filename may
show the *first* one instead of the new one — which has happened. A page whose
provenance is unclear is worse than no page, because it invites a decision based
on the wrong build. `diff_specimen.py` does all of this automatically; anything
hand-rolled must do the same.

**A PR that closes or downgrades a test carries the comparison.** Same tool,
attached to the pull request. Nobody should have to take "this now matches" on
trust, and a reviewer who can see the frames can catch a wrong call in seconds.

**Read the label before believing the diff.** Every capture has the test's own
parameters printed over it in white by the guest. If those pixels differ between
our render and the golden, the golden was produced by a *different build of
nxdk_pgraph_tests* — and that build may have uploaded different source data, in
which case the comparison is not measuring this emulator at all.

`TexFmt_R6G5B5` cost hours as a suspected decode defect. Hardware prints
`C: 0`; we print `C: 1`. That is the suite's own `require_conversion`, and it
selects between two entirely different upload paths — a hand-written packer or
SDL converting to the row's pixel format. Different bytes reached texture
memory, so the "two gradient ramps versus one" that looked like a channel bug
was the two runs texturing from different data. Fitting a decode to it produced
two models that each matched that one test and made `Bump map` worse.

One capture in forty was affected, and the evidence was on screen the whole
time. `score_sweep.py` now reports `label-differs` per test; treat such a row as
void rather than as a defect.

**A palette gate cannot see placement.** `palette_gate.py` asks whether we drew
the hardware's colours in the hardware's proportions; it is the right first
filter for low-palette suites and it caught a 92% solid-red render that a mean
error called fixed. It is blind to the right colour in the wrong place, which is
exactly what a coordinate or perturbation defect looks like. Pair it with
`placement_gate.py`, which counts differing pixels, before calling a suite done.

**Suspect the memory before the maths.** Bump map rendered ~4,900 colours where
silicon renders four. Eight hypotheses were eliminated in the shader, the
sampler and the coordinates before anyone dumped the bytes. Guest VRAM held a
perfect two-colour checkerboard; what reached the GPU was 36% someone else's
pixels. The habit that finds this quickly: dump the source and the decoded
result to files, pull them, and *look at them as images* — a swizzle-order
staircase in the corruption told us the loss was a contiguous tail, and its size
(94,208 bytes) named the surface that overwrote it.

**A retained GPU copy of guest memory is a write-back obligation, and it needs a
watch.** Surfaces here are shelved or invalidated lazily: the VkImage is kept and
written back to VRAM only if something later reads that memory. That obligation
outlives the surface's life as a render target, so between the two the guest can
take the memory back — and it does. Anything that defers a copy into guest
memory must keep watching that memory until the copy lands, and must drop the
copy if the guest writes there first: once the CPU has written a range, VRAM is
authoritative for it.

**The handheld stops charging because the supply is 4.5W, and stays awake
because ES-DE is the home app.** Both were measured on the Nova rather than
guessed, and neither is hakuX's doing:

- `/sys/class/power_supply/usb/usb_type` reports `Unknown [SDP] DCP CDP ACA C
  PD PD_DRP PD_PPS BrickID` — the brackets mark the active type. **SDP** is a
  PC data port: `current_max=900000` at `voltage_max=5000000`, so **4.5W in**.
  Measured `current_now`: asleep and idle **+122uA**; adb polled once a second
  with no app, still asleep, **+2.1mA** (so adb itself is innocent); emulator
  running **-459mA average, -1122mA peak**. A three-hour sweep takes roughly
  1.4Ah out of a 5.18Ah battery. The port negotiates DCP/CDP/PD, so a wall
  charger plus `adb tcpip 5555` moves the input to 15W+ and the problem goes
  away. That is the only real fix for long runs; everything below is damage
  control.
- ES-DE (`org.es_de.frontend`) is the device's **default home app**, and its
  `MainActivityHomeApp` window carries `FLAG_KEEP_SCREEN_ON` (verified:
  `mOwnerUid=10140`, and the `SCREEN_BRIGHT_WAKE_LOCK 'WindowManager/displayId:0'`
  is attributed to `WorkSource{10140}`). So force-stopping the emulator hands
  the foreground straight back to a window that pins the display on, the 30s
  timeout never fires, and the device sits at **-107mA** indefinitely. It also
  holds an `AudioMix` wake lock.

`KEYCODE_SLEEP` overrides `FLAG_KEEP_SCREEN_ON` where the timeout cannot —
Awake to Asleep, display suspend blocker released, `current_now` back to 0.
`stop-emulator.sh` and `sweep_queue.sh` now send it wherever they release the
device. Any new runner must do the same: stopping the emulator is only half of
leaving the device alone.

```bash
adb shell dumpsys power | grep -E "mWakefulness|DisplaySuspendBlocker"
adb shell cat /sys/class/power_supply/battery/current_now   # <0 = draining
```

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
| A mashed skip sequence can end the run without crashing | Mashing A, B and Start through a title's intro once ended at the game library. B is **not** the cause and is not a crash: pressed alone it leaves the emulator running, same pid, nothing in the crash buffer. The likely path is the guest itself being powered off from its own menu, which the emulator handles by exiting the process (#20's fix). Treat "we are suddenly at the library" as the guest exiting, not as a fault, and confirm with `pidof <pkg>:xemu` before chasing it. |
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

**Write the prediction down before the device runs, or the result proves
nothing.** `docs/testing/request.sh` enforces this: a suites request needs
either `--expect FILE`, naming a prediction registered with
`ab_compare.py --register`, or `--no-expect REASON` for a run that is not an
A/B arm. The prediction's sha256 is recorded in the request at queue time and
checked when the arm is judged, so a verdict reads `PRE-REGISTERED`,
`TAMPERED`, `UNBOUND` or `POST-HOC`. Only the first is worth citing.

**A SOAK needs the prediction bound too, and needs it more than a disc arm
does.** `--expect` works on `--title` requests as of 2026-09-13; before that
the binding block sat inside the suites branch, so a soak's `--expect` was
accepted and its `expect_sha` silently never recorded. A soak writes no
captures, so `runs: 0`, nothing computes a verdict, and **you read your legs
off the logcat yourself** -- which is exactly why the sha matters: it is the
only thing that makes a leg quietly widened after the numbers arrive
detectable. `--no-expect REASON` stays correct for a genuine baseline, survey
or noise-floor run. Say which.

Two soak-path traps fixed with it, both of which had cost measurements:
`--wait` died with `KeyError: 'disc_id'` because the reader assumed a disc
result, and **`--runs N` was accepted and ignored** -- a requester asking for
three runs got one, with a one-sample noise floor and no indication. Queue N
separate soaks under one consistent `--who`: **the replicate for a no-oracle
measurement is the RUN, not the window.** A rule computed over all windows
tightens with every window a longer soak happens to produce, and absolute
per-window counts have been measured varying 3-5x *within a single run*.

Four rules, each of which cost a real verdict on 2026-09-12:

- **State the falsifier as a measurement, not a pixel count.** Name the
  quantity your mechanism changes and predict *that*. Residual classes
  overlap: a pixel can be wrong for two independent reasons at once, so
  removing one cause need not move the count at all. Good falsifiers from that
  day: per-column depth spread, which cube face a pixel selects, a swatch's
  centre row, the mean light term over a lit region, the recovered byte for a
  named float component.
- **A tool that reads captures must accept either directory shape.** The
  dispatcher puts PNGs in `captures<N>/` inside a result directory, named
  `<Suite>::<test>.png`, and callers pass both shapes. Use
  `docs/testing/captures.py` (`resolve`, `find`) rather than joining paths by
  hand. Two falsifiers were bitten on 2026-09-12; one reported all three of
  its captures MISSING on an arm that contained them, which reads exactly like
  a failed render and would have been taken as refuting a change that passed.
- **A different exclusion reason per case, chosen after seeing the result, is
  a curve fit and not a mechanism.** On 2026-09-12 a gate was proposed for #51
  that excluded one capture for "has no sign to survive" and another for
  "never underflows" -- two unrelated justifications, each selected after
  seeing which way that capture's delta went. It reads like a principled rule
  and is really one rationalisation per data point. If your rule needs a fresh
  reason for each exception, you are fitting, and the giveaway is that no
  single statement of the precondition predicts the whole set.
- **A mechanism-shaped falsifier separates "it did not happen" from "it
  happened and the model is wrong". A pixel count cannot.** #13's arm on
  2026-09-12 delivered its predicted bias *exactly* -- the fitted line centre
  moved to the golden's interval on 18 of 18 widths on one edge and 7 of 7 on
  another, and y was untouched 16 of 16 -- and the same arm scored **+394,027
  differing pixels**. The change was applied correctly, on the right axis, at
  the right magnitude, on the right pipelines, and the model behind it was
  still wrong. A total would have said only "worse" and left the two
  possibilities indistinguishable, which decides whether you fix a constant or
  abandon an entry point.
- **A falsifier your own change guarantees is not a falsifier.** Before
  registering a leg, ask what would have to be true for it to FAIL. If the
  change you are about to make forces it true, it is a description of your
  own output, not a test of it. On 2026-09-12 an arm registered four legs and
  two of them -- "every differing pixel lands on a positive-face corner" and
  "no interior texel" -- were tautologies of a fix that substitutes a
  positive-face corner direction. They read exactly like measurements. Predict
  something the *goldens* constrain, not something your patch constrains.
- **A failed arm is a diagnosis, not a revert.** Push through to the root
  cause before reverting, and check whether the reasoning that motivated the
  change still applies -- usually the entry point is right and only a value is
  wrong, which is a one-line edit. #40 was reverted on a failed arm and the
  fix that passed was the same guard with one constant changed. Reverting code
  that fixes nothing still applies at the *end* of an investigation, not at
  the first disappointing arm.
- **A flat count does not mean the change was inert.** Diff arm A's captures
  against arm B's before concluding it did nothing -- a guard that fires and
  returns a *different wrong answer* is indistinguishable in the totals.
- **Register tolerances as tolerances.** A prediction whose prose said
  +/-3,000 registered an exact value and turned a passing measurement into a
  violated check.
- **Register deltas, not absolutes**, whenever the baseline was read from a
  different binary than the arm that will run.

And a mean is a poor summary: on 2026-09-12 one hid an 87,381-pixel defect
behind "0.00" and another hid an ordered dither behind "+0.98". Report
differing-pixel count plus max delta, and compare RGBA, never RGB.


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

When the answer is "a state distinction we do not implement at all", the pixel
shader half of that question needs no device:

```bash
cd docs/testing/psh_differ && make && ./build/psh-differ
```

It varies one field of `PshState` at a time and reports whether the generated
GLSL changes. State that produces byte-identical GLSL never reached the GPU.
Three seconds, no ROMs, no hardware. Read
[`docs/testing/psh_differ/README.md`](docs/testing/psh_differ/README.md) before
acting on a result — "no effect" is a claim about which baselines were tried,
and extending them is the intended use.

**Regression-test one suite at a time, not the full sweep.** Some pgraph tests
are order-dependent (issue #15): a test can pass in one sweep and fail in the
next with no code change. A full-sweep diff will show regressions that are not
real. Confirm any single-test delta by running that suite in isolation on both
builds.

Which tests those are is measurable rather than folklore, and it does not need
the device:

```bash
docs/testing/order_dependence.py --suite "Pixel shader" ...     # self-contamination
docs/testing/order_dependence.py --target "Pixel shader::Passthru" ...  # which suite does it
```

A run is about 40 seconds on the desktop lane, which runs the Vulkan renderer
on lavapipe (see `docs/testing/desktop-runs.md`). Order-dependence is a property
of what the emulator resets between draws, so it reproduces on any renderer —
unlike an accuracy question, which that lane cannot settle. Measured so far:
`Pixel shader` does **not** contaminate itself, and `Pixel shader::Passthru`
is unchanged behind every one of the other 99 suites on both renderers (#15).
A run that stops writing captures for `--stall` seconds is killed and reported
as stalled; a segfault is retried and printed, never silently.

**The Khronos validation layer runs on the lane.** `apt-get install
vulkan-validationlayers`, then `[display.vulkan] validation_layers = true` in
the toml; reports go to stderr as `[vk]` lines. It found eight defects in one
afternoon that no capture showed (#34), so run it on any change to the Vulkan
backend before calling the change verified. Count distinct VUIDs, not lines:
one root cause cascades into thousands of messages.

## Establish what your instrument cannot see, before you believe a zero from it

The four sections that follow were all added on one day, all from real errors,
and they are four faces of one mistake: **a negative result read from an
instrument that could not see the mechanism.** Read them as one principle.

| what was believed | the instrument | what it could not see |
|---|---|---|
| "nothing is scheduled for tomorrow" | `CronList` | a systemd timer, which had run successfully that morning |
| "float Z is structural, not one channel is one step" | a per-channel diff | a packed depth word, where one ULP moves a channel by 8 |
| "the blend factor is applied, the images differ" | a whole-image sha256 | a test that prints its own name into rows 0-63 |
| "the barrier fix has no benefit" | a suite that uploads once and draws | a first-use race, which that workload cannot contain |
| "the re-exec picks up tree edits" | a hash of `$HERE` | that `$HERE` **was** the snapshot it was comparing |
| "the index matches the tree" | `check` with no `--tests` | an empty suite half, which both sides agreed on |

Every one of those is a **passing** or **empty** result. None of them errored.
That is the whole difficulty: a guard satisfied by the absence of the thing it
guards reports success, and an instrument blind to the mechanism reports zero.
Both are indistinguishable from good news.

So before a negative result changes a decision, write down the answer to: *if
the thing I am looking for were present, what would this instrument show?* If
you cannot answer, the reading is not evidence yet. And prefer an instrument
with a control inside it -- an impossible row, a within-run reverse-order
arm, a `MIN`/`MAX` case that must read 1 by specification. A number with no
control is a number you have to trust.

## The test disc's ratios are properties of the disc, not of a workload

The goldens come from `nxdk_pgraph_tests`, so almost every ratio in this
campaign is measured on it. That is right for accuracy -- the disc is the
oracle. It is **wrong for anything about cost**, because a test disc sets state
exhaustively and draws rarely, which is the opposite shape from a game.

Measured on 2026-09-13, and the refuted premise was the orchestrator's own. #44
was briefed as: "the guarantee only needs to hold where a draw is outstanding,
and the disc makes 148,704 submissions for 180 draws, so a draw-only bound is
**826x** cheaper than holding at every submission." A lane built it, and it
works exactly as designed.

    submissions carrying a draw
      Texture border disc     3.6%     <- what the sizing was computed on
      Galleon                94.2%, 93.2%

The disc submits 27x more often than it draws. Galleon submits **1.05x per
draw**. So the selective bound held at 94.8% of submissions and cost precisely
what the unselective one cost -- `gfps` p90 29 -> 13, identical to mode 1 --
and the conclusion is about the guarantee rather than the patch: *no
unprocessed draw while the guest runs* is intrinsically as expensive as
holding always, on draw-dense content, because there is nothing to skip.

**Before sizing any cost or coverage claim, ask which disc the ratio came from
and whether that ratio is a property of the workload or of the test.** An
accuracy figure transfers from the disc; a *density*, a *rate per draw*, a
*fraction of submissions* does not. The tell in hindsight is that 826:1 was a
suspiciously large factor for a mechanism nobody had tuned -- a factor that big
usually means the denominator is an artefact.

Two corollaries earned the same day:

**A cheap mechanism can still be worthless, and say which it is.** The scan
here costs 0.0173% of wall clock and is provably correct; mode 0 pays literally
nothing for it. Reporting "the selective bound failed" would libel the
implementation. The implementation does what it was designed to do -- the thing
it was designed to exploit is not there.

**The surviving lever is the one whose cost does not scale with the thing that
defeated the others.** Every submission-time mechanism scales with draw
density and therefore dies on a real title. Write-tracking -- trapping the
guest's store to a range a queued draw will read -- does not, which is why it
is the candidate, and it lives in a different file from every attempt so far.

## A rate or a mean over a busy window measures the BUSYNESS

Three registered legs on 2026-09-13 turned out to measure device occupancy
rather than the mechanism they were aimed at. Each was fixed the same way, and
the replacement was cleaner than the leg it replaced every time.

| leg | what it measured | occupancy-free form |
|---|---|---|
| #64's cost: median `gfps` | how busy the device was -- series is bimodal, ceiling 29-31, floor 5-20, and the median tracks which one it sits in | **the ceiling**: p90/max. Noise floor then +-1, measured inside the experiment |
| #65's U5: deferred lateness, POOLED across regimes | how much of the run was in each regime -- unlock occupancy halved between soaks and the regimes have different caps | **per regime**: +0.6% and +2.0%, both inside tolerance |
| #65's D1: clamp rate as a ratio to arm A | arm A's own occupancy, which moved **3.2x between two runs of one binary** (0.2212 -> 0.0681, tracking 34 -> 6 fully-unlocked windows) | **count the windows where the condition holds**: arm A had 6 then 1 cap-bound windows, arm B had **0**. Eliminated, not reduced |

The pattern: **a rate, a mean or a median over a window whose occupancy varies
is a measurement of that occupancy.** It will reproduce on a repeat -- both of
#64's runs agreed -- and still be measuring the wrong thing, which is why
repeating it is not the check.

Two remedies, in order of preference:

**Count events of a condition instead of averaging over time.** "How many
windows were cap-bound" cannot be diluted by idle windows; "the mean clamp
rate" can. This is what turned #65's D1 from undiscriminating into decisive.

**Condition on the state, then compare within it.** If the quantity only
exists in one regime, pool nothing across regimes. #65's U5 failed on a pooled
figure while holding in both regimes separately -- and the judge had been
written to pool by assertion count specifically to avoid that trap, then the
leg was registered on the pooled number anyway.

And the corollary that makes this cheap: **state the statistic and its noise
floor before the arm runs**, then check the noise floor is smaller than the
effect. #64's median moved 8 against a tolerance of 2 and the reverse-order
control moved 8 too. The ceiling's floor is +-1 against an effect of 15.

**A within-ref floor is a lower bound on the floor, never the floor.** The
replicate being the RUN is necessary and not sufficient, because a run can be
bimodal. Measured on #69's corrected waste ratio: three runs of one ref agreed
to **2%**, which would have licensed quoting "4.96 +- 2%" -- and three runs of
another ref, which cannot differ in the quantities feeding it, gave
**6.14 to 11.68**. The ratio is bimodal BY RUN, not noisy within a mode, and a
floor taken from the tight ref would have passed a leg that the loose ref
fails. So take the floor across every ref you have, and if two refs disagree
about the spread, the spread is the finding.

The same lane supplied the sharpest version of why an exact agreement is not
reassurance: its stronger identity `sp + ov == di` held **exactly in every
window of all six runs**, while the weaker one (visits = discards +
already-invalid) held only to +-1 -- because `visited` prints on one log line
and `ai`/`di` on the next, with the guest running in between. **Three exact
zeros in the first round were luck, and believing them made two successive
versions of its check wrong.** An identity that holds exactly tells you the
two sides are read at the same instant; one that holds to +-1 tells you they
are not, which is information about the instrument rather than noise.

## A falsifier's power depends on the baseline rate, so an old floor can turn it into a coin flip

`2D_BorderTex_SZ` is judged by `stale_px == 0` on 10 of 10 runs. That bar was
set against a measured floor of 6 of 10 runs non-zero, where a binary with NO
fix passes it by luck at 0.4^10 = **0.01%**. On 2026-09-13 an arm A control
read 2 of 10 non-zero -- and at that rate the same bar is passed by luck at
0.8^10 = **10.7%**.

**The bar did not change. The disc did.** A one-in-nine coin flip is not a
falsifier, and an arm B reading zero would have been cited as a pass.

So a falsifier stated as "N clean runs" carries a hidden dependency on the
baseline rate, and a floor taken long ago silently erodes it. Two things
follow:

**Register a VALIDITY GATE on arm A, and void the pair when it fails.** The
lane's V0 -- "arm A must show >= 3 of 10 non-zero, or the pair is void" -- is
what caught this, before an arm B zero could be read as a win. A validity gate
is not a leg about the fix; it is a leg about whether the instrument is
pointing at anything.

**And a stale floor OVERSTATES a defect, which flatters every later arm.** The
`Texture border` floor in use was 128 commits old. Anything measured against
it gets credit for whatever fixed the flake in between -- including, in this
case, the arm that closed the issue.

The honest fallback is also worth naming, because it is tempting and wrong:
after V0 failed, "the rate has fallen" is NOT established. 2 of 10 against a
6-of-10 floor is Fisher two-sided **p = 0.160**; against a 5-of-10 control,
**p = 0.350**. Separating 0.2 from 0.6 at this bar needs roughly twenty runs
per arm. A per-run coin flip has almost no power without replicates -- which is
why a RATE over many events inside one run (0.5661 and 0.5672 across two runs,
reproducible to 0.2%) is a strictly better instrument than a count of clean
runs, and why its bar can be an identity rather than a tally.

## A predicted FALL is also a claim about the baseline, and it can become unsatisfiable

Registering "this quantity falls by at least X" looks like a claim about the
fix. It is two claims: that the fix removes X, and that **the baseline has X to
give**. The second is usually invisible, and when the baseline is
occupancy-dependent it can go false between registration and judging -- at
which point the leg cannot be met by any fix whatsoever, and it still reports
as a failure of the change.

Measured on 2026-09-13, on #65. A previous lane registered D2 as a
fully-unlocked drift **fall of at least 500,000 ns**, against a published
baseline of 3,746,966 ns, which was ample. Re-judged on the new pair, arm A's
drift was **444,340 ns**. A 500,000 ns fall from 444,340 is arithmetically
impossible -- it would require a negative drift larger than the arm has -- so
D2 FAILED on data where the underlying rate had in fact improved, 58.08-58.40
Hz to 59.85-60.00 Hz.

The pattern across that judge's nine legs is the useful part, because it is not
one accident:

    legs that HELD:   clamp counter, negative-lateness control, locked-window
                      control, gfps ceiling, window count -- all ABSOLUTES
    legs that FAILED: D2 drift fall, D5 hold fall, D7 defers-per-window --
                      all DIFFERENCES or RATIOS against a moving baseline

Arm B's own two runs had 7 and 32 fully-unlocked windows, a 4.6x swing **inside
one binary**, with defers per window 37.9 against 84.8. Any leg normalised by
that is measuring the swing.

**So: register the absolute, not the fall.** "The worst window clamps at most
2" survived every one of these regime changes; "the hold falls by three poll
intervals" failed twice on arithmetic that had nothing to do with the constant
under test. When a fall is genuinely the quantity of interest, check at
registration that it is **smaller than the baseline's plausible range**, and
say what makes the baseline stable -- and prefer the run-paired form, which at
least fails for a reason connected to the change.

The companion failure is the same shape from the other side: a leg registered
against a **proxy** for the thing you care about. #65's E1 counted windows
where an estimator exceeded a margin, and it failed at 2 and 3 windows while
**the direct `clamp=` counter read 0 and 1 in the same runs** -- the estimator
over-predicts by two to three times, because `def_max` can come from a
`remaining`-bound deferral whose true lateness never exceeded a period. The leg
built on the counter passed; the leg built on the proxy failed. The counter had
been added precisely because the reasoning had been wrong once before, and the
proxy was registered against anyway. Every exceedance figure quoted from that
estimator, on either device, is an over-estimate.

## When a direct counter for the mechanism exists, register the leg on the COUNTER

Three times in one day a leg built on a proxy was contradicted by a direct
counter, and every time the counter was right:

    #65   E1 counted windows where an estimator exceeded a margin: FAILED at
          2 and 3 windows. E2 read the `clamp=` counter in the same runs: 0
          and 1. The estimator over-predicts by 2-3x, because `def_max` can
          come from a `remaining`-bound deferral whose true lateness never
          exceeded a period.

    #44   V4/W5/X4 were built on `gave`, which "held" at 0.4144 -- 41.4% of
          covered submissions released with work outstanding -- while `Tr`,
          the direct race counter, read ZERO on the same arm. `gave` counts
          "released with PUSHBUFFER outstanding", not "released with a DRAW
          outstanding": the pusher parks on `waiting_for_nop` at a NOP method
          that comes AFTER the draw it follows, so the draw is already
          consumed and its texture already read when `gave` fires.

    tools The `fifoskew` reader's `--selftest` compared against a frozen
          sample and printed ok while its regex matched nothing on the live
          line. Found by running it against a real logcat.

Note the direction: in all three the proxy read **more defect than existed**,
and in all three a leg "held" on it. A proxy that over-reads makes a fix look
necessary and its verification look successful, which is the comfortable
failure rather than the loud one.

**So: if a counter for the mechanism exists, the leg goes on the counter.** Use
the proxy for direction only, and say in the registration which quantity is
which. And when a proxy and a counter disagree, do not average them or pick the
plausible one -- the disagreement is a fact about the proxy's definition, and
chasing it is how `gave`'s real meaning was finally established.

## A cost is often a property of the workload, not of the mechanism

Corollary to the test-disc rule, and it corrects an over-generalisation of the
orchestrator's own, made from one title.

The #44 bound was recorded as "mode 2 costs what mode 1 costs" on the strength
of Galleon: `gfps` p90 29 -> 13, max 29 -> 15. On Crimson Skies, in the **same
mode**, p90 falls by **0** and max by **3** -- while the guest is blocked 30.7%
of wall clock at a hold mean 74% LARGER than Galleon's.

A bigger hold, no frame-rate cost. The resolution is that the cost is not a
property of the bound at all: it is a property of **whether the guest CPU
thread is that title's critical path.** Galleon's is (83% busy); Crimson's is
not, so blocking it for a third of wall clock costs nothing observable.

**One title cannot establish a cost, and two titles that disagree are the
finding rather than a problem.** Before writing "this change costs X", say
which title X was measured on and what about that title makes the guest thread
matter. The same discipline as the disc-ratio rule, one level up: a cost
measured on one workload is a fact about that workload until a second one
agrees.

## A falling rate on a WEAK observable is not evidence the defect closed

The corollary to the stale-floor rule, and it was measured the same day rather
than reasoned to.

`Texture border`'s `stale_px` flake fell from 6-of-10 at an old floor to
**2-of-10** at the tip, and the orchestrator floated the obvious hypothesis in
a write-up: the race must have been closed by `cdd8dc4c89`, #56's
stale-binding fix. **It has not been.** At the *same ref* those disc runs
used, Crimson Skies reports `Tr:11829/19167` -- **61.7% of texture uploads
raced**, higher than the published 0.566 baseline. The race is live.

Both readings are true, and the resolution is the observable, not the defect: a
disc whose eighteen draws sit inside one frame with no flip between them is
simply a **poor detector** of a race that a flipping title shows on three
fifths of its uploads. The disc's 2-in-10 measures the detector.

**So before reading a falling rate as a fix, ask what the observable's power
is on the workload that produced it.** The two instruments here differ by
everything that matters:

    stale_px on the disc    a per-run coin flip; 20-30 replicates for power
    Tr on a real title      19,167 uploads in ONE 240 s run, reproducible to
                            0.2%, with its own impossible row (Xd) and a
                            negative control (Vr = 0/3,040)

A rate over tens of thousands of events, carrying its own contradiction check,
is not the same kind of number as a count of runs that did or did not flake --
even when both are "the measurement we have". When a defect has a weak
observable and a strong one, the weak one's movement is a fact about the weak
one.

## Predict an intermediate value, not just an improvement

A leg that says "this class will improve" is satisfied by any change that
helps. A leg that says "this class will reach exactly 70.36% and NOT 100%"
can only be satisfied by the mechanism you claim.

#13's `geom.c` arm on 2026-09-13 is the worked example. Two legs:

  `Tri`  58.22% -> 100.00%   -- landed 100.00%
  `TFan` 47.57% -> 70.36%, and explicitly NOT 100%  -- landed 70.36%

The `Tri` leg is the weaker of the two. A fix aimed at `Tri` was always going
to move `Tri`, and 100% is the value any correct-looking change trends toward.
The `TFan` leg is the measurement: it names a specific shortfall, caused by a
rotation in a DIFFERENT file that the change cannot compensate for, and a
change that "merely helped" would have overshot or undershot it.

So when a mechanism predicts partial credit somewhere, register the partial
value. It is free, it is the half of the prediction that can fail, and an
intermediate value landing exactly is worth more than a headline reaching its
ceiling.

The corollary is about where the prediction came from. The lane's first answer
for `TFan` was derived by HAND-TRACING the composition and was wrong -- and
reading the code harder could not have fixed it, because two readings both
reproduce the measured `Tri` figure and only one reproduces the measured
`TFan` figure. What separated them was calibrating the model against arm A's
eleven classes. **When a model has a free parameter you cannot read off the
source, calibrate it on data you already have rather than tracing again.**

## Let the gate's exit code decide something

Running a check and then not letting its result change what you do is worse
than not running it: you have paid for the information and then produced a
commit that looks checked.

Twice on 2026-09-13 the orchestrator chained `git add && git commit &&
git push` past a gate that had just printed FAIL -- once on a stale nv2a
index, once on a territory file listing one path as both claimed and free.
Both times the gate was correct, both times the push went out, and both times
the output *said so* two lines above the push. The `&&` chain made the gate's
verdict decorative.

So: put the gate in the condition, not in the transcript.

    if python3 docs/testing/check_territory.py; then
        git commit ... && git push ...
    else
        echo "GATE FAILED -- not pushing"
    fi

And when reading a multi-gate script like `preflight.sh`, read the VERDICT
line, not the last `ok` you happen to see -- its per-gate lines print in order
and a passing gate can be the last thing above a failing summary.

## When a failure recurs, look for the instruction that is producing it

Three lanes dirtied the shared tree on 2026-09-13 and stalled the dispatcher
251 times between them. The first two were treated as mistakes -- told, fixed,
moved on. The third made it obvious that three independent agents converging on
one wrong behaviour is not three mistakes.

It was an instruction. A project memory note said, verbatim: *"For an
instrumented build, patch the main tree uncommitted, build, save the APK,
`git checkout --` the files."* Written before the dispatcher's dirty-tree
refusal mattered, and every lane that read it and complied did the right thing
with the wrong information.

So when the same failure arrives from independent directions, **stop correcting
the instances and go looking for the source.** The question is not "why do
agents keep doing this" but "what is telling them to". Candidates, in the order
they are worth checking:

  - a memory note or doc that predates the constraint it now violates;
  - a brief of your own that says one thing while a table says another -- a
    stale territory row did exactly this, and the lane correctly reported the
    brief as wrong;
  - a tool whose default contradicts the written rule;
  - an example in a doc that is now the wrong pattern.

The tell is convergence. One agent doing something odd is an agent; three doing
the same odd thing is a document. And the fix is cheaper at the source: one
note rewritten against three lanes corrected and a fourth still to come.

Two of this campaign's recurring failures resolved this way, both to something
written down rather than to carelessness: the dirty-tree stalls above, and an
orchestrator declaring a working systemd timer missing because it read
`CronList` -- a tool that cannot see a systemd timer -- and then overwrote the
unit files it had just declared absent.

## A checker must have no side effects on the tree it checks

`check_territory.py` was added on 2026-09-13 to catch a stale territory
allocation, and it recorded its high-water mark by writing a **tracked** stamp
file. `dispatcher.sh` refuses to build any ref while the shared tree carries a
tracked modification -- correctly, because with several implementers holding
uncommitted work "run my build" is ambiguous. So the guard stalled the build
path: **129 requeues**, every queued arm needing a new binary bouncing every
thirty seconds.

And it was a loop. Each `preflight.sh` run rewrote the stamp and re-dirtied the
tree, so reverting the file by hand fixed it only until the next check. The
orchestrator ran preflight repeatedly and read `preflight passed` every time.
It was found by a lane that noticed **its own arms requeueing**.

Two rules follow, and the second is the general one:

**A checker writes nothing.** If it needs state, derive it. The wave
high-water mark is in `git log -p` on the file it is about: every committed
value is there, the maximum cannot be forged by a fold, and nothing is written
anywhere. A `.gitignore` line would have hidden the symptom and left a checker
with a side effect.

**Ask what your tool does to the things downstream of it.** `preflight.sh`
exists to protect a CI run; it had no reason to consider the *dispatcher*, and
the dispatcher had no reason to consider preflight. The interaction lived in
neither. When adding a gate to a shared tree, the question is not only "does
it pass" but "what else reads this tree, and what does it now see?"

## Shared state read inside a worktree is frozen at the branch point

Every lane here works in its own worktree, and a worktree's `git log` walks
only the history of the branch it is standing on. So any tool that derives
shared state from history derives the state **as of the lane's branch point**,
with everything committed since invisible -- and it reports success, because it
is internally consistent.

`check_territory.py` derives the territory allocation's high-water wave from
`git log -p -- territory.toml`, specifically so it has no side effects. In the
shared tree that is right. In a worktree it read the branch point and nothing
after.

Measured on 2026-09-13. The #31/#10 lane branched at wave 12 and ran its entire
life against a table where `glsl/psh.c` sat in `[free]` with **no owner at
all**. The live table had claimed that file for that very lane at wave 13. Its
`preflight.sh` printed `territory ok` on every run. The checker was not wrong
about the file it was handed; it was handed a file four waves stale. Nothing
collided only because the file the lane saw as free happened to be allocated
**to it** -- a lane in that position can take a file another lane claimed after
it branched, and its preflight will pass.

The fix is `--all`, and in a worktree it costs nothing because the object store
is shared: the same call that derived 12 derives 16.

**A stale read and a live read are indistinguishable once they are quoted into
one sentence.** The lane reported this as an overlap: "wave 13 lists `psh.c` in
both `[lane.psh]` and `[free]`". No committed wave ever contained that overlap.
The two halves came from two different files -- `[lane.psh]` from the live
table it had been briefed from, `[free]` from its own frozen copy. The report
was false and the underlying bug was real and worse, which is the argument for
checking the claim rather than either believing or dismissing the report. This
is the same shape as the stale-artifact and stale-floor failures already
recorded, arriving through a checker that said ok.

**A finished lane's worktree can still hold live bindings.** Two #10 arms were
queued with `expect` pointing at a prediction inside `/home/justin/hakuX-wt-31-10`.
The lane then finished. Removing the worktree would have made a hash-bound
prediction unresolvable at judging time -- and the dangerous version of that is
not the missing file, it is a *different* file of the same name hashing cleanly.
Before retiring a worktree, check what in `dispatch/queue` and
`dispatch/running` still names a path inside it. Re-pointing a **queued**
request at a byte-identical copy is safe and provably neutral, because the
binding is the content hash and not the path; a **claimed** request is never
edited.

## Two masks of equal cardinality can be disjoint

A residual carried between captures -- "this one is at the floor, so that one
should be too" -- is being compared by **cardinality**, which says nothing
about whether it is the same defect.

Measured on #38: nine `Bump_map` captures sit at exactly 1,576 differing
pixels, and their masks are **byte-identical** -- the same 1,576 coordinates
across seven texture formats. So 1,576 is a MASK, not a count. And the capture
that appeared to go "below the floor" at 668 px overlaps that mask in **19
pixels**: the sets are nearly disjoint, so the fix **replaced** the residual
rather than partly clearing a shared one.

`intersection == union` is the two-line check, and it is the difference
between "the same floor" and "a coincidence of size". Run it before
transferring a floor, a residual class or a noise band from one capture to
another.

## A wrong zero stops work; a wrong ratio redirects it

Both are measurement defects and the second is more expensive, which is not
obvious and is worth stating.

A negative read from a blind instrument stops one investigation, and the cost
is bounded by whatever that investigation was worth. A *confident number* from
a wrong instrument sends everybody somewhere, and the cost is everything built
on top of it.

The worked example is 2026-09-13's retranslation waste ratio. Two counters,
each wrong in a different way:

  `hakux_tb_generated` counts CALLS to `tb_gen_code`, not generations -- a
  call that recycles a block from `inv_htable` takes `goto recycle_tb` and
  never reaches codegen. Measured recycle rate about 5:1.

  `hakux_tb_invalidated` counts TBs VISITED, not discarded -- it increments
  before `tb_phys_invalidate__locked`, which early-returns when `qht_remove`
  fails, BEFORE `tb_remove`. So an already-`CF_INVALID` block is counted, left
  on the page list, and counted again on the next store.

Their quotient was published as **2.8:1**, "79 blocks destroyed and 29
regenerated every frame", and `performance-next-three.md` ranked its three
levers on it. It is visits over calls. Neither counter was ever checked against
an invariant, because neither ever produced an absurd value on its own -- the
absurdity only appeared in a THIRD quantity derived from them, guest
instructions per generated block, at 0.38. A block cannot hold less than one
instruction.

So: before a number ranks work, divide it by something and check the units.
A counter that is never divided is never falsified, and a ratio of two
plausible counters can be arbitrarily wrong while both look fine. State what
each counter counts in terms of the EVENT you care about -- "calls" and
"generations" are different events, and so are "visited" and "discarded" --
and put the increment on the far side of every early return.

The related cheap habit, which is what made this diagnosable: the lane added
its `ai=` counter for the early-return case PRE-EMPTIVELY, from reading the
code rather than from being surprised by a number. A probe built for a hazard
you have not yet hit is what turns an impossible row from suspicious into
explainable.

## A measurement that disagrees with the arithmetic is the instrument until proven otherwise

A probe that only ever reports plausible numbers cannot be checked. One that
reports something the arithmetic forbids has told you, for free and before the
number was believed, that it is measuring the wrong population.

The worked example is #60's alias probe on 2026-09-13. It counted surface
reuses the compatibility predicate permits across a guest-format change, and
reported ten instances of `A8R8G8B8 -> R5G6B5` -- a transition the predicate
cannot allow, since bpp *and* internal format both differ. The impossible row
was the finding: the probe guarded on `s1->color == s2->color`, which is also
true of two ZETA surfaces, whose `shape.color_format` is meaningless. Guarded
on `s1->color && s2->color` the row vanished and the remaining four agreed
exactly with the map.

The reusable part is not "check your probes". It is the specific failure:
**a field that is meaningless for one variant of a union still compares
equal.** Every probe that keys on a struct field shared by two kinds of object
has this available to it, and the symptom is a plausible number in the rows you
expected plus one row that cannot happen.

So when a probe and the arithmetic disagree, do not reconcile them by
adjusting the arithmetic. Find the row that cannot happen and explain it
first -- and if every row is plausible, that is not reassurance, it is the
absence of a check.

## A blocker is a claim, and it needs the same evidence as a fix

"A failed arm is a diagnosis, not a revert" has a mirror image, and #41 cost
three passes to learn it. Each of those passes declined to fix the issue on a
*stated* blocker, and all three blockers were false:

  - "a transformed vertex position is not something the CPU can read back" --
    it does not have to be read back; the matrix is in `vsh_constants` and the
    vertex in `inline_value`, which is what #42 already uses;
  - "nothing in the corpus can run the experiment" -- the fixed-function
    captures of the identical scene ARE the experiment, once the geometry is
    validated against them, which it was, to 0.99 of one quantisation step;
  - "writing the constant would be arbitrary for every other guest" -- the
    orchestrator's own, and wrong because the value is computable rather than
    a constant to be guessed.

None of the three was measured before it was used to stop work, and the
cheapest refutation took one offline script over captures already on disk.

So: a sentence that ends an investigation carries the same burden as a change
that closes one. Write the blocker down in the form of the measurement that
would refute it -- "this is impossible because X" becomes "if X were false,
Y would be observable" -- and if Y is cheap, run it before recording the
blocker rather than after someone doubts it. A blocker nobody can refute
cheaply is the most expensive kind of comment a tracker can hold: it stops
work for as long as it stands, and it costs nothing to write.

## An inference can be valid and still wrong, because the model it is valid inside was never checked

Contributed by the remote lane on 2026-09-13, from its own retraction on #51,
and it is a different failure from bad reasoning.

Silicon picks a cubemap corner from `sign(dot_1)` and `sign(dot_2)`; the third
sign selects nothing. That is measured -- 100.0% pure on all eight sign classes
across all six captures, at most 70 stray pixels in 56,909, all on class
boundaries. The tracker said exactly that from the beginning. It was
"corrected" to two products, `sign(z)*sign(x)` and `sign(y)*sign(x)`, by an
argument that assumed the corner arrives through the cube-face projection
`(s,t) = (-z/x, -y/x)` of a saturated direction, and then reasoned about which
PAIR of corners the unsigned dotmaps can reach -- an edge rather than a
diagonal.

**That inference was sound. The projection it was sound inside had never been
measured.** Silicon reads two sign bits; it does not project our vector. So a
correct step produced a specific wrong answer, an arm was built on it, and four
captures regressed.

It is worth distinguishing from the failures already in this file. A curve fit
is an answer chosen to match the data. A tautological falsifier is a leg your
own change forces true. This is neither: the reasoning is checkable and holds,
and the conclusion is still false, because the premise was a model somebody
adopted without measuring. It reads as evidence precisely because the argument
survives inspection.

So when an inference rests on a transform, a projection, a layout or an
encoding, say which of those is MEASURED and which is assumed, in the same
breath as the conclusion. If the model underneath is unmeasured, the conclusion
inherits that and must be registered as a candidate rather than a finding --
and the legs should be the measurement itself, not the expression derived from
it. The same lane's next step got this right: register the sign-to-corner table
as the prediction, not the `vec3` expression that reproduces it.

A related tell, and it is cheap to check: when a measurement agrees with a
model to 100%, ask what a SYSTEMATIC error in the instrument would do. Here a
consistent sign error in our own dots would have RELABELLED the table rather
than adding noise, and no purity figure can see that.

## A correction is not evidence of accuracy

Changing your conclusion without changing your instrument gets you a second
wrong answer that feels safer than the first.

#43 on 2026-09-13 is the worked example and it cost three readings. The
before/after sweep showed all fifteen `#spot_*_SADD` captures disagreeing with
their goldens over exactly 104,205 px, where before they had scattered from
91,310 to 111,381.

  READING 1: the blend factor has stopped being read. Published, with the
  distinguishing check named in the same comment -- diff our fifteen captures
  against each other.
  READING 2: ran that check, got fifteen distinct sha256s on our side and
  fifteen on the golden side, and published a retraction: the factor IS
  applied, and what is constant is the disagreeing REGION.
  READING 3, from the lane: `TestSpot` ends with `pb_printat(0, 0, name)`, so
  every capture carries its own test name in rows 0-63. A whole-image hash
  reports fifteen distinct images WHATEVER the renderer did, and fifteen
  distinct goldens too. Crop the label and silicon renders ONE picture for all
  fifteen source factors under the signed equations, our pre-fix arm gives 13,
  and our post-fix arm gives 1. The collapse was the fix AGREEING with
  silicon.

Reading 2 was more confident than reading 1 and no better founded: both came
from a whole-image hash, which cannot see the question. The retraction changed
the answer and kept the instrument.

So when you correct yourself, state what you changed about the MEASUREMENT,
not only about the conclusion. If the answer moved and the instrument did not,
you have a coin landing the other way up. And prefer an instrument with a
control in it: `MIN`/`MAX` ignore blend factors by specification on both
sides, so their reading of 1 is what proved a 1 here was silicon's answer
rather than a broken renderer -- the same role the impossible row plays for a
probe.

The corollary is specific and reusable: **a capture that prints its own name
into the frame cannot be compared by hashing the whole image.** Crop, or
compare the region the test is about.

## Conventions

- Defects live in GitHub issues, grouped by likely shared cause, each carrying
  measured evidence.
- `docs/investigations/` holds long-form records of bugs chased in depth.
  Read the relevant one before re-deriving it.
- `docs/archive/` is superseded material. Nothing there should inform decisions.
- Commit messages follow the existing `area: summary` style — `git log` is the
  reference.
