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

## The harness is being restructured (2026-09-19)

Read [`docs/ORCHESTRATION-DESIGN.md`](docs/ORCHESTRATION-DESIGN.md) before
anything below it. In short: **`master` is the trunk** and the campaign branch
is being folded into it; every lane is a branch `lane/<name>` from master with
one draft PR whose body lists its files; the board (`territory.toml`,
`nv2a_issues.toml`, briefs) is moving to the orphan `board` branch and is
written by the board job only; the long-lived orchestrator session is
replaced by scheduled jobs; CI runs on every PR because it is free on this
public repository, so `[skip ci]` is no longer required. Where a rule below
names the campaign branch, read `master`. Where it says "ask the
orchestrator", write a board request and carry on. The measurement
discipline below -- predictions registered before the run, per-capture
verdicts, two audit passes -- is unchanged.

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

## The answer is usually already on disk

This is the deepest failure this project has, measured six separate times in
one session. Every one looked like a different problem and every one was this:

  - **#79's mechanism.** Filed as "Stencil is nondeterministic", blocked on an
    instrument that had to arrive with a fold-in. Eight runs of captures were
    already on disk; comparing them byte-for-byte gave the diagnosis and took
    minutes.
  - **#13's phase.** Blocked on "the goldens cannot determine it". The goldens
    determine it at 100.0000% over 20,946 cuts. The old instrument recorded
    the run's LENGTH and discarded its POSITION, which is the half that pins
    the phase.
  - **#54 and #77's "waiting on the Nova".** Both said Galleon lives only on
    that handheld. One read-only `device_titles thor` refutes it -- and that
    function exists precisely because guessing a filename had cost five failed
    queue claims.
  - **#54's counter.** The read-side probe it was blocked on had existed since
    `e353735028` and had RUN ON GALLEON THREE TIMES, including the two runs the
    issue's own cost table was built from. Nobody had read its output.
  - **#38's mechanism 2.** "Needs five captures that do not exist upstream."
    Three of the five are answered by data on disk; two remain.
  - **140 commits unpushed.** Held back on a CI cost that a one-minute check of
    the workflow triggers shows does not exist for this branch.

**The rule.** Before accepting that work is blocked on something you do not
have, spend five minutes establishing that the answer is not already on disk.
Specifically: has an instrument for this ever run, and did anyone read its
output? Do the captures, goldens or logs already in `dispatch/results/` contain
the discriminating case? Is the claim about a FILE, a DEVICE or a CAPABILITY
that can be checked with one command?

This project generates data faster than it reads it. The corpus, the captures
and the logs on this box already contain answers to questions that are
currently written down as blockers, and the cheapest refutation of almost every
blocker here has been an offline script over artefacts that were already
present.

## Paper cuts are tracked, and a DX pass runs daily

Friction that has cost real time lives in `docs/testing/papercuts.toml`, with
what it actually COST rather than a description -- a paper cut with no cost
attached loses every prioritisation argument it is ever in.

**Why it exists.** Six instruments were fixed on 2026-09-13/14 and every one
was fixed REACTIVELY, at the moment it cost something. That means the only
paper cuts that ever get fixed are the ones that draw blood twice; the rest
stay, get rediscovered by the next agent, and cost the same time again. The
record of them lived in commit messages, which is where knowledge goes to be
unfindable.

**The daily pass.** A DX lane is dispatched once a day against that file,
ordered by `bit` -- observed occurrences -- descending, then by cost.
Recurrence is evidence of recurrence. The pass must also HARVEST new cuts from
the last day's commits and agent reports before dispatching, because the whole
point is to reach the ones that have only bitten once.

Rules specific to a DX lane: it may not touch `hw/`, `target/` or `accel/` --
paper cuts are tooling and process, not emulator behaviour; every fix is
negative-tested against real data on disk rather than fixtures; and entries
are REMOVED when fixed, naming the commit. A backlog that only grows is a
list, not a backlog.

**The schedule is a systemd USER TIMER, `hakux-dx.timer`, not a session cron.**
The first version was a session cron and it was wrong for a reason worth
keeping: held in memory, dead when the session exits, auto-expiring after
seven days. That would have been the THIRD piece of this project's automation
that looks installed and is not -- the Stop hook is read from settings.json at
session start, and `idle-watchdog.sh` is read lazily by byte offset so editing
it mid-run changes nothing in the running instance.

It follows `hakux-nightly.timer` exactly, including `Persistent=true`, which
is load-bearing here: this host is WSL2 and is shut down whenever the user
closes it, so a plain cron silently misses every day the box was off -- and an
unharvested day is indistinguishable from a day with no friction. Copies of
both unit files live in `docs/testing/` so the schedule is in the repo and not
only in `~/.config`.

`dx_pass.sh` HARVESTS and marks a pass due; it does NOT dispatch. Choosing a
lane, writing its territory row and briefing it is orchestrator work, and a
timer that spawned agents would be dispatching without a board in view.

## Code is audited twice before it is trusted, and preflight is not an audit

Set by the owner on 2026-09-14, after **+1,531 / -539 lines of compiled code
landed in fourteen hours with nobody reading a diff** -- across eleven files
including `target/i386/tcg/fpu_helper.c`, which reaches every title, and
`vk/draw.c`, which three separate lanes touched.

**`preflight.sh` is not an audit.** Its six gates -- psh_differ, aci_vmstate,
nv2a index, territory, coverage, commit subject -- check that the TREE and the
BOARD are consistent. Not one of them reads a change. Passing preflight says
the index is current and the tracker is honest; it says nothing about the code.

**And a measurement is not an audit either.** This campaign verifies claims
well: a prediction is bound before the device runs, an arm is judged against
silicon, a rival sweep is registered in advance. All of that establishes that
a change moves the pixels it said it would. None of it looks at error paths,
resource lifetimes, cross-thread access, integer overflow, or behaviour in
cases the corpus does not contain -- and `nxdk_pgraph_tests` is nearly all
static content, so "the captures moved correctly" is a narrow claim.

### The loop

  1. **Audit pass 1** reviews the DIFF of a lane's work before it folds.
     Findings are classified **HIGH / MEDIUM / LOW**, each with a file, a line,
     and the concrete scenario in which it bites. A finding with no failure
     scenario is an opinion -- say so, and downgrade it.
  2. **Every HIGH and MEDIUM is remediated before the code folds in.** Not
     deferred, not noted. The fold waits.
  3. **Every LOW is reviewed and a DECISION IS LOGGED** if it is not
     remediated. "Reviewed, not fixed, because X" is an acceptable outcome;
     silence is not.
  4. **Audit pass 2 verifies the remediation was effective** -- not that a
     commit exists, but that the scenario pass 1 named can no longer occur.

