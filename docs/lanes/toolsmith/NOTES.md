# lane.toolsmith -- a coverage gate that reported `ok` without running

2026-09-19. Brief only, no tracker issue. Found by `lane.remote` on PR #162,
from a Claude Code cloud container, and flagged rather than touched because
`docs/testing/` is this lane's.

Its words on the shape, which are the best summary of it: *"a check reporting
success without doing the work, with the sentence admitting it swallowed."*

## What was actually wrong

Two independent defects that compounded into one silent gate.

1. **`gh issue list` and `gh pr list` are GraphQL**, and a Claude Code cloud
   session's proxy refuses GraphQL wholesale:

       HTTP 403: GitHub GraphQL is not available from Claude Code sessions;
       use the REST API (gh api repos/{owner}/{repo}/...)

   So in that environment `check_coverage.py` took its fail-open branch on
   *every* invocation. The fail-open is correct and deliberate -- a network
   blip must not make the repository unpushable -- but it was being reached
   by the question never being asked, not by the network being down.

2. **`preflight.sh` printed `ok` over it.** Its coverage step did
   `sed -n 1p /tmp/preflight-coverage.log`, which was right until
   `check_coverage.py` grew a provenance line (`board read from: ...`) and
   that became line 1. From then on the operator saw where the board was read
   from and nothing about what was checked -- on a passing run *or* a
   fail-open one. Every "preflight green" claimed from a cloud session
   included a coverage check that had never run.

Neither was visible from the owner's host, where GraphQL works and the gate
genuinely runs. Verified here 2026-09-19T20:53Z on master: `coverage ok (23
open: 0 AVAILABLE, 23 blocked, 13 owned by a lane)`, exit 0.

## Measured, not assumed

`GH_DEBUG=api` prints the request line, so which transport each subcommand
uses is a measurement (`.lanework/ghprobe.sh` in the run, not committed):

| command | transport |
|---|---|
| `gh issue list` | `POST /graphql` |
| `gh pr list` | `POST /graphql` |
| `gh pr view --json statusCheckRollup` | `POST /graphql` |
| `gh issue view --comments` | `POST /graphql` |
| `gh api repos/{r}/issues` | `GET /repos/.../issues` |
| `gh api repos/{r}/pulls` | `GET /repos/.../pulls` |

And the trap the brief warned about, measured on this repository the same day:

| `gh api repos/{r}/issues?state=open` | rows |
|---|---|
| total returned | 32 |
| carrying a `pull_request` key | 9 |
| genuine issues | 23 |

23 is exactly what `gh issue list` reports. **REST's `/issues` returns pull
requests as well as issues.** An unfiltered reader would have demanded a
tracker row and a lane for every open PR and gone red on work that is not an
issue at all -- a worse failure than the one being fixed, because the old bug
made a gate silent and this one would have made it wrong.

## What changed

| file | change |
|---|---|
| `gh_rest.py` (new) | the issue and PR lists over REST. Paginated at `per_page=100` with explicit `page=N`; running out of pages is an **error**, not a truncation. Filters `pull_request is None` -- *is None*, not falsey, because an empty dict would read as "not a PR". |
| `check_coverage.py` | uses it. The fail-open line now reads `coverage NOT CHECKED -- THE GATE DID NOT RUN` and says in words that its exit 0 means "not checked", not "checked and fine". The summary reports how many PRs the filter dropped, so the filter is observable rather than assumed. |
| `fleet.py` | both calls converted. Its `issue-blind` and `PR-BLIND` notices were already honest -- they were just permanently on in the cloud. |
| `preflight.sh` | a third verdict, `DID NOT RUN`, rendered by `render_coverage()` keyed on the `^coverage ` line instead of line 1. Plus `--render-coverage <log>`, so the self-test drives this code rather than a paraphrase of it. |
| `idle-watchdog.sh` | the same defect twice, found while reading it. |
| `selftest.d/98-coverage-rest.sh` (new) | the fixture, below. |

### `idle-watchdog.sh` had it twice, and nobody had noticed

- Its `case "$cov" in FAIL*)` stopped matching **any** coverage gap the day
  the provenance line became line 1. Every real gap fell through to the `*)`
  branch, which then advised on the assumption that nothing was uncovered.
  (Its `sed -n 2p` detail line was off by one for the same reason, and its
  three `sed -n 1p` hints printed the provenance line.) Worse: the `FAIL`
  lines go to **stderr** while the summary goes to stdout, so under `2>&1 |`
  -- stdout block-buffered, stderr not -- their relative order was never even
  fixed. It now pulls each piece out by the prefix its writer guarantees.
- Its own `issue_count()` used `gh issue list ... --jq length`, i.e. GraphQL,
  *and* the REST replacement would have counted open PRs as issues. That
  matters here beyond a wrong number: the watchdog **exits** when the count
  reaches 0, so a PR-inflated count is a watchdog that never terminates.

