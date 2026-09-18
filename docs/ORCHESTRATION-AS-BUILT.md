# The hakuX orchestration harness, as built

Written 2026-09-18 for an **external audit**. The owner's brief was explicit:
*"We're consistently failing to monitor or dispatch work"* and *"we can't
continue with your haphazard disjointed approach."*

So this describes **what exists**, including what does not work, with the
evidence. It is not a design proposal and it is not a defence. Where a
mechanism has failed, the failure is named next to it, because a harness
audited against a flattering description is audited against nothing.

**Read this first, then `AGENTS.md`.** `AGENTS.md` is the canonical file agents
read and is ~2,500 lines of accumulated rules; this is the map.

**`docs/orchestration.md` is STALE** — written 2026-09-12, last touched
09-13, and it is a lessons-from-failures narrative rather than an as-built
account. It still discusses a territory table that moved into
`docs/testing/territory.toml`. Do not audit against it.

---

## 1. What this project is

An Android Xbox emulator (QEMU/xemu-derived, Vulkan on Adreno) measured
against `nxdk_pgraph_tests` golden framebuffers captured from **real XBOX 1.0
silicon**. Accuracy is the product: a change is worth landing when it moves
pixels toward the goldens and nothing else moves.

Two handhelds do the measuring — a Retroid Pocket Nova (`ee317437`) and an
Ayn Thor (`bdc158a5`), both Adreno 740 / `kalama`, shipping a byte-identical
driver. **Device time is the scarce resource** and most of the harness exists
to stop it being wasted.

## 2. The roles

| role | what it owns | how many |
|---|---|---|
| **orchestrator** | dispatch, the board, folding decisions | 1 (this session) |
| **lane** | one issue or a small set, on files it claims | many, serial-ish |
| **standing lane** | a domain, not a task | `toolsmith`, `fold`, `triage` |
| **audit lane** | reading someone else's diff; claims **no files** | per-audit |
| **dispatcher** | the device queue | 1 daemon per device |

A **lane** is one agent with a **territory claim** and a brief. An **audit
lane** deliberately holds nothing: an auditor that can fix what it finds has an
incentive to find fixable things.

### The orchestrator is the known bottleneck

Every dispatch brief, every board edit, and (until today) every fold passed
through one session. Measured cost on 2026-09-18 alone:

- **Two fleet-wide stalls.** A fold is six operations long and the shared tree
  is dirty throughout; `dispatcher.sh` refuses to build an uncached ref against
  a dirty tree and requeues silently. Seven requeues, then more.
- **A deadlock built out of politeness.** A lane was twice told *"ask and I
  will grant it"* for a file **that was in `[free]` the whole time**. It never
  asked; nobody followed up. **77 commits waited hours** on a grant that needed
  no decision.
- **Three ready arms unqueued** while both devices sat idle. Nothing was
  blocked; nobody had queued them.
- **A week with no comment review.** The first pass found **five** open issues
  whose comments carried verified results the tracker did not reflect, three
  apparently closable — and one whose only copy of a 126-check PASS was a bare
  unexpanded path into a scratchpad that gets reaped.
- **A severity overstated in four places** (`#84`, "unbounded" → bounded);
  a lane caught the fourth.
- **A false premise in two dispatch briefs**, each refuted by the lane before
  it could start.

The pattern is **latency, not judgement**: work sitting still while it waited
for prose. `lane.fold` and `lane.triage` were created today to attack that.

## 3. The board: two TOML files, machine-checked

### `docs/testing/nv2a_issues.toml` — the tracker

One entry per issue, mirroring GitHub. Load-bearing fields:

- `status` — `open`, `fixed-part`, `fixed-verified`, `fixed-unlanded`,
  `unmodellable`, `harness`, `closed-duplicate`
- `fixed_by` — **a list of shas**, required by the gate when
  `status = "fixed-unlanded"` (a fix that exists on a lane branch, not here)
- `blocked_on` — prose. **A blocker is a claim and gets tested**: seven were
  refuted in one day, two of them the orchestrator's own
- `blocker_falsifier` — the world in which the blocker is false
- `blocker_tested` — whether anyone checked

