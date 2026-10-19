# homeroot1018 (#433, home branch root: move chart.svg/chart2.svg/COPYING.LIB under docs)

## Step 0: Already-tried table

Read `docs/lanes/statuspage1013/PR.md` and `NOTES.md` (the model this brief
names: host-only `status_md.py`/`status_page.py`/`status_svg.py` changes
delivered as copies under `docs/lanes/statuspage1013/host-tools/` for
lane.local to review and install, with the exact three-chart-key change
`dashboard_blobs()` makes and the real-fixture-render testing discipline
that caught a bug no unit test did), `docs/lanes/titledb1014/host-tools/
INSTALL.md` (the install-note phrasing convention for a host-only file:
diff against the live copy, replace, name the timer/cadence that picks it
up), and `home_page.py`/`status_page.py`/`status_md.py` themselves (read at
`/home/justin/hakux-work/host-tools/`, not writable from this lane).

| Column | Source used this session | Confirmed |
|---|---|---|
| home's current root matches the brief's listing | `git ls-tree --name-only origin/home` | `.github CHANGELOG.md CODE_OF_CONDUCT.md CONTRIBUTING.md COPYING COPYING.LIB KNOWN_ISSUES.md LICENSE PRIVACY.md README.md SECURITY.md STATUS.md chart.svg chart2.svg docs` -- exactly as the brief states |
| `docs/images/` already exists on home | `git ls-tree origin/home:docs` | holds `hakux-logo.svg` only, carried via `home_page.py`'s `src=` logo mechanism; a precedent for `docs/images/` holding home-authored assets, not just master-carried ones |
| charts are written by `status_page.py`, linked by `status_md.py`, kept by `home_page.py` | read all three at `/home/justin/hakux-work/host-tools/` | `status_page.py` `dashboard_blobs()` (~line 234) writes `home["chart.svg"]`/`home["chart2.svg"]`; `status_md.py` `block()`'s `svg` branch (~line 206) emits `![Titles over time](chart.svg)`/`![Titles toward 1.0](chart2.svg)`; `home_page.py` `STATUS_FILES = ("STATUS.md", "chart.svg", "chart2.svg")` is what the carry-forward loop keeps across updates that don't supply a fresh render |
| `COPYING.LIB` is carried by `home_page.py`'s `FILES`, not optional | read `home_page.py` `FILES`/`OPTIONAL` | `COPYING.LIB` is in `FILES`, not in `OPTIONAL = {"SECURITY.md", "CODE_OF_CONDUCT.md"}` -- it is a required file on master, unlike those two |
| only CONTRIBUTING.md links `COPYING.LIB` besides README | `grep -rn "COPYING.LIB" --include=*.md --include=*.py` across the repo and across both host-tools dirs | README.md's licence paragraph links only `LICENSE` (brief's own claim, confirmed); `CONTRIBUTING.md` line 73 links `[COPYING.LIB](COPYING.LIB)`; no other `.md`/`.py` in-repo reference; the three host-tools scripts only reference it by its `FILES`-list membership, not a literal relative link |
| no other reference to `chart.svg`/`chart2.svg` besides the three host-tools scripts | `grep -rn "chart2\?\.svg"` across `host-tools/`, `docs/`, `status/`, README.md | only `status_page.py` (writes the blob) and `status_md.py` (writes the link); nothing in this repo's `docs/`, `README.md` or `status/` names either file |
| `home_page.py` rebuilds the whole tree every run, not incrementally | read `update()` end to end | every call does `git update-index --add --cacheinfo ...` into a fresh temp index built from `FILES` + carried `src=` images + `STATUS_FILES`-named blobs, then `write-tree`; a path that stops being written on one call is simply absent from the next tree -- the "delete the old root copies" the brief asks for is a consequence of changing the write path, not a separate step |

Stop rule: no repeated failure for one cause this session; the one real
bug found (the flat `ls-tree`, below) was fixed on first discovery and
re-verified, not retried against the same failure twice.

`Selftest: 81-home-root` (claimed on the board before creation; see
"Selftest" below).

## What changed

- `docs/lanes/homeroot1018/host-tools/home_page.py` (edited copy of
  `/home/justin/hakux-work/host-tools/home_page.py`):
  - `RENAME = {"COPYING.LIB": "docs/licenses/COPYING.LIB"}` (new). The
    `FILES` loop's `update-index --cacheinfo` call now writes each file
    at `RENAME.get(f, f)` instead of always at `f`.
  - `STATUS_FILES = ("STATUS.md", "docs/images/chart.svg",
    "docs/images/chart2.svg")` (was the two root names).
  - `absolute()` gained a `home=()` parameter: a relative link to a file
    home carries stays relative so the visitor stays on home, and if that
    file has a `RENAME` entry the link follows it there (so
    CONTRIBUTING.md's `[COPYING.LIB](COPYING.LIB)` becomes
    `[COPYING.LIB](docs/licenses/COPYING.LIB)` on home instead of a dead
    relative link to a file no longer at that path). `rewrite()` and
    `update()` thread the carried-files set through as `home`.
  - The carry-forward loop's `git ls-tree parent` gained `-r` -- see "the
    ls-tree bug" below.
