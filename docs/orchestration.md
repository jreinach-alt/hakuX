# Running this project with several agents

Written 2026-09-12, after a day in which two lanes independently produced the
same fix twice, five mechanism claims were retracted, the issue tracker drifted
until an audit found six closed issues listed as open and three entries
silently deleted, and the single most valuable finding of the day — that two
suites were being scored on 6.7% and 18% of their available oracle — came from
reading progress logs side by side rather than from any planned work.

The design below is shaped by those specific failures, not by a general theory
of agents.

## The binding constraint is the device, not the agent count

| resource | capacity | consequence |
|---|---|---|
| **Nova (one device)** | serialised | a measurement is 1–10 min with the image pull and scoring, so the *whole system* does roughly 10–30 device measurements an hour however many agents exist |
| **Native build** | one tree | a fresh git worktree **cannot build the native side here** (JDK 21 against a system Java 25 JRE), so implementers cannot each hold a private build |
| **Host CPU** | 8 cores | scoring 1,291 captures takes ~20 min, largely single-threaded; 2–3 concurrent scorers are fine |

So the ceiling is about **two device-bound implementers plus as many
analysis-only agents as there is work**. Adding device-bound agents past that
does not go faster, it queues — and queueing is where "stepping on each other's
toes" actually comes from.

**Split streams by resource class, not by topic.** That is the change that buys
concurrency.

## Roles

### Dispatcher — owns the device, and owns comparability

Agents do not touch the Nova. They submit a request and wait for a result.

The dispatcher exists for three reasons, in order of value:

**1. Batching, which is the real throughput win.** The overnight sweep only
became viable by pulling the 1.5GB disk image once per hundred tests instead of
once per test — the difference between three hours and a day and a half. A
single implementer asking for one suite cannot see that. A dispatcher holding
eight requests coalesces them into one boot and one pull. That is a 5–10×
effect on the binding constraint; nothing else here comes close.

**2. It makes invalid comparisons impossible rather than caught later.** Both
of the day's bad calls were comparability failures, not measurement failures: a
shared-disc number compared against a per-suite number, which caused a working
fix to be reverted. So a request carries, and a result records:

```
request: { ref, disc_id, suites|tests, arm: company|solo, requester, purpose }
result:  { tsv, apk_sha, disc_id, classifier_rev,
           captures_vs_goldens, progress_log_proof, runs }
```

* **`ref`, not "what's in my tree."** The dispatcher builds a named commit and
  records the APK sha. With three implementers holding uncommitted work, "run
  my build" is ambiguous the moment two of them ask — today five APKs were in
  flight and kept straight by hand.
* **`disc_id` — which suites are on the disc.** Two results are comparable only
  if the ref differs and the disc identity matches. The dispatcher refuses any
  other comparison.
* **`classifier_rev`.** The boundary-shift class exists only from `d0114a49`;
  residual splits computed without it are wrong in a way that already corrected
  one cross-lane ranking.
* **`captures_vs_goldens`.** Free to compute, and it is what found the 5.4×
  depth and 15× blend oracle gaps.
* **`progress_log_proof`.** A run counts only if its own log shows the test
  completing. Neither file mtimes nor "the PNG exists" substitute: a truncated
  run leaves the previous image in place and reads as a pass.
* **`runs ≥ 2` for any no-oracle measurement** (audio, timing, performance). A
  single Nova run can be a one-off band.

**3. It holds the lease continuously**, so the Stop hook cannot kill a run
mid-flight — that has destroyed three sessions — and it re-queues rather than
fails on a device drop. A drop once marked every queued test FAILED and emptied
the queue.

**Failure modes to design for:** the dispatcher is a serialisation point and a
single point of failure. It needs a queue file a human can read, a per-request
timeout, and requeue-on-restart. If it dies, every requester blocks.

### Orchestrator — sole writer of the issue log

Today's drift is the argument. Six closed issues were still listed as open,
which pollutes `issues_for_suite` and therefore every `query` and `blast`;
eighteen open ones were absent; and one conflict resolution deleted three
entries while its commit message talked about something else. Nothing but an
audit against the GitHub list found any of it — `nv2a_index.py check`
validates suite *names*, not whether an issue exists.

So: one writer, and the audit becomes a gate that runs before any tracker
commit. It compares every entry against the live issue list for existence,
state and title, and validates every suite name against the derived index.

The orchestrator also holds the claim ledger. Every duplicate today — the
surface-as-texture decode, the line-width analysis, the coverage gap — happened
because we posted *results* rather than *intentions*. Claim before the first
build, not after the measurement.

### Reviewer — a checklist, not judgement

Each item below cost real time today, which is why it is a list and not advice.

1. **Same binary in both arms**, or an improvement has two explanations.
2. **Same disc composition in both arms.** A regression measured on a shared
   disc is not a regression until it reproduces in isolation.
3. **Better/worse per capture, never totals.** Six better and seven worse hid
   behind an exact count that moved by one.
4. **Compare regions, not point samples.** Point samples through structured
   content manufacture whatever agreement you look for; two mechanisms died to
   this in one day.
5. **Date the captures against the commit.** A capture older than the fix reads
   exactly like a live defect.
6. **Prove the code path is live.** A patch to the legacy pipeline path changed
   nothing at all — 0 better, 0 worse, identical to the pixel — because the
   device takes the dynamic path.
7. **Capture count against golden count.** The mismatch is the tell for a
   partially retired suite, and it is free.
8. **Never add or subtract overlapping classes.** One-step and boundary-shift
   overlap; subtracting both gives negative residuals.

### Implementers — by resource class

* **Device-bound** (max ~2 concurrent): the accuracy issues.
* **Host-only** (many): classification, corpus re-ranking, the
  unhandled-method inventory per suite, oracle recovery scoring, code reading.
* **Build-only** (serialised behind the dispatcher): anything needing a binary.

## The three new streams have no oracle, and that changes everything

Audio, timing and performance have **no goldens**. "Verified" cannot mean
better/worse per capture, so each needs a harness before it can have a fix.

| stream | what exists | what is missing |
|---|---|---|
| **Performance** | `FramePacingStats`, the `hakuX-perf` line, the 7.2 ms texture-bind figure, the critical path established as the guest CPU thread | a repeatable scene and a variance band; two runs minimum per claim |
| **Timing** | the VBLANK deferral bootstrap flaw (`enter_thresh = period*1.5`, so a title at exactly two periods can never enter unlock mode), `HAKUX_VBLANK_HZ` | a measurement that separates a pacing change from a rendering change |
| **Audio** | the voice-lock fix landed and was confirmed by ear | **no harness at all.** "It is quiet" is an open report with nothing to measure it against. This stream needs a capture-and-compare path before any fix can be claimed |

Audio is the one to start with precisely because it has no harness: the first
deliverable is the ability to measure, not a fix.

## Nightly builds

A build needs no device, so it does not contend — but a nightly that also
*runs* tests would collide with an overnight sweep. So: build and publish
nightly, and leave running to the dispatcher's queue.

- 00:30 America/Los_Angeles.
- Build the branch HEAD, stamp the version with the date and the short sha.
- Publish as a GitHub pre-release on the fork, with the day's commit subjects
  as the notes.
- Report the outcome either way. A silent failure is worse than none, because
  it looks like a day with no work.
- Signing uses the fork's key from `android/key.properties`, which is
  gitignored and must never be echoed anywhere.
