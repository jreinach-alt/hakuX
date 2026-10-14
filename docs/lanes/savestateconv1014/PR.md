# savestateconv1014: R3 admits --from-state; Nova probe of the save-state design (#433)

State: draft

Lane: savestateconv1014    Issue: #433
Base: master @ a45f88b319
Files: docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py, docs/lanes/savestateconv1014/NOTES.md, docs/lanes/savestateconv1014/PR.md
Prediction: none: analysis-only so far (no device-timed arm registered yet)
Needs device: yes (Part B probe pending)    Needs NDK: no

Part A (merge lane/holdfollow1013 + finish its R3 gate): done. Merged
lane/holdfollow1013 (R3 admits `--no-record` re-hold of a known path) and
added the `--from-state` case to `r3_refusal()`: a hold started from a
captured save state does no navigation at all, so R3 admits it
unconditionally on a known-path title, stronger than `--no-record` (no
replay either). A title with no known path is untouched by this branch --
that case belongs to the state-load check itself (Part D), not R3.
`python3 docs/testing/titles/pathfind_selftest.py` passes twice (post-merge,
and again after the `--from-state` addition): "pathfind_selftest: all ok".
Mutant testing in progress, will report results and tag this ready once
complete and Part B's device probe has run (or is blocked with evidence).

Release note (none): harness/profile-gate work only, nothing device-facing
shipped yet.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
