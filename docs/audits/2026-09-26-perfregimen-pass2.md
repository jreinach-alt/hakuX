# Audit pass 2: PR #444 lane/perfregimen

Head verified: `aebb693f5c`. Pass 1 (`2026-09-26-perfregimen-pass1.md`, head
`5586ca27ed`) found 1 MEDIUM and 3 LOW. This pass checks that each pass-1
scenario can no longer occur, not only that a commit claims to fix it.

**Verdict: clean, so the PR goes to `fold-ready`.** M1 can no longer occur. The
three LOWs stay as pass 1 accepted them. There is one new LOW (N1).

## M1: the Thor's FAN_MAX=5 cooled less than REST when hot. Cannot occur.

**The scenario.** A default (`PERF_REGIMEN=max`) Thor soak writes fan_mode 5
(SPORT, a fixed 25000 duty). At 66-74 C, SMART (REST) would have driven
27500-29000.

**What changed.** `f4e086a5d3` moved the regimen values out of the shared tail
of `device_env` and into each serial's row in `docs/testing/devices.sh`:

- Thor (`bdc158a5`): `DEVICE_PERF_MAX=2 DEVICE_FAN_MAX=4 DEVICE_PERF_REST=0 DEVICE_FAN_REST=4`.
- Nova (`ee317437`): keeps `2/5`, as pass 1 recommended.

The shared tail no longer exports any `DEVICE_*_MAX`, so nothing after the
`case` overrides a row.

**Traced to the write.** `soak_title.sh:129` reads the four values from
`device_perf_values "$SERIAL"`. That function (`devices.sh:165`) runs
`device_env` for the serial and prints the row's values. `perf_enter` then
writes `device_perf_set "$PERF_MAX" "$FAN_MAX"`, which is 2/4 on the Thor.
Only one place sets the values, so no second copy can put 5 back.

**Checked by running it.** `docs/lanes/perfregimen/run_fragment.sh
selftest.d/84-perf-regimen.sh` at this head gave 21 passed, 0 failed. That
includes two new legs:

- `device_perf_values bdc158a5` gives fan MAX 4.
- A soak run as the Thor starts the title at 2/4 and leaves the device at 0/4.

**Mutant.** In a scratch worktree I set the Thor row back to
`DEVICE_FAN_MAX=5`. The fragment then went to 20 passed, 1 failed:
`FAIL thor: device_perf_values gives fan MAX [5]`. The guard catches the
regression pass 1 described.

**The queued pilot follows the change.** `perfregimen-pilot-thor-queued.json`
now expects `max_fan: 4`. Its prose says the pair tests the performance half
alone, and it records `amended_utc` and `amended_why` ("amended before either
arm ran"). No arm has run under either version, so this amendment does not
move a goalpost after a result.

## L1-L3: unchanged, and accepted as LOW

- **L1** (soak fps changes regimen across the fold): still true. It is bounded
  by `perf_regimen.json` in every result dir. The fold note should name the
  fold sha as the regimen boundary.
- **L2** (a serial not in `device_env` runs at the device's own modes): still
  true. It fails safe and is logged (`off(no values)`).
- **L3** (`release()` worst case grows by about 82 s on a hung adb): still true.
  It only costs time when adb is already failing.

## New LOW

### N1. The PR body still describes the pre-remediation Thor

On the PR body's `Prediction:` line, the queued Thor file's sha256 is still
`8695c163...`. That is the pre-amendment blob. The file at this head hashes to
`f6028953...`. The Thor paragraph also says "fan MAX=5 is not the fan's
maximum" but does not say that MAX is now 2/4.

Nothing reads that hash mechanically. `arms.sh` hashes the file itself and
skips soak predictions (`arms.sh:827`), and the pilot is queued by hand with
`request.sh`. So the only failure is a reader who compares the body against the
file and finds they disagree. The next lane edit to the body should fix it.
