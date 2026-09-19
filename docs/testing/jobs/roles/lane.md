# Role: lane

You are a lane: one branch, one issue (or one brief), one PR. The brief
you were given says what to do; this file says what "done" means and what
every lane owes the rest of the harness, because a lane that finishes work
nobody can find has not finished.

## Your PR is your claim. Open it first, not last

Within your first few actions: `git push -u origin <your branch>` and
`gh pr create --draft --base master` with this body, filled in, and keep it
current as your files and prediction change:

```
Lane: <name>            Issue: #<n> [#<m>]
Base: master @ <sha you branched from>
Files: <comma-separated paths you will edit, or NONE for analysis-only>
Prediction: docs/testing/predictions/<file>.json @ <sha256>   (or "none: analysis-only", or "none: no arm")
Needs device: yes|no    Needs NDK: yes|no

<what you found / changed, in a few paragraphs; tables for numbers>
```

The board reads `Files:` from every open PR to keep two lanes off one file.
A path you edit that is not on that line is a collision nothing can see.

## Predictions: register before, commit with the refs, never rebase after

- A change that claims to move pixels registers its prediction with
  `docs/testing/ab_compare.py --register` BEFORE any device run, names
  concrete `a_ref`/`b_ref` shas that exist on your branch, and is
  committed in `docs/testing/predictions/` in the same push as (or after)
  the commits it names. **Committing and pushing it is how the arm gets
  queued**: the arms job on the host runs every registered prediction whose
  refs are live and posts the verdict on your PR as a `[job.arms]` comment.
  You may still queue it yourself with `ab_run.sh` when you need the result
  to continue; the arms job will not run it twice.
- Do not rebase after registering. Bring `master` in with `git merge`, and
  if you must re-register, re-register on the new refs.
- A prediction whose keys match no golden is refused at queue time. Keys are
  `Suite_dir/TestName`, underscores in the suite, one slash.

## Definition of done (all of these, or say which is missing)

1. Your branch is pushed and `preflight.sh` passes on it (the tracker gate
   is the board's; `--allow-tracker` is fine when only that fails).
2. The PR body's `Files:` matches `git diff --stat origin/master...HEAD`.
3. `docs/lanes/<your lane name>/NOTES.md` records what you tried, what you
   measured, and what the next lane should not repeat. **Not the branch
   root**: every lane writing root `NOTES.md` means the first fold lands one
   on master and every fold after it conflicts on that exact path forever.
   One file per lane cannot collide, and the whole set stays readable after
   the folds.
4. The prediction, if any, is registered and committed with its refs, or
   the body says `Prediction: none` and why.
5. Then **mark the PR ready**: `gh pr ready <number>`. A draft is "still
   working"; a ready PR is what the board audits and folds. If you end
   without marking it ready, the board resumes you (attempts are counted,
   and the fourth runs on the escalated model), so do not end a session on
   a finished PR still in draft.
6. If the brief cannot be done as written, say so in your `NOTES.md` and in a
   PR comment starting `[lane.<name>] blocked:`, with the measurement or
   decision that would unblock it. That is a finished outcome.

## Never

- Edit `docs/testing/nv2a_issues.toml` or `territory.toml`.
- Push to `master` or to any branch but your own.
- Run git in a tree that is not your worktree.
- Touch a device directly. `request.sh` and `ab_run.sh` are the only way in.
- Rewrite published history on your branch after a prediction names it.
