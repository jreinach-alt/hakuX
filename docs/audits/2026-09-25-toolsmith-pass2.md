# Audit pass 2: PR #229 (lane/toolsmith) -- nxdk_vsh_tests on a handheld

Auditor: job.cloud, 2026-09-25. Verifies pass 1
(`2026-09-25-toolsmith-pass1.md`, at 71f2a0a4df) against the remediation
14612833b9 ("vsh: refuse a log.txt the previous run left").

Result: **clean. M1 can no longer occur as described; L1 and L2 fixed; L3
open (LOW, accepted). `fold-ready`.**

## M1: a run that dies before nxdk_vsh_tests starts scored as complete -- CLOSED

The pass-1 scenario, step by step against the new code:

1. Run 1 completes. `run_disc.sh` extracts with `--manifest`, reads
   `log.txt`'s FATX created time from `.fatx_times.json`, and writes it to the
   per-device ledger (`$HOME/hakux-work/vsh-last-log-$DEVICE_LABEL`; the
   dispatcher's vsh branch passes `DEVICE_LABEL`, dispatcher.sh:940).
2. Run 2 dies before `main.cpp`. The appear/miss loop ends, the HDD is
   pulled, and before extraction the ledger is copied into the results dir as
   `.previous_log_created` (the `rm -rf "$RESULTS"` precedes the copy, so the
   copy survives).
3. The extracted `log.txt` has run 1's created time. At the vsh completion
   block, `VSH_LOG_CREATED == VSH_PREV`, so `run_disc.sh` prints
   `vsh: STALE LOG` and exits 1 **before** the "Testing completed normally"
   grep that used to exit 0.
4. `vsh_score.py`'s `stale_keys` sees the same equality (`_parse(prev) ==
   start`) and returns every `Suite::*.txt` key as STALE with
   `log_stale=True`; `score()` then forces `log_completed=False`. No test can
   be IDENTICAL/DIFFERS, so `captures` in `result.json` is 0, and the run
   entry carries `log_stale: true` and `run_disc_exit: 1`.

So the A/B shape pass 1 feared (a B that cannot run reporting "identical to
A") now reports zero captures, not complete, and a non-zero `run_disc_exit`.
The TIMEOUT variant (a hung run that never reached main) exits 1 at the
TIMED_OUT check first, and vsh_score still marks everything STALE because
the ledger copy is made before that check.

Checked around it:

- The ledger only advances when an extraction yields a log time, so a failed
  pull (exit before extraction) cannot overwrite the record with nothing.
- `run_disc.sh` has `set -u`, not `set -e`, so the `$(python3 -c ...)` that
  reads the manifest cannot abort the script when the manifest has no
  `log.txt`; the empty result skips both the ledger write and the STALE check,
  and the existing INCOMPLETE branch handles the missing log.
- `echo $? > run_disc$r.rc` directly follows the `run_disc.sh` call, and the
  result writer's `basename(j)[3:-5]` maps `vsh<r>.json` to that `<r>`.
- The selftest leg drives the real `run_disc.sh` (fake adb and extractor)
  through three runs: first, replaced log, same log. Leg 3's `rc == 1` and
  "STALE LOG" assertions cannot pass on 71f2a0a4df, which has no such branch
  and exits 0 on a log that says completed; leg 2 pins that a replaced log is
  not refused, so "always stale" fails too. Full selftest on 14612833b9:
  1181 passed, 0 failed, all nine M1 legs ok.

Residual, stated and not a finding:

- **First vsh run on a device with no ledger** (including the first after the
  fold) is not protected. Pass 1 already scoped M1 to runs with a
  predecessor; the code now says so in `staleness` ("no previous-log record,
  so a log left by an earlier run is NOT detected"), which a selftest leg
  asserts.
- **False refusal** would need two runs that genuinely replaced `log.txt` to
  get the same FATX created time (2 s granularity). That needs a guest clock
  that repeats across boots; there is no vsh capture on this host to date the
  guest clock against, but the failure direction is a loud refusal (exit 1,
  every file STALE), not a wrong score, so it would surface on the first
  post-fold handheld run rather than hide.

## L1: dispatcher scored vsh runs whatever run_disc.sh returned -- FIXED

`run_disc_exit` is now recorded per vsh run in `result.json`, alongside the
new `log_stale`.

## L2: request.sh left the scratch ISO copy on interrupt -- FIXED

`trap 'rm -rf "$VSH_TMP"' EXIT` plus an INT/TERM trap that exits 130, both
cleared after the normal `rm -rf`. The refusal `exit 2` path inside that
block is covered by the EXIT trap.

## L3: pgraph `--base-iso` reads the whole image at queue time -- OPEN (LOW)

Unchanged. Correct, slow on a large image; no failure scenario. Not a fold
blocker.
