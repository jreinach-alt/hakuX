# handback.sh: resume a draft once per new VERDICT, not once per new head

Lane: handbackstrand            Issue: none (harness defect, dispatched directly)
Base: origin/master
Files: docs/testing/jobs/handback.sh, docs/testing/jobs/selftest.d/99-handback-strand.sh,
docs/lanes/handbackstrand/**
Needs device: no. Needs NDK: no. Prediction: none. This is harness work: the
proof is the selftest fragment, mutants, and a falsification run against the
old handback.sh.

## The defect, measured 2026-09-25 on PR #245

A draft PR labelled `verified` or `regressed` gets the cause
`draft-strand-arm`, which means "the arm this lane was waiting for has been
judged" (handback.sh:109, :481). The once-only marker for any cause is
`$H/done/$label-$pr-$head` (:625). That key is the **head sha**.

So a lane that reacts to a verdict by pushing gets resumed again, with no new
verdict, the next time handback runs. Registering a replicate, committing
NOTES, and merging master all make a new head. Each resume counts toward
`DRAFT_STRAND_MAX` (3), and at the cap the PR is labelled
`blocked:needs-owner`.

lane.vshnobegin242 on #245:
- It got a single-run FAIL (4 of 403) and registered a 3-run replicate to
  supersede it, which is correct.
- It was strand-resumed at 16:10Z, at 16:29Z (a manual handback run), and at
  16:32Z (after its replicate push).
- At 16:42Z the PR was labelled `blocked:needs-owner` while its replicate was
  queued on the Thor. The host cleared it by hand.
- handback now also runs every 10 minutes from a host timer
  (`hakux-handbackpace`), besides after every fold, so the loop closes faster.

## The job

1. **Key `draft-strand-arm` on the verdicts, not the head.** A strand-arm
   resume is due once per new set of judged verdicts for the branch's
   predictions: the `(prediction sha, verdict)` pairs `arms.sh` has judged for
   that branch. Read them the way `arms.sh state <branch>` does; do not
   re-derive verdicts.
   - A new head with no new judged verdict is not new information, so do not
     resume.
   - `draft-strand-quiet`, the clock-based cause, keeps its current key.
2. **Do not strand-resume a lane whose own arm is in flight.** If a request for
   the branch is in `$DISPATCH_DIR/queue` or `running`, the lane is waiting on
   it. Log it once per request id, and do nothing else.
3. **Keep the cap, the attempt bookkeeping and every other cause unchanged.**
   The cap still bounds a lane that really is looping on new verdicts.

## Proof

- **`selftest.d/99-handback-strand.sh`**, built on `99-handback-draft.sh`'s
  shims. A draft labelled `regressed`:
  - (a) the verdict lands: one resume;
  - (b) the lane then pushes a new head with no new verdict: **no resume**;
  - (c) a second verdict is judged (the replicate): one more resume;
  - (d) a request for the branch sits in `queue/` or `running/`: no resume, and
    one log line;
  - (e) the quiet cause still resumes on the clock, as today.

  Assert on the calls the shims record, and on output words, not only on exit
  codes. Use three candidate verdict sets where one must be chosen, so the
  right one sits in the middle.
- **Mutants, each red:**
  - key on the head again, so (b) resumes;
  - drop the in-flight check, so (d) resumes.
- **A falsification run** of the fragment against the real old handback.sh:
  - do it in a scratch worktree at `origin/master`; never swap the file in
    place, and stage by name;
  - (b) must be red for the reason this brief exists: the old code resumes on a
    new head.
- `bash docs/testing/jobs/selftest.sh`: all green, with the totals in the PR
  body.

## Do not

- **Touch `arms.sh`, `fold.sh` or the `regressed` computation.** lane.shadetie224
  proposed on PR #252 dropping a FAIL once the branch no longer touches the
  arm's files. That is a different rule in `arms.sh` (lane.toolsmith's), and it
  is not this lane's.
- **Change `DRAFT_STRAND_MAX`.**
- **Trigger CI as a self-check.**

## Done when

- The fragment and mutants are green and red as stated.
- The falsification reds are recorded in NOTES.
- The PR carries the lane template with its `Files:` line.
- Preflight passes, and the PR is marked ready.