## The fixture, and the mutant per invariant

`selftest.d/98-coverage-rest.sh`. Every assertion is on the **output words**,
never the exit code: `check_coverage.py` exits 0 both when it checked and when
it failed open -- that is the whole defect -- so an exit-code assertion passes
against the broken version for free.

Four mutants, each built in the fixture and each confirmed to trip:

| invariant | mutant | what it does |
|---|---|---|
| the gate runs where it used to fail open | `gh_rest` asking over `gh issue list` again | fails open -- which also proves the shim really refuses GraphQL, so the positive check is not vacuous |
| an open PR is not an issue | `if r.get("pull_request") is None` → `if True` | goes red naming `#900`, the pull request, by number |
| a second page is not dropped | `if len(batch) < per_page:` → `if True:` | reports a clean board over the row it never saw, and never mentions `#101` |
| `preflight` prints the verdict | `grep -m1 '^coverage '` → `sed -n 1p` | calls a fail-open a pass, and hands over the provenance line on a real verdict |

The pagination mutant is the strongest shape available: **the mutant goes
green and the real code goes red.** A silently truncating reader cannot fake
that.

The fail-open itself is pinned in both directions -- the visibility checks
above, *and* a check that it still exits 0. The goal was visibility, not
brittleness.

## For the next lane: do not repeat these

- **`98-` and not `101-`.** `selftest.sh`'s fragment loader matches
  `[0-9][0-9]-*.sh` -- exactly two digits -- and anything else hits its `*)`
  arm and `exit 2`s the **entire run** rather than being skipped. A
  three-digit fragment does not fail quietly; it takes the whole self-test
  with it. Duplicate numbers are fine and already in use (55, 86, 97, 98).
  **`territory.toml` currently grants `lane.stalecheck` the filename
  `docs/testing/jobs/selftest.d/100-stale-check.sh`, which will do exactly
  this.** Either that lane renames, or `selftest.sh`'s glob widens; this lane
  did not touch `selftest.sh` because it is shared and unclaimed.
