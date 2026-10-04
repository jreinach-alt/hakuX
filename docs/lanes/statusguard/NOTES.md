# lane.statusguard (#507): never publish a degraded dashboard render

## The incident, 2026-09-28 17:42 PDT

Both handhelds left USB at 17:40. The board tick's `status.sh` published a
20 KB page: "Measured 0 / 145, Benchmarked 0 / 145, Playable 0 / 50; 0 lanes;
no devices; queue not read". PAGES_MIN_GAP then held the good 17:48 render back.

## The cause, from the code

Every one of those words is what `status_html.py build` renders when
`$S/lanes.json` is missing. The titles, the devices, the queue's `constraint`
and the lane rows all come from `lanes.json`'s `first` block. With a readable
`lanes.json` the device list is never empty (one entry per `STATUS_DEVICES`),
and `constraint` is never empty. So the lane block (`status_html.py lanes`,
run under `timeout 300`) exited non-zero or was killed that tick.

Each `gh` read in `gather()` has its own 60 s timeout, so five hung reads are
enough to reach the 300 s limit. That fits the NUDGE FAILED at 17:43:10. The
tick also discarded `lanes.err` along with the rest of the output, so which
read hung is not recorded anywhere. From now on it is.

## The change

- `status_html.py page_facts(status.json)` reads what the guard compares:
  - whether `first` exists (the lane block was read), plus `board_ok`, `prs_ok`
    and the queue's constraint;
  - the device, lane-row and title counts;
  - the measured, benchmarked and Playable counts, computed the same way
    `_glance` computes them.
- `status_html.py degraded(new, old)` lists what the new render lost:
  - a read flag that went from true to false;
  - devices or titles that fell to 0;
  - all three counts at 0 where any was non-zero before.

  A count that only fell is not a loss.
- `status.sh`:
  - Keeps the lane step's exit code and how long it took. Makes its limit
    configurable (`STATUS_LANES_TIMEOUT`, default 300).
  - Writes `$S/render-facts.json` after the build.
  - `publish_pages` runs the guard first, before the unchanged and gap checks:
    - Exit 1 means refuse. It prints and logs `pages: degraded render (<lost>);
      not published` and writes `$S/pages-refused`.
    - Any other non-zero exit means the guard itself failed. That is logged and
      the page publishes anyway, so a broken guard cannot hold every page back.
  - With `pages-refused` present, the next render that passes publishes at once,
    ignoring PAGES_MIN_GAP.
  - Each successful publish copies the render's facts to
    `$S/pages-facts.json`, which is the baseline for the next comparison.
  - A lane or build step that fails, or a render with no facts, appends the
    step, its exit code, its duration and the tail of `lanes.err` and
    `status_html.err` to `$S/render-degraded.log` (capped at 2000 lines, then
    cut to 1000). This happens whatever the caller does with stdout.

## Proof

`selftest.d/99-status-degraded.sh` has its own work dir, its own gh shim and
a local bare repo standing in for gh-pages. The gh shim can hang gather()'s
`pr list --limit 300`, and `STATUS_LANES_TIMEOUT=3`. There are two measured
titles, from verdicts. It runs 5 `--pages` ticks against the real scripts, then
again against 4 mutants:

| case | real | mutant that must turn it red | mutant result |
|---|---|---|---|
| refuse: a hung tick past the gap does not replace the page | ok | guard branch `if false` | red; gh-pages reads "Measured 0 / 145 · Benchmarked 0 / 145 · Playable 0 / 50" (the incident page) |
| atonce: the next complete render publishes inside the gap | ok | `pages-refused` bypass `if false` | red; "changed, but published 0 min ago" |
| decrease: Measured 2 -> 1 publishes | ok | any decrease refused | red |
| why: log has `lanes exited 124`, the stderr line, the refusal (stdout to /dev/null) | ok | render record removed | red |

On the host the fragment takes 50 s. It is independent of every chain.

## For the next lane

- The very first publish after this lands has no baseline, so it is not
  guarded. Every publish after it is.
- The guard only protects gh-pages. The legacy #107 comment path (it runs
  until the pointer switch) still posts whatever was rendered.
- If `render-degraded.log` shows `lanes exited 124` again, the fix is a
  budget for `gather()` as a whole (skip the rest of the gh reads once one has
  timed out), not a longer `STATUS_LANES_TIMEOUT`.
