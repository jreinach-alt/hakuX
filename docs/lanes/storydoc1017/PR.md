# storydoc1017: a project history page, linked from the README's More table

State: ready

Lane: storydoc1017            Issue: none
Base: master @ 6295705f20
Files: README.md, docs/HISTORY.md, docs/lanes/storydoc1017/NOTES.md, docs/lanes/storydoc1017/PR.md
Prediction: none: docs only
Needs device: no    Needs NDK: no
Selftest: none -- searched docs/testing/jobs/selftest.d/ for `public_docs`, `HISTORY.md` and "More table": no fragment reads any of the three. The 10 fragments that otherwise mention README.md/readme (e.g. 86-nightly-notes.sh, 99-cloud-lane-branch.sh) use it only as a generic fixture filename inside a synthetic throwaway repo they build themselves, never the real README or its More table.

Release note (none): a project history page, linked from the README.

## What this is

`docs/HISTORY.md` is the project's story so far -- how hakuX CE is built, including the agents and the harness
that drive the work -- at the owner's request (2026-10-17). Its text is the staged, owner-reviewed copy, copied
byte for byte from `/home/justin/hakux-work/briefs/storydoc1017.HISTORY.md` (sha256
`47884a90112be7f4b462c9b7b6ec5cc3bb440d56c07eda351fecfe425f69b9bb`, verified against the copy in this PR). Nothing
in its text was edited by this lane.

README.md's `## More` table gets one new row, directly after Roadmap:
`| [How we got here](docs/HISTORY.md) | The story of hakuX CE so far |`. Nothing else in README.md changed --
the `_Last updated_` line is not bumped, since adding a link is not a review of the whole document.

`docs/HISTORY.md` is deliberately **not** added to `docs/testing/public_docs.txt`: that list drives a 14-day
freshness alarm (`docs/testing/docs_freshness.py`) for pages that describe the current build's state. This page is
a dated narrative of how the project got here, not a description of the current build, so the alarm would flag it
on a schedule it has no way to act on.

Checked `docs/testing/title_registry.py`'s README reader (`page_playable_counts`, ~line 879-885): it applies two
regexes, `\[(\d+) Playable games\]` and `(\d+) games rated Playable\.`, to README.md's full text. The new row's
text contains neither phrase, so it cannot match either regex before or after this change -- confirmed by reading
the regexes against the new text, not by re-running the tool.

`docs/lanes/storydoc1017/NOTES.md` has the Step 0 already-tried table.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
