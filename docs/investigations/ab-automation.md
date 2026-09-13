# Automating the per-issue A/B (issue #17)

Written 2026-09-12 by the tooling lane. Everything below marked MEASURED was
computed from dispatch result directories already on disk; no device was
touched to write this.

## What this is

About a dozen A/Bs were hand-rolled on 2026-09-12 and every one of them had
the same four steps: pick a fix commit and its parent, queue two `request.sh`
arms differing only in `--ref`, wait, compare `scores1.tsv` per capture. Three
scripts now do that:

| script | does |
|---|---|
| `docs/testing/ab_compare.py` | two result dirs in, per-capture better/worse/same table out, PASS/FAIL against a registered prediction |
| `docs/testing/ab_run.sh` | a fix ref in: derives the parent, queues both arms, waits, compares |
| `docs/testing/ab_bisect.sh` | binary search over a commit range for the first commit at which one capture regressed |

`ab_compare.py --probe DIR --capture SUITE/TEST` prints one capture's per-run
values, median and band. It exists so that only one file knows the TSV layout,
and it is the oracle `ab_bisect.sh` reads.

Nothing here touches live infrastructure. They *call* `request.sh`; they do not
modify it, `dispatcher.sh`, `run_disc.sh`, `score_sweep.py` or the tracker.

## The trap each refusal comes from

Every refusal below was a real cost on 2026-09-12, and each is a hard exit
rather than a warning.

**Totals hide regressions.** MEASURED, and reproduced as the primary test
fixture: the #48 blend A/B (`1789251491-blend48-base` →
`1789251814-blend48-fix2`) is −271,760 differing pixels overall and reads as an
unambiguous win. Per capture it is 10 better, 2 worse, and one of the two worse
is `Blend_surface/DstAlpha_ARGB8` going **from bit-exact to 98,304**. The
per-capture table is printed first; the total is printed last and labelled
advisory.

A second instance, found while testing and not previously written up:
`Texture_Framebuffer_Blit/FBToZetaAsTex` regressed **14,383 → 34,382** between
the #33 image-blit arms `b5ed87489c` and `d42a8d79bc`, inside a headline
−264,629 px (`Image_blit/BlitBeyondWidth` 284,628 → 0). The next arm,
`f1a7703876`, put it back to 14,383 exactly. So it was caught and fixed — but a
total would not have shown it either time.

**`progress_log_proof` false means the arm is absent, not zero.** MEASURED:
`1789240604b-depth-baseline` has proof false and 704 captures against
`1789238988-depth-agent`'s 1042. Refused. The same failure one level down —
per-suite capture counts that disagree between arms — is refused too, and the
message names the suites and both counts, because a suite that half-ran looks
exactly like a suite that improved.

**One binary measured twice.** The dispatcher caches builds at
`$DISPATCH_DIR/builds/$sha.apk`, so two refs resolving to one sha silently
serve one APK to both arms. Identical `apk_sha` is refused unless
`--allow-same-binary` says the point is to measure the noise floor.

**`--ref HEAD` in a queued request is a moving target.** `request.sh` already
resolves at queue time, which fixes the original incident. `ab_run.sh` resolves
both refs itself before queueing anything and passes concrete shas — and
resolves them **in the tree the dispatcher builds in** (`DISPATCH_TREE`,
default `/home/justin/hakuX`), not the caller's, because that is the tree the
APK comes out of.

The trap I expected here turned out not to exist, which is worth recording as
a negative. I predicted that a commit made in an agent worktree would resolve
at queue time and then fail to build, because `request.sh` resolves against its
own checkout. MEASURED: it resolves and builds fine, because a git worktree
**shares the object database** — `git rev-parse --git-common-dir` is
`/home/justin/hakuX/.git` for every agent worktree here. Tested by committing
this work and asking `ab_run.sh --dry-run` to use that sha: it resolved in the
dispatch tree and derived the correct parent. The check is kept because it is
cheap and it *does* fire for the remote lane — a second session on another
machine with its own checkout, per `docs/orchestration.md` — and for a typo.
Its message now says which case it is.

**The parent is derived, never typed**, and a merge is refused: a merge has two
parents, "its parent" is not a thing, and silently taking `^1` makes the
baseline the wrong side of the merge while still looking like a working
comparison. `--parent` names it explicitly.

**A dirty dispatch tree** means the binary is not the ref. Refused — but only
when a build is actually needed, since a cached APK requires no checkout. That
condition is read off `build_ref`'s real behaviour rather than assumed.

## Nondeterminism: measured, and narrower than feared

MEASURED from `1789255594-exp54-stst-correct`, ten runs of **one unchanged
APK** (`5ae2667e0f30`) over `Texture border`:

- 17 of 18 captures have band **0** across all ten runs. The device is
  bit-reproducible almost everywhere.
- `Texture_border/2D_BorderTex_SZ` alone gives
  `0 0 0 0 0 146 181 1847 2352 2430 5640` — five runs bit-exact and five not.

