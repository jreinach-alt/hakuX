# lane.remotechannel — the delivery channel is a file the recipient cannot read

PR #154. Harness only; no emulator file touched, no prediction, no device.

## What was measured before anything was changed

`$DISPATCH_DIR` on this host, 2026-09-19:

| path | mtime | size |
|---|---|---|
| `deliveries/remote.md` | 2026-09-18T20:48:08Z | 8779 |
| `deliveries/toolsmith.md` | 2026-09-14T11:53:57Z | 12441 |
| `lanes/remote.lastbrief` | 2026-09-14T10:35:15Z | 21 |
| `lanes/toolsmith.lastbrief` | 2026-09-14T08:28:48Z | 21 |

Both stamps are four days older than the delivery files they back, on both
lanes that have one — which is the failure `check_coverage.py`'s own comment
predicted when it moved off them ("a second thing to remember").

**The watcher was not running.** The brief says `watch_remote_lane.sh` "is
*still running* on this host". It is not, as of 14:05Z: `ps -eo args` matches
nothing but this session's own command line, which contains the string because
the brief does. A blocker is a claim and so is a liveness report; this one was
true when written and had expired. It is retired in the tree anyway, because
the reason to retire it is that it has no destination, not that it is running.

## The finding that changes the disposition: the recipient exists

The brief describes the remote session as "a session that was deleted" and
`watch_remote_lane.sh` as polling "to wake a session that does not exist".
**That is no longer true, and it was refuted while this lane was working.**

At 2026-09-19T14:07:15Z — seven minutes before the first scan this lane ran —
`lane.remote` posted a full answer on #138: *"I am that lane — the cloud
session… The 74+ commits are in `master`."* It proves containment commit by
commit, disposes of all nine claimed issues, and says it is picking up
`gl/surface.c` under the new lane contract. `check_coverage.py` independently
lists `remote` among the RUNNING lanes.

So the conclusion is the opposite of the fallback the brief allowed for, and
better: **there is a reachable remote session, it reads and writes GitHub issue
comments, and the reporting-back direction of the channel was working the whole
time.** What was broken was only the direction *towards* it — and that
direction was aimed at a file on a disk it cannot mount. Nothing about routing
needs to be moved to a local or cloud lane for want of a recipient.

This is also the measurement that says the migration is right rather than
merely tidy: the session that could not open `deliveries/remote.md` answered on
the exact medium this PR moves the channel to, unprompted, on the same day.

## What was built

**`docs/testing/jobs/deliver.sh`** — the channel.

    deliver.sh send <lane> <thread> -b '...'   route work (a comment)
    deliver.sh inbox <lane>                    read what was routed
    deliver.sh last <lane>                     when it was last briefed
    deliver.sh scan [--since <iso>]            refresh the cache from GitHub

A delivery is a comment whose first line is `[job.deliver] lane.<name>`,
matching the `[job.board]` / `[job.arms]` convention. Anchored at the start of
the first line, so a comment that *quotes* the marker is prose about a delivery
and not one — pinned by a check, because this project has had a grep match its
own explanatory text before.

**One endpoint, no enumeration.** `GET /repos/{o}/{r}/issues/comments?since=`
returns every issue comment in the repository, pull requests included, in one
paginated call. `watch_remote_lane.sh`'s lesson was "THE ENDPOINT WAS WRONG,
not the page" — it watched PR #45 alone and missed three replies on issue
threads. Its own fix, enumerating open issues plus the PR, is still an
enumeration that can be wrong about a closed issue or a thread opened after the
loop started. This one has no list to get wrong. Verified live: one call
returned comments on #10, #31 (issues) and #143, #151 (PRs).

**`check_coverage.py`** — the `UNBRIEFED` source is now the newest delivery
comment's `created_at`, read from `$DISPATCH_DIR/delivery-cache/<lane>.json`.

The cache is **not a second channel** and this distinction is what keeps the
old defect out: nothing reads it to learn what was routed (`inbox` reads GitHub
for that), and no local clock reading ever enters it — every timestamp in it is
GitHub's own `created_at` for a comment that exists, read back from the POST
that created it or from a scan. It is an index of one field so that a gate
running inside every lane's preflight costs no network call. A missing or
unreadable cache reads as `never`, which reports a lane unbriefed rather than
reporting a brief nobody sent.

What it cannot see, stated in the code as well as here: a delivery posted by
hand is invisible until the next sweep folds it in (so the note names the
cache's own refresh age when that age is the thing you are actually looking
at), and it cannot see whether the lane *read* the delivery. It measures
routing, not receipt — the same limit the file had, carried forward rather than
quietly dropped.

**`comment_sweep.sh`** — absorbed the watcher's polling and, more importantly,
**got a destination**. It now (a) refreshes the delivery cache, which
`check_coverage.py` reads onto the summary line the board job and the idle
watchdog both take, and (b) posts its report as one comment on the
`harness-status` issue, edited in place by remembered comment id — the same
single URL `status.sh` uses, for §5's reason: the owner reads GitHub from a
phone and nothing else here is reachable from one. It also now sees PR threads,
which the old `gh issue list` enumeration could not.

