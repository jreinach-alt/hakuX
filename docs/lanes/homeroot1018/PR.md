# home branch root: move chart.svg/chart2.svg/COPYING.LIB under docs (#433)

State: ready

Lane: homeroot1018             Issue: #433
Base: master @ f98feca3ba6a71046ae496df242ac88492478396
Files: docs/lanes/homeroot1018/**, docs/testing/jobs/selftest.d/81-home-root.sh
Selftest: 81-home-root
Prediction: none: harness/host-tools change, no device or pixel claim, no emulator arm
Needs device: no    Needs NDK: no

Release note (none): host-tools/docs-only; nothing a player sees changes.

The `home` branch's root carried `chart.svg`, `chart2.svg` and
`COPYING.LIB` beside its markdown files (owner 10-18: looks sloppy). This
moves the two charts to `docs/images/` and the licence text to
`docs/licenses/`; `LICENSE` and `COPYING` stay in the root. After the
change, home's root is exactly `.github`, the markdown files, `COPYING`,
`LICENSE` and `docs` -- confirmed by building a `home` tree with the
edited `home_page.py` in a scratch clone (never the real offline mirror,
never pushed; `home` is pushed by the home tick, not this lane).

`home_page.py`, `status_page.py` and `status_md.py` are not in this repo
(they run from `/home/justin/hakux-work/host-tools/` on the host); edited
copies are at `docs/lanes/homeroot1018/host-tools/`, following
`statuspage1013`'s pattern, with the exact diff/install commands and the
reasoning for why no restart is needed in `host-tools/INSTALL.md`.

Also fixes a real bug found by testing, not review: the carry-forward
logic that keeps an unchanged chart across an update with no fresh render
used a flat `git ls-tree`, which only lists top-level entries. Harmless
while the charts lived at the root; once their path is nested under
`docs/images/`, a flat `ls-tree` can never find them, so every update
without a fresh dashboard render would silently delete both charts from
the tree. Fixed by adding `-r`. One accepted (not engineered around)
consequence remains: if the very first post-install update happens to run
on a stale/degraded render, that one commit has no charts at all --
self-heals on the next successful render, ~15-30 minutes later. Full
account, including the one real bug and the accepted gap, in NOTES.md.

Tested at three levels: a hand-built stub against scratch clones of the
real offline git (caught the `ls-tree` bug); a real end-to-end render
(`docs/lanes/dash432/fixtures/run_fixture.sh`) fed through the edited
`status_md.py` and `home_page.py`; and the `81-home-root.sh` selftest
fragment (claimed on the board before creation), 9/9 green in isolation
(`SELFTEST_ONLY="81-home-root"`), including 4 mutants each confirmed to
turn a case red. Full account in NOTES.md.

Does not touch README.md (lane.readme1018's territory) or any ledger,
compat or Wall surface.

See docs/lanes/homeroot1018/NOTES.md for the full account.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