Severity, as used here:

  - **HIGH** -- incorrect behaviour, memory or resource unsafety, a crash
    path, or a change that is wrong outside the cases the goldens exercise.
  - **MEDIUM** -- a real defect with bounded blast radius, or a correctness
    risk behind a condition that is not currently reachable and not guarded.
  - **LOW** -- quality, clarity, dead code, a guard nothing can currently reach.

Records live in `docs/audits/<date>-pass{1,2}.{md,json}`. The JSON carries
severity, file, line, summary, scenario, remediation, so a gate can consume it
rather than a human re-reading prose.

**A REMEDIATION IS A CLAIM, LIKE A BLOCKER.** The finding is usually right; the
proposed fix is a suggestion from someone who did not have to make it work.
Twice in one chain a remediation was wrong and only the lane implementing it
caught that: pass 2 found the first HIGH's assert was implied by the condition
it sat under and could never fire, and M5's proposed eviction-on-insert rested
on "a superseded entry can never be recycled again" -- false, because `ihash`
is over guest bytes, so alternating overlays make it recyclable, and evicting
would have destroyed exactly the hit the cache exists for. **A lane that
disagrees with a remediation should decline it with a reason rather than
implement it**, and say so in its report. Both lanes did this unprompted; it is
written down so the next one does not assume the finding is authoritative.

**The auditor does not fix what it finds.** Remediation is dispatched as its
own work and audited again in pass 2. An auditor that patches its own findings
is grading its own homework, and this project has already learned that a
checker which reads live state while writing it turns its own staleness into
somebody else's fault.

## Routing on paper is not routing

Four audit findings -- M2, M4, P2 and L5 -- were recorded as "routed to
lane.remote" in decision records. The lane had been dispatched before any of
them existed and its brief named none. Audit pass 2 filed it as a MEDIUM
against the orchestrator; `lane.lows`, reaching the same conclusion
independently one lane later, named the real defect: **the routing MECHANISM
is the bug, not the individual deliveries.**

Writing the routing is the satisfying part. It closes the item in the document
you are working in, the checker that reads that document goes quiet, and the
recipient is not in the room to notice the silence. Every gate reports healthy.

**So "routed" requires three things, and a record is only the first:**

  1. the decision recorded;
  2. **an append-only entry in `$DISPATCH_DIR/deliveries/<lane>.md`**, which
     the lane reads at session start and after every message. A message to a
     cloud session is one-way and leaves no record either side can check; a
     file does;
  3. **somewhere for the work to live** -- an issue, a tracker row, a lane
     claim. Work with no row is invisible the moment the message scrolls past.
     M4 had none for hours.

The same shape as a lane briefed with files never claimed in `territory.toml`:
the brief is not the claim, and the record is not the delivery. When a hand-off
crosses a session boundary, assume it did not arrive until something on the
receiving side shows it did.

## A lane cannot satisfy a gate it is barred from fixing

Found by `lane.toolsmith` auditing the checkers, and it is a governance bug
rather than a code one: **five of `check_coverage.py`'s six FAIL paths and both
of `check_territory.py`'s can only be satisfied by editing `territory.toml` or
`nv2a_issues.toml`** -- the two files lanes are contractually barred from
touching. So a lane's own `preflight.sh` can fail on a condition it is not
allowed to fix, and its only move is to stop and ask.

That is the retired-lane bug's shape at governance scale: a wall that looks
like the lane's problem and is actually the orchestrator's.

**So a lane writes a BOARD REQUEST instead of editing the board.** Drop a file
in `$DISPATCH_DIR/board-requests/<lane>.md` naming what the board needs to say
and why, and put the same thing in your final report. The orchestrator applies
it. A lane must never edit `territory.toml` or `nv2a_issues.toml` directly,
and must never be blamed for a gate it cannot reach.

## Who does what, and what must NOT flow through the orchestrator

Set by the owner on 2026-09-14 after the orchestrator had spent a session
doing three jobs that were not its own. Each violation below actually
happened, which is why they are listed as violations rather than as advice.

**The orchestrator** dispatches work to agents and folds completed work in. It
arbitrates `territory.toml` and `nv2a_issues.toml`, because the tracker is the
one hand-maintained table in the index and an agent editing the claim registry
while claiming territory in it is circular. That is the whole job.

It does NOT:

  - **Queue device arms on an agent's behalf.** A lane owns its own
    measurement: it registers its prediction and calls `request.sh` itself.
    The dispatcher serves the queue; the orchestrator is not a step in that
    path. Roughly eight arms went through the orchestrator in one session and
    every one of them serialised work that had no reason to be serial.
  - **Edit the instruments.** `ab_compare.py`, `request.sh`, the checkers, the
    watchdog and `sweep_agreement.py` belong to `lane.toolsmith`. Six
    instrument fixes landed inline in one session. Each emerged from a failure
    being diagnosed, which justifies the first and not the sixth.
  - **Hold a fold in its foreground.** A fold costs a ~6-minute Android build
    plus preflight, and during it nothing is being allocated.

**A lane** owns its issue, its files, its predictions and its own device
requests. It reports what it measured. If it needs something outside its
territory -- a grant, a decision, a file nobody claimed -- it must say so **in
its final report**, and the orchestrator records that in the fleet registry.
`lane.padwrite` needed one line in a file nobody had claimed, said so, and it
sat until a human read the prose.

**The fleet registry** is `$DISPATCH_DIR/fleet/<lane>.json`, written by the
orchestrator at dispatch and updated when a report lands. `fleet.py` reports
RUNNING, REPORTED-BUT-NOT-FOLDED, WAITING-ON-THE-ORCHESTRATOR, LANE-CLAIMED-
WITH-NO-RUNNING-AGENT, and DISPATCHABLE-NOW-BUT-NOT-DISPATCHED. It is written
by the orchestrator and not by agents on purpose: an agent cannot be trusted
to record that it is stuck, and the point is to make the orchestrator's own
bookkeeping checkable by something other than the orchestrator.

**TASK LANES AND STANDING LANES ARE DIFFERENT, AND ONLY ONE GOES STALE.** A
**task lane** holds files to do one job and releases them when its agent
reports -- a claim it still holds afterwards is asserting coverage that does
not exist, which is the row `[free]` below warns about. A **standing lane**
owns a domain for as long as the domain needs an owner: `lane.toolsmith` owns
the instruments, and its claim is correct while no agent is running. It carries
`standing = true` so a territory/fleet cross-check can tell the two apart
instead of reporting it as a stale claim every time it is idle.

