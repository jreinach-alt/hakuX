# lane.crashattr outbox

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