- `docs/lanes/homeroot1018/host-tools/status_page.py` (edited copy):
  `dashboard_blobs()`'s two chart keys are `docs/images/chart.svg` /
  `docs/images/chart2.svg` instead of the root names, matching
  `home_page.py`'s new `STATUS_FILES`.
- `docs/lanes/homeroot1018/host-tools/status_md.py` (edited copy):
  `block()`'s `svg` branch links the two inline charts as
  `docs/images/chart.svg` / `docs/images/chart2.svg` instead of the root
  names.
- `docs/lanes/homeroot1018/host-tools/INSTALL.md` (new): the exact diff/
  install commands for lane.local, and why no restart is needed (the
  host's own 15-minute render cycle, per `status_page.py`'s own footer
  text, picks the new paths up on its next run).
- `docs/testing/jobs/selftest.d/81-home-root.sh` (new, claimed on the
  board first -- see "Board claim" below).

## A real bug found by testing, not by review: the flat `ls-tree`

`home_page.py`'s carry-forward loop (inside `update()`) reads the current
`home` tree to find the existing blob for any `STATUS_FILES` entry not
given fresh in this call's `status_blobs` (the case where the dashboard
render is stale/degraded and `status_page.py`'s `dashboard_blobs()`
returns `{}`). It used a flat `git ls-tree parent`, which only lists
top-level entries. That was harmless while every `STATUS_FILES` name was a
root file; once `STATUS_FILES` names `docs/images/chart.svg` etc., a flat
`ls-tree` can never find them (it sees only the top-level `docs` tree
entry, not names nested under it), so carry-forward would silently fail
and **the charts would be deleted from the tree on every update that runs
without a fresh render** -- not a one-time migration glitch but a standing
bug from that point on.