**EVERY RUNNING LANE HAS A ROW, COMMITTED AND PUSHED BEFORE IT STARTS.** That
is the general rule, and it is written in this form because the specific form
was fixed twice and found a new door each time.

  - `lane.padwrite` was briefed with four files described as "yours" and **no
    row was ever written**. It edited three of them. Nothing collided, because
    nothing else wanted them that hour.
  - `lane.tcginval`'s row was written and validated, and then **dispatched
    before it was committed**. The lane fast-forwarded to a tip that predated
    the commit and opened its board request reporting `territory.toml` at wave
    42 with no such row -- correct, from where it stood.
  - `lane.audit-tcg` was dispatched with **no row because an auditor claims no
    files**, so I reasoned it needed none. It needs one: a row with
    `files = []`.

The common failure is not forgetfulness. Each time, the thing I checked was
true -- the brief named the files, the row existed, the auditor genuinely
claimed nothing -- and the thing that mattered was not checked. **A lane that
is running and unclaimed is invisible to every guard**, because
`check_territory.py` cannot see a lane that does not exist in the file, and
`fleet.py`'s LANE-CLAIMED-WITH-NO-RUNNING-AGENT only looks the other way.

So: write the row, validate, commit, **push**, then dispatch. A lane that
claims no files still gets a row. And the cheap check that catches all three
is to compare `territory.toml`'s lanes against `$DISPATCH_DIR/fleet/*.json`'s
running set in both directions -- which is how the third was found, and found
`lane.tcginval` still claiming files after it had retired at the same time.

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

**THE DESKTOP HALF IS CURRENTLY UNMEETABLE ON THIS HOST AND MUST NOT BE
CLAIMED.** Verified 2026-09-14: `libcurl4-openssl-dev` is not installed, there
is no `build/` tree, and installing it needs a sudo password this session does
not have. Three separate lanes reported being unable to run it and each was
correct; `preflight.sh`'s `psh_differ` and `aci_vmstate` steps compile a
little C and are the closest thing to a desktop check that runs here.

So: a lane that cannot build desktop must SAY SO in its report rather than
passing over it, and must not write "built both". A rule that is
systematically violated and never corrected is worse than no rule, because it
teaches everyone to treat the list as decorative. The fix is one package
install by the owner:

    sudo apt install libcurl4-openssl-dev

Until then this is a KNOWN, NAMED gap and not a lane's failure.
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

**THERE ARE TWO LEASES, AND CHECKING ONLY THE SHARED ONE IS MISLEADING.** That
path is the shared lease, touched by `hold_device.sh` and the older
single-device scripts. **`dispatcher.sh` holds one lease PER DEVICE instead** --
`devices.sh` names it, e.g. `/tmp/hakux-device-lease.thor` -- so two
dispatchers cannot mistake each other's run for their own. `stop-emulator.sh`
resolves that per-device path through `devices.sh` exactly when the shared file
is stale, which is why a stale shared lease does not mean the device is
unclaimed.

This paragraph used to describe only the shared lease, and on 2026-09-13 that
cost a lane a false alarm: it found the shared file **18.7 hours stale** while
a hundred-suite sweep was mid-run, correctly concluded the hook would not
defer, and warned that its turn ending would kill the run. The per-device lease
was 26 seconds old and the hook would have deferred on it. The lane read one
input and concluded about a system with two, because this file only told it
about one.

**So before reporting that the device is unleased, resolve the per-device path**
-- the hook's own `device_lease()` does it in three lines -- or better, simulate
the decision rather than reasoning about it. And note what the lane got right:
it refused to touch the lease, because faking one on another batch's behalf
suppresses the interlock it exists to provide. Raising a suspected interlock
failure is correct even when the suspicion is wrong; silencing one never is.

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

> **DEVICE TESTING IS SUSPENDED, 2026-09-18, BY THE OWNER.** The Ayn Thor has
> somehow disabled its top screen and the owner is troubleshooting the
> hardware: *"Can we suspend on device testing for the moment while I
> troubleshoot that?"* The nova has been held since 2026-09-13, so **the whole
> fleet is out of service** -- there is no second handheld.
>
> `$DISPATCH_DIR/hold/thor` is placed, with the reason in `hold/thor.why`. The
> dispatcher claims nothing while a hold file exists and resumes when it is
> removed, so **a request already in `queue/` is not lost and must not be
> re-queued.** Do not remove either hold. If a queue looks stalled, that is the
> hold working.
>
> **This is not a reason for a lane to go idle.** Every issue on this board has
> offline surface, and this campaign has closed or re-diagnosed findings with no
> device at all at least six times -- twice from a counter that had been running
> unread, once from a query printed four times into a logcat nobody opened, once
> from a scores file the tracker had summarised wrongly. The offline order is:
> finish the implementation, prove the unreachable paths by reading and
> compiling, **register the prediction and leave it bound**, and only then wait.
> A bound prediction costs nothing while it waits and is what stops the eventual
> run being scored post-hoc.
>
> If you find yourself wanting *one quick run* to settle something, that
> instinct is exactly what the hold exists to refuse. The owner is holding a
> physically broken device; a run is not a small favour to ask.


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

## `git reset --hard` to undo a test commit also deletes the change under test

Testing a gate often needs a commit to test it against -- an empty commit with
a deliberately wrong subject, say -- and the obvious cleanup is
`git reset --hard HEAD~1`. That discards the working tree too, including the
uncommitted patch you are testing.

On 2026-09-13 this produced a false conclusion about a gate that was correct.
A new `preflight.sh` check was written, tested, and seen to print FAILED on the
bad input. Then `git reset --hard HEAD~1` removed the test commit **and the
patch**, and the next run -- the one checking that the gate changed the EXIT
CODE -- ran against the restored file. It exited 0. For a few minutes the
reading was "the gate prints FAILED but does not fail", which is a real and
serious bug, and it was not the bug: there was no gate left to fail.

Two habits, either of which is enough:

**Commit the change under test before testing it.** Then `reset --hard` is
safe, and this is usually right anyway -- a gate worth testing is a gate worth
committing.

**Or clean up with `git reset --soft HEAD~1`**, which drops the commit and
keeps the tree.

The general shape is worth more than the git detail: when a test's *setup or
teardown* can modify the thing under test, a failure is ambiguous between the
subject and the harness -- and the harness is the explanation nobody checks
first. This is the same family as the stale-snapshot and frozen-selftest
failures elsewhere in this file, arriving through version control instead.

## Narrowing a disc changes what it measures -- and the difference is itself a measurement

`--skip-tests` and `--only-tests` exist to make a question affordable: five
runs of one capture instead of five runs of 1,673. They also change the thing
being measured, because the tests you removed were leaving state behind.

Measured on 2026-09-13, on the five `Blend tests` captures of #50:

    capture               full disc (1,673)   5-test disc   difference
    1-dstA_SUB_1-cRGB              16,384         12,512       +3,872
    1-dstRGB_MIN_1                  8,192          8,192            0
    cA_MIN_srcRGB                   8,192          8,192            0
    srcA_REVSUB_1-cA               16,384         16,384            0
    1-srcRGB_SADD_0        76,032 / 98,304         76,032    (2 states)

