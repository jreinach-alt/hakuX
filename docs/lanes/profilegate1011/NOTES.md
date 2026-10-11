# lane.profilegate1011 -- NOTES

## Attempt 1: why it did not finish

Attempt 1 wrote the bulk of `titlestate.py`'s profile gate (`admit()`,
`gate_report`, `title_routes`/`proven_route`/`known_path`, `title_saves`,
`readiness`, the `--save` disk-composition path, CLI wiring) and the R3
check in `pathfind.py`, plus a first slice of `titlestate_selftest.py`
covering the four `admit()` clauses and the transition file. It opened
PR #930 early, per protocol -- but every one of those changes stayed
**uncommitted** in the worktree. The PR body claimed files
(`docs/lanes/profilegate1011/**`, the selftest.d fixture, the
request.sh/dispatcher.sh patch) that were never written, and the branch
itself carried zero commits ahead of the base it was opened from. With an
empty diff against master, PR #930 was later closed as `MERGED` with a
merge commit (`b73d50a070`) that is just master's own tip -- none of
attempt 1's work landed. The uncommitted changes were still sitting in the
worktree when this attempt (2) started; nothing was lost, but nothing had
been delivered either.

Lesson applied this attempt: commit the in-progress work immediately
(checkpoint commit `c80bc65549`) before doing anything else, including
before merging origin/master, so a repeat of the same failure mode cannot
silently discard it again. Opened a fresh PR (#933) since #930 is closed.

## Addendum 3: the grant is in

`lane.local`'s board (`d09966237f`) released `request.sh`, `dispatcher.sh`
and `AGENTS.md` after `lane.soakvideo1011` folded (`b73d50a070`, 14:55
PDT). Merged `origin/master` into this branch (merge commit on top of
`c80bc65549`) -- clean, no conflicts: soakvideo1011's changes to
request.sh/dispatcher.sh/AGENTS.md (route_refs staging, video) don't touch
anything attempt 1 wrote in titlestate.py/pathfind.py.

## Evidence

`profilegate1011-inventory.py` and `profilegate1011-inventory.txt` (copied
from `/home/justin/hakux-work/briefs/`) are the brief's inventory of every
route, its state, its title's golden, and 3 days of runs -- the basis for
"The rule"/R1-R3 above.

## Rule actually implemented (Addenda 1 + 2, replacing the original "The rule")

`admit(title_id, route_name=None, route_text=None, device=None,
find_route=None, routes_dir=None, remake_profile=None, path_broken=None)`
in `docs/testing/titles/titlestate.py`. Refuses only:

- **R1** a `first-run` route on a title that already has a golden (either
  kind) -- override `--remake-profile "<why>"`.
- **R2** a `first-run` route with no `mark profile-saved` on a title with
  no golden -- way forward is the recipe (module docstring).
- **R3** a route-finding run (`--find-route`, or a `pathfind.py` session)
  on a title with a known path -- queued runs are blocked only by a
  *proven* route (one with `mark gameplay` AND a result whose
  `verdict.json` says `reached_gameplay`); `pathfind.py` sessions are
  blocked by that OR a `pathknow/paths/<TID>.json` success (Addendum 2:
  a route's own first proof soak still needs `--find-route` even though
  pathknow already succeeded once). Override `--path-broken <result id>`,
  checked against the known route/title.

Admitted unconditionally: `returning`/`any`/no-route on a title with a
profile (data-only counts under `any`/no-route, not `returning`),
`make-profile`, `--find-route` with no known path, a live
`profile-transition.toml` entry, and the two overrides above.

`--save <save_id>` (compose/plan/rebuild/prepare) swaps a specific stored
save in for a title's slot instead of its golden; refused when the save
isn't in the store, was rejected on the device, or (returning) has no
save directory.

## Status at end of this session

See PR #933 body / `State:` line for current status; this file is kept
up to date as work proceeds in this session.
