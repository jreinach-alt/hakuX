# pagesfix1018: fix the stale `check --pages` falsifier fixture

State: ready

Lane: pagesfix1018                Issue: #433
Base: master @ f473f6b4c4
Files: docs/lanes/pagesfix1018/**, docs/lanes/titledb1014/fixture/pages_check_falsifier.py
Prediction: none: harness defect, no device-facing behavior change to predict
Needs device: no    Needs NDK: no

`docs/testing/jobs/selftest.d/66-status-titles.sh` runs
`docs/lanes/titledb1014/fixture/pages_check_falsifier.py` as part of the full
`selftest.sh` suite and requires its output to start with `PASS`. The
fixture (written 2026-10-14, three days before `title_registry.py` gained
`readme_has_numberless_line()` on 2026-10-17) wrote README.md's Playable
line in the old NUMBERED form, which can never match the numberless line
`home_page.py` now requires -- so the "every page agrees" case always
FAILed with `exit=3`, regardless of whether the counts actually agreed.

Reading the current `check --pages` code (not just the brief's diagnosis)
showed the drift was larger than the README text: README's check changed
from a numeric comparison to a boolean exact-line-format check, and
`page_playable_counts()` now has 4 entries (status page, COMPATIBILITY.md
header, COMPATIBILITY.md table rows, Wall), not the 6 the old fixture
assumed, with no `"README.md (bullet)"` label at all. Both of
`66-status-titles.sh`'s assertions on this fixture (PASS when every page
agrees; names the one page a mutant disagreed on) were broken, not just
the one the brief named.

Fixed `pages_check_falsifier.py`: `write_pages()` now writes README.md's
exact numberless line (matching `README_NUMBERLESS` byte-for-byte, read
from `title_registry.py` rather than guessed); `main()`'s assertions now
expect 4 `"matches the table"` lines plus the numberless-line confirmation
on the agreeing case, and the mutant breaks the numberless line's exact
text (the only way README can now disagree) rather than a bullet number,
expecting the real `"the Playable line is not the numberless form
home_page.py rewrites"` line with the other 4 pages still agreeing.
Nothing else in `write_pages()` changed -- the other three pages' regexes
in `page_playable_counts()` still match the fixture's existing output.
`title_registry.py` and README.md: not touched.

Ran the fixture directly against this repo (PASS, both the agreeing and
mutant cases print the right lines) and the full `selftest.sh`, all 4
shards to completion: 290 + 1021 + 1219 + 1203 = 3733 passed, 0 failed
across all 153 fragments. `66-status-titles.sh` (shard 3/4) shows `ok
check --pages passes when every page agrees and fails naming the one page
a mutant disagreed on`. This is the same fragment/assertion lane.devpushro1018
reported as the one pre-existing failure in its own full-suite run just
before this lane started (3732 passed, 1 failed) and explicitly left
untouched as out of its scope -- confirms this was the harness defect
blocking folds on every lane touching harness files today, and it is now
closed.

Release note (none): harness self-test fixture only, no emulator or app
behavior change.

Selftest: 66-status-titles

🤖 Generated with [Claude Code](https://claude.com/claude-code)