**One of five depends on disc composition, by 3,872 px**, and the narrowed disc
is the *closer* one -- so on the full disc that capture carries 3,872 px
contributed by tests that ran before it. This is the same class as
`Texture render target::RenderTextureLoop`, which `make_test_iso.py` documents
as one test poisoning every test after it; here it appears in reverse, because
narrowing removed the poisoner.

**Two consequences, and the second is the useful one.**

**A narrowed-disc figure may not be compared with a full-disc figure.** I
pooled 13 observations across a 1,673-test disc, a 5-test disc and a 1-test
disc and published a rate from them. It was possible because `disc_id` did not
include `only_tests`, so all three carried one id -- fixed, and they now tag
`only5:a5e8ba/`. But the discipline does not live in the tool: ask what the
disc contained before comparing two numbers from it.

**The difference between compositions MEASURES the leakage.** That is a new
instrument, not just a hazard: run the capture alone, run it in company, and
the gap is what its neighbours contributed. It needs no golden and no new
code -- and here it says that 3,872 of one capture's 16,384 differing pixels
are not that capture's defect at all. Any issue quoting a full-disc absolute
should expect that question.

**AND THE ANSWER IS USUALLY ZERO, so do not discount a residual until you have
asked.** The instrument was turned on the worst suite on the scoreboard --
`W param`, 2,261,810 px structural -- and its two largest captures came back
with **no leakage at all**:

    capture                            alone (3 runs)   in company (3 runs)
    prog_w_zero_inf__bitri_w-0.00            271,518              271,518
    ff_w_zero_inf__bitri_w-7.52e-37          146,504              146,504

Identical to the digit, three runs each, in both compositions, on one binary.
So those 418,022 px are that suite's own defect, `W param` is not a flaky
suite, and the scoreboard's largest single numbers are not measurement
artefacts. Tally so far: **1 of 7 captures across two suites shows any
composition dependence at all.**

That negative result is worth as much as the positive one. A rule that cited
only the Blend case would license discounting every full-disc absolute, which
would be wrong in six of seven cases measured -- and "some of this might be
leakage" is exactly the kind of unmeasured caveat that makes a number
unusable without making it more accurate.

## Before measuring an effect on a class, check the class is non-empty

The cheap structural check and the expensive exhaustive one often answer the
same question, and reaching for the second first is a habit worth breaking.

On 2026-09-13 a scorer change gated on `test.endswith("_ZB")` landed between
two arms of a pair, so the pair straddled two `score_sweep.py` revisions and
`ab_compare` warned about it. The question was whether that change could have
touched the suite in question. I started re-scoring all 1,673 of one arm's
captures with the new scorer and diffing -- the exhaustive answer, twelve
minutes in and still running, competing with the dispatcher for CPU.

The decisive check was one command:

    ls captures1 | grep -c '_ZB\.png$'     ->  0
    ls goldens/Blend_tests | grep -c '_ZB'  ->  0

**Zero `_ZB` captures in that suite, in the captures and in the goldens.** The
gate is never true there, so the change provably cannot alter a single row --
a structural proof, not an inference from reading the code, and it took a
second.

**So: before measuring an effect on a class of input, ask whether this data
contains that class at all.** An empty class settles the question outright and
costs nothing; a non-empty one tells you the exhaustive check is worth
running. Note this is not an argument for reasoning instead of measuring --
the `ls` IS a measurement, of the input rather than the output, and that is
usually the cheaper end.

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

**But "use the ceiling" is a rule about one shape of series, and an
intervention can change the shape.** The reasoning above -- the series is
bimodal, the median tracks which mode it sits in, so take p90 -- assumes the
series sits AT the ceiling most of the time. That is true of the arm #64 was
measured on and **false of a bounded arm**. When the intervention changes how
OFTEN the ceiling is reached rather than how high it is, a high percentile is
**nearly blind to it by construction**.

Measured on #44, 2026-09-14, on the same statistic. With the bound on, only
~15% of windows are at the ceiling, so the 90th percentile of 66 windows lands
just inside that top band and reads 26-28 against the control's 29. The
registered leg -- p90 falls by >= 8 -- **failed at a fall of 3**, and the lane
first reported the cost as not reproducing at the tip. The cost was 37.6% of
guest frames.

p90 was not broken. It was faithfully answering *"can this still reach 30
sometimes?"*, and the answer is yes. **That is not the question a cost decision
asks.**

The deeper rule elsewhere in this file is the one that works, and it is the
same rule: **count events of a condition.** "How many windows were at the
ceiling" (81% -> 16%) and "how many guest frames in 240 s" (6,480 -> 4,020)
both show the effect immediately, and the second needs no percentile at all --
`gfps` is printed every 60 **guest frames** (`profile.c:600`), not on a timer,
so the line count IS a frame count and a fixed-duration run yields a direct,
occupancy-free total.

Two things the lane did here that are the reason this is written down. It
**reported the failed leg** rather than quietly re-deriving a passing one on
the better statistic. And it **retracted its own published conclusion within
the hour**, naming the instrument rather than the result -- which is the only
kind of correction that is worth anything, because a conclusion that moves
while the instrument stays still is a coin landing the other way up.

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

## A residual attribution is a MODEL, and a correct fix can fail a leg derived from a stale one

A leg that predicts "this residual falls to X" usually rests on an attribution:
a belief about which pixels belong to which defect. That belief is a model, it
was formed before the fix, and a fix that works can move pixels the model
assigned elsewhere -- so the leg fails while the change is right.

Measured on 2026-09-13. #43's F6 predicted the `#spot_` residual landing in
`[7,350, 19,140]`; it measured **80,007 and 76,897**, wrong by four times. The
floor came from a pre-fix attribution that assigned every ink pixel to the sign
fold. With the fold independently proven bit-exact on another suite, 54,015 px
remain attributable to it alone and 8,280 sit in neither class -- **the
104,205-px region was never all sign fold.** The same run shows **32,478 px
that the old model required to be wrong are now exact.**

So the leg was measuring the attribution, not the fix. Two consequences:

**A failing leg of this shape is evidence about the model.** Read it that way
before reading it as a failed change -- particularly when the direct legs pass,
as they did here on a bit-exact absolute with a counter behind it.

**Derive a bound from something the fix cannot move.** #43's surviving legs did:
an exhaustive `(S,D)` table, a control equation that is bit-exact on the same
path, and a pass counter. None of those depends on which pixels belong to which
defect.

It also cuts the other way, which is why this is worth a rule rather than a
footnote: had the fix been wrong, the same stale attribution could have
produced a leg it *passed*. An attribution-derived bound is weak evidence in
both directions, and its failure and its success are equally uninformative.

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

