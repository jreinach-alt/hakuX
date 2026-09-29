# Audit pass 2: PR #611, lane.affinitybatt (lane/toolsmith)

Verifies each pass-1 scenario in `2026-09-29-toolsmith-pass1.md` against the
remediation commit `4336ee7157` (affinity.py, its NOTES.md, and
`selftest.d/99-affinity-battery.sh`). Diff read against pass 1's head
(`b8082131cf`). `battery_admit.py` is untouched by the remediation, matching
pass 1's "not findings" (it was never the defect).

## M1: rule 3 read mutable state, so a pair could split across the claim window

Fixed. `_battery_alt` now takes `commit`, wired `commit=notes` at all three
call sites (the explicit-pin fallthrough, rule 2b's queued-sibling
fallthrough, and the rule-3 hash pick) -- pass 1's suggested remedy was to
apply the one-way rule wherever rule 3 can flip, not only at the incident's
call site, and all three now carry it.

The first claim to decide a move for key K writes `moves/<key>.battery.json`
naming the target and K's ids; every later reader for K follows that record
rather than re-deriving from the live level files, and gives it up only when
its own named target refuses K (a refusing device cannot claim, so no
claimable flip remains) or none of its ids is still queued or running. Traced
against pass 1's own five-step scenario: at step 2 the thor's claim of arm A
commits `to: thor` before the battery gate's dumpsys read begins (the
window pass 1 found starts after the affinity decision, and the commit
happens inside the decision, not after the gate). At step 3, the nova
crossing 49.6 no longer matters: `_battery_alt` for arm B finds the kept
move, sees the thor not refusing, and returns thor without consulting the
nova's level at all. The split pair pass 1 walked through cannot occur.

Ran `selftest.d/99-affinity-battery.sh` directly (`docs/testing/jobs/selftest.sh`
with `SELFTEST_ONLY=99-affinity-battery`, on this host): 35 passed, 0 failed.
Two checks reproduce pass 1's scenario directly: "M1: the nova's level
crosses its need mid-claim; the pair still goes to the thor" and its
separating control, "M1 (the check separates): with no kept move, the same
state sends the pair back to the nova" -- confirming the fixture would have
shown the split on the pre-remediation code and does not on this one. A
further four checks cover the remedy's own edge cases: the move retiring
when its target refuses, a claim that retires it removing the file, a kept
move naming none of the key's live ids being re-derived, and a question
(`notes=False`) never writing one. CI on the PR's head (four selftest shards,
two builds) is green, which runs this fragment along with the rest of the
suite.

The remaining gap pass 1 did not ask about -- the instant between a claim
computing the move and writing it -- is named in both the code comment and
NOTES.md as the same kind of gap rule 2's docstring already accepts
(rename-to-owner-write); it is not the ~30 s dumpsys-read window M1 found,
and pass 1's own downside bound (one wasted pair, caught by the confound
re-run) would apply to it if it ever fired.

**M1 no longer occurs.**

## L1: after a move, the refusing device's record never went stale

Addressed, as pass 1 asked ("worth one sentence in the comment"): the
comment and NOTES.md both now state the asymmetry -- a refusing device is
judged on the level it refused at once its reading goes stale, and after a
move it is not offered the key again, so an idle refuser that has recharged
keeps passing the key on until other work refreshes its level. Cost is
delay, as pass 1 found; nothing else changed here.

## L2: `_key_ids` still loads every queued/running request per affinity call while a refusal exists

Not addressed. Quality-only per pass 1; the remediation did not touch this
path's cost (the move-record read path uses it too, unchanged complexity).
Nothing further asked of this PR here.

## L3: selftest proof was local only

CI is now visibly green on the remediation's head (build x2, selftest x4,
all pass) -- the gate of record pass 1 named. Nothing further asked.

## Verdict

Clean: M1 (the only MEDIUM) no longer occurs, verified by direct trace
against pass 1's own scenario and by re-running the fragment that encodes
it, with a control showing the fixture would have caught the pre-remediation
behavior. L1 was fixed; L2 and L3 were LOWs pass 1 did not require action on.
`needs-audit-2` -> `fold-ready`.