**Only the orchestrator edits this.** A lane editing the registry it claims
territory in is circular. `preflight` now refuses a lane commit that touches
it.

### `docs/testing/territory.toml` — who holds which files

Monotone `wave` counter; `check_territory.py` fails if it goes backwards,
because the allocation **was silently reverted once** by folding a lane branch
that carried an older copy. Currently at wave 87.

Rules it encodes, all earned: a file whose arm is *queued but not yet judged*
is still claimed; when a fix spans two territories **grant** rather than wait;
issues split from a common parent are never assigned concurrently.

**Known weakness:** files can be in **no** row and not in `[free]`. Three were
found in that state (`fleet.py`, `dispatcher.sh`, `swizzle.c`) — invisible to
every collision guard. Nothing enumerates the tree and asks what is unplaced.

## 4. Dispatch and the device queue

`$DISPATCH_DIR` = `/home/justin/hakux-work/dispatch`.

```
queue/ → (atomic mv claim) → running/ → results/
```

`docs/testing/dispatcher.sh` runs one worker per device. A request is JSON:
ref, arm label, run count, suites, and an `expect` path to a **prediction
file**.

**`$DISPATCH_DIR/bin/dispatcher.sh` is a `cp -f` snapshot** of the tracked
`docs/testing/dispatcher.sh`. The two differ mid-detach. Editing the snapshot
is the dangerous option; the tracked file goes live on the worker's next
re-exec, which sits **before** request claiming, so no run is disturbed.

**Holds.** `touch $DISPATCH_DIR/hold/<label>` takes a device out of service;
the worker claims nothing while it exists and resumes when removed. A hold
placed mid-run takes effect **after** the current request. Queued requests
survive a hold untouched and **must not be re-queued**.

### Predictions, and the three ways one goes inert

An arm is an A/B pair with a prediction **registered before the run**.
`ab_compare.py` returns `PRE-REGISTERED`, `TAMPERED`, `UNBOUND` or `POST-HOC`.

1. **Wrong key shape.** `expect` keys are `Results_Directory/TestName`, not
   `Suite name::Test`. Ten legs bound nothing in one day and the arm still read
   as a triumph.
2. **A key that names no capture.** `Image_blit/OverlapFIFO` was a registered
   control scored in **neither** arm — the golden exists, the capture never
   does. `request.sh`'s gate checks `$GOLDENS/<suite>/*.png`, so it asks *does
   a golden exist* and never *will this arm score it*.
3. **A stale `b_ref`.** A rebase silently un-ancestors it. Worse, a
   **reachable-but-stale** ref makes the dispatcher build fine and measure the
   **wrong binary**. **Four occurrences**, one caused by the orchestrator
   folding a prediction *ahead of its own code*.

Mitigation in force: every ref a live prediction names is tagged `arm/*` and
pushed; worktrees holding bound prediction copies are `git worktree lock`-ed.
**The queue-time ancestry gate AGENTS.md specifies does not exist yet.**

### A poison test that can void a whole arm

`Texture render target::RenderTextureLoop` leaves the texture stage disabled,
so the 40 `TexFmt_*` tests after it render **flat black** — 3,209,634 px
against 324,349. `queue_full_sweep.sh` skips it automatically. **A hand-built
`--suites` request does not, and nothing warns**; the hazard is documented in a
`request.sh` comment only. One lane avoided a catastrophic-looking false
regression by reading that header before queueing.

## 5. How code is folded

**Folding = cherry-picking a lane's commits onto the campaign branch**
(`claude/es-de-launcher-disc-error-ojnl14`) and fast-forwarding the shared
tree. It never pushes to a lane's own branch.

Since 2026-09-18 it is `lane.fold`'s, and the procedure is:

```
cd /home/justin/hakux-work/fold                  # a detached scratch worktree
git fetch -q origin && git reset -q --hard origin/<campaign-branch>
# cherry-pick -x, regenerate the index, run preflight, commit
git push origin HEAD:<campaign-branch>
git fetch -q origin \
  && git merge --ff-only origin/<campaign-branch>
```

The shared tree is therefore **never dirty** — its working copy changes once,
in a sub-second fast-forward. That property is the whole point: the previous
in-place method stalled every uncached build twice in one hour.

**Rules `lane.fold` enforces:**

