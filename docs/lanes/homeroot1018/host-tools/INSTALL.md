# host-tools -- lane.homeroot1018 (#433)

None of the three files below are in the repo; these are edited copies of
the live scripts at `/home/justin/hakux-work/host-tools/` for lane.local to
diff, review and install.

## home_page.py

Live at `host-tools/home_page.py`. `STATUS_FILES` now names
`docs/images/chart.svg` and `docs/images/chart2.svg` instead of the two
root paths, and a new `RENAME` dict sends `COPYING.LIB` to
`docs/licenses/COPYING.LIB` (consulted by `absolute()` so a relative link
to it, e.g. CONTRIBUTING.md's licence paragraph, follows the file to its
new home path). The carry-forward loop's `git ls-tree` gained `-r`: it was
flat, which only ever mattered while every `STATUS_FILES` entry was a
root-level file, and silently drops anything under `docs/` on any update
that runs without a fresh chart render (see NOTES.md, "the ls-tree bug").
`update()` still rebuilds the whole tree from scratch each run, so once
these paths are live, the next update simply stops writing the three old
root files -- no separate delete step, and nothing to do for files already
on `home` at the old paths; they age out on the first update after install.

## status_page.py

Live at `host-tools/status_page.py`. `dashboard_blobs()`'s three home-blob
keys (around line 234) are now `docs/images/chart.svg` /
`docs/images/chart2.svg` instead of the root names, matching
`home_page.py`'s `STATUS_FILES`.

## status_md.py

Live at `host-tools/status_md.py`. `block()`'s `svg` branch now links the
two inline charts as `docs/images/chart.svg` / `docs/images/chart2.svg`
instead of the root names, matching the above.

## Install

All three move together -- a STATUS.md built by the new `status_md.py`
links to paths only the new `home_page.py`/`status_page.py` write.
Install order doesn't matter (nothing imports these three until the next
tick calls them together), but install all three in the same sitting:

```
diff /home/justin/hakux-work/host-tools/home_page.py   docs/lanes/homeroot1018/host-tools/home_page.py
diff /home/justin/hakux-work/host-tools/status_page.py docs/lanes/homeroot1018/host-tools/status_page.py
diff /home/justin/hakux-work/host-tools/status_md.py   docs/lanes/homeroot1018/host-tools/status_md.py
cp docs/lanes/homeroot1018/host-tools/home_page.py   /home/justin/hakux-work/host-tools/home_page.py
cp docs/lanes/homeroot1018/host-tools/status_page.py /home/justin/hakux-work/host-tools/status_page.py
cp docs/lanes/homeroot1018/host-tools/status_md.py   /home/justin/hakux-work/host-tools/status_md.py
```

No restart needed: `status_page.py` is invoked by the host's own 15-minute
render/push cycle (`status_page.py`'s own docstring: "Rebuilt on the host
every 15 minutes and pushed here at most every 30"), and the first run
after install carries the new paths. That first post-install run only
writes fresh `docs/images/chart.svg`/`chart2.svg` blobs if the dashboard
render is fresh (not stale/degraded) at that moment; if it happens to run
degraded, the charts are dropped from that one commit and come back on
the next successful render -- same self-healing behaviour the root-path
charts had before this change (see NOTES.md, "the one-tick gap").
