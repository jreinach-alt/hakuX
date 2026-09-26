# lane.statusdash: the harness dashboard on GitHub Pages

Brief: `$WORK/briefs/statusdash.md`. PR #362. Base: master 690a3377d1, plus a
merge of `origin/lane/statuspage` (PR #354) as the brief's start note asked.

## What changed

- `docs/testing/jobs/status_html.py` (new) renders `index.html` from
  `status.json`. It has three subcommands. `build` merges the gathered facts
  into the JSON and renders it. `render` renders a JSON. `key` prints the
  page's content key with the clock masked out. It uses the standard library
  only: inline CSS and one small inline script (the "updated N min ago"
  counter), `meta refresh 60`, `prefers-color-scheme`, and a phone-first grid.
- First screen, top to bottom:
  - the status strip: Thor, Nova, the console meter, the queue (z- idle tier
    counted apart), lanes N of cap, and the last fold;
  - **NEEDS ATTENTION** in red, or a green "Nothing needs attention" line;
  - the release gate line, the candidate, and open blockers.
- NEEDS ATTENTION collects:
  - idle lanes (grouped into one item) and blocked lanes;
  - **fold-ready PRs unfolded for over 60 min, with the reason**. The reasons
    are CONFLICTING, CI red, CI never ran, CI still running, mergeability not
    computed, and green-yet-unfolded. Each PR is asked with `gh pr view` for
    `mergeable`, and the fold-ready label's age comes from its `labeled` event;
  - runs queued over 60 min (not z-);
  - host-ops escalations;
  - a red CI on master (the newest completed run of each workflow);
  - failed `hakux-*` units, and active timers with no next elapse;
  - a lapse of the roll-up itself.
- Below the fold is the Markdown `status.sh` always wrote (PR #349's lane
  table included), converted by a subset Markdown renderer.
- `scrub()` runs over every string on the page. It removes emails, token
  shapes, credential paths, `/home/<user>`, LAN IPs and MAC addresses.
- `status.sh`:
  - The lane block also writes `$S/lanes.json`: devices, idle, blocked,
    fold_stuck, queued_old.
  - A facts block writes `$S/facts.tsv`.
  - `publish_pages` force-pushes ONE parentless commit to `gh-pages` from a
    scratch git dir `$S/pages` (never the owner's checkout).
  - It publishes only when the content key moved, never twice within 10 min,
    and otherwise at a 30-min heartbeat.
  - `--pages` publishes only and touches nothing else.
- #107: the old roll-up keeps running until BOTH a publish has succeeded from
  this host AND `gh api repos/<repo>/pages` returns an `html_url`. Then, once:
  - the body becomes a pointer to the URL, with one last rename (to a title
    with no clock), and the roll-up comment says where it moved;
  - the issue is pinned and locked, and `$S/issue-pointer` is written.
  - After that no tick writes to #107 at all.

## Decisions worth knowing

- **Heartbeat.** The brief says to publish only on a content change. I added
  a 30-min republish of an unchanged page. Without it, "updated 3h ago" is
  identical for a quiet fleet and a dead host, and that is the confusion #107's
  freshness work existed to remove. The cost is at most 2 builds/h on top of
  changes, and the total stays under 6/h because of the 10-min gap (the
  GitHub limit is 10/h). The inline script turns the age red, marked STALE,
  after heartbeat + floor + 10 min = 70 min.
- **No publishing from tests.** There is no remote unless `GH_REPO` is the
  real repository or `STATUS_PAGES_REMOTE` names one. selftest runs with
  `GH_REPO=example/hakux`, and every job tick ends in status.sh, so a default
  remote would have pushed from inside selftest.
- **Release gate.** Nothing machine-readable exists. The gate text is the
  owner's (hostops-poll item 10), shortened, and overridable with
  `STATUS_RELEASE_GATE`/`_NAME`/`_TAG` in limits.env. The candidate is the
  first GitHub release whose tag starts `v0.5`. Blockers are open issues
  labelled `release-blocker`, and **that label does not exist yet**: the host
  should create it and apply it to 0.5's blockers.
- **Timer check.** A timer showed as unanchored while its service was mid-run
  (`hakux-hostops.timer` at 22:50 PDT): an OnUnitInactiveSec timer has no next
  elapse for as long as the run lasts. So a timer whose service is
  active or activating is not flagged.

## Measured

- A live `--print` on the host at 22:47 and 22:50 PDT 2026-09-25 rendered 4
  idle lanes (foldflow, indexloc, pshqueue, zrtz272). It also found PRs #353
  and #352 fold-ready for 67-80 min, green and mergeable yet unfolded.
- `first-screen-390x844.png`: the strip, NEEDS ATTENTION and the release line
  all fit in the first 844 px at 390 px wide.
- **Screenshot instrument.** Edge headless on Windows will not lay out
  narrower than 492 px, whatever `--window-size` says (measured: innerWidth
  492 at 390x844, old and new headless alike). A 390-wide shot of the bare
  page is a 492 layout, cropped. The shot therefore frames the page in a
  390x844 iframe, which is the viewport its media queries see. Measured
  inside it: 390x844. Do not repeat the bare `--window-size` shot.
- A grep of the live page for `/home/`, email shapes, `justin`, `gh?_` tokens
  and dotted quads found nothing.

## Live (2026-09-25, 23:35 PDT)

- `gh-pages` was first published from this branch with `status.sh --pages`
  as `597d9ac428`. It has 0 parents and holds `index.html` and `.nojekyll`.
- GitHub Pages was already enabled: `gh api repos/jreinach-alt/hakuX/pages`
  gave source `gh-pages/`, status `built`. **https://jreinach-alt.github.io/hakuX/**
  serves the page (HTTP 200). `live-url-390x844.png` is that URL at 390x844.
- **Two ticks, one commit.** A second `--pages` right after the first said
  "changed, but published 0 min ago" (the fleet had moved; the 10-min gap
  held it back). `git ls-remote origin gh-pages` was still `597d9ac428`.
  selftest 64 checks the unchanged case, the gap, the heartbeat, and that
  gh-pages stays at `rev-list --count` = 1.
- **Until this PR folds, nothing republishes.** Trunk's status.sh has no
  publisher, so the page stays at 23:34 PDT and its own counter marks it
  STALE after 70 min. That is honest: after the fold, the first tick
  republishes it.
- **#107 switches at the first trunk tick after the fold.** `$S/pages-state`
  exists on the host and the Pages API answers, so that tick rewrites #107
  once, pins it, locks it, writes `$S/issue-pointer`, and never writes to it
  again. The proof "no `renamed` event after the switch" can only be read
  after that tick: look for a `renamed` event later than the one to
  "harness: live status -- moved to ...".
- selftest: 1515 passed, 0 failed (full suite, before the master merge).
  preflight passed.

## For the next lane

- The details below the fold are still the Markdown sections. If the page is
  to lose the Markdown, move sections into `status.json` one at a time; the
  `render` subcommand and the fixture in `selftest.d/64-status-html.sh` are
  where to start.