Found by running `home_page.update()` twice in a row against a scratch
clone, the second time with no fresh chart blobs (simulating the common
case: most ticks don't carry a changed STATUS.md): the second call
returned a new commit (expected: `None`, unchanged) whose tree had dropped
both `docs/images/chart.svg` and `docs/images/chart2.svg`. Fixed by adding
`-r` to that one `git ls-tree` call. Re-ran the same two-call scratch test
after the fix: second call now correctly returns `None`, and the tree
still carries both charts. This is also the "stable" and "nested" cases in
the `81-home-root.sh` selftest fragment (the fragment's `root`/`nested`
checks run a second `update()` with the same inputs and assert it's a
no-op, which would have caught this with `-r` reverted -- confirmed: the
`oldpaths`/`oldpaths2` mutants, which revert `STATUS_FILES` to the root
names, turn `root`/`nested` red).

## Accepted, not fixed: the one-tick gap on first install

If the very first post-install `home_page.update()` call happens to run
while the dashboard render is stale or degraded (`status_page.py`'s
`dashboard_blobs()` returns `{}`), the carry-forward loop looks for the new
`docs/images/chart.svg`/`chart2.svg` names in the *current* `home` tree,
which (before this change ships) still has the charts at the old root
names -- so neither is found, and that one commit has no charts at all.
The very next successful render (within ~15-30 minutes, per
`status_page.py`'s own cadence) writes fresh blobs at the new paths and
the gap closes itself. Verified directly: ran `update()` against a scratch
`home` seeded with charts at the *old* root names, called with no fresh
`status_blobs` (the degraded case) -- the resulting tree has no chart at
either old or new path, confirming the gap, then a second `update()` with
fresh blobs at the new paths restores both. Not engineered around (no
one-time migration shim): it is a single rendering cycle with no visible
chart on a page that otherwise self-heals within half an hour, and the
brief does not ask for a glitch-free transition, only that the next
regular update stop writing the old paths.

## Testing

Three progressively stronger checks, in order:

1. **Hand-built stub** (`/tmp/homeroot1018-test-driver.py`..`3.py`,
   scratch only, not part of the deliverable): called `home_page.update()`
   directly against fresh `git clone --bare` scratch copies of the real
   offline git mirror (`/home/justin/hakux-work/offline-git/hakuX.git`),
   with hand-written `STATUS.md` text and placeholder `<svg>...</svg>`
   blobs. Found the `ls-tree` bug above. Confirmed the target root shape
   (`git ls-tree --name-only home`: exactly `.github`, the markdown files,
   `COPYING`, `LICENSE`, `docs`) and that `CONTRIBUTING.md`'s rewritten
   home copy links `docs/licenses/COPYING.LIB`.
2. **Real end-to-end render** (`/tmp/homeroot1018-test-driver4.py`,
   scratch only): ran `docs/lanes/dash432/fixtures/run_fixture.sh` against
   this worktree's real (unedited) `docs/testing/jobs/status.sh`, producing
   a real `index.html` with one real inline chart SVG (`<svg
   class="chart"...>`, release-0.5 conf, no curve). Fed that real HTML
   through the edited `status_md.py`'s `build()`, mirrored
   `status_page.py`'s `dashboard_blobs()` key-naming (its own home-path
   logic reads real host paths outside this repo and isn't itself
   exercised here; its three changed lines are a direct visual diff,
   reproduced in NOTES/INSTALL), and fed the result through the edited
   `home_page.py`'s `update()` against a fresh scratch clone. Result: root
   listing exactly `.github CHANGELOG.md CODE_OF_CONDUCT.md CONTRIBUTING.md
   COPYING KNOWN_ISSUES.md LICENSE PRIVACY.md README.md SECURITY.md
   STATUS.md docs` (the real offline-git master has SECURITY.md/
   CODE_OF_CONDUCT.md, unlike the minimal selftest fixture below); a
   second `update()` with the same inputs returned `None`.
3. **Selftest fragment** (`81-home-root.sh`, the deliverable): see below.

## Selftest

`docs/testing/jobs/selftest.d/81-home-root.sh`, run in isolation via
`SELFTEST_ONLY="81-home-root" bash docs/testing/jobs/selftest.sh` (9
passed, 0 failed). Independent of every other fragment: its own scratch
git repo (seeded with the minimal `FILES` set `home_page.py` requires on
`master`, built fresh each case, never the real offline mirror), its own
synthetic `index.html` (a `<main>` with two inline `<svg class="chart">`
elements, just enough markup for `status_md.py`'s parser), and its own
`sys.path` pointed at `docs/lanes/homeroot1018/host-tools/`. Never pushes
anything; `home_page.G` is pointed at the scratch repo before any call.

Five cases, each run once against the real edited copies and, for every
case sensitive to one, once against a mutant that reverts that one piece
to its pre-fix form:

| case | checks | mutant | mutant outcome |
|---|---|---|---|
| `root` | home's root carries no `chart.svg`/`chart2.svg`/`COPYING.LIB` | `oldpaths`: `home_page.py`'s `RENAME`/`STATUS_FILES` reverted to `{}`/root names | red (confirmed) |
| `nested` | the charts and the licence land at their `docs/` paths | `oldpaths2`: same mutant, reused | red (confirmed) |
| `links` | `STATUS.md`'s chart images point at `docs/images/...`, not the root | `oldlinks`: `status_md.py`'s first chart-link line reverted to `(chart.svg)` | red (confirmed) |
| `rewrite` | `CONTRIBUTING.md`'s `COPYING.LIB` link follows it to `docs/licenses/` | `oldrename`: `home_page.py`'s `RENAME` alone reverted to `{}` | red (confirmed) |
| `stable` | a second `update()` with the same inputs is a no-op | none (idempotence, not itself a reverted behaviour) | n/a |

All four mutants applied via a `python3 -c re.subn` that asserts exactly
the expected number of matches before writing (the `99-status-degraded.sh`
convention) -- a mutant that silently matches zero times would prove
nothing. `stable` has no dedicated mutant because it is a property of
`update()`'s general design (same tree sha -> no new commit), not of this
lane's specific path change; it is still useful as a regression check and
is exercised by every scenario run, including the mutants.

The full unsharded selftest suite exceeds the ~580s practical foreground
limit on this host (same constraint `statuspage1013`'s NOTES.md records);
ran `81-home-root` in isolation only. It is new and self-contained (own
scratch repo, own `sys.path`, no shared state with any other fragment,
confirmed by reading it end to end above), so isolation is the right
scope for this diff -- there is no existing fragment this change could
regress, since no other fragment references `home_page.py`, `status_md.py`
or `status_page.py` (`grep -rl` across `selftest.d/` for all three found
nothing before this lane).

## Board claim

`territory.toml` on `origin/board` already carried this lane's claim on
`docs/lanes/homeroot1018/**` (written by lane.local at dispatch time).
Before creating `81-home-root.sh`, added it to that same lane's `files`
list via a scratch worktree (`pull --rebase origin board`, edit, commit,
`push origin HEAD:board`), per the brief's constraint that a selftest
fragment under `docs/testing/jobs/selftest.d/` must be claimed there
first. `wave` bumped 310 -> 311. Worktree and local branch removed after
the push landed.

## Not touched

`README.md` (lane.readme1018's territory; this lane never reads or writes
it, and `home_page.py`'s `readme()` function, which does rewrite README.md
for home, is untouched here -- its two regex substitutions target the
Playable-count sentence and the Compatibility table row, neither of which
names `chart.svg`/`chart2.svg`/`COPYING.LIB`). No ledger, compat or Wall
surface.

## Base

Branched from `origin/master` at `59623bbe0e`. Not rebased since; no merge
needed before marking ready (checked: still 0 behind at prediction/PR
time).

## Status

Done: both host-tools changes (charts to `docs/images/`, `COPYING.LIB` to
`docs/licenses/`), the real `ls-tree` bug found and fixed, the one-tick
gap identified and accepted (not engineered around), tested at three
levels of fidelity (hand-built stub, real fixture render, selftest
fragment with 4 confirmed mutants), `INSTALL.md` with the exact sync
commands, board claim for the new selftest fragment, `home` never pushed
from this lane. PR.md set to `State: ready`.
