# lane.restoreleak1009 -- device_build.py queues an unbounded pile of duplicate master-restore requests (#433)

## Attempt 1, why it did not finish

Started 2026-10-09 18:16:04 PDT, stopped externally about a minute later
(18:17:04) and never resumed -- a stranded lane found during a routine
hostops jam-duty sweep of the inbox, not a failure of the approach. The
worktree already held most of the fix when attempt 2 picked it up: a
`restore_pending()` helper in `docs/testing/jobs/device_build.py` checking
`queue/` and `running/` for an existing `dispatch.restore` request on the
same device, wired into `cmd_restore` before it writes a new one, plus an
updated module docstring. It compiled clean (`py_compile`) but had not been
verified against the dispatcher's actual request shape, had no selftest
leg, and nothing was committed.

## Attempt 2 (this one)

### Verified `restore_pending()` before building on it

Checked the two fields it matches, `requester` and `device`, against:

- `restore_request()` (device_build.py:107-121), which is the only writer
  of a `dispatch.restore` request and is what lands in `queue/` -- it sets
  both fields exactly (`"requester": RESTORE_REQUESTER`, `"device": label`).
  Confirmed by running it directly: see the printed dict in this session's
  transcript, field values match.
- `dispatcher.sh:1333`, `mv "$req" "$D/running/$id.req"` -- a plain rename,
  no rewrite, so a request claimed into `running/` carries the identical
  JSON and the same two fields. So checking both `queue/*.req` and
  `running/*.req` with the same field names, as the existing diff does, is
  correct; there is no second shape to account for.

No changes needed to the helper itself. It was correct as attempt 1 left it.

### The `dispatcher.sh` ASCII-priority question (brief's second bullet)

**Decision: left as a documented follow-up, not touched.** Did not request
an OUTBOX grant for `dispatcher.sh` this attempt. Reasoning:

- The brief's own framing is right: giving `dispatch.restore` a `0-*`
  prefix would stop the backlog from growing past 1 even under a `1-`
  prefixed chain that starves it indefinitely, because a 60 s restore is
  cheap and bounded, and once this lane's dedup fix lands there is only
  ever one such request in flight to jump the queue with -- it cannot
  compound into the kind of unbounded head-of-line blocking that `0-*`
  exists to avoid elsewhere.
- But the dedup fix in this PR already resolves the brief's actual defect
  as titled: "queues an unbounded pile of duplicate ... requests." After
  this fix, the backlog is bounded at exactly 1 per device regardless of
  how long a `1-`-prefixed chain runs. What starvation still costs is
  *latency* to a clean build, not *growth* of the queue -- a different,
  smaller problem (the device sits on a stale/test build longer than it
  would with `0-*`, but every real run already sets its own ref and env
  explicitly at soak start, so a starved restore still does not corrupt a
  later measurement; see the brief's own "not a correctness bug today").
- Touching `dispatcher.sh`'s priority convention is also a behavior change
  to a convention two other docs (hostops-poll.md, dispatcher.sh's own
  comment) describe, and it is outside this lane's pre-granted territory
  (`docs/testing/jobs/device_build.py`, `docs/testing/jobs/selftest.d/
  99-build-gate.sh`, `docs/lanes/restoreleak1009/**`). Given the dedup fix
  already converts "unbounded growth" into "bounded at 1, served whenever
  the chain next yields," the cost of requesting and waiting on a grant for
  a separate, smaller latency improvement did not seem to pay for itself in
  this attempt. Left as a follow-up for whoever next finds restore latency
  (not restore *count*) to be the active complaint.

### Selftest

Extended `docs/testing/jobs/selftest.d/99-build-gate.sh` (did not add a new
file -- the brief said not to unless the existing one did not fit, and it
fits: it already has `dbrun`/`dbcheck` fixtures and a restore leg (f) to
build the new leg next to). Added:

- Leg (l): two non-master runs for the same nova label, `restore` called
  back to back. First call queues a restore and prints its id; second call
  prints nothing and queues nothing; exactly one `dispatch.restore-*.req`
  survives in `queue/` afterward. This is the brief's required leg.
- A mutant for (l): `device_build.py` with the `if restore_pending(...)`
  line's condition forced to `if False:`, confirming the leg goes red
  without the fix (two requests survive instead of one) -- leg (l) is not
  vacuous.

Ran the full selftest (`docs/testing/jobs/selftest.sh`); see PR.md for the
result this attempt recorded.

## Which half(s) landed

- **Dedup (cmd_restore / restore_pending)**: done, verified, tested.
- **ASCII-priority starvation (dispatcher.sh)**: not touched; documented
  above as a deliberate follow-up, not an oversight.