Two consequences, both implemented:

1. **The band is per capture, not per suite.** Flagging the whole of
   `Texture border` as unreliable would suppress 17 trustworthy captures to
   catch one.
2. **A delta no larger than the measured band is classed NOISE**, not better or
   worse, when both arms carry repeated runs. Re-slicing that real ten-run
   measurement into two five-run arms and comparing them gives 0 better, 0
   worse, 17 same, 1 noise — the flaky capture's 0 → 1,847 correctly
   neutralised against its measured band of 5,640.

That second test caught a bug in the first draft, worth recording: the draft
counted the flicker across zero as "regressed from exact" and returned FAIL for
a comparison of one binary against itself. Crossing zero now counts as a
regression only if the capture also moved outside its band, and a flicker is
reported under its own heading.

With `--runs 1` there is no band to measure. `KNOWN_UNSTABLE` in
`ab_compare.py` then applies as a warning of last resort
(`Texture_border/2D_BorderTex_SZ`, `*/DotSTR3D_*`), and a mover that is on that
list with an unmeasured band does not on its own condemn an arm — the verdict
is UNJUDGED with an instruction to requeue at `--runs 3`.

Independent corroboration of band 0, from three separate boots rather than
repeated runs: `FBToZetaAsTex` reads 14,383 → 34,382 → 14,383 across three
arms, and refs `f4e029b1d3` → `0bb035d89e` give **byte-identical** scores on
all 137 blend captures from two different APKs — those commits were entirely
inert for that disc.

## Predictions, and why a timestamp beats an honour system

Today's convention was to write the prediction into `--purpose`, so the
dispatcher stores it in `result.json`. That is genuinely good and it caught
things — but prose is not checked, and MEASURED, one of them was half wrong
without anyone noticing.

`1789253269-blend48b-fix` registered: *"Predicted 10 better / 0 worse / 127
same, exact 4 → 7, 6,511,182 → 6,136,728 px; DstAlpha_ARGB8 → 0 and
ARGB8_Add_SrcA_DstA → 47,272"*. Measured:

| claim | predicted | measured |
|---|---|---|
| `DstAlpha_ARGB8` | 0 | **0** ✓ |
| `ARGB8_Add_SrcA_DstA` | 47,272 | **47,272** ✓ |
| better / worse / same | 10 / 0 / 127 | **2 / 0 / 135** ✗ |
| exact | 4 → 7 | **6 → 7** ✗ |
| total px | 6,511,182 → 6,136,728 | **6,239,422 → 6,136,728** ✗ |

The two per-capture predictions were exactly right. The three aggregates were
all wrong in the same way: they were written against the **wrong baseline** —
`4` exact and `6,511,182` px are `eb536abd50`, the *original* #48 base, while
the arm's baseline was `0bb035d89e`, the tree with the first fix already in it.
The prediction described both fixes cumulatively; the measurement was of the
second alone. Nothing caught it, because nothing was checking.

So `ab_compare.py --register` writes a JSON expectations file that names
`a_ref` and `b_ref` and stamps the time, and the comparison:

- refuses a file whose refs are not the arms' refs — a prediction registered
  for other refs is not a prediction about this measurement, which is exactly
  the failure above;
- reports **POST-HOC** and fails if the file is newer than the results it
  judges;
- refuses to register anything with nothing falsifiable in it;
- checks `must_not_move` globs, per-capture `expect` values and
  `expect_counts`, and fails a `must_not_move` glob that matched no capture —
  a guard that matched nothing was never applied.

`ab_run.sh` registers **before queueing**, so the timestamp is evidence rather
than a claim. It refuses to run with no prediction at all; `--no-expect` opts
out and says out loud that the result will be reported UNJUDGED.

With no expectations file, a comparison reports UNJUDGED rather than PASS. A
measurement with no pre-registered prediction confirms nothing, and saying
"pass" would be the wrong word for it.

## Is a real bisect practical? Yes — and the device time was never the cost

MEASURED from `dispatch/logs/dispatcher.log`, consecutive request start times:

| arm | wall |
|---|---|
| one-suite disc incl. build (`blend48tex-base`, `-fix`, `f24-base`) | 2m15s–2m20s |
| 137-capture two-suite disc (`blend48b-base` → `-fix`) | 4m52s |
| ten runs of an 18-capture suite (`exp54-stst-correct`) | 16m35s |

The Android build is cheap because the ninja tree in `android/app/.cxx`
survives the dispatcher's detach-and-checkout, so a step recompiles only the
translation units the jump touched. The slowest gradle run in the entire day's
build logs is `BUILD SUCCESSFUL in 12s`.

MEASURED today: **215** first-parent commits touch
`hw/xbox/nv2a/pgraph/{vk,glsl}` since 2026-01-29, and **185** touch `vk`
alone (184 in a bisect range, once the good endpoint itself is excluded).
Issue #17 counted 139 on 2026-09-08, so the range grows by roughly 19 commits a
day. `ceil(log2(184))` = **8 steps**, plus 2 endpoint arms, ≈ **23 minutes** of
device time for a one-suite bisect. That is one blend A/B. It is affordable,
and issue #17's estimate of 7–8 steps at 2–5 minutes holds up.