- **It authors nothing.** A conflict in a file it does not hold goes **back to
  the authoring lane**. Two commits were returned this way rather than merged.
- **A generated file is regenerated, never hand-merged.** `nv2a_index.json`
  records source line numbers; a hand-merge is the stale-index failure the gate
  exists to catch. Regenerate with **both** `--tests` and `--support` — without
  them the suite half is silently dropped (2,306 lines, done once).
- **It does not edit the board.** It reports what an entry should say.
- **Folding a subset of a stack drags derived line numbers with it.** A partial
  fold of a two-commit stack left `nv2a_index.json` recording `vk/surface.c`
  **59 lines high**; the index gate caught five MOVED sites. A third commit was
  required to regenerate.

## 6. How code is audited

**Two passes, and preflight is not an audit.**

1. **Pass 1** reads a diff *before* it folds and writes
   `docs/audits/<date>-<lane>-pass1.{md,json}`. Severities: **HIGH** =
   incorrect behaviour, unsafety, a crash path, or wrong outside what the
   goldens exercise; **MEDIUM** = a real defect with bounded blast radius, or a
   risk behind a currently-unreachable condition; **LOW** = quality. *A finding
   with no failure scenario is an opinion and is downgraded.*
2. **HIGHs and MEDIUMs are remediated before the fold. LOWs need a fix or a
   logged decision** — "reviewed, not fixed" is acceptable; silence is not.
3. **Pass 2 verifies the pass-1 scenarios can no longer occur** — *not* that
   the commits exist. It has caught a remediation whose `assert` was **implied
   by the condition it sat under**, so it could never fire.

**Why the protocol exists, in one sentence:** a 53-commit fold and a guest-CPU
fix both went in unaudited, and the audit that followed found a **HIGH** that
was reachable from the DMA thread by the very workload the fix existed for.

**What the loop has actually caught** (21 audit records on disk):

- `#82` — x87 `FSCALE` returning `±0` where it must return `±inf`, in an
  otherwise-correct fix, **invisible on the path the fix was aimed at** and
  unreachable by anything on the test disc.
- `#59` — a synthetic pipeline-key field placed on **bits 16..17**, colliding
  with `NV_PGRAPH_BLEND_LOGICOP_ENABLE`. Root cause: a `grep | head -30` that
  truncated before the colliding define, and **the wrong conclusion was written
  into a comment as justification**, which is why it survived its author's own
  review.
- `#84` — a narrow-format guard placed in the **leaf** rather than the entry,
  so it returned *after* the caller had cleared `download_pending` and set
  `upload_pending`. The author had cited a precedent and **copied its idiom
  while leaving its placement behind.**

**Audits are the only evidence for a large class of defect.** All 20
`BLENDAND` goldens are 32bpp, so `#84`'s narrow-format bug **could never be
surfaced by an arm on any fleet**. Likewise `#59`'s HIGHs live on the static
pipeline path, which `OPT_DYNAMIC_BLEND 1` leaves **dead on Adreno** — so an
arm here confirms the accuracy claim and *cannot* confirm the remediation.

## 7. Gates

`docs/testing/preflight.sh` runs before every push. Seven gates:

| gate | what it refuses |
|---|---|
| `psh_differ build` / `report` | shader translator regressions |
| `aci_vmstate` | save/load dropping device state |
| `nv2a index` | stale source line numbers in `nv2a_index.json` |
| `territory` | a non-monotone wave, or a claim collision |
| `coverage` | an open issue with neither a lane nor a blocker; a status that disagrees with GitHub; `fixed-unlanded` without `fixed_by`; a blocker naming a retired lane |
| `board files` | malformed TOML |
| `commit subject` | a missing or near-miss `[skip ci]` (catches `[skip ki]`, which landed four times) |

`docs/testing/fleet.py` is the dispatch view. It exits non-zero on
**actionable-by-the-orchestrator** states: reported-not-folded, waiting-on-the-
orchestrator, dispatchable-not-dispatched, lane-claimed-with-no-agent,
running-with-no-territory-row, blocker-never-tested.

**Known gate weaknesses, all live:**

- `check_cited_commits.py` **fails at HEAD on nine entries and `preflight`
  does not run it** — the gate built for cited-sha drift gates nothing.
