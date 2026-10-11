# failgate: a failed or unproven run goes for identification, not a re-run (#433)

State: ready

Lane: failgate            Issue: #433
Base: master @ 4a3308a21e (merged into the branch)
Files: docs/lanes/failgate/NOTES.md, docs/lanes/failgate/item5-wall.diff, docs/lanes/failgate/PR.md, docs/testing/hitch_report.py, docs/testing/jobs/selftest.d/89-title-verdict.sh, docs/testing/jobs/selftest.d/96-failgate.sh, docs/testing/jobs/selftest.d/99-play-share.sh, docs/testing/jobs/selftest.d/99-verdict-10min.sh, docs/testing/request.sh, docs/testing/title_verdict.py
Prediction: none: harness only (no pixels move)
Needs device: no    Needs NDK: no

Release note (none): harness and verdict only

## What changed

1. **Liveness window falls back to `frames/`.** When there are fewer than three
   post-mark route-frames, `hitch_report` measures the post-mark `frames/`
   samples. Fewer than three in both: `measured: False`.
2. **An unmeasured window fails the verdict.** `window unmeasured: <reason>` is
   a failure, so a window with no frames is not Playable-eligible.
3. **Position-change test.** Consecutive post-mark samples are compared with
   `classify.motion()`. The verdict fails when the first and last samples are the
   same picture, or when more than half the consecutive pairs are still.
4. **`request.sh` admission gate.** When `failure_intake.py` is present, a
   request for a held title is refused (exit 3). `--identified <id>` admits it
   and is recorded in the request. A failing gate also refuses. No tool, no gate.
5. **Contact sheet names its sources.** Route frames and boot samples sit under
   separate headers, and each tile carries its time.

The Playable wall (item 5 in the brief) is not in this PR; its diff is
`docs/lanes/failgate/item5-wall.diff`. See NOTES.md for the replay table over
stored results and the open question about menus with frames.

## Checks

- `SELFTEST_ONLY="89-title-verdict.sh 96-failgate.sh 99-play-share.sh 99-verdict-10min.sh"`: 139 passed, 0 failed (with PIL); 138 passed, 0 failed with PIL and numpy blocked.
- The other fragments that read a verdict or go through `request.sh`: 392 passed, 0 failed (18 fragments), and the arms and handback fragments: 0 failed.
- The fixtures in 99-play-share and 99-verdict-10min carry post-mark frames when PIL is present. Without PIL a leg's only allowed failure is `window unmeasured`.
