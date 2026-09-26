# lane.relprio432 -- release requests queue ahead of other requests (#432 item 2)

Spec: `dispatch/board-requests/pri432.md` (lane.pri432's design, accepted by
hostops 2026-09-26 15:47 PDT).

## What changed

| file | change |
|---|---|
| `docs/testing/request.sh` | `ID="${HAKUX_RELEASE_PRIO:+1-}$(date +%s)-$WHO-$$"`, with a comment saying why it sorts where it does |
| `docs/testing/ab_run.sh` | reads the labels of `--issue` (else the `--expect` file's `issue` field) once; `0.5` on any listed issue sets `HAKUX_RELEASE_PRIO=1` for both arms. `--dry-run` shows it as a `HAKUX_RELEASE_PRIO=1` prefix on the printed request.sh lines |
| `docs/testing/jobs/arms.sh` | `release_prio()`: the same read per prediction, passed to both request.sh calls. The tick log's `queue` line ends `release-prio` when set |
| `docs/testing/jobs/selftest.d/97-release-prio.sh` | naming, glob order, and arms.sh's three label outcomes |

Rules shared by both callers:
- The label is `${HAKUX_RELEASE_LABEL:-0.5}`, matched exactly (`grep -qxF`),
  so `blocked:after-0.5` and `0.5-candidate` do not count.
- The issue field can be `88,91` or `#88`. It is split on `,` and `#`, and
  the arm is prioritised if any number in it is labelled. Anything that is not
  a number (one prediction has `Nd-lines`) is skipped.
- If gh fails, the failure is logged (arms: tick log; ab_run: stderr) and the
  arms are queued at normal priority. A failed read never refuses an arm.
- A `HAKUX_RELEASE_PRIO` already in the environment is kept, so the host can
  still promote a caller by hand.

The dispatcher processes run under `LANG=C.UTF-8` (read from
`/proc/<pid>/environ` on 2026-09-26). The host has only the C, C.utf8 and POSIX
locales installed, so glob order is byte order.

## Proof

**Selftest fragment, real code** (`bash docs/lanes/relprio432/prove.sh`, which
runs selftest.sh with its fragment list narrowed to 97):

```
  ok   request.sh without HAKUX_RELEASE_PRIO names <epoch>-relprio-<pid>
  ok   request.sh with HAKUX_RELEASE_PRIO=1 names 1-<epoch>-relprio-<pid>
  ok   glob order under LC_ALL=C: 0-0-x-9 0-probe 1-1759000500-b 1-1790463648-relprio-1244007 1759000000-a 1790463647-relprio-1243753 z-sweep-x
  ok   glob order under LC_ALL=C.UTF-8: 0-0-x-9 0-probe 1-1759000500-b 1-1790463648-relprio-1244007 1759000000-a 1790463647-relprio-1243753 z-sweep-x
  ok   arms.sh, issue read 'label': 1-1790463704-arms-relprio-base-1263202 1-1790463704-arms-relprio-fix-1263377
  ok   arms.sh, issue read 'nolabel': 1790463742-arms-relprio-base-1281314 1790463742-arms-relprio-fix-1281389
  ok   arms.sh, issue read 'fail': 1790463785-arms-relprio-base-1292058 1790463785-arms-relprio-fix-1292101
  ok   arms.sh read the issue's labels once per prediction (3 ticks, 3 reads of #7)
  ok   a failed label read is said in the tick log
selftest: 9 passed, 0 failed
```

The priority request was written one second AFTER the plain one, and it is
still served first.

**Selftest fragment, prefix removed** (request.sh's ID line reverted to
`ID="$(date +%s)-$WHO-$$"`, everything else unchanged):

```
  ok   request.sh without HAKUX_RELEASE_PRIO names <epoch>-relprio-<pid>
  FAIL request.sh with HAKUX_RELEASE_PRIO=1 names 1-<epoch>-relprio-<pid>
  FAIL glob order under LC_ALL=C: 0-0-x-9 0-probe 1-1759000500-b 1759000000-a 1790464617-relprio-1780783 1790464618-relprio-1782341 z-sweep-x
  FAIL glob order under LC_ALL=C.UTF-8: (same)
  FAIL arms.sh, issue read 'label': 1790464659-arms-relprio-base-1835623 1790464659-arms-relprio-fix-1835906
  ok   arms.sh, issue read 'nolabel': ...
  ok   arms.sh, issue read 'fail': ...
  ok   arms.sh read the issue's labels once per prediction (3 ticks, 3 reads of #7)
  ok   a failed label read is said in the tick log
selftest: 5 passed, 4 failed
```

With the prefix removed, the release request sorts last among the plain
requests (arrival order), and arms.sh's labelled arms lose the `1-`. The file
was restored with `git checkout` afterwards.

**Full jobs selftest** on this host: 1871 passed, 1 failed. The failure is
`64-status-html.sh:117` "the republished page carries the change". It fails
the same way when that fragment runs alone (twice). It is unrelated to this
change: on this host the fixture's page renders the real host's state ("Last
fold 16:05 PDT (11m ago) PR #438", "Queue 0 queued"), so the fixture's queued
request never appears. None of this lane's files are involved. CI runs on a
clean runner and is the gate of record.

**request.sh dry run** (`bash docs/lanes/relprio432/dryrun.sh`). Both requests
go into a scratch `DISPATCH_DIR` that no dispatcher serves, and the scratch dir
is deleted afterwards:

```
--- HAKUX_RELEASE_PRIO=''
queued 1790462491-relprio-dry-865329
--- HAKUX_RELEASE_PRIO='1'
queued 1-1790462492-relprio-dry-865424
--- scratch queue in the dispatcher's glob order (LC_ALL=C)
1-1790462492-relprio-dry-865424.req
1790462491-relprio-dry-865329.req
```

request.sh has no dry-run mode of its own. Pointing `DISPATCH_DIR` at a
scratch directory gives the real naming path and cannot reach a device.

**ab_run.sh --dry-run** (`bash docs/lanes/relprio432/abrun_dry.sh 433 188 5f89032611`):

```
=== #433 labels: 0.5
  priority release (HAKUX_RELEASE_PRIO=1: ids sort 1-<epoch>, ahead of plain requests)
HAKUX_RELEASE_PRIO=1 request.sh --who relprio-dry-base --ref c3e13f09a2 --suites 'Blend surface' --runs 1 \
HAKUX_RELEASE_PRIO=1 request.sh --who relprio-dry-fix  --ref 5f89032611 --suites 'Blend surface' --runs 1 \
=== #188 labels: xbox-hardware blocked:after-0.5
request.sh --who relprio-dry-base --ref c3e13f09a2 --suites 'Blend surface' --runs 1 \
request.sh --who relprio-dry-fix  --ref 5f89032611 --suites 'Blend surface' --runs 1 \
```

## Every code that reads a request id: does a `1-` prefix break it?

Each row was evaluated on `1-1790462491-lane-foo-12345`. No code in either tree
takes an epoch out of an id. Every age comes from the file's mtime or from the
request's `queued_utc`.

### Repo (docs/testing)

| file:line | what it does with the id | `1-` |
|---|---|---|
| `titles/table.py:48` | breaks a tie on `judged_utc` by comparing `request_id` strings ("starts with the queue time") | **breaks the tie-break only**: `'1-1790…' < '1790…'`, so a newer `1-` soak verdict loses to an older plain one, but only when `judged_utc` is equal or empty. Soaks are queued by `request.sh --title`, which no caller runs with the variable set. Not in this lane's files. If it matters, the fix is to strip a leading `1-` in the key |
| `jobs/handback.sh:235,249` | `re.search(r"(?:^|-)\d{9,}-(.+)-\d+$")` recovers who, only when `requester` is empty | fine: the match starts at `-1790…`, so who = `lane-foo` |
| `jobs/handback.sh:299` | sorts a lane's runs by id | fine (only affects display order) |
| `fleet.py:277,390` | rebuilds the workers' glob order to spot a skipped request | fine: same byte order |
| `jobs/status.sh:122,448`, `jobs/arms.sh` waiting count, `jobs/board-status.sh:57`, `backlog-gate.sh:223`, `idle-watchdog.sh:209,308` | treat `z-*` as a separate tier; everything else is ordinary work | fine: `1-` counts as ordinary work, which is correct |
| `jobs/arms.sh`, `ab_run.sh:267`, `ab_bisect.sh:153` | `${q##* }` takes the id from `queued <id>` | fine |
| `collect_sweep.sh:58`, `queue_full_sweep.sh:211` | sweep ids `0-<label>-NNN-*` / `z-…`, written directly rather than through request.sh | not affected |
| `dispatcher.sh:1587`, `desktop_channel.sh` | serve `queue/*.req` in glob order | this is the mechanism the change relies on. The comment at `dispatcher.sh:1544` still lists only `0-*` and `z-*`; that is the dispatcher owner's comment to update |

Selftest fixtures already named `1-lost` (51), `1-unpinned` (56) and
`1-selftest-dash` (64) are harmless, because no code classifies `1-`.

### Host tools (read-only here; any fix belongs to the host)

| file:line | what it does | `1-` |
|---|---|---|
| `attention.sh:39-42` | "STUCK" age from `stat -c %Y` (mtime) | fine |
| `park_requests.sh:34-40` | keeps a requester's first N in `sort` order (filters on JSON `requester`) | fine: a `1-` sorts first, and it is the one that should be served first |
| `dispatch_jamcheck.sh:95,156-165` | age from `queued_utc`, falling back to mtime; the id is only printed | fine |
| `harness_health.py:79,501` | lane name as a substring of the id | fine |
| `harness_health.py:289-296` | skips `z-`; age from mtime | fine |
| `harness_health.py:528` | `re.match(r'z-([0-9a-f]{7,12})[-.]')` for sweeps | fine (not a sweep) |
| `remote_results.py:49` | `rid.split("0-0-x-",1)[-1]`, then looks for the id in delivery comments | fine, `0-0-x-1-…` strips to `1-…`. It would misfire only if a delivery quoted the id without its `1-` |

No host-tools file needs a change. Hostops item 00(c) (promoting 0.5 requests
by hand) can retire once this folds and the dispatcher snapshot carries the new
request.sh. The callers run request.sh from the tree (ab_run: `$HERE`; arms: the
trunk worktree `board.sh` re-execs from), not from the dispatcher snapshot, so
the fold is enough.

## For the next lane

- A second release changes the label once in each of two places
  (`HAKUX_RELEASE_LABEL` default in arms.sh and ab_run.sh), or it can be set in
  `limits.env` for arms.
- A request the host renames to `0-0-x-<id>` is not found by `arms.sh` under
  its queued name (`results/$ida`). This is not new with `1-`.
- The Bash tool here rejects `$VAR` expansions in inline commands. The dry
  runs are files in this directory for that reason.
