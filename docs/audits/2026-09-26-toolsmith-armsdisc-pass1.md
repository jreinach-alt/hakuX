[job.cloud] Audit pass 1: PR #386 (lane/toolsmith-armsdisc), head a66d9c0ad5

Pass 1 found no HIGH or MEDIUM, only two LOWs, so the PR goes to `needs-audit-2`. The fragment passes 9 of 9 on its own and its mutant goes red.

## Scope

This pass reads the diff of `origin/master...a66d9c0ad5`:

- `docs/testing/jobs/arms.sh`: the new `disc_list()`, the `narrow` array passed to both `request.sh` calls, and `skip=`/`only=` on the list and queue log lines.
- `docs/testing/jobs/selftest.d/94-arms-disc-narrow.sh`: the new fragment and its mutant.
- Notes under `docs/lanes/dispatch-hardening/` and `docs/lanes/toolsmith/`.

## Verified

- **Both arms get the same flags.** `narrow` is built once per prediction and splatted into the base call and the fix call alike, so the two arms cannot differ on a narrowing axis.
- **An empty array is safe under `set -u`.** It is expanded as `${narrow[@]+"${narrow[@]}"}`. The plain prediction in the fixture exercises that path.
- **Comma-joining is lossless.** `request.sh` splits `--skip-tests`/`--only-tests` on commas and strips whitespace (request.sh:1047, 1055). `disc_list` strips the same way. `ab_compare.disc_axes` sorts both sides, so order cannot cause a mismatch.
- **Existing readers still work.** The log lines only append ` skip=[..]` / ` only=[..]` after `suites=[..]`, and only when a list is non-empty.
- **The failure paths are covered.** A skip whose suite `suites_for` dropped for having no goldens, or a prediction with both lists, is refused by `request.sh` at the base arm. That goes through `refused()`, which tells the lane once, and the fix arm is never queued. Before this change the same prediction would have been queued and then REFUSED by `ab_compare`, or downgraded for a delta-only prediction, after spending device time. Refusing at queue time is the better outcome.
- **Ran the fragment alone** in a scratch worktree at a66d9c0ad5, with `selftest.d/` holding only `94-arms-disc-narrow.sh`: **9 passed, 0 failed**, including the mutant check. That check confirms the skip and only predictions are REFUSED by `ab_compare.composition_notes` when the flags are removed, and that the plain prediction stays ok.

## Findings

### LOW 1: arms.sh accepts a comma-string axis that ab_compare will refuse, and the fixture hides it

`disc_list()` and `suites_for()` accept `"disc": {"only_tests": "A::x,A::y"}`. `ab_compare.composition_notes` does not: it compares `sorted(want.get(k) or [])` (ab_compare.py:1265), which sorts a string's characters. A hand-written prediction in comma-string form is therefore queued correctly on both arms and then REFUSED by the judge.

The `dnonly` leg of the fixture normalises the string itself before calling `composition_notes` (its own comment says so). As a result, "and its composition check passes" is green for a disc the real judge would refuse.

This is LOW because `ab_compare --register` writes lists, and no prediction under `docs/testing` uses the string form (grep for `"only_tests": "` / `"skip_tests": "` finds nothing).

Remedy, either:
- normalise a string axis in `ab_compare` the way `arms.sh` reads it, or
- drop the fixture's normalisation and have the `dnonly` leg use a list.

### LOW 2: "unblocks #379" needs a re-registration, and neither the PR nor the notes says so

`tiecode282-binade.json` has already been judged (REFUSED), so `$A/judged/<sha>` exists and `already_ran` returns 0 for that sha forever. The judged marker is not version-gated the way a `request.sh refused` marker is. After this folds, the same bytes will never be queued again.

lane.tiecode282 has to change the file (re-register) for the arm to run with the skip. That is a new sha, as `refused()`'s own comment says. Tell #379 that when this folds.

## Next state

No HIGH or MEDIUM → `needs-audit-2`. Pass 2 should confirm:
- whether either LOW was addressed or explicitly declined, and
- that a head rebased onto current master (this branch is 37 commits behind) still passes `94-arms-disc-narrow.sh`.