**AND A REGISTERED SET OF OUTCOMES CAN BE INCOMPLETE.** #50's five movers were
registered against a clean three-way split -- device difference, a race, or a
coincidence of five samples -- and the answer was a fourth thing: **4 of the
five are device, 1 is a race.** A same-device pair reproduced arm B on 1,672 of
1,673 captures; four of the five movers came back bit-identical, and the fifth
moved again on one device, to a value equal to the *other* device's. Nothing in
the registration was wrong and no leg had to be voided -- the enumeration was
simply not exhaustive, and a mixed population is what you should expect from a
handful of captures nobody has yet shown to share a mechanism. When registering
"either A or B", ask whether the sample could be a mixture.

**AN ABSOLUTE CAN BE UNSATISFIABLE TOO, by the arm's own construction.** The
rule above is about falls, and that is too narrow -- the orchestrator broke it
the same day with an absolute. #52's L1 had failed at "784 captures,
`partial: false`" on a run-budget timeout, and the retry was to be the `Cn`
half of the disc, which is redundant because `Cn`/`Cy` are bit-identical on
196/196. I asked for L1 to be re-registered unchanged: *784 captures with
`partial: false`*.

That is arithmetically impossible on a half disc. 196 of 392 tests is 392 of
784 goldens, so **`partial: true` is the CORRECT outcome**, and registering the
old number would have manufactured a failed leg on a run that did exactly what
was asked. The lane caught it and registered 392 with `partial: true`, plus a
better guard than the total: **exactly 49 `_ZB` rows in each of the four
cells**, because a per-cell count proves every retired cutoff arrived where a
bare total cannot.

So the check before registering any leg, fall or absolute, is the same one:
**is there a world in which this arm, working perfectly, still fails this
leg?** If the answer is yes and that world is the one you are in, the leg is
measuring your arithmetic rather than the change.

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

## A FIXED difference gives a consistent sign; a RANDOM one does not -- and look for structure, not direction

Two lessons from one set of five data points, and the orchestrator got the
first backwards.

**THE DIRECTION ARGUMENT, corrected.** #50's five movers split 4 better / 1
worse, and the orchestrator wrote: *"if this were device difference you would
not obviously expect an asymmetry, and if it is an ordering hazard you might."*
That is the wrong way round.

- A **device or driver difference** is a *fixed* difference in some operation.
  Whichever device is more nearly right for that operation is closer to the
  golden on every affected capture, so a **consistent direction is expected.**
- A **race** resolves per run and per capture into one of several discrete
  states, and whether a given state lands closer to or further from the golden
  depends on the capture, so there is **no reason for a consistent direction.**

So directional asymmetry, if it meant anything, weakly favours the *fixed*
cause. It is worth having the general form right: **a consistent sign is
evidence of a fixed cause; sign-indifference is evidence of a random one.**

**AND THE DIRECTION QUESTION WAS EMPTY ANYWAY, while a structural one on the
same five points was decisive.** At n = 5 a 4-1 split is two-sided
p = 0.375 -- what a coin does more than a third of the time. But:

    capture               nova (A)   thor (B)   B / 8192
    1-dstA_SUB_1-cRGB       27,136     16,384      2
    1-dstRGB_MIN_1          23,552      8,192      1
    1-srcRGB_SADD_0         76,032     98,304     12
    cA_MIN_srcRGB           66,375      8,192      1
    srcA_REVSUB_1-cA        23,552     16,384      2

**All five of thor's values are exact multiples of 8,192 and none of nova's
is** -- 8,192 being 64x128, half a 64x256 stack region, with three of thor's
five also multiples of the full 16,384. Fisher exact on 5/5 against 0/5 is
two-sided **p = 0.0079**, roughly fifty times the evidential weight of the
directional split, on the same five captures.

The readings differ physically too: a residual quantised to exact half-stack
blocks is what "a whole swatch is wrong" looks like, while a ragged residual --
nova's includes the odd value 66,375 -- is what partial coverage or per-pixel
disagreement looks like.

**So: before reporting that a small sample is uninformative, ask a different
question of it.** Direction and magnitude are the obvious statistics and often
the weakest. Structure in the values -- alignment, quantisation, a common
divisor with geometric meaning -- can be decisive where the obvious test is a
coin flip. Held as an OBSERVATION and deliberately not bound, because it is
post-hoc on five captures, which is the curve fit this file warns about; but it
names the discriminator to check first on the next arm, which is what a good
observation does.

## A guard that FAILS tells you where to look -- diff the failure by region before calling it noise

A `must_not_move` guard exists to void a measurement, so the reflex on a
failure is to discard the arm and re-run. Sometimes the failure is the better
measurement, and the way to find out costs one diff.

Measured on 2026-09-13. #50's determinism guard failed: 5 of 1,673 captures
moved between two runs of the same APK on the same disc, one by 58,183 px, and
the pair was device-split so the failure was unattributable. Discarding it
would have been defensible. Diffing the five **by region** instead:

    capture               stack A   stack B   stack C   outside   labels
    1-dstA_SUB_1-cRGB      11,264         0    11,264         0        0
    1-dstRGB_MIN_1         11,264         0    11,264         0        0
    1-srcRGB_SADD_0           304    22,272       304         0        0
    cA_MIN_srcRGB           6,111    49,280     6,111         0        0
    srcA_REVSUB_1-cA        7,168         0     7,168         0        0

**Stack A and stack C change by exactly the same pixel count on every one**,
with the aliasing relation holding 1,024/1,024 in both arms.

That is a stronger result than the static measurement the issue was built on.
The static figure -- our stack C equals our stack A on 1,567 of 1,568 -- shows
the two are EQUAL. This shows they are **COUPLED**: perturb stack A by any
means at all, including whatever caused the guard to fail, and stack C follows
it pixel for pixel, because stack C's blit *is* stack A's image. **A clean pair
with zero movers could not have shown it.**

The `outside blits = 0` and `label rows = 0` columns are what make it a finding
rather than a story: nothing moved in the background or the overlay, so none of
the five is void and the movement is confined to the mechanism's own regions.

So when a guard fails: before re-running, ask **where** it moved. Region, not
total. A failure confined to exactly the structures the mechanism predicts is
evidence for the mechanism; a failure smeared across the frame is noise; and
the two are indistinguishable from a differing-pixel count.

## A two-column sweep diff is TWO SINGLE RUNS, and cannot tell a regression from variance

The corpus sweep runs **one run per suite**. So a diff of two sweep columns is
one run before against one run after, and on any suite with a nondeterministic
failure that difference is indistinguishable from noise. I filed a regression
off exactly that on 2026-09-13 and it was not one.