- `fleet.py`'s dispatchable bucket cannot distinguish *unallocated* from
  *ordered* or *deliberately deferred*; all three render identically.
- `waiting_on` is one string serving two questions (*what* is this waiting on
  vs *who* must act), so lanes waiting on a dispatched audit appear as waiting
  on the orchestrator.
- `check_coverage.py`'s `commits_behind()` resolves the campaign tip from the
  **local** ref, so an unpushed commit in the shared tree tells every worktree
  it is behind and invites it to blame its own checkout.
- `ab_compare` annotates a violated leg with any open harness issue owning the
  **suite**, which once excused a real 139,303-px regression by naming an issue
  about a *different capture*.

### The Stop hook, and why it has never fired

`.claude/settings.json` wires three Stop hooks: `stop-emulator.sh`,
`goal.sh check`, and `backlog-gate.sh`. The gate refuses to end a turn while
work is actionable, **fails open** on any inability to establish state, and has
a **release valve** (6 blocks / 30 min).

Reworked 2026-09-18 to gate on `fleet.py`'s FAIL lines instead of the raw
open-issue count — because 31 issues are open and most are floors, capability
gaps or upstream questions that no amount of turn-taking moves, so the old
signal either always blocked or trained everyone to ignore the valve.

**It has fired zero times in the session that most needed it.**
`settings.json` is read at **session start**; it was last edited
2026-09-12 21:46:58, and the gate's invocation log stops at 21:43:40 the same
day — three minutes earlier — while the orchestrator session claiming the role
dates to 16:08 that morning. **A hook reworked mid-session cannot take effect
in that session.** For six days the discipline it encodes has been manual, and
manual is exactly what has been failing.

Two bugs were found *while* reworking it, both of which made it fail open on
the condition it exists to catch: it read `fleet.py`'s stdout when the FAILs go
to **stderr**, and a `|| fleet_out=""` clause fired on `fleet.py`'s
**by-design non-zero exit**, blanking the output it had just captured.

## 8. Scheduled work (systemd **user** timers, not cron)

All three use `Persistent=true` because the host is WSL2 and is shut down
whenever the user closes it — a plain timer silently misses every window the
box was down, and **an unrun window looks exactly like a window with nothing to
do.**

| unit | when | what |
|---|---|---|
| `hakux-nightly.timer` | `00:30` daily | `nightly_build.sh` — build and publish a **prerelease** |
| `hakux-dx.timer` | `09:23` daily | `dx_pass.sh` — harvest paper cuts, mark one due |
| `hakux-comments.timer` | hourly at `:17` | `comment_sweep.sh` — report unabsorbed issue comments |

`hakux-comments` was created **2026-09-18** after the week-long gap. The lesson
it encodes is not "read comments": a *standing lane* had already been created
for that job, **run once, and never scheduled** — so the process reverted to
the orchestrator not doing it. A habit that depends on remembering ends at the
next context boundary; that is why this is a timer and a file on disk.

**The nightly deliberately runs no tests.** A build needs no device, so it
never contends with the queue; running belongs to the dispatcher. It reports
either way, because a silent failure is worse than no nightly — a missing
release looks like a day with no work.

## 9. What triggers a release build

**Nothing automatic, and CI is treated as an exceptionally finite resource.**
The owner's standing instruction: *"CI is for full build releases only and is
to be run on demand. Otherwise, never run it."*

- **Every `push:` trigger in `.github/workflows/` is `branches: [master]`.**
  The campaign branch is not master and has **no PR**, so day-to-day pushes
  cost nothing.
- **All four release workflows are `workflow_dispatch:`** —
  `release-on-tag.yml`, `release-on-dispatch.yml`, `prerelease.yml`, and
  `release.yml` (`workflow_call`). **Manual only.** Nothing in this harness
  triggers one.
- `release-published.yml` fires on `release: [published]` — a consequence of
  publishing, not a trigger for building.
- The **nightly** publishes a prerelease via `gh release create --prerelease`
  from a locally-built artifact. It does **not** invoke a workflow.
- `[skip ci]` goes in **every** commit subject as belt-and-braces.

