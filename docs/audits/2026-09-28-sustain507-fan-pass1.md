# Audit pass 1: PR #554, lane/sustain507-fan (#507 Part D.2)

Head audited: `e406cafa7b` (base master `559ea2fc07`). Diff read in full:
`docs/testing/thermal_state.py`, `docs/testing/jobs/selftest.d/99-thermal-pause.sh`,
`docs/lanes/sustain507/FAN.md`.

**Verdict: no HIGH, no MEDIUM, one LOW.**

## Checked, no finding

- **Sample script.** The fan loop is `[ -f X ] && echo ...; done; echo end`.
  On a device with no `/sys/class/gpio5_pwm2`, each `[ -f ]` fails, nothing is
  printed, and `echo end` still runs. `adb_shell`'s `^end$` check still passes,
  so a device without the node gets no `fan` key and the sample is not errored.
  If the node exists but a read fails or is not numeric, the line is
  `fan duty ` (or text), the `-?\d+$` regex does not match, and the field is
  left out. It is never read as 0, which matches the `ps` rule.
- **Parse order.** The new `continue` after the `ths` match changes nothing.
  No earlier pattern matches a `fan ` line: `cd`/`tz`/`ps`/`ths` are all
  anchored on their own prefix.
- **Readers of the samples.** `title_verdict.py` reads only `paused`,
  `dev_ts`, `episodes`, `in_window`, `coverage`, `first_*` and `power_over`.
  None of them looks at a `fan` key, so verdicts are unchanged.
  The `THERMAL:` line is written to run.log and nothing parses it. The fan
  text goes after the battery text, so the existing fixtures, which match on
  prefixes, still match.
- **Selftest leg.** I ran `SELFTEST_ONLY=99-thermal-pause` on this head: 16
  passed, 0 failed, including `fan`. The leg can fail. If the parse drops the
  lines, `r` reads `None None None False`. If the summary skips `fan_range`,
  the `*"; fan duty 13700-29000 of 50000"` suffix is missing. If `FAN_DIR`
  is not spliced into `SAMPLE_SH`, the replace is a no-op and the leg exits.
  Running the whole `SAMPLE_SH` on the host is safe: the thermal and
  power_supply globs that match nothing produce lines the parser drops, and
  `dumpsys` is absent with its stderr sent to /dev/null.

## LOW-1: the summary's fan range includes the cool-down samples

`summary()` calls `fan_range(ok)`, and `ok` holds every readable sample,
including the `cool` samples the cool-down gate takes before `start`. The
battery figure a few lines above is deliberately limited to `t0` → last
reading ("the run, not the cool-down before it"); the fan range is not.

Failure scenario: a hot Thor waits 4 minutes in the gate. SMART holds 40000
duty while xo-therm falls from 75 C to 65 C. Then the run itself never goes
above 29000. run.log reads `fan duty ...-40000 of 50000` on the run's line,
so Part D ("what does SMART's curve do under load") would credit the run
with a duty that only the idle, hot cool-down reached.

Bounded: every sample's `fan` object in thermal.jsonl is correct and
labelled. Only the one-line readout mixes the two phases.

Suggested fix: `fan_range([r for r in ok if dev_ts(r) >= t0])`, or name the
cool-down range separately. Add a fixture `cool` sample whose duty is above
the run's, so the leg fails if the cool-down duty leaks into the range.