The claim was: three `Stencil_ZERO*` captures went from exact to
40,000/30,000/30,000 px between two columns, the category's whole +100,652.
Thirteen runs at matched disc composition on one device across four refs
refuted it twice over, and neither fact needs the other column:

    0026f00534  (the "after")   4 runs    0 ... 180,000 px   <- one binary
    2501f35211  (the "before")  4 runs    0 ... 140,000 px   <- called CLEAN
    8191d97296  (the tip)       4 runs    0 ...  60,000 px

The "before" column reaches 140,000 px on `ZERO_ST_DT` and `ZERO_ST_DT_ZB` at
exactly 30,000 each -- **two of the three captures the regression was attributed
to.** Its zero was one lucky run. The rate is 7 of 13, reproducing the known
5-in-10 for that suite. Two commits were named as suspects and both were
exonerated without either diff being read.

**What makes this worth a rule is which check I did and which I skipped.** I
ruled out the scorer, correctly and with a real control: re-scoring *both*
capture sets with the *same* code gave 0/0/0 and 40,000/30,000/30,000. But that
establishes only that the **pixels differed between those two runs** -- never
that a change caused them to differ. The cheap control I skipped is a **repeat
run at the same ref**, and the project memory already said to rerun twice before
debugging a lone score change. Having the rule is not applying it.

**So: before attributing any sweep-column delta to a commit, re-run the suite at
one of the two refs.** If the delta is inside one ref's own spread, there is
nothing to bisect.

**DO NOT DIFF TWO COLUMNS BY HAND -- `docs/testing/sweep_diff.py` is the gate,
and it EXITS NON-ZERO rather than warning.** That distinction is the whole
reason it exists: the hand-rolled diff did print the movers and a reader could
have applied this rule to them, and the conclusion was drawn anyway. It pools
every same-ref repeat on disk, refuses to believe a band behind fewer than
`MIN_RUNS` runs, and prints the exact `request.sh` line that would settle an
unattributable mover.

It also reports when a column is internally mixed across `score_sweep.py`
revisions, which one column was for five hours -- the sweep runs long enough
that a scorer change lands mid-column. And the ordering that caught this is worth copying: the first
build went to the **tip** rather than into the window, and it returned the three
named captures exact with a *different* capture broken at the same total -- a
failure that relocates at constant total is nondeterminism, not a fix.

The sweep's own gap is recorded as #76: a two-run disagreement guard was
recommended in writing when this was predicted, and never built.

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

## Register two legs that CANNOT both be satisfied by turning the feature off

A guard stops a fix from breaking something else. It does not stop a fix from
doing nothing, and neither does a tautology check on a single leg. The stronger
construction is a **pair** of legs in tension.

#43's arm registers W1 -- ring 0 returns to bit-exact -- and W2 -- both signed
texture captures *stay* bit-exact. Disabling the fold satisfies W1 immediately,
because ring 0's regression is caused by the fold. It fails W2, because the
signed captures are only bit-exact *with* the fold working. **No inert change
and no disabled feature can pass both.** That is a property of the pair, not of
either leg.

Look for it whenever a fix has both an intended effect and a regression to
undo: register the undo AND the effect, and check that the trivial way to get
one loses the other. It costs nothing at registration time and it closes the
gap a per-leg tautology check leaves open -- a leg can be non-tautological on
its own and still be satisfiable by reverting.

## A state field keyed into a cache whose dirty-check uses a FIXED register list

`PshState` is hashed into the shader cache key, and
`pgraph_glsl_check_shader_state_dirty()` decides when to rebuild it from a
**hard-coded list of registers**. So a new `PshState` field driven by a register
absent from that list is stale by construction: the cache hands back a shader
built for different state, and nothing reports it.

Found structurally on 2026-09-13, with one grep, before any code was touched:

    NV_PGRAPH_BLEND in check_shader_state_dirty()'s register list:  0

#43's sign fold put `signed_blend_fold` in `PshState` from `NV_PGRAPH_BLEND`.
`DrawQuad` calls `SetBlend(false)` for its colour half between two blended
alpha draws, so the **folded shader was reused on a draw with blending off** --
where green `0xCC` = 204 sits above the sign bit, was masked to `f1 = 0`, and
reached the framebuffer unblended. That predicts `G 204 -> 0`, and ring 0
measures exactly `G 204 -> 0` against a golden of 204 on all 11,280 px:
agreement on the **value**, not merely the direction.

**Adding the register to the list fixes the instance and leaves the class.**
The next field driven by an unlisted register fails the same way, silently. The
fix that removes the class is to keep the new state **out of the cache key**
entirely -- emit the code unconditionally, gate it at run time on a
uniform-valued selector, and recompute the condition from the **live** register
at every staging. Nothing cached, nothing stale.

So before adding a field to `PshState`: grep that list for the register that
drives it. If it is absent, prefer a runtime gate to a cache-key extension.

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

## Commit BEFORE the long test, not after -- an uncommitted edit blocks every build

`dispatcher.sh` refuses to build any uncached ref while the shared tree carries
a tracked modification, and it fails by requeueing every thirty seconds. So the
window between editing a file and committing it is a window in which no arm can
be built.

The natural order -- edit, test, then commit once it passes -- holds that window
open for the whole length of the test. On 2026-09-13 the orchestrator ran that
way for an afternoon and the dirty-tree requeue count went from 123 to **197**:
74 requeues, none of them a stall, all of them avoidable. Three of them hit one
lane's arm B, which stalled at 15:00:45, 15:01:16 and 15:01:47 before
recovering -- and that lane's first instinct was that shared infrastructure was
broken, which would have been its third false report of the session.

**So: commit first, test after, amend on failure.** The dirty window shrinks
from minutes to seconds, and nothing untested escapes, because the push is
gated on `preflight.sh` regardless -- an untested commit that fails the gate is
amended and never reaches the remote.

This also removes the `git reset --hard` hazard recorded elsewhere in this
file: a change that is already committed cannot be destroyed by cleaning up a
test commit.

The requeue path is correct and did its job -- 90 seconds and three retries,
not the 251-requeue class. But "the recovery works" is a poor reason to keep
generating the failure, and an orchestrator committing every few minutes is
the single largest source of it.

### The orchestrator folds in a separate worktree, and the shared tree only fast-forwards

"Commit first, test after" is right for a lane and is **not sufficient for a
fold-in**, which is several operations long by nature: cherry-pick, tracker
edit, territory edit, index rebuild, preflight, commit. The tree is dirty for
all of it, and no ordering of those steps makes the window short.

On 2026-09-14 this stalled the whole queue twice in one hour. The first window
requeued one lane's tip-ref control seven times with eight more of its arms
behind it; the second was longer. Both times the lane diagnosed it correctly
from outside -- it is worktree-isolated, so it materialised the tip from the
object store and diffed the shared working tree against it -- and both times
it was right not to touch it. Neither was a lane's fault and neither was
recoverable by anything a lane could do.

