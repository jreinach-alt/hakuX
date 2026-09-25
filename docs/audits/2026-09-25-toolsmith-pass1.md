# Audit pass 1: PR #229 (lane/toolsmith) -- nxdk_vsh_tests on a handheld

Auditor: job.cloud, 2026-09-25. Diff read: `origin/master...origin/lane/toolsmith`
at 71f2a0a4df (3 commits: e2fcb882b0, 142df69716, 71f2a0a4df).

Result: **1 MEDIUM, 3 LOW. Not clean: `needs-remediation`.**

Files read in full as diff: `request.sh`, `dispatcher.sh`, `run_disc.sh`,
`make_test_iso.py`, `extract_results.py`, `ab_compare.py`, `vsh_score.py` (new),
plus the unchanged parts of `run_disc.sh` the vsh path depends on (the HDD
pull) and every caller of the two changed interfaces (`FatxFS.listdir` has no
caller outside `extract_results.py`; `patch_xbe_run_all_interactive.py` imports
`make_test_iso` only for `read_header`/`read_directory`/`SECTOR`, unchanged).

## M1 (MEDIUM): a run that dies before nxdk_vsh_tests starts is scored as complete, with the previous run's values

**Where:** `vsh_score.py` `read_log` / `stale_keys`; `dispatcher.sh` vsh
branch (ignores `run_disc.sh`'s exit status); `run_disc.sh` completion check.

The staleness guard assumes the `log.txt` it reads belongs to this run. It
takes the run's start to be `log.txt`'s FATX *created* time and calls any
`.txt` modified before that STALE. But the handheld's `hdd.img` persists
across runs (`run_disc.sh` pulls `files/x1box/hdd.img`, never resets it), and
`e:\nxdk_vsh_tests` is a fixed directory -- the PR's own comment in
`run_disc.sh` says so. `log.txt` is only replaced when `main.cpp` reaches its
delete-and-reopen. Nothing compares the log's time to when *this* run began.

**Failure scenario.** `request.sh --program vsh --runs 2 ...` (or any second
vsh request on the same device, e.g. arm B after arm A). Run 1 completes
normally. In run 2 the emulator starts and exits within seconds, before the
guest program runs (an apk that aborts on boot, an XBE load failure, a crash
in init -- any death before `main.cpp` deletes `log.txt`):

1. `run_disc.sh` sees the process vanish, prints `ran Ns`, pulls the HDD and
   extracts run 1's `log.txt` and run 1's `Suite::*.txt`.
2. Its new check greps "Testing completed normally" in run 1's log, prints
   `vsh: log.txt says Testing completed normally`, exits 0.
3. `vsh_score.py` reads run 1's log: `log_completed: true`, start = run 1's
   created time, so no file is STALE; every test is IDENTICAL/DIFFERS exactly
   as run 1 scored it.
4. `result.json` for run 2 carries full `captures`, `log_completed: true`,
   and a `staleness` note that reads as checked.

For an A/B this is the worst shape: a B binary that cannot run the program at
all reports "identical to A". The pgraph path is not exposed the same way
because its `gdir` is unique per run (`d<md5(id+r)>`); the vsh path sets
`gdir="nxdk_vsh_tests"` by necessity, so it needs a guard pgraph did not.

MEDIUM, not HIGH: it needs a run that dies before the program starts, and
the first vsh run on a device has no predecessor to impersonate. But when it
fires, the output looks fully valid and nothing flags it.

**What would close it** (lane's choice): tie the run's start to the host.
For example, record the host wall-clock time before `am start` and have
`vsh_score.py` (or `run_disc.sh`) refuse a `log.txt` whose created time is
earlier than that minus a stated guest/host skew bound. Or clear or rename
the log on the image before the run, so an old log cannot survive into this
run's extraction. Add a selftest leg with a manifest whose `log.txt` predates
the run start and all of whose `.txt` postdate the log: today that case
scores IDENTICAL/complete. The fix must make it report incomplete or
refused.

## LOW

- **L1** `dispatcher.sh` vsh branch runs `vsh_score.py` whatever `run_disc.sh`
  returned. `TIMEOUT` and `vsh: INCOMPLETE` exist only in `run$r.log`.
  `log_completed` in `result.json` covers the incomplete case except M1's.
  Recording `run_disc.sh`'s exit status in the run entry would make M1-class
  disagreements show up.
- **L2** `request.sh`: `VSH_TMP=$(mktemp -d)` holds a full copy of the base
  ISO, and no `trap` removes it. An interrupted `request.sh` leaves it in
  `/tmp`.
- **L3** `request.sh`, pgraph with `--base-iso`: every such request now reads
  the whole base image into memory (`inspect_image` on a `bytearray`) at
  queue time, only to identify the program. It is correct but slow on a large
  image. Reading `default.xbe` through `lookup` without loading the full ISO
  would do the same job.

## Checked and not a finding

- A worker running a pre-fold dispatcher against a post-fold snapshot: the
  old pgraph branch calls the new `make_test_iso.py`, which reads the program
  off the image and refuses (`carries the vsh program, not --program pgraph`).
  The request fails fast and does not hang. `request.sh`'s snapshot check
  covers the normal path.
- Suite names: the pgraph path's `${s//_/ }` rewrite is correctly not applied
  to vsh. `request.sh` and the dispatcher pass the same trimmed names, and
  `make_test_iso.py` refuses any name outside the closed `VSH_SUITES` list.
- `disc_id`: the `vsh:` prefix goes before the `iso:<tag>/` prefix, so a vsh
  id cannot equal a pgraph id.
- `ab_compare.py` refuses a non-pgraph result before it reads `runs[]`.
  `request.sh --wait` has its own `kind == "vsh"` summary.
- The stale-key naming in `vsh_score.py`: `stale_keys` and `index_tree` split
  nested `A::B::name` the same way, at the first `::`.
