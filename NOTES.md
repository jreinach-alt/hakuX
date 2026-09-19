# lane.armsskip — a structural skip must reach the lane

## The defect

`docs/testing/jobs/arms.sh` had two rejection paths and only one of them spoke.

- `refused()` — a `request.sh` refusal — wrote `$WORK/arms/skipped/<sha>` **and**
  posted `[job.arms] REFUSED` on the lane's PR.
- `skip()` — every structural refusal (no `a_ref`/`b_ref`, `a_ref == b_ref`, a
  ref that does not resolve, a `b_ref` that is not a live ancestor, a soak, no
  suite with goldens) — wrote the marker and said nothing at all.

Measured on PR #115: a cloud session registered
`undersized-pitch-swizzle-layout.json` with English prose where the `a_ref`
belonged ("4129a349e6 with xemu.toml [display] renderer = OpenGL"). The job
refused it at 04:29:32Z on 2026-09-19 and has refused it every 30 minutes
since. Nothing on the PR mentions it. The lane believes it has an arm running.
A cloud lane has no host disk, so for it the marker does not exist at all.

## What was built

`skip()` now records **and** tells; `mark()` is the record-only half that
`refused()` uses, because `refused()` posts its own, richer comment with
request.sh's stderr in it and must not get a second one.

The comment is `[job.arms] SKIPPED: ...` carrying the marker's own reason
verbatim, posted on the lane's PR via the existing `pr_for()`, falling back to
the issue via the existing `post()` for a master or host-registered prediction.

## The one design decision worth arguing about

The obvious implementation is "the marker's existence is the record that it has
been said" — which is what `refused()` does. **That would have exempted exactly
the two markers this was written for**, both of them written by a version that
told nobody, one of them #115's. This file has already made that mistake once:
`already_ran`'s retry was keyed on an `arms=` stamp introduced by the same
commit as the retry, so the single refusal it existed to clear took the `else`
and was skipped forever (see the comment block at `already_ran`).

So the marker holds the reason and a separate `told=` line holds the
announcement, and an unstamped structural marker is announced on the next tick.
`tell_skip()` is therefore also called on the `already_ran` path.

**What bounds that backlog** is not the 131 predictions on disk and not the 38
behind the watermark — history is counted and `continue`d before any `skip()`
runs and leaves no marker. The backlog is exactly the files under
`$WORK/arms/skipped`, i.e. everything `skip()` and `refused()` have ever
written. On the day this shipped there were two:

```
3236c83efc10  master:docs/testing/predictions/tier81fix-timetofull.json: no suite with goldens in its keys or disc
d8522a7e87f7  lane/cloud-109:docs/testing/predictions/undersized-pitch-swizzle-layout.json: a_ref 4129a349e6 with xemu.toml [display] renderer = OpenGL does not resolve
```

The first goes to its issue, the second to PR #115. That is the whole first
tick's traffic.

`told=nowhere` is written when there is no open PR and no `issue` field, so a
permanently unpostable marker does not log a failure every 30 minutes. A
genuine post failure is *not* stamped, so it is retried on the next tick.

## The check, and that it fails against the code it replaces

Five new checks in `selftest.sh` under
`== arms.sh: a STRUCTURAL skip reaches the lane too, exactly once`, using PR
#115's exact registration shape. Against `origin/master:arms.sh` (restored into
the tree, new selftest kept) the five that pin the new behaviour fail; against
this branch all pass. See the PR body for the two runs.

Three of the checks are must-not-move and pass both ways, which is the point of
them:

- a `request.sh` refusal is not *also* told as a structural skip;
- a second tick does not tell the same marker again;
- a **broken** prediction behind the watermark is neither marked nor
  announced. Its `a_ref` is prose too, so it would skip structurally if the
  watermark did not fence it first — that is the 38-comments-in-one-tick guard.

## What the next lane should not repeat

- `selftest.sh` is not "seconds" on this host any more: each `arms.sh` tick
  re-runs `collect()`, which `git cat-file`s every prediction on master and on
  every live `lane/*` branch, plus a network fetch. The whole file takes minutes
  and my four extra ticks are a small part of that. If it needs to be fast,
  cache `collect()` per tick rather than trimming checks.
- Do not edit a job script while `selftest.sh` is running against it. Bash reads
  a script lazily by byte offset and each tick re-execs it; an edit mid-run
  invalidates the run (and can corrupt an in-flight tick). I did this once and
  had to restart.
- `status.sh` prints a skipped marker with `cat`; the appended `told=` line
  joins the preceding line as a lazy markdown continuation, so it reads as one
  row. Nothing to fix there, but do not be surprised by it.
</content>
