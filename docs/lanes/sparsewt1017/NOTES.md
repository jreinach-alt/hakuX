# lane.sparsewt1017 -- lane worktrees are created sparse, without docs/lanes/pathfind/runs

## What changed

`docs/testing/lane.sh`'s `start` command built two different `git -C "$REPO"
worktree add --quiet ...` invocations: the resume-after-crash form
(`-B "$branch" "origin/$branch"`, taken when the branch already exists on
origin) and the fresh form (`-b "$branch" FETCH_HEAD`). Both now go through
one new helper, `lane_worktree_add()` (defined just above `case "$cmd" in`,
beside `lane_path()` and the other one-definition helpers this file already
has):

- `git worktree add --quiet --no-checkout <path> <args...>` first, so the
  tracked `docs/lanes/pathfind/runs/` subtree is never written to disk only
  to be deleted again.
- `git -C <path> sparse-checkout set --no-cone '/*' '!/docs/lanes/pathfind/runs/'`
  to record the exclusion.
- `git -C <path> checkout --quiet <branch>` to populate the working tree
  under that exclusion (HEAD already points at `<branch>` from the `-B`/`-b`
  above; this is what actually reads the tree into the index and files).

Exemptions (brief item 2), checked against the lane name and a brief-level
marker, both inside the helper:
- `name = pathfind`: its worktree IS the live harness tree and reads its own
  `runs/`, so it is created as a plain full checkout.
- `$WORK/briefs/<name>.fullcheckout` exists: an explicit opt-out for any
  other lane, same full-checkout path.

Both the shared repo config and the real checkout were left alone, as
required (brief item 3) -- see Measurements below.

## New selftest fragment

`docs/testing/jobs/selftest.d/99-lane-sparse-worktree.sh`, following the
shape of `99-lane-path.sh` and `99-lane-model-file.sh` (a throwaway bare
origin + a real `lane.sh start`, not a mocked worktree step -- only
`systemd-run`/`gh`/`systemctl` are shimmed, by the harness's own global
fixture). It exercises, for real:

1. The fresh form (`sparselane`, no origin branch yet): the runs file is
   excluded, the rest of the tree is present, `git status` is clean, HEAD is
   `lane/sparselane`.
2. The resume form: pushes `lane/sparselane` to the throwaway origin
   (simulating what a real lane does once started), removes the worktree
   (simulating `lane.sh rm` or a crash), and starts the same name again --
   `refs/remotes/origin/lane/sparselane` now exists, so `lane.sh` takes the
   `-B branch origin/branch` path. Same four checks.
3. `name = pathfind`: the runs file IS checked out.
4. `$WORK/briefs/<name>.fullcheckout`: the runs file IS checked out.
5. The shared repo's `config` never gains `core.sparseCheckout`.
6. Structural: exactly one `lane_worktree_add()` definition, exactly one
   `!/docs/lanes/pathfind/runs/` exclusion pattern, and exactly two raw
   `git -C "$REPO" worktree add` call sites left in the file (both inside
   the helper -- `start`'s own two call sites now go through it).
7. A falsifying mutant: the exemption condition forced to `if true; then`
   (always full checkout). Confirmed this makes the exclusion check fail
   (the runs file reappears), proving the checks above are not merely
   checking that `lane.sh` ran.

22 checks, all green against the modified `lane.sh`; the mutant leg is
confirmed red against the unmodified condition (i.e. the real file passes,
the deliberately broken copy fails the same assertion).

## Measurements

Scratch test under `/tmp/sparsewt-scratch` (left in place -- `rm` is
disallowed for this lane and there is no `mv`-aside need since it is outside
any git worktree):

- A scratch bare origin with `docs/lanes/pathfind/runs/` holding ~600 KB of
  random data plus one ordinary tracked file.
- Fresh form (`--no-checkout` + `-b branch FETCH_HEAD`, then
  `sparse-checkout set`, then `checkout`): resulting worktree 12 KB,
  `git status --short` empty, `git branch --show-current` = the lane
  branch, `docs/lanes/pathfind/runs/` absent.
- Resume form (`--no-checkout` + `-B branch origin/branch`, same two
  follow-up commands): same result, 12 KB, clean, correct branch, excluded.
- `core.sparseCheckout`: unset in the scratch repo's shared config, `true`
  in each worktree's own `config.worktree` (the repo already carries
  `extensions.worktreeConfig = true`).
- Confirmed against the REAL repo per brief item 3:
  `git -C /home/justin/hakuX config --get core.sparseCheckout` prints
  nothing (exit 1), `docs/lanes/pathfind/runs/` is still present there, and
  `extensions.worktreeConfig` is already `true` there too -- nothing this
  lane did touched the shared config.

These scratch numbers are illustrative (a few hundred KB of synthetic data,
not the real 1.9 GB subtree); the selftest fragment is the thing that keeps
the behaviour pinned going forward, not this one-off measurement.

## What I could not verify

- The real-world ~2.3 GB -> ~0.4 GB drop the brief describes for existing
  hand-converted trees: this lane only proves the mechanism (sparse
  exclusion, both worktree-add forms, the two exemptions, the config
  isolation) against a scratch repo with a small synthetic payload. I did
  not create a multi-GB fixture to re-measure the real ratio; the brief's
  own "owner 10-17" numbers for the hand-converted trees stand as the
  reference measurement for the real subtree's size.
- The full `selftest.sh` suite (147 fragments) does not finish inside this
  tool's 10-minute command limit. Ran instead: the new fragment alone (22/22
  green), every other `lane.sh`-related fragment under `selftest.d`
  (`98-lane-shape.sh` 92/92, `99-lane-path.sh` 32/32, `99-lane-model-file.sh`,
  `99-lane-no-background.sh`, `99-cloud-lane-branch.sh`,
  `99-handback-lane-line.sh` all green), and `63-status-lanes.sh`, which has
  4 pre-existing failures unrelated to this change -- it never references
  `lane.sh` at all (`grep -n "lane.sh" 63-status-lanes.sh` is empty), and the
  failing checks are about the status page's stranded-lane wording and
  retirement-age wording, nothing this lane touched.
- Did not run a fresh `lane.sh start` against the REAL `$REPO`
  (`/home/justin/hakuX`) -- only against scratch/selftest fixtures, per the
  brief's "harness shell only, no device" scope and the general rule never
  to run git in a tree that is not this lane's own worktree.
