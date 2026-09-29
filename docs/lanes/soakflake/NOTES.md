# lane.soakflake (#600): the soak probe checks lost a poll to whole-second rounding

## Cause

`soak_title.sh`'s hold loop (near line 916) is

    while [ "$s" -lt "$SECONDS_TO_HOLD" ]; do
        sleep "${SOAK_POLL_S:-5}"; s=$(( $(date +%s) - t0 ))
        ...
        alive; r=$?

`s` is read in whole seconds, AFTER the poll sleep and BEFORE the probe, and
the loop test uses that value. So a probe never skips once its iteration has
started; what is lost is the next iteration. The fixture held 2 s with a
0.2 s poll. If the first `sleep 0.2; date` ends two second-boundaries after
`t0` (1.0 s or more of real time when `t0` is read late in its second, 2.0 s
at worst), iteration 1 reads `s=2`, probes once (`up`), and the loop ends.
The `fail` at scenario line 2 is never read, so run.log says
`adb_failures=0`.

A correction to the brief's model: a slow probe (a slow fake `ps`) does NOT
reproduce it, because the clock is read before the probe. The stall has to be
in the poll sleep or the `date` after it, i.e. the scheduler, which is what a
loaded host gives.

Every check that needs a second or third probe is exposed, not only the one
that failed on master 20f072b240:

| check | probes needed | hold-loop iterations |
|---|---|---|
| `up fail up`: adb_failures=1 | 3 | 2 |
| `up up down`: a real exit is seen | 3 | 3 |
| `up fail fail fail up`: adb_failures=3 | 5 | 2 |
| mutant (one failure is an exit) caught | 2 | 2 |

## Reproduction

A `sleep` shim ahead of `/bin/sleep` on PATH stalls the FIRST `sleep 0.2`
each `soak_title.sh` process makes (only the hold loop sleeps 0.2 s; its
parent's cmdline names soak_title.sh), then runs the unchanged fragment with
`SELFTEST_ONLY=89-title-verdict`:

    if [ "$*" = 0.2 ] && tr '\0' ' ' < /proc/$PPID/cmdline | grep -q soak_title.sh \
       && mkdir "/tmp/soakflake-stall.$PPID" 2>/dev/null; then
        exec /bin/sleep "${SOAKFLAKE_STALL:-2.05}"
    fi
    exec /bin/sleep "$@"

A 1.1 s stall reproduces the host's line exactly, phase-dependent (the
`up up down` and 3-failure scenarios survived that run):

    == soak_title.sh: one failed adb probe is not a guest exit
      ok   one failed probe did not end the soak
      FAIL adb_failures=1 missing from run.log: adb_failures=0
      ...
      FAIL mutant SURVIVED: treat one adb failure as an exit

A 2.05 s stall is deterministic. Old fragment (base 170a21df37):

    == soak_title.sh: one failed adb probe is not a guest exit
      ok   one failed probe did not end the soak
      FAIL adb_failures=1 missing from run.log: adb_failures=0
      ok   the soak held to its deadline
      ok   the route was started and stopped with the hold
      FAIL a real exit was not seen
      FAIL three failed probes: adb_failures=0
    == soak_title.sh mutant: treat one adb failure as an exit
      FAIL mutant SURVIVED: treat one adb failure as an exit
    selftest: 77 passed, 4 failed, PARTIAL: 1 of 106 fragments

New fragment, same shim:

    == soak_title.sh: one failed adb probe is not a guest exit
      ok   one failed probe did not end the soak
      ok   adb_failures=1 is written to run.log
      ok   the soak held to its deadline
      ok   the route was started and stopped with the hold
      ok   a real exit (ps works, no xemu) still ends the soak
      ok   three failed probes are unknown, counted, and keep holding
    == soak_title.sh mutant: treat one adb failure as an exit
      ok   mutant caught: treat one adb failure as an exit
    selftest: 81 passed, 0 failed, PARTIAL: 1 of 106 fragments

## Fix

Fixture only (option a of the brief). `soak_run` takes its hold from
`SOAK_HOLD_S` (default 2), and the four probe soaks call it as
`SOAK_HOLD_S=5 soak_run ...`: a prefix assignment, so nothing leaks into the
selftest shell that sources the fragment. A 5 s hold survives a 4 s stall.
The logcat soak keeps 2 s (one probe is enough there). `soak_title.sh` is
unchanged; production polling and its defaults are untouched. The
assertions still read run.log's words.

## Measurements (8-core WSL host)

Per soak, no stall:

| scenario | hold 2 | hold 5 |
|---|---|---|
| up fail up | 1.61 s | 4.99 s |
| up up down | 1.05 s (exit) | 1.03 s (exit) |
| up fail fail fail up | 1.91 s | 6.42 s |

The mutant soak ends at its `guest exited`, so it costs nothing extra when
caught. Fragment alone: 32 s before, 43 s after on the same host (host log
for 20f072b240 had it at 25 s). About 8 s of that is the two held soaks;
the rest is run-to-run noise on a shared host.

With all 8 cores busy (`while :; do :; done` x nproc), five in a row:

| run | result | fragment |
|---|---|---|
| 1 | 81 passed, 0 failed | 59 s |
| 2 | 81 passed, 0 failed | 65 s |
| 3 | 81 passed, 0 failed | 60 s |
| 4 | 81 passed, 0 failed | 61 s |
| 5 | 81 passed, 0 failed | 63 s |

## For the next lane

- A fixture that counts loop iterations against a wall-clock deadline read in
  whole seconds needs a hold with margin for a stalled poll, not a hold that
  just fits the iterations at nominal speed.
- To force a scheduler stall in a shell script under test, shim `sleep` on
  PATH and key it on the argument and the parent's cmdline; a slow fake adb
  does not move a clock read that comes before the adb call.
