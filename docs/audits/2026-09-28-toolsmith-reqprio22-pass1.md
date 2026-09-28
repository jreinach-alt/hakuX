# Audit pass 1: PR #577, lane/toolsmith-reqprio22

`request.sh --priority blocker|arm|study|sweep` (defect 22, the request.sh half).
Head audited: `a3c3fdec9b`. Auditor: job.cloud, 2026-09-28.

**Verdict: no HIGH, no MEDIUM, three LOW.** The PR goes to `needs-audit-2`.

## What was checked

- **The diff:** three files. They are `request.sh`, the new fragment
  `selftest.d/99-request-priority-flag.sh`, and the dispatch-hardening NOTES.
- **The fragment, run on the host:**
  `SELFTEST_ONLY="99-request-priority-flag 99-request-release-prio"` gives
  **40 passed, 0 failed**.
  - The order leg read `0-0-x-…-hostops 0-…-rpf-blocker 1-…-rpf-armrel …-rpf-armplain z-sweep-001-Alpha_func`.
  - The mutant queued its blocker as `1-` and put it third. The shared order
    predicate was red on it. So the mutant check is not a pattern that only the
    fixed code can match.
- **Every reader of a queue or result id**, grepped across `docs/testing` and
  `host-tools` for tier prefixes and for parsing the epoch out of an id:
  - The dispatcher's glob, and the comment at `dispatcher.sh:1586`.
  - The `z-*` idle counts in `arms.sh`, `status.sh`, `board-status.sh`,
    `backlog-gate.sh` and `idle-watchdog.sh`.
  - `status_html.py`, which skips `z-*` for ETA and position.
  - `handback.sh:235`'s `(?:^|-)\d{9,}-(.+)-\d+$`.
  - `collect_sweep.sh`'s `0-<label>-NNN-*` / `z-<label>-NNN-*` globs.

  Results:
  - No reader strips only a `1-` prefix.
  - No reader parses the epoch by position.
  - No code deletes or moves `z-*` requests wholesale.
  - Nothing already reads a `priority` field from a request, so the new field
    collides with nothing.
  - A `z-<epoch>-…` id and a `0-<epoch>-…` id are each handled correctly by
    every reader listed above.
- **Edge cases:**
  - `--priority` given with no value exits on `set -u` ("$2: unbound
    variable"). This is the same as every other option.
  - `--issue '#311'` is stripped to `311` in the message.
  - A blocker with a comma list of issues is accepted and printed as the list.
  - `HAKUX_RELEASE_PRIO` from `arms.sh`/`ab_run.sh` still applies to
    `arm`/`study`, and neither caller passes `--priority`.

## Findings

### LOW 1: the blocker tier is self-asserted

`request.sh` lines around 757-764 accept `--priority blocker` when any `#N`
appears in `--purpose`. They do not read the issue, or any label saying the
issue is a blocker. The `0-*` tier's documented contract (`dispatcher.sh:1590`)
is "a 45-second probe that unblocks an agent". A blocker can be any length.

*Scenario:* a lane queues a 2100 s soak with
`--priority blocker --purpose "soak for #474"`. It sorts ahead of every
release arm, and nothing refuses it.

*Why LOW:*
- It needs a lane to choose the flag.
- The choice is recorded in the id and in the `priority` field.
- The host's `0-0-*` heads still sort ahead of it.
- The PR states that this is the design.

A label check (e.g. the issue carries `blocker` or the release label) would
close it.

### LOW 2: dispatcher.sh's tier comment is now stale

`dispatcher.sh:1590-1596` still says that `0-*` means probes and `z-*` means the
corpus sweep's `z-sweep-*`. Lane requests can now land in both tiers. The
comment is documentation only, and dispatcher.sh is held by lane.fanduty507,
which is why this PR does not touch it. It belongs with the `yield` half.

### LOW 3: `--priority ""` is silently `study`

`PRIORITY="${PRIORITY:-study}"` turns an explicit empty value, e.g. from an
unset variable in a caller's script, into the default. It is not refused. The
blast radius is a request queued at the default tier.

## Nothing for pass 2 to re-verify beyond

The three LOWs are not required fixes. Pass 2 needs to confirm two things:
- The head is still `a3c3fdec9b`, or any later push keeps the 40/0 fragment
  result.
- The mutant leg is still red on the mutant.
