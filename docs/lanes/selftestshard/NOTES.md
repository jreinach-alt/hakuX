# selftestshard: `jobs selftest` as a CI matrix

## The defect

`jobs selftest` ran all 93 `selftest.d/` fragments in one job with
`timeout-minutes: 25`, and took 18-25 min, so it hit the cap at random. A
capped run concludes CANCELLED, which `fold.sh ci_green()` reads as RED:
4 of the last 20 runs on 2026-09-27 (master f82e7e87fe run 36372679047,
lane/thermal507-default, lane/sweepclock, lane/cloudlaneguard).

## What changed

- `selftest.sh` collects the fragment list before building any fixture and
  takes `SELFTEST_SHARD=k/n`. With no selector it runs every fragment, as
  before; the summary line now says `all N fragments` or `PARTIAL: ...`.
- Every fragment prints `selftest: <frag> took Ns`, so the next rebalance has
  its numbers in any run's log.
- The workflow runs a 4-job matrix (`selftest (0)`..`selftest (3)`), each with
  its own fake host, `timeout-minutes: 25` per shard, `fail-fast: false`.
- `SELFTEST_ONLY="<frag> ..."` runs named fragments alone (a debugging knob,
  and how the dependencies below were measured).

### Why not `i % n`

Fragments share state on purpose (10..64 drive one dispatcher queue in
sequence; 92/94 read what 40/50 left; 99-handback-{runs,strand} copy
99-handback-draft's shims). A modulo split would scatter those and fail, or
worse, pass for the wrong reason. `SHARD_CHAINS` in `selftest.sh` names the
sets that must share a shard; everything else is a unit of one. Units go
longest-first onto the lightest shard, weighted by `SHARD_SECS`.

### The guard

Before a shard runs anything, `shard_check` asks for each of the n shards
exactly as a run does, and fails unless their union is the full sorted
fragment list with each fragment once, no chain is split, and the workflow's
matrix is `[0..n-1]` with the same `/n`. `selftest.sh --check-shards n` runs
only the guard; `--list-shards n` prints the split.

### fold.sh

`ci_green()` maps every entry of `statusCheckRollup` and is GREEN only when
all are SUCCESS/SKIPPED/NEUTRAL; any CANCELLED/FAILURE is RED. Four matrix
checks are four entries, so every shard must be green. No job looks a check up
by the name `selftest`, and master has no branch protection naming it.

## Attempt 1 did not finish (2026-09-27)

It ran every fragment alone (`.lane/iso.sh`, 5 at a time) plus the full run
as a `run_in_background` task, and ended its session waiting for it. The
session exit killed the full run (its log stops mid-fragment); the 93 alone
runs had all finished. The commit was never pushed and no PR was opened.
Attempt 2 used what the alone runs left, pushed, opened #540, and ran the
local checks inside its own session.

## Finding the chains: every fragment alone

Each of the 93 fragments run with `SELFTEST_ONLY=<it>` in a fresh fake host.
Ten fail alone, and every one is a member of a declared chain:
30, 51, 55-localtime, 60, 63, 92, 94-arms-label-state (arms chain, need the
queue 10..50 leave), 87-nightly-trunk (calls a predicate 86-nightly-notes
defines; this chain was added in attempt 2), 99-handback-runs and -strand
(copy 99-handback-draft's shims). Every other fragment passes alone, so no
other placement can break it.

## A defect found on the way

Fragments are sourced in `selftest.sh`'s own shell, and the run loop used
`f` and `t0`. Several fragments set `f`, so the `took Ns` line named the wrong
fragment (11 of 93), and 84-perf-regimen sets `t0` to an epoch, so it printed
`took -1790567307s`. The loop now uses `_st_frag`/`_st_t0`. Iteration itself
was never affected (bash expands the `for` list once).

## Measurements

Alone times on the host (sum 3181 s over 91 fragments; 84 and 92 have none)
are `SHARD_SECS`. The split they give, in host-seconds:

| shard | fragments | weight (host s) |
|---|---|---|
| 0 | 13 (the arms chain, alone) | 1090 |
| 1 | 29 | 707 |
| 2 | 26 | 707 |
| 3 | 25 | 707 |

### CI on #540 (two pushes, runs concurrent)

| job | run 36378023715 @ 1e8b70ec76 | run 36378079077 @ 2dac2e559b |
|---|---|---|
| selftest (0) | SUCCESS 9:40 | SUCCESS 11:59 |
| selftest (1) | SUCCESS 3:32 | SUCCESS 3:58 |
| selftest (2) | SUCCESS 4:47 | SUCCESS 5:05 |
| selftest (3) | SUCCESS 4:27 | SUCCESS 3:56 |

The whole run was 18-25 min before this. The longest shard is under 15 min
but not by much (shard 0, the arms chain): the next lane to make it faster
has to shorten 40-arms-refusal, 50-arms-requeue or 94-arms-label-state.

After those runs master brought in two new fragments (99-cloud-lane-branch,
99-request-release-prio; 95 in all) and a change to 92. Each new one passes
alone (16 and 20 checks, 0 failed), so neither needs a chain; they take the
default weight. The guard covers 95. The final head's CI run is the check for
the merged tree.

### Locally, the tree before that merge (all five runs at once, so wall times are inflated)

| run | fragments (`NN-*.sh took` lines) | passed | failed | wall |
|---|---|---|---|---|
| no selector | all 93 (93) | 2278 | 0 | 2174 s |
| SELFTEST_SHARD=0/4 | 13 | 263 | 0 | 1048 s |
| 1/4 | 29 | 704 | 0 | 444 s |
| 2/4 | 26 | 685 | 0 | 440 s |
| 3/4 | 25 | 626 | 0 | 409 s |

13+29+26+25 = 93 fragments, and 263+704+685+626 = 2278 checks, exactly the
unsharded run's count: no check is lost or run twice by sharding.

The arms chain is a third of the whole and cannot be split without changing
fragments, so shard 0 sets the floor; 4 shards is the most that helps.

### The guard, with one fragment dropped

A copy of `selftest.sh` whose `shard_frags` omits `77-issue-sweep.sh`:

```
$ bash zz-drop-demo.sh --check-shards 4; echo rc=$?
selftest: shards 0..3 of 4 are not the fragment list, each once (< missing, > extra):
32d31
< 77-issue-sweep.sh
rc=1
$ SELFTEST_SHARD=2/4 bash zz-drop-demo.sh; echo rc=$?
(same message)
rc=2
```

A shard refuses to run anything when the guard fails.

## Do not repeat

- Do not split by `i % n`; chains fail in other shards.
- A new fragment that reads another's leftovers goes into `SHARD_CHAINS`;
  check with `SELFTEST_ONLY="<it>"`.
- Do not wait on a `run_in_background` task at a session end.
