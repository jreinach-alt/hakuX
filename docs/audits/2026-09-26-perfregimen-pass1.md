# Audit pass 1: PR #444 lane/perfregimen (MAX perf+fan during title soaks, REST on every exit)

Head audited: `5586ca27ed`. Read the diff against `origin/master`. The code that
reaches production is `docs/testing/devices.sh` (regimen values, `device_perf_*`)
and `docs/testing/soak_title.sh` (`perf_enter`, `perf_leave`, the trap change).
Everything under `docs/lanes/perfregimen/` is lane tooling and notes, and the four
prediction files are soak pilots that `arms.sh` skips.

Checked by running it: `run_fragment.sh selftest.d/84-perf-regimen.sh` gave
19 passed, 0 failed, three mutants included.

**Verdict: 1 MEDIUM, 3 LOW, so the PR goes to `needs-remediation`.**

## MEDIUM

### M1. The Thor's FAN_MAX=5 (SPORT) cools less than REST at gameplay temperature, and this is the lane's own measurement

`devices.sh` exports `DEVICE_FAN_MAX=5` for every device, the Thor included, and
`soak_title.sh` now applies it to every title soak by default.
`NOTES.md` 5d measured the Thor at 66-74 C:

- SMART (4, REST) ran at 29000, 29000, 27500, 25500 and 25000 duty.
- SPORT (5, MAX) ran at a fixed 25000.

The registered P2 of `perfregimen-pilot-thor.json` ("duty at 5 >= every other
mode") failed. The NOTES say it plainly: "under a hot gameplay load, MAX (2/5) can
run the fan slower than REST (0/4) would."

**Failure scenario.** After the fold, a default (`PERF_REGIMEN=max`) Thor title
soak runs, for example the queued Blinx arm. The GPU floor is pinned at 615 MHz,
so the SoC heats faster than at REST. It reaches the measured 66-74 C band, where
SMART would drive 27500-29000 duty, but SPORT holds 25000. So the regimen named
"MAX" runs the Thor hotter than REST would, on every Thor soak. The costs are:

- earlier thermal throttling, which pushes fps down, against the regimen's
  purpose;
- a hotter handheld on unattended soaks;
- a Blinx REST/MAX pilot whose fan legs compare a slower fan in the MAX arm.

Every Thor soak hits this, not an edge case, and the PR body ships it knowingly.
Soak fps is outside what any golden exercises.

**Remediation (no device needed).** Set the Thor's fan MAX to 4 (SMART) in its
`device_env` row. The per-row values exist for exactly this case. Alternatively,
drop the fan half of MAX on the Thor (MAX = 2/4) until CUSTOM (6) and the PWM
period are read. From the measured data, SMART is at or above SPORT everywhere
at 66 C and higher, and below SPORT only when the device is cool enough that
extra duty buys nothing. Update the comment that says the two devices' values
"agree today", and add a selftest check that the Thor's `device_perf_values` fan
MAX is not 5. Leave the Nova at 5, since its measurement (5a) supports it.

## LOW

### L1. Soak fps changes regimen across the fold, and result.json cannot show it yet

The default becomes `max` for every soak caller. Before this PR, the Thor sat at
0/4 and the Nova at 1/4. So any fps comparison of a pre-fold soak against a
post-fold soak mixes regimens. `perf_regimen.json` records the modes in the
result dir, but `result.json` does not until the dispatcher patch
(`dispatcher-result-fields.patch`, deferred to #440's territory) lands.

Scenario: a perf lane compares Blinx fps before and after its own fix. The fix
folds after this PR, and the lane credits the regimen's GPU-floor gain to its
fix. This is bounded because the file exists in the result dir. Recommend that
the fold note, or a one-line entry in the soak docs, names the fold sha as the
regimen boundary.

### L2. A serial not in `device_env` runs at the device's own modes

`device_perf_values` goes through `device_env`, which is keyed on the two literal
serials. A handheld reached by any other serial (a TCP `ip:port`, or a third
device) gets empty values. `perf_enter` then logs `PERF: no regimen values` and
runs as `off(no values)`. This fails safe, since nothing is set and nothing is
left at MAX, and it is logged. Noted only because the regimen is then silently
absent from any comparison that does not read `perf_regimen.json`.

### L3. The worst case for `release()` grows by about 82 s on a hung adb

`perf_leave` can make two `device_perf_set` attempts. Each is a 20 s write plus
a 20 s read-back, with a 2 s sleep between them. The dispatcher does not wrap
`soak_title.sh` in a timeout, so nothing kills it mid-release, and the lease is
still removed last. This only delays the next claim when adb is already failing.

## Checked and found correct

- **Request path derivation.** `CAPTURE_LOG=$D/results/<id>/logcat.txt` maps to
  `$D/running/<id>.req`, which matches `dispatcher.sh:659,686,762`.
- **Exit status.** The dispatcher ignores `soak_title.sh`'s exit status, so the
  new 143/130 exits change no result.
- **The trap change.** Before, a TERM ran `release()` and returned into the hold
  loop. Now it runs `release()` exactly once, via EXIT. The logcat restart
  subshell keeps its own TERM trap.
- **`PERF_SET=1` is assigned before the write.** A failed or partial MAX write is
  still restored.
- **`run_disc.sh` is untouched.** Pgraph runs never switch modes (selftest check).
