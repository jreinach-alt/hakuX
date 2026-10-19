# foldjam1018: fix the three silent causes of the 2026-10-18 fold jam so they can't recur

State: ready

Lane: foldjam1018             Issue: none (harness defect, dispatched directly)
Base: master @ f3eb1122b0
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
- **A, found by this PR's OWN first fold attempt (investigation doc section 6)**: item A's widening correctly
  pulled `51-dispatch-hardening.sh` into this PR's `SELFTEST_ONLY` run (it mentions `check_territory.py`, a
  changed file), but 51 calls `clear_markers`/`finish_queue`, which are only DEFINED in `50-arms-requeue.sh` --
  a full suite run only works because bash sources every fragment, in order, before 51 runs. The partial run
  never sourced 50, so both calls silently failed open (`command not found`, non-fatal under `set -u`),
  corrupting fixture state and cascading into unrelated FAILs/a hang instead of a clear error -- confirmed by
  blacklisting this PR's own head three times (`foldqueue.log` 00:11, and two later master shas) before
  hostops root-caused it. Fixed: `offline_fold.py` gains `shard_chains()` (reads `selftest.sh`'s own
  `SHARD_CHAINS` array, which already lists `50-arms-requeue 51-dispatch-hardening ...` as a group that shares
  state) and `close_chains()`, which unions any selected fragment's full chain into the `SELFTEST_ONLY` set
  before running -- reusing the one place this project already curates "these fragments must run together"
  instead of inventing a second notion of it. For a dependency `SHARD_CHAINS` hasn't caught up to yet,
  `fold_fail_message()` greps a failing log for the `<name>: command not found` shape this exact bug produces
  and names it plainly instead of a bare "selftest failed (rc N)".

Testing: `docs/testing/jobs/selftest.d/98-foldjam1018.sh` and `98-foldjam1018-territory.sh` ran for real
through `docs/testing/jobs/selftest.sh` (`SELFTEST_ONLY=98-foldjam1018` + `66-status-titles` re-run) -- 0
failures. The chain-closure bug and its fix were both reproduced for real, not just in unit tests:
`SELFTEST_ONLY="51-dispatch-hardening" bash docs/testing/jobs/selftest.sh` alone against this tree fails
exactly as the investigation doc describes (`clear_markers: command not found`, then hangs); running the full
13-fragment chain `close_chains` computes for that input passes clean. The two new/extended fragments mirror
the external tools' key logic inline (documented, with the staleness risk named) since `offline_fold.py`/
`foldqueue.sh`/`driver_tick.py` live outside this repo and cannot be imported by a selftest fragment.
Everything outside the repo was also verified by `py_compile`/`bash -n` plus isolated unit tests against
synthetic fixtures (`host-tools/driver_selftest.py` gained 11 new cases, all passing; its one pre-existing
unrelated failure was reproduced identically against the pre-edit backup).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
