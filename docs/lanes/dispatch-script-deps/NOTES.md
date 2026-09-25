# dispatch-script-deps (PR #206) -- remediation of audit pass 1

Audit: `docs/audits/2026-09-24-claude/dispatch-script-deps-pass1.md`
(1 HIGH, 2 MEDIUM, 5 LOW). Remediated 2026-09-24 on this branch, after
merging master in (merge, not rebase, so the audited shas stay).

## H1 -- what "passed over" means, and why neither earlier rule has it

The shipped rule was "older than 120 min, and some result landed after it
was queued". The audit is right: under ASCII-order service that is true of
every request not at the head. Its proposed fix -- "a request queued after
me COMPLETED" -- has the same hole one level down, and the audit's own
failure scenario shows it: affinity rule 2 pins an A/B pair to one handheld,
so the other handheld correctly serves later work while the pair waits for
its own device. The owner's lead (an order violation, read from
running/*.owner) has the same hole if any single claimer's violation counts.

**The rule now in `fleet.py:queue_stall()`**: a queued request R is stalled
only when EVERY live claimer has walked past it, where walked past means
either

- it is running X with X sorting after R and claimed after R was queued
  (X written after R, or claimed more than a settle period after R), or
- it has been idle, with nothing claimed or finished anywhere, for longer
  than a settle period (120 s, several worker ticks) since R was written.

Evidence older than the last change to what decides R's pin -- `lanes/`,
`hold/`, a lane file's pid, or (rule 2) a claim or result of a request
naming the same prediction -- does not count. Liveness is
`affinity.serving()` (kill -0), not a second copy of it. The desktop lane is
a claimer like any other: it walks the same queue by the same protocol, so
its own idleness is the evidence that it will not take a handheld request,
and nothing here needs to know OFFPOOL's claim rule. A request only a held
device can take is reported on stdout as waiting on the hold.

**z-* is no longer exempt**, because it no longer needs to be. It waits
behind agent work because it sorts after it, so a claimer busy with agent
work is not evidence against it; a free sweep request that idle claimers do
not take is a real stall. selftest.d/98 pins both halves.

## Measured on the real queue, not only on fixtures

`replay_queue_stall.py` rebuilds the dispatch directory from what the real
one records -- claim time is the result directory's birth time (checked
against the log's claim line: same second), finish is DONE/ERROR/result.json
(not the directory mtime, which a re-score bumps) -- and asks the real
`queue_stall()` every 5 minutes from 09-12 11:03 to 09-24 22:40: 3,597
moments, 1,923 with a non-empty queue.

| rule | FAIL episodes | false episodes | first sees 09-20 |
|---|---:|---:|---|
| this one | 6, all 09-20 | 0 | **02:03** (queued 01:45) |
| as shipped in #206 | 3 | 2 | 03:48 |
| audit pass 1's remedy | 1 | 0 | 03:48 |

The shipped rule's two false episodes:

- **09-14 07:43 -> 09-18 11:28, four days.** Six Crimson soaks pinned
  (`device: thor`) sat behind `1789389229-lane.blit38-4028618`, which the
  thor claimed 09-14 06:29 and finished 09-18 09:23 -- a HUNG RUN, stopped
  between run 2 and run 3 and eventually marked ABORTED. The soaks were
  waiting their turn; the right diagnosis was the hang, and the old FAIL
  text ("check the pin") pointed away from it. The new rule reports those
  soaks as waiting on the thor's hold for 09-18 09:23-11:08 and is otherwise
  quiet. Hung runs are a different detector's job: see below.
- **09-19 08:38 -> 09:08.** Two pairs (glerr86, clrsurf91) waiting 2-3 h
  behind other work and claimed in order. H1 exactly.

The audit's remedy had no false episode on this history; its failure case
is constructed (98's H1 fixture), not observed. What it cannot do is see the
incident before its age threshold.

The replay's blind spots, which is why each episode above was read against
`dispatcher.log`: withdrawn requests; time the host was off; a device absent
while its worker churned. Owners it cannot recover (149 old results) become a
label no claimer has, and the desktop lane is left out; both can only add
stalls, so they bias the false-positive count up, not down.

## Each check was seen to fail

`SELFTEST_FLEET_SRC=<dir>` points 98 at another fleet.py/affinity.py pair.
Eleven mutants of `fleet.py`, one per invariant, each turn exactly their own
checks red and nothing else. Re-run them with `python3 mutate98.py` from this
directory (it drives 98 through `runfrag.sh`, which sources one fragment with
selftest.sh's helpers):

| mutant | red |
|---|---|
| drop `x > name` (order) | H1 fixture; z-* behind agent work |
| drop `claimed > changed` (staleness) | lane-set change; sibling claim |
| `changed = epoch` (no sibling term) | sibling claim |
| drop `lane not in between` | owner file, request gone |
| `quiet_since` without `last` | just finished, not walked yet |
| drop the age gate | just queued (the pinned-to-no-one half) |
| lane files without kill -0 | dead lane's orphan |
| pooled without kill -0 | dead lane file, held branch |
| no all-handhelds-held branch | both held fixtures + both stdout/FAIL checks |
| no explicit-pin-held branch | explicit pin to a held device |
| no `queue_stall()` call in main | board pipeline FAIL; rc; stdout hold line |

First version of the "just queued" fixture was inert against the age-gate
mutant: an idle claimer's evidence already starts at the request's write
time. It now also carries a request pinned to a label nobody serves, which
is the one path where the gate decides.

## M1, M2, and the LOWs

- **M1** -- fixed as above (kill -0 via affinity.serving; held branch by
  holds, not by comparing every file in lanes/). Note a second reason the old
  quiet branch was unreachable: a held worker RELEASES its lane file
  (`lane_release` in the hold path), so with every handheld held, lanes/
  held only desktop and could never be a subset of hold/.
- **M2** -- `sweep_queue.sh` and `make_isolation_discs.py` (which
  sweep_queue.sh runs) are now in both lists, and 97 asserts the snapshot is
  CLOSED under what its scripts run, in all four forms used in this tree
  ($HERE/x, `$(cd ... && pwd)/x`, `os.path.join(HERE, "x")`, a Python
  import). 97 carries its own mutant per form. Seen to fail against the
  pre-M2 dispatcher.sh through a symlink tree.
- **L1** -- the wrong claim about result-directory names went with the code.
- **L2** -- the call now sits after the `if unclaimed:` block its comment
  documents.
- **L3** -- no line numbers in the FAIL text; it names the evidence and the
  snapshot diff instead.
- **L4** -- 98 runs board.sh's exact `fleet.py 2>&1 >/dev/null | grep
  '^FAIL'` against a scratch board; the `nocall` mutant turns it red.
- **L5** -- lane header block added to the PR body.

## Found on the way, NOT fixed here, and routed

1. **The legacy sweep preemption path fails even with M2 fixed.**
   `sweep_queue.sh` requires `BASE_ISO`, `GOLDENS`, `RESULTS` and
   `BASELINE_APK` at top level with `${VAR:?}`, before its `pause` case;
   `preempt_sweep` passes only `SWEEP_STATE`, and the workers' environment
   has none of them. It also passes no `SERIAL`, so `pause` would
   force-stop the app on the first adb device, and it is called from either
   worker although only `SWEEP_DEVICE` resumes the sweep. Dormant: the
   runner's pid has been dead since 09-12 and "preempting the sweep" has
   never appeared in dispatcher.log. Fix or delete; either is a harness lane.
2. **Unbounded adb calls in the serve path.** `adb install -r`, the run-as
   pref reads/writes and `am force-stop` in dispatcher.sh have no `timeout`.
   The 09-14 run hung for four days; run_disc.sh's per-call deadline
   (since 09-10) did not cover it. lane-local's host-only
   `dispatch_jamcheck.sh` detects HUNG and can restart; the unbounded calls
   remain.

## Do not repeat

- Do not score a queue-stall rule on fixtures alone. The replay is cheap
  (30 s) and it is where the four-day false episode showed up.
- Do not read a stall off one claimer's order violation: pins make the
  OTHER handheld legitimately serve later work.
- The desktop lane needs no special case; its behaviour is its evidence.