What makes a bisect expensive is not the arms:

1. **It may converge on nothing.** Issue #17's own first application is the
   case: a bisect over the DXT decoder would have run 7–8 builds and found no
   commit, because no commit in that history broke DXT decoding — the defect
   was never a regression. `ab_bisect.sh` therefore validates both endpoints
   first and refuses a range whose ends do not straddle the defect.
2. **The oracle must be deterministic.** A binary search reading
   `2D_BorderTex_SZ` once per step takes a wrong turn with probability ~0.5 at
   every step and then names a commit with total confidence. The endpoint check
   measures the band at `--endpoint-runs 3` and **refuses to search a capture
   whose band is not zero**. Raising `--runs` does not rescue a 50/50 capture
   across eight steps; the honest move is to fix the nondeterminism or pick a
   band-0 capture in the same suite. Since 17 of 18 measured captures are
   band 0, there usually is one.
3. **It monopolises the shared build tree, not just the device.** Each step
   detaches `/home/justin/hakuX`, and anyone committing into one of those eight
   windows commits onto the wrong base — which is what the dispatcher's
   `DETACHED` marker exists to make visible. A bisect is exclusive work and the
   brief that launches one has to say so. This, not the 23 minutes, is the real
   scheduling cost.
4. **History is not monotone.** Binary search assumes one transition. A capture
   that broke, was fixed and broke again has more than one boundary. The result
   is reported as "the first commit in this range at which the capture is bad",
   with every measurement taken printed in commit order, so the claim can be
   read rather than trusted.

It deliberately does **not** use `git bisect run`. That puts the shared
checkout into bisect state for the duration, and a killed session leaves it
there — in the tree three other agents build in. `git rev-list` plus an index
is the same search with no state to leave behind, and it lets an unbuildable
commit be skipped by moving the index rather than by teaching a bisect script
the difference between "broken commit" and "bad commit".

## What these tools refuse to do

- **Score.** They read `scores*.tsv`; `score_sweep.py` remains the only thing
  that looks at a PNG.
- **Compare arms that are not comparable.** Proof missing, disc differing,
  per-suite counts disagreeing, different capture sets, one binary in both
  arms, or a result dated before the commit it claims to be of: all hard
  refusals naming the specific disagreement.
- **Average a failed arm in.** If one arm errors, `ab_run.sh` exits and says to
  requeue it rather than comparing against the arm that did complete.
- **Decide whether a mixed result should land.** They say what moved. Per
  `docs/orchestration.md`, a mixed result escalates, and if a change improves
  accuracy the trade is the owner's to make.
- **Bisect a nondeterministic capture**, or a defect not established as a
  regression.
- **Touch the device, or CI.** `--dry-run` on both shell scripts prints exactly
  what would be queued and queues nothing; that is how all of this was
  developed, with a live request and a sweep backlog in the queue throughout.

## Negatives recorded

- **`git bisect run` as specified in issue #17 is the wrong shape here** — not
  because bisection is impractical, but because the state it leaves in a shared
  tree is worse than the index it replaces.
- **A hardcoded flaky-suite list would have been wrong.** The instinct was to
  mark `Texture border` unreliable; measurement says 17 of its 18 captures are
  bit-stable and the instability is one capture wide.
- **`KNOWN_UNSTABLE` is hearsay and is treated as such.** It only applies where
  there is no band to measure, and it never overrides a measured band.
- **The worktree-ref trap does not exist on this machine.** Worktrees share the
  object database, so an agent's commit is already buildable from the dispatch
  tree. Predicted, coded against, then measured false — see above. The check
  survives for the remote lane only.
- **`--purpose` prose predictions are not a substitute for a checked file**,
  and the blend48b table above is the proof: two exact per-capture hits
  alongside three aggregate claims computed against the wrong baseline, all in
  one string, none checked.
- **The status column moves with the pixels.** 10 of the 12 movers in the
  blend48 A/B also changed `status` between `ok` and `label-differs`, because
  the label is drawn into the same framebuffer the defect corrupts. The
  transition is reported inline but it is a consequence here, not an
  independent signal — do not read it as a stale-golden finding without
  checking the label region itself.

## A request, not a change

`request.sh` resolves `--ref` against its own checkout — correct, and it fixes
the `--ref HEAD` incident. But for an agent in a worktree that is the wrong
tree: the dispatcher builds in `DISPATCH_TREE`. `ab_run.sh` works around it by
resolving there first and passing a concrete sha, which is sufficient. If
`request.sh` is ever touched for another reason, resolving against
`DISPATCH_TREE` and refusing a ref absent from it would move this check from a
wrapper into the one place every requester goes through. Not urgent, and not
changed here: `request.sh` is live infrastructure other work depends on right
now.
