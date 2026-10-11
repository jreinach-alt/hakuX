# lane.crashattr outbox

## none (harness defect, dispatched directly) -- 2026-10-02 13:20 PDT

[lane.crashattr] resolved: `title_verdict.py` and `89-title-verdict.sh` were granted at 13:12 PDT once
`[lane.routedriver2]` retired. Applied the fix from the entry below, re-verified against the merged
tree (`falsify.py` 0 of 19 rows wrong, `SELFTEST_ONLY=89-title-verdict` 114/0, `preflight.sh
--allow-tracker` passed), committed, pushed, PR.md `State: ready`.

Re-judged the three already-failed 10-02 runs with the patched classifier (via `judge()` directly, not
`main()`, so no `verdict.json` on disk was touched -- that re-score is host ops'):

```
VERDICT ToeJam & Earl III: Mission to Earth nova FAIL(duration: 299 s of gameplay < 600 s screening) crash=False
VERDICT Tron 2.0 - Killer App (USA, Europe).iso nova FAIL(reached_gameplay: unconfirmed (generic route) ...) crash=False
VERDICT Tron 2.0 - Killer App (USA, Europe).iso nova FAIL(duration: 232 s of gameplay < 600 s screening) crash=False
```

All three (`1790951866-titleroutes2-46925`, `1790951914-titleroutes2-68595`, `1790953776-titleroutes2-447685`)
re-judge from `crash:true` to `crash:false`. All three still FAIL on their original non-crash reason
(duration under the 600 s screening bar, or an unconfirmed generic route) -- the fix removes a false
reason, it does not make any of them Playable. They still need a re-queue for a real screening result.

## none (harness defect, dispatched directly) -- 2026-10-02 11:02 PDT

[lane.crashattr] waiting: on a territory grant (`board-requests/crashattr.md`, 08:56 and 11:02 PDT) for
`docs/testing/title_verdict.py` (in [lane.routedriver2], whose branch has no diff in it),
`docs/testing/jobs/selftest.d/89-title-verdict.sh` ([free]) and `docs/lanes/crashattr/**`. It resolves when those
three paths are in [lane.crashattr].files on origin/board and the lane is resumed.

The fix is built and verified as `docs/lanes/crashattr/crashattr.diff`:

- A tombstone counts as hakuX's by its `Cmdline:`. A libc line counts by its pid, or by the 15-character comm in a
  `Fatal signal` line.
- Old and new differ in exactly the 4 bystander runs among 965 result dirs. The 3 media.extractor runs drop to 0
  hakuX crash lines. In the surfaceflinger run hakuX really exited, so its crash stays true.
- The 9 real hakuX crashes still crash. Each left only a nameless libc line from hakuX's pid, so a name-only check
  would have missed all of them.
- The full selftest with the diff: 120 fragments, 0 failed.
- The three 10-02 runs still fail without the crash: two are under the 600 s duration bar, and the third is on an
  unconfirmed generic route. They need a re-queue.