**So the fold happens somewhere else.** `/home/justin/hakux-work/fold` is a
detached worktree kept for this:

    cd /home/justin/hakux-work/fold
    git fetch -q origin && git reset -q --hard origin/<branch>
    # cherry-pick, edit the board, rebuild the index, run preflight, commit
    git push origin HEAD:<branch>
    git merge --ff-only origin/<branch>

The shared tree is never dirty. Its working copy changes once, in a
fast-forward checkout that takes under a second, and `dispatcher.sh` sees a
clean tree at a new HEAD rather than a dirty one at the old one.

Two things this does not fix, recorded so nobody reads more into it. A lane
cannot run `git` against the shared tree at all, so the *diagnosis* still costs
it the object-store trick. And `dispatcher.sh` still logs an identical line
every thirty seconds while it waits, which reads as a hang rather than as a
blocked queue -- it should name the dirty files and the wait duration. That is
lane.toolsmith's, and it is the half that helps whoever is blocked rather than
the half that stops blocking them.

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

## An availability fix can silently change what a queued measurement MEASURES

Infrastructure changes have measurement semantics, and the scheduler is where
they hide. A fix that keeps the fleet busy can quietly convert a registered
comparison into a different comparison, and nothing errors.

Measured on 2026-09-13, and the change was the orchestrator's. The nova was
taken out of service for four hours with #50's arm A already run on it. Arm B
was queued, `affinity.py` rule 2 pinned it to the nova from arm A's owner file,
and the thor -- idle -- would have skipped it for the whole outage. So the rule
was changed: **a pin to a device that is not serving is not a pin.** Right call
for availability; arm B ran immediately.

What it did to the measurement: arm A on the nova, arm B on the thor. The
registered determinism legs -- `must_not_move` over a suite, and
`better=0 / worse=0` -- were written to ask *"is this 1,673-capture disc
deterministic run-to-run?"* They now answer **"run-to-run AND device-to-device
together"**, with no way to separate the two from that pair. No leg said that,
nothing failed, and the lane noticed only because arm B's device run was 20%
faster than arm A's and it thought to check `device_label`.

Two things follow.

**Do not reach for the equivalence check to rescue it.** The two handhelds
measured 62 of 62 captures byte-identical, same SoC, same Turnip -- a real
result, and it was measured on `Texture DXT` + `Surface clip` on the STOCK
disc. It has never been run on the interactive disc, nor on 1,673 captures.
Citing it for a different disc is the same transfer this file warns about one
level up.

**A fallthrough that changes a comparison must say so.** The scheduler is the
only actor that knows a pin was dropped, and it was the only one not
recording it. `affinity.py` now writes a note under `$DISPATCH_DIR/splits/`
naming the prediction and the device it declined to pin to, so the decision is
discoverable rather than reconstructed from a pace difference. The note is not
the strong mechanism -- `device_label` in the result is -- it exists so nobody
has to infer that a choice was made.

The general form: **when changing scheduling, availability, or retry
behaviour, ask which queued measurements the change re-defines.** Requests
already in the queue were registered against the old behaviour, and a
prediction bound by content hash does not notice that the world moved under it.

**And the FAIL case is worse than unattributable.** A lane sharpened this
better than the entry above did: its registration named the world in which the
leg fails -- *"FAILS IF the disc is non-deterministic on TestDetailed"* -- and
with a split pair a failure is **no longer evidence for that named world**,
because a device difference produces the same signature. So the change did not
merely confound the measurement, it **retroactively reduced a bound
prediction's diagnosticity.**

That is a failure class the registration machinery was never built for. Every
guard in `request.sh` and `ab_compare.py` protects against **the prediction
changing** -- TAMPERED, POST-HOC, UNBOUND, the content hash taken at queue
time. Nothing binds **the execution environment the prediction assumed**. An
infrastructure change landing between queue and claim leaves the hash intact,
the leg unedited, and its diagnostic power quietly lower, and no check
anywhere notices.

Two partial answers now exist and neither is complete: `ab_compare` warns when
the arms' `device_label` or `scorer_rev` differ, and `affinity.py` records a
note when it declines a pin. Both are detection after the fact. The discipline
is the durable part -- before changing anything the scheduler does, read the
queue.

## An agent worktree is created on a STALE base -- rebase before doing anything

Measured on 2026-09-13, across every worktree this campaign has created:

    49 agent worktrees
     1 within 5 commits of the branch tip
       range: 4 to 764 commits behind

**None of the stale ones contains `docs/testing/territory.toml`** -- which is
where a lane's own brief lives -- and the older ones have no `request.sh`, no
`ab_compare.py`, no `preflight.sh`. A lane that reads its instructions from its
own checkout therefore reads a tree that predates the instructions.

Two consequences, and the second is the dangerous one:

**The tooling is missing, which is loud.** One lane worked around it by reading
tooling out of a ref with `git show` and invoking the shared tree's
`request.sh`, which is safe because that script writes only into the dispatch
directory and never into the repo. Another rebased onto the campaign tip and
proceeded normally. Both noticed immediately.

**A commit on that base is silent.** An arm requested at a ref whose parent is
400 commits old builds a tree missing every fix since -- and it will produce
captures, score them, and report them with a perfectly consistent `apk_sha`.
That is the stale-artifact failure with a fresh timestamp on it, and nothing
downstream can see it.

**AND THE ORCHESTRATOR MUST ASK FOR THE WORKTREE -- a lane cannot choose one.**
Isolation is a dispatch parameter, so a lane spawned without it works in
`/home/justin/hakuX` itself and commits onto the shared branch. That is the
condition `dispatcher.sh` refuses to build under: a tracked modification in the
shared tree stops every uncached ref, silently, by requeueing every thirty
seconds. It has cost 123 requeues in this campaign.

Done once on 2026-09-13, to the Galleon lane, and it cost nothing only because
the device queue happened to be empty for the whole hour it worked. The tell
was in its own report -- "the shared tree advanced 4 commits while I worked",
which is what a lane in the shared tree sees and a lane in a worktree never
does. Check that line in a report; it identifies the mistake after the fact.

**So the first action in a worktree is to establish its base**, and the cheapest
tell is whether `docs/testing/territory.toml` exists at all:

    git -C <worktree> rev-list --count HEAD..<campaign-tip>
    ls docs/testing/territory.toml

If it is behind, rebase onto the campaign tip before committing anything. If a
rebase is refused, the lane is restricted to measurement and analysis -- which
is a complete kind of result here, but say so explicitly rather than committing
on the stale base. A brief that asks for a fix must also say which tip to rebase
onto.

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

**A CHECKER THAT READS LIVE STATE AND DISK STATE TOGETHER TURNS YOUR
STALENESS INTO SOMEBODY ELSE'S FAULT.** `check_coverage.py` reads the open-issue
list from GitHub, live, and the tracker from the working tree. So a lane four
commits behind sees a real issue with no tracker entry and reports, correctly
from where it stands, that the board is broken and its push is blocked by
shared infrastructure.