- **The host is not the cloud, and most of these jobs are host-only.**
  `fold.sh`, `arms.sh`, `board.sh`, `status.sh`, `handback.sh` and `cloud.sh`
  run under systemd timers on the owner's host, where GraphQL works. Their
  `gh pr list` / `gh issue list` calls are *not* broken today and converting
  them would be churn. What actually bites is code that runs **inside a
  session**: `check_coverage.py` (every lane's preflight), `fleet.py`,
  `backlog-gate.sh`, `idle-watchdog.sh`. Scope the sweep by *where it runs*,
  not by *what it calls*.
- **A gate's first line is an interface, and so is a line number.** This is
  now the sixth time in this campaign that where output was placed decided
  whether it was read. The fix in both files here was the same: key on a
  prefix the writer guarantees, never on a position.

## Not done here, and why -- three handoffs

These are the rest of Finding 3's sweep. Each is a *report*, not an edit:
`roles/lane.md:79` and this lane's own row keep it out of files other lanes
hold, and this lane's standing rule has always been to ask rather than take.

1. **`docs/testing/jobs/board.sh:218`** (lane.windowbudget). It runs
   `check_coverage.py 2>&1 | grep -E '^(FAIL|  #)'` -- which **drops the
   `coverage NOT CHECKED` line entirely**, so a fail-open is indistinguishable
   from a clean board in the board's own status report. This is Finding 2 in a
   third consumer. One-line fix: `grep -E '^(FAIL|  #|coverage NOT CHECKED)'`.
   Low urgency now that the gate answers over REST, but the shape survives.
2. **`docs/testing/backlog-gate.sh:167`** (unclaimed, in no row and not in
   `[free]`). Runs as a Stop hook *inside a session*, so it is in the bitten
   set. Its count falls back to `?`, which is an honest unknown, and the
   comment above it says the count "no longer decides anything" -- so this is
   cosmetic, not a silent pass. It does cache a number that includes open PRs.
   Fix is two lines:
   `gh api "repos/$REPO/issues?state=open&per_page=100" --jq 'map(select(.pull_request == null)) | length'`.
3. **`docs/testing/jobs/cloud.sh:386`** (lane.cloudterritory) -- **the one
   worth acting on.** The prompt `cloud.sh` writes for a cloud-class lane says
   *"Read the issue with `gh issue view $num --repo $GH_REPO --comments`"*.
   Measured above: that command is `POST /graphql`, which is precisely what a
   cloud session's proxy refuses. Every cloud lane is being handed an
   instruction that cannot work in the environment it is handed to.
   `gh api "repos/{r}/issues/{n}"` and `.../issues/{n}/comments` are the REST
   equivalents. Related, and not this lane's to fix either: a cloud lane
   cannot check its own CI, because `gh pr view --json statusCheckRollup` is
   GraphQL too.

`docs/testing/comment_sweep.sh:242` (lane.remotechannel) was also on the
brief's list and is **fine**: it is a host job, and it already prints
`(no harness-status issue; not posted)` when it comes back empty. Converting
it would be portability work, not a defect fix.

## Coordinated touches outside this lane's files

Changing how `check_coverage.py` and `fleet.py` ask GitHub breaks every
fixture whose `gh` shim answered `issue list`. Five shims needed the REST
spelling of the same canned data, plus `gh_rest.py` added to three copy
lists. These are small, mechanical, and flagged rather than claimed, per the
pattern this board already uses for cross-lane touches at fold:

| file | holder | touch |
|---|---|---|
| `selftest.d/93-backlog-state.sh` | unheld (lane.backlogstate retired) | shim → REST; `gh_rest.py` added to the copy list |
| `selftest.d/66-deliveries.sh` | lane.remotechannel | one `*"/issues?"*` case in a shim that already parsed `gh api`; `gh_rest.py` in the copy list |
| `selftest.d/55-localtime.sh` | lane.localtime | `gh_rest.py` in the copy list (one filename) |
| `selftest.d/96-fleet-registry.sh` | unheld | shim → REST, **and its PR fixture rewritten into REST's shape** |
| `selftest.d/97-board-gate.sh` | unheld | shim serves **both** transports |

In 93, 66 and 55 no fixture **data** changed -- only the question the scripts
ask. The pull-request and pagination semantics live in this lane's own new
fragment rather than being folded into somebody else's board fixture.

96 and 97 needed more, and the reason is worth recording because the first
attempt at each was wrong and the full self-test caught it (13 red):

- **96's `prs.json` was in `gh pr list --json`'s shape.** REST spells the same
  three fields differently -- `head.ref` for `headRefName`, `draft` for
  `isDraft`, `updated_at` for `updatedAt`. `gh_rest.open_prs` normalises them
  back so every check reads the spellings it always did, but the *fixture* has
  to be what the endpoint actually sends or it tests the normaliser against
  itself.
- **97 has two consumers on two transports, from one fixture.** `board.sh`
  still asks over GraphQL (`gh issue list` / `gh pr list` at `board.sh:132`
  and `:135`) -- correctly, since it only ever runs on the owner's host -- and
  it *invokes* `fleet.py` and `check_coverage.py`, which now ask over REST.
  Replacing the shim's GraphQL arms with REST ones silently starved
  `board.sh`'s own two calls and took out all 13 of that fragment's checks.
  The shim now answers both, converting the flat PR fixture to REST's shape on
  the REST arm only. That conversion deliberately does **not** fall back to
  `[]` on error: swallowing it would turn a broken fixture into a quietly
  passing "no PRs" run, which is the exact shape this whole change removes.

## Why attempt 1 did not finish, and the shape of that failure

Attempt 1 ended with PR #170 in draft, CI **red** on `0c3edf5595`, and no
`[lane.toolsmith] waiting:` comment. Nothing downstream could act: `board.sh`,
`fold.sh` and `fleet.py` all skip drafts, correctly, because a draft means the
lane is still working -- and it was not. `jobs/handback.sh` resumed it.

The red was not a mystery and not a new defect. **The 96 and 97 fixes described
above were made in the working tree and never committed.** CI therefore built
`0c3edf5595`, which still carried the first, wrong versions of both shims, and
went red on exactly the 13 checks those two fragments own -- 3 in 96, 10 in 97.
The local tree was green the whole time. The gap between "green here" and
"green on the head" was one `git add`.

Two things follow, and they are the transferable part:

- **The self-test that matters is the one CI ran, on the sha CI built.** A
  local green proves the working tree, and the working tree is not what is
  pushed. This lane's whole subject is a check that reported success without
  doing the work; ending the session on an uncommitted fix is the same shape
  one level up, with the operator's own tree as the thing that swallowed.
- **Ending while waiting is fine; ending silently is not.** The cost was a
  full resume, and only because `handback.sh` exists to catch it. A PR comment
  naming what was being waited for, plus the same line here, is the entire
  price of that not happening.

## Board request (a lane cannot write one; it goes here and on the PR)

`territory.toml`'s `[lane.toolsmith]` `files` should gain
`docs/testing/gh_rest.py` and `docs/testing/jobs/selftest.d/98-coverage-rest.sh`.
Both are new files created by this lane; neither collides. The `selftest.d/**`
glob held by `lane.cloudterritory` does not read as a collision with a named
fragment under `check_territory.py`'s exact-match rule -- the same reasoning
the board already applied to `[lane.desktopchannel]` and `[lane.windowbudget]`.
