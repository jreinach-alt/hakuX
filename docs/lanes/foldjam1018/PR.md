# foldjam1018: fix the three silent causes of the 2026-10-18 fold jam so they can't recur

State: ready

Lane: foldjam1018             Issue: none (harness defect, dispatched directly)
Base: master @ 72af9cb92c
Files: docs/investigations/foldjam1018.md, docs/lanes/foldjam1018/**, docs/testing/check_territory.py, docs/testing/jobs/selftest.d/98-foldjam1018.sh, docs/testing/jobs/selftest.d/98-foldjam1018-territory.sh
Prediction: none: analysis-only plus host-tool/dispatcher changes outside this repo; no renderer/emulator code, no device arm
Needs device: no    Needs NDK: no
Selftest: 98-foldjam1018 98-foldjam1018-territory 66-status-titles
Release note (other): none -- harness/process tooling only, nothing a player sees

Owner order 2026-10-18 ~20:40 PDT, dispatched directly (no issue): the fold path jammed for 12+ hours on
three separate, silent causes, and the owner had to ask four times to get two ready lanes folded. Scope:
process/tooling only -- no gameplay, no device, no emulator code. Full writeup in
`docs/investigations/foldjam1018.md`; what actually shipped, in order (D, then B, then A, then C as far as
it goes):

- **D** `offline_fold.py --owner-order "<reason>"` (outside the repo, `offline-git/offline_fold.py`): skips
  the harness selftest, still runs py_compile/bash -n on changed files, still requires a device run for
  emulator code, journals `checks.selftest.skipped`. This formalizes what lane.local did by hand for the
  real incident (commit `72af9cb92c`) into one command.
- **B** blacklist keyed to master sha (`offline-git/foldqueue.sh`, `host-tools/driver_tick.py`, both outside
  the repo): a selftest-failed head used to stay blacklisted forever (keyed by bare head sha); now it's
  keyed `head@master:sha` and retries once master moves past that sha. The driver's jam row says
  `blacklisted: <reason>, since <time>` instead of `watching`.
- **A** `offline_fold.py`'s `Selftest:` claim is checked against what the suite's fragments actually cover,
  not trusted. This is the one that actually explains the incident, and the brief's suspected mechanism was
  wrong: `compat1017b` didn't name a subset that omitted fragment 66 -- its PR.md declared `Selftest: none`
  outright, an unchecked "nothing applies" claim that was false (fragment 66 does exercise the file it
  changed, by basename in a comment, not by full path -- a plain "does the text contain the changed path"
  grep would still have missed it). `mentioning_fragments()` matches on full path OR basename and now runs
  against the `none` claim too, not just a named subset. Also: `master_health_check.sh` (new,
  `offline-git/`) backgrounds the full suite against origin/master after every fold
  (`foldqueue.sh` + `systemd-run`), and `driver_tick.py` raises `master-red:<fragment>` if it goes red and
  the checked sha is still live.
- **C** (partial) `docs/testing/check_territory.py`'s FREE-but-claimed message now names the exact fix
  ("release it from [free] in the same commit that adds it to [lane.X]'s files") instead of just the fact.
  The rest of item C (ready-time territory check, fold-to-running-lane notification) is spec only in the
  investigation doc -- `lane.sh` is sparsewt1017's, and the notification channel is a dispatch-ownership
  call, not mine.
- **E**: spec only, by design -- `hold.sh` is holdcap1018's, `battery_admit.py` is toolsmith's.

Testing: `docs/testing/jobs/selftest.d/98-foldjam1018.sh` and `98-foldjam1018-territory.sh` (new) ran for
real through `docs/testing/jobs/selftest.sh`, alongside a re-run of `66-status-titles.sh` to confirm no
regression from the `check_territory.py` edit -- 35 checks, 0 failed. The two new fragments mirror the
external tools' key logic inline (documented, with the staleness risk named) since `offline_fold.py`/
`foldqueue.sh`/`driver_tick.py` live outside this repo and cannot be imported by a selftest fragment.
Everything outside the repo was also verified by `py_compile`/`bash -n` plus isolated unit tests against
synthetic fixtures (`host-tools/driver_selftest.py` gained 11 new cases, all passing; its one pre-existing
unrelated failure was reproduced identically against the pre-edit backup). Nothing was run end-to-end
against the live `/home/justin/hakuX` repo or the live fold queue -- per "never run git in a tree that is
not your worktree," that is lane.local's to exercise for real.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