Three times on 2026-09-13, from two different lanes, and each report was a
sound argument run against the wrong inputs -- the same shape as the stale
index, where a lane proved its commit touched "neither the index nor the tests
tree" while having moved 71 symbols in a file the index records sites from.

**So the check before reporting infrastructure blocked is
`git rev-list --count HEAD..<campaign tip>`.** If it is not zero, rebase before
concluding. A gate failing in a stale checkout is evidence about the checkout.

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

## Three ways a prediction can be inert, all of which still read as PRE-REGISTERED

`PRE-REGISTERED` is a statement about **binding**: the file existed before the
device ran and still hashes the same. It says nothing about whether any leg in
it could ever have failed. All three of these happened on 2026-09-13 and 14,
and each produced a result that looked decisive.

**1. A key that matches no capture.** Ten legs were registered as
`Blend tests::#spot_0_ADD` -- the derived suite spelling with `::`, which is
what `nv2a_issues.toml` and the test binary's capture filenames use.
`ab_compare` keys its rows `"%s/%s"`, the results-directory spelling:
`Blend_tests/#spot_0_ADD`. All ten matched nothing. The arm returned
`PRE-REGISTERED`, every capture went to exactly the predicted value, and the
whole machine-readable half of the prediction had been inert. Both spellings
exist on purpose -- the index carries `results_name` separately -- so this is
not fixable by picking one. `request.sh` now refuses such a key at queue time
with a `did you mean`; trust that gate rather than re-deriving the spelling.

**2. A `must_not_move` that meant `must_not_regress`.** `must_not_move` is
bit-identical. It was for a long time the only guard, so every "leave this
alone" intent got written as it. #13's wide-line arm then FAILED on eleven
captures that all moved **better** and none worse -- at w=1.0 a correct fix
*must* move a non-axis-aligned line. Both legs now exist. Write down which one
you mean; a guard nobody can state correctly gets stated incorrectly.

**3. An absolute derived from a stale baseline.** #67's legs said fifteen
`#spot_*_SADD` must fall to 96,855. The figure was **re-derived** from
`scores1.tsv` rather than copied, and said so in the prediction as the reason
to trust it -- true of the arithmetic, false of the premise, because the
result it came from was an older sweep where #43's ink still existed. On the
armed ref the baseline was 17,024 and the captures correctly went to 0. Check
the `apk_sha` and date of whatever you derive an absolute FROM, and prefer
arm A's own measured value: run the baseline arm first, or predict directions
and deltas rather than absolutes.

After any PASS, check how many legs actually **bound to rows**. A count of
checks *performed* is the number that matters, not the count written.

## `merge-base --is-ancestor` answers a question about SHAS, not about patches

Lane work is rebased in constantly here, so **a cited sha being absent is the
normal state for work that shipped**. Three tracker entries drew a wrong
conclusion from ancestry in one day, in both directions:

  - I read `merge-base --is-ancestor 8d2bf50075 HEAD` returning false as
    "#43's sign-fold fix is not present", published a refutation of #43's
    attribution on it, and withdrew it. `8d2bf50075` was not the fix at all --
    it was the arm-**B ref** of the pair `322adc3a01 -> 8d2bf50075` -- and the
    real fix was on the branch as `c2d57ba21a66`, an ancestor of the very arm
    I had called clean.
  - #62's entry said "zero of the six findings landed", from the same
    inference. Two of them are in the tree, at `gl/surface.c:561` and
    `:1368-1390`.
  - #72's `fixed_by` listed a **docs** commit first, reading as though that
    were the fix.

`docs/testing/check_cited_commits.py` does this properly: patch-ids, scoped to
the paths each commit touches so it covers all of history rather than a recent
window, and it prints every sha's **subject**, because half the hex in the
tracker is A/B refs, dispatch request ids and prediction sha256 prefixes. Two
dead ends are in its docstring so nobody rebuilds them -- `git cherry HEAD
<sha>` lists the whole divergent range, and a `-200` window silently misses
older history.

What it cannot see is in the docstring too: patch-id matches exactly, so a fix
folded in with a resolved conflict or one extra comment line reads ABSENT
while its substance is present. ABSENT means "no byte-identical patch", not
"the work is missing" -- go and read the code.

### A prediction naming a `b_ref` must be registered AFTER the last rebase

A rebase rewrites every commit it moves, so **a `b_ref` that was an ancestor
before a rebase is not one after it** — and a `merge-base --is-ancestor` check
run *before* the rebase reports healthy. There is no warning at the moment the
binding breaks.

This bit #59 **twice, from two different causes**, which is why it is a rule and
not an anecdote:

  - First from an abandoned branch. The prediction's `b_ref` was not an ancestor
    of the lane tip, but shared a patch-id with a commit that was, and was still
    reachable from an older branch — **so the dispatcher built it successfully**
    and would have produced an arm B *without* the fix the lane had since
    written. Nothing announced it. The pair would have completed and scored.
  - Then from a routine rebase. The lane fixed that, rebased once to clear a
    territory gate, and **reintroduced the identical defect** — discovering it
    only because it re-checked afterwards.

So: **register last.** Do the rebases, then register, then do not rebase. If the
fold rebases the commits, the prediction has to be re-registered — and
re-registering is cheap, while a silently-wrong arm costs the device time plus
the time to discover it was void.

Two supporting habits. Run `merge-base --is-ancestor` on both refs **after** the
last rebase, not before. And prefer the queue-time gate to the discipline: a
`b_ref` that is not an ancestor of any live branch tip should be refused when
the request is queued, which is where the other inert-prediction classes are now
caught.

**The reachable-but-not-an-ancestor case is the dangerous one**, because it
fails in the direction that looks like success. An unreachable ref makes the
dispatcher fail loudly; a reachable stale one makes it produce a clean,
confident, wrong measurement.

**And a rebase is not the only thing that unbinds it.** The rule above was
written after two rebases broke the same prediction. It was then broken a
**third** time, by the orchestrator, with no rebase involved at all: the
prediction file was folded onto the integration branch **ahead of its own code
commits**, to make it durable against worktree reaping. At the integration tip
the `b_ref` was therefore not an ancestor; at the fold candidate both refs were
fine. Good intention, wrong result.

So the rule generalises: **a prediction and the refs it names must land
together, or the refs must land first.** Folding a registration early buys
durability and costs the binding — and the binding is the thing the
registration exists for. If a prediction must be preserved before its code is
ready, preserve it *somewhere other than the branch the dispatcher resolves
refs against*, or re-register it the moment the code lands.

Nothing catches any of this today: `check_cited_commits.py` reads the tracker,
not `predictions/*.json`.


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