*Stated tension:* that issue's body says "do not comment here; the roll-up is
the only content". This adds a second job roll-up, edited in place and never
growing — not discussion, which is what that sentence is guarding against. If
the owner disagrees, the destination is four lines at the bottom of
`comment_sweep.sh`.

**`watch_remote_lane.sh`** — retired in place, not deleted: it is named in
`ORCHESTRATION-DESIGN.md`, `ORCHESTRATION-WIND-DOWN.md` and two hand-offs, none
of which this lane owns, and a stub answers in four lines what a deletion sends
a reader to `git log` for. It exits 64 so nothing restarts it as a background
loop. Everything it learned is kept verbatim in its header.

## Where the old records went

`deliveries/remote.md` and `deliveries/toolsmith.md` are the record of routing
decisions that were really made (audit M2, M4, P2, L5 and the rest), so:

- **archived verbatim** at `docs/lanes/remotechannel/deliveries-archive/*.md`,
  which puts them on `master` after the fold — durable, diffable, and readable
  by a cloud session, which the original location was not;
- **the originals are marked retired in place** on this host, with a banner
  above the untouched body saying nothing reads them, why, and what to run
  instead. Appending to them now routes nothing and moves no gate.
- `lanes/*.lastbrief` is read by nothing after this PR. Left on disk untouched:
  `affinity.py` has a check that a `<lane>.lastbrief` sharing that directory is
  not mistaken for a device, and renaming them is exactly how that check would
  start earning its keep for the wrong reason.

## Live end-to-end, not only against a shim

    $ deliver.sh send remotechannel 154 -b '...'
    delivered to lane.remotechannel on #154 at 2026-09-19T14:16:28Z
    $ deliver.sh last remotechannel
    2026-09-19T14:16:28Z  154  .../pull/154#issuecomment-5742574838
    $ deliver.sh inbox remotechannel --since 2026-09-19T14:00:00Z
    === 2026-09-19T14:16:28Z ...  [job.deliver] lane.remotechannel ...

Routed to this lane on its own PR on purpose: it exercises the real POST, the
real read-back and the real cache write while touching no other lane's gate.

A live `scan --since 2026-09-17` folded **48** comments and found **zero**
deliveries and 20 lanes' reports. That is break #1 measured rather than
asserted: in three days, every lane reported and nothing was ever routed.

`check_coverage.py` prints byte-identical summary lines before and after on the
real board (23 open, 0 AVAILABLE, 23 blocked, 12 owned), because every open
issue currently carries a `blocked_on`, so no lane has an idle issue and the
UNBRIEFED path is quiet either way. The change adds no noise to a live board.

## The self-test, and what it is worth

`docs/testing/jobs/selftest.d/66-deliveries.sh`, 34 checks, and the whole
fragment can be pointed at the old scripts with `SELFTEST_DELIVER_SRC`.

Falsified against `origin/master` (extract `comment_sweep.sh`,
`watch_remote_lane.sh`, `check_coverage.py`, `board_files.py` into a tree and
set that variable): **26 of 34 fail**, for five independent reasons — no
`deliver.sh` at all; `check_coverage.py` reading a file mtime; the sweep
enumerating issues so PR #45's comment is invisible; the sweep having no
destination; the watcher still looping. The 8 that pass are the positive
control, the both-directions pins, and three that are vacuous against code
lacking the feature.

Two traps it is built around:

- **The discriminating fixture is a `deliveries/alpha.md` written FRESH** next
  to a cache saying the last delivery comment was ten hours ago. The old code
  reads the fresh mtime and reports the lane briefed. That is the defect in one
  assertion: a channel the recipient cannot read will report a brief that
  reached nobody.
- **Assert on words, never on the exit code.** The retired watcher check would
  pass for free on rc alone: the old file also exits non-zero here, with 124,
  because `timeout` kills its sixty-second poll loop.
- The fragment opens with a **positive control** on its own gh shim, because
  every check below it reads an empty feed as "no deliveries", which is
  indistinguishable from a working shim on a quiet repository.

## For the next lane

- **`AGENTS.md` still names the old channel** — "Routing on paper is not
  routing", item 2, `an append-only entry in $DISPATCH_DIR/deliveries/<lane>.md`.
  That sentence is now wrong and is the one place a future session would go to
  find the channel. **This lane did not edit it: PR #143 claims `AGENTS.md`.**
  The replacement clause is: *an addressable delivery comment,
  `deliver.sh send <lane> <thread>`, which the lane can read back with
  `deliver.sh inbox`.* Items 1 and 3 are unchanged and still right.
- `docs/ORCHESTRATION-AS-BUILT.md`'s timer table entry for `hakux-comments`
  describes the sweep's old behaviour. Cosmetic; not claimed by this lane.
- Nobody has ever sent a delivery. The channel works and is empty. Whether
  `lane.remote` should be *routed* anything is the board's call and #138's, and
  this lane deliberately did not make it.