**Where CI has been burned:** six runs, on a lane branch that has PR #45 open,
from four commits whose subjects lacked `[skip ci]`. The orchestrator then
compounded it by treating those four commits as a **fold blocker for hours** —
wrong, since a fold never pushes to that branch. **PR #45 must stay a draft and
unmerged.**

## 10. Working against a device — the rules that bite

- **Never `pm uninstall` the release package.** It deletes
  `/sdcard/Android/data/com.jreinach.hakux/`, including a 1.18 GB user
  `hdd.img`.
- **`adb shell input keyevent` terminates the emulator.** Do not inject input.
- **Force-stop after every run:**
  `adb -s <serial> shell am force-stop com.jreinach.hakux.debug`.
- **Core-QEMU `fprintf(stderr)` never reaches logcat** — use
  `__android_log_print` inside `#ifdef __ANDROID__`. This is why counters need
  a logcat tag at all, and why `#81`'s measurement was void until
  `hakuX-tier1:D` reached the **running** dispatcher's `LOGCAT_SPEC`.
- **The Android build is long-running.** `run_in_background` plus a wait loop
  on `GRADLE_EXIT=`; `JAVA_HOME=/home/justin/toolchains/jdk21`. A detached
  build also needs `/home/justin/Android/Sdk/cmake/<ver>/bin` on `PATH` and
  `android/local.properties` present, or meson fails with *"Could not detect
  Ninja"* — **environmental, not a code defect**, and easy to misreport as one.
- **The desktop build does not work on this host** —
  `libcurl4-openssl-dev` is absent. Five lanes have named it. It matters
  because the **Khronos validation layer is desktop-only**, and that layer
  found eight defects in one afternoon. A second finding: the layer is **not
  installed at all**, so `validation_layers = true` would silently load
  nothing.

## 11. The recurring failure modes, for the auditor's convenience

Every one of these is documented in `AGENTS.md` with the measurement behind it,
and every one has recurred *after* being documented:

1. **A total hides a regression.** `#88`'s arm improved the disc by 12,018 px
   while regressing one capture by 139,303. A pixel-count total would have
   folded it.
2. **A zero is mistaken for evidence.** Establish what the instrument *cannot*
   see before an absence changes a decision.
3. **A stale baseline re-derives beautifully.** *"I recomputed it myself"* is
   true of the arithmetic and false of the premise. Date the evidence.
4. **Ancestry answers a question about shas.** This repo rebases constantly, so
   a cited sha being absent is the **normal** state for work that shipped.
   Compare patch-ids.
5. **A tautological falsifier.** `#60`'s entry named a `+104/−0` pure addition
   as its "real falsifier"; it was run, and 0 of 44 captures moved.
6. **Test-disc ratios are not the workload's.** 3.6% draw-carrying on one disc
   against 94.2% on a title. Mixed into one ratio three times in a day.
7. **The answer is usually already on disk.** **Eight times** in one session,
   including a counter that had been running unread for a day and a tier-1 log
   tag whose zeros were an absence of looking.
8. **Routing on paper is not routing**, and *told-to-ask* is not a handoff.

## 12. What an auditor should probably look at first

Offered as the orchestrator's own view of where this harness is weakest, not as
a limit on scope:

1. **The orchestrator is a single serialisation point** for dispatch, board
   edits and fold decisions, and its failures today were **latency, not
   judgement**. `lane.fold` and `lane.triage` are hours old and untested at
   scale. A board lane — owning the two TOMLs and taking structured requests —
   is the obvious next split and has not been built.
2. **Gates that do not gate.** `check_cited_commits.py` is not wired into
   `preflight`; the queue-time `b_ref` ancestry gate is specified in
   `AGENTS.md` and does not exist; the Stop hook has never fired.
3. **State that lives in one place.** Two near-losses in one day: a 126-check
   PASS whose only copy was a scratchpad path, and a 705-line audit report
   existing only as an unpushed commit in one working tree.
4. **`AGENTS.md` is ~2,500 lines and growing** with one section per failure.
   Whether an agent reliably reads and applies it is unmeasured, and several
   failures above are re-occurrences of rules already written down.
5. **Standing lanes with no schedule revert to nothing.** One did, within
   hours. Only three timers are wired.
