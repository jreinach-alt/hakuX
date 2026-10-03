# RETURN: moving the harness's work back to GitHub when the account is restored

Design only. Nothing here runs. The owner decides when to execute; lane.local runs it.
Status 2026-10-03: GitHub suspended since 09-29. The forge (`http://127.0.0.1:3330`, repo
`jreinach-alt/hakuX`) holds the working record. The bare stand-in
(`~/hakux-work/offline-git/hakuX.git`) is still origin and still the source of truth for
code, because the forge copies it (option (b) in NOTES.md section 2).

## 1. What has to come back, and from where

| thing | source of truth now | goes to GitHub as | risk |
|---|---|---|---|
| `master`, `board` | bare stand-in (forge copies) | fast-forward of GitHub's ref | GitHub moved while suspended: stop and reconcile |
| `lane/*` branches with open work | bare stand-in | push, one per branch | must be open PR.md work, not folded |
| issues #1-#640 | forge (seeded from the board and from lane.issuerecon) | keep their numbers; GitHub already has them | nothing to create; body and comments may need a sync pass |
| local-only issues (#641 and up, label `local-only`) | forge | **create**, get GitHub numbers | GitHub numbers differ; a map is required (section 3) |
| forge PRs (PR.md) | forge, mirrored from PR.md | draft PRs, then ready when folded | prsync titles and bodies carry lane process text (section 4) |
| issue comments and lane posts | `OUTBOX.md` files, forge comments | one summary per issue, or a comment in time order | a burst of comments; section 5 |
| labels | forge (`ensure-labels.sh` plus `lane:*`, `local-only`) | created on GitHub before the first issue | label names must match the scripts' |
| releases (nightly APK) | forge prereleases | not transferred; rebuilt by the nightly on GitHub | none |

## 2. Order of operations

1. **Dry run**, no writes: `recover_github.py` (no flags) prints the plan. It must be run
   **without the shim on PATH**, because of the `gh api user` probe in section 6:
   `env PATH=/usr/local/bin:/usr/bin:/bin python3 ~/hakux-work/offline-git/recover_github.py`
2. **Labels** on GitHub: `docs/testing/jobs/ensure-labels.sh` run against GitHub, with the
   real `gh`. Done first, so no issue or PR is created with a label that does not exist.
3. **master**, then **board**: fast-forwards only. Throttled CI markers are checked first
   (the script's `hakux-ci-throttle` check).
4. **Lane branches** with open PR.md work, in batches of **at most 5 per hour**, each push
   followed by a 10-minute wait. A push starts CI on GitHub only if a workflow still has a
   `push` or `pull_request` trigger, which section 2a rules out before the first push.
5. **Issues**: the local-only issues in numeric order (section 3), then the summaries.
6. **Draft PRs** for pushed lane branches, then ready for each PR that the fold admits.
7. Record a journal line per batch. Stop on the first error.

## 2a. CI on the return: no workflow may start itself

The owner's direction (2026-10-03): GitHub receives a curated share of the work, about 10%
(master in batches, release artifacts, issue and PR summaries). The rest stays on the forge.
CI does not resume as it was. It ran, failed, queued runs and never fixed a problem. It may
come back in a diminished role, as a manual dispatch or a release gate only.

Before the first push of any batch, every file in `.github/workflows/` must be trigger-less
or `workflow_dispatch`-only. Check it with:

    grep -l -E '^\s*(push|pull_request|pull_request_target|schedule|workflow_run):' .github/workflows/*.yml

The check must print nothing. A workflow that prints is edited first, on master, in its own
commit. A returning push then cannot restart the old CI, because nothing it contains fires.

Not done in this lane: the `.github/workflows/` files are on master, outside this lane's
territory, so the edit is a lane.local decision. Until it is made, the check above is the
gate, and the batch does not run.

## 3. Local-only issues: number map

GitHub numbers its issues and PRs from one counter. The forge's #641+ numbers are local. When a
local-only issue is created on GitHub, GitHub assigns the next free number, which will not equal
the local one. Therefore:

- `~/hakux-work/forge-import/local-number-map.tsv` is the map: local number, title, created, forge
  state, and an empty GitHub-number column to fill when the issue is created. It was regenerated
  from the forge on 2026-10-03 (17 `local-only` issues, #656-#677). The first seed had 14 rows with
  placeholder titles and no #670 onward; the rest were created after `post-suspension.md` was written.
- Every reference inside issue bodies and OUTBOX text to `#641`-and-up is rewritten through the
  map before posting. A reference that the map does not cover is reported, not guessed.
- The map is append-only and is committed to the repo once the return is complete, so the
  mapping is kept for the record.

## 4. PR summaries: public text

The forge PR body is PR.md. Some PR.md files carry process commentary (for example the
"Local checks (no GitHub CI while offline)" section, and "waiting for ..." lines). The
public-text rule applies: a PR summary says what changed and why, with numbers, and does not
narrate how the lane worked. Of the PR.md files on `master`'s lane branches, 30 mention "Local checks", "offline", "OFFLINE" or
"waiting" (`git grep -l -E 'Local checks|offline|OFFLINE|waiting' -- 'docs/lanes/*/PR.md'`, 2026-10-03).
None has been rewritten. Before a PR is created on GitHub:

- strip the `State:` line (the script does this already);
- remove the sections that describe local infrastructure (CI on the forge runner, the shim, the
  offline protocol);
- keep the `Lane/Issue/Base/Files/Prediction/Needs device` lines and the `Release note` line,
  which the nightly notes read.

The rewrite is reviewed by lane.local, not done by the script, until it has been checked on five
PRs.

## 5. Issue comments: a rate, not a burst

`recover_github.py --post` posts one comment per issue, 90 seconds apart. An issue can collect
several lane posts while the account is suspended (the OUTBOX files, not one per issue). The return posts:

- **one summary per issue**, the time-ordered entries, under the header "While the account was
  suspended ... Their posts, in order";
- at most **20 comments per hour**, and never two issues' summaries in the same 90-second window;
- **not** the forge's bookkeeping comments (`harness-status`, `[job.*]` status and sweep
  comments). They describe the forge's own state and mean nothing on GitHub.

## 6. What `recover_github.py` does, and what it lacks

It does (`offline-git/recover_github.py`, 170 lines):

- a dry run by default; `--execute`, `--post`, `--prs` are opt-in;
- checks that GitHub's `master` and `board` have not moved since the baseline
  (`github-baseline-20260929.txt`), and stops if they have;
- checks the CI throttle marker is on the stand-in's master;
- computes the push plan: master and board fast-forwards, then lane branches with open PR.md
  work; folded and untouched branches are skipped;
- writes one summary per issue to `recovery-posts/<n>.md` from every lane's OUTBOX;
- on `--execute`: removes the insteadOf redirect, fetches GitHub, pushes the plan, and writes a
  journal line.

It lacks, or gets wrong:

1. **It uses whichever `gh` is on PATH.** With the shim first (route.sh phase 3), `gh api user
   --jq .login` answers from the forge with the forge login (checked 2026-10-03: the shim returns
   `lanes` for that call), and the script reports "GitHub answers as <forge login>" and carries on. Every later `gh` call (`issue comment`, `pr list`, `pr create`) would then go
   to the forge. Fix: pin `GH=/usr/bin/gh` and refuse when `gh --version` says `forge-shim`.
2. **It creates no issues.** Local-only issues never reach GitHub; the map in section 3 is missing.
3. **It does not check the labels exist** on GitHub before creating PRs or comments.
4. **It does not sync the forge's issue bodies or comments**, only the lane OUTBOX text.
5. **Its `--prs` branch is a blind title and body copy** of PR.md, with no public-text pass
   (section 4) and no check that PR.md's `Files:` line matches the diff.
6. **The 90-second throttle has no batch cap or hourly budget** (section 5).
7. **Nothing reads the forge.** Its plan is built from the bare stand-in, which is right for code,
   but PRs closed on the forge by prsync (folded) and forge-only comments are invisible to it.

## 7. Dry-run command for the owner

```
env PATH=/usr/local/bin:/usr/bin:/bin python3 ~/hakux-work/offline-git/recover_github.py
```

Expected while the account is suspended: step 0 stops with "GitHub still refuses the account",
and nothing is changed. To see steps 1 to 4 without GitHub, add `--simulate-baseline` (test only;
it takes GitHub to equal the baseline, and the script refuses it with `--execute`).

## 8. Before the first execute

- Fix item 1 in section 6 (pin `/usr/bin/gh`), and add a test that the probe refuses the shim.
- Build the number map (section 3) and check it against `forge_import.py`'s records.
- Run the public-text pass on five PRs and review them.
- Agree the batch sizes in section 2 and section 5 with lane.local.
