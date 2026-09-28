# Audit pass 1: PR #588, lane.forzadecay414 -- clocks in every thermal sample (#414)

Head audited: `ce044d4787`. Files: `docs/testing/thermal_state.py`, `docs/testing/jobs/selftest.d/99-thermal-pause.sh`.

**Result: one MEDIUM, three LOWs. Goes to `needs-remediation`.**

The code reads and parses what it says it reads. The sample loop drops a field that does not read, the parse drops a line with no value, the ceiling fallback holds when a sample mixes the two ceilings, the new `clk` key breaks no consumer, and no parser reads the `THERMAL:` tail, so moving the fan clause later breaks nothing. The MEDIUM is about the claim the fields are there to support: the doc and the summary treat `scaling_cur_freq` as the delivered clock, and this repo already records that it is not.

## MEDIUM

### M1. `scaling_cur_freq` may not show an LMh cap, and the new text says a full-speed reading rules one out

`thermal_state.py` module doc (CLOCKS) and the comment above `CPUFREQ_DIR` say that without these fields "a core held at a fraction of its clock at 95 C reads exactly like one at full speed", which implies that with them it does not. `clock_range`'s docstring says "A minimum well under that ceiling with no cooling device set is LMh/DCVS at work". The PR title is "LMh made visible".

`scaling_cur_freq` is the policy's current frequency as cpufreq records it. On a fast-switch driver such as qcom-cpufreq-hw, that is the frequency the governor last *requested*. Upstream, the LMh-throttled frequency is read from a separate register and delivered to the scheduler as thermal pressure. It does not reach `policy->cur`, and LMh does not move `scaling_max_freq` either. This repo has direct evidence of the same blindness on these handhelds. `docs/lanes/gta482/NOTES.md:415`: while `thermal-pause-F8` held cpu3-7 off, "`scaling_cur_freq` still reads each cluster's maximum". `:547`: "Do not trust ... `scaling_cur_freq` to show the pause". `docs/lanes/thermal507/NOTES.md:442` says the same.

**Failure scenario.** A Nova soak for #414 reaches 95 C at the junction. LMh caps cpu7 at around 1.5 GHz and no cooling device is set. The governor keeps requesting the top step, so every sample reads `scaling_cur_freq` 3187200, and run.log reads `clock MHz ... cpu7 3187-3187 of 3187`. By the PR's own text, a reader of #414 takes that line as positive evidence that the big core ran at full speed. They drop LMh as the cause of the Forza decay, which is the question this instrument was added to answer. The selftest cannot catch this: it uses fake nodes, so it proves the plumbing, not what the node means.

This is MEDIUM, not HIGH. It is a host diagnostic, not emulator behaviour, and it is plausible rather than confirmed: no device run has put a known LMh cap next to a `scaling_cur_freq` reading. That is also why it cannot be left as written. Nothing planned would expose it. The post-fold soaks named in the PR body would show that the fields exist, not that they move.

**Remediation (either of these clears it):**
- (a) Correct the claim in the three places it is made: the module doc, the `CPUFREQ_DIR` comment and the `clock_range` docstring. Say that `scaling_cur_freq` is the requested clock, and that a reading at the ceiling does not rule out LMh (cite gta482 NOTES:415). Then name what would decide it on a device: a hot soak where fps falls with no cooling device set, and whether the cpu7 minimum moves in that window. Record that as the post-fold check on #414. The GPU half (`gpuclk` from kgsl devfreq) does not share this problem and can keep its wording.
- (b) Also read a source that reflects the delivered clock or the cap, if one can be read without root on these kernels (for example `cpuinfo_cur_freq`, which is usually 0400 and would then be left out as unread; or a per-CPU `cpu_capacity`). Keep the wording from (a) for whatever still reads as requested.

## LOW

### L1. `gpu throttling 1` reads as "throttling now"

kgsl's `throttling` node is the switch that enables thermal throttling, not a live state. The module doc names it correctly ("kgsl's `throttling` switch"), but the summary clause `gpu throttling 1` will be read as "the GPU was throttled". Suggest `gpu throttling enabled` / `gpu throttling off`, or `gpu throttle-switch 1`.

### L2. The selftest has no middle policy

The fixture has policy0 and policy7 only. A lexical sort puts `cpu0, cpu7, gpu` in the same order as the numeric `key`, so the leg cannot tell the two apart, and it never exercises the `policy3` row that both handhelds have. A `policy3` fixture, which could be a `policy10` for the numeric-versus-lexical case, would make the ordering assertion real. Nothing observable goes wrong today because both devices have at most `policy7`.

### L3. Twelve more forks per sample

The sample adds 3x3 `cat`s for the CPU policies and 3 for the GPU. `docs/lanes/gta482/NOTES.md:549` warns that a sampler forking per file cost about 12 of every 17 s on a paused device. The existing zone loop already forks per zone and dwarfs this addition, so this is marginal. It is noted only because the sample runs every 30 s during a scored soak.

## Checked and clean

- Unreadable `scaling_max_freq` (the Thor's policy0): the `cat` fails silently and the line ends in an empty value. The regex `clk (\S+) (\S+) (-?\d+)$` does not match it, so the field is absent, not 0. The ceiling falls back to `cpuinfo_max_freq`. The selftest's `of 0` mutant covers this.
- `\r` from adb is stripped in `adb_shell` before the parse, so the `$` anchor holds.
- No earlier parse branch (`cd`, `tz`, `ps`, `ths`, `fan`) matches a `clk` line.
- The GPU loop's final `[ -f ] && ...` can leave status 1, but it is followed by `;` and `echo end`, so `adb_shell`'s `^end$` check still passes.
- `summary` passes only `ok` records to `clock_range`, the same set as `fan_range`. No consumer outside `thermal_state.py` parses the `THERMAL:` tail (grep over `docs/testing`: `title_verdict.py`, `soak_title.sh` and `dispatcher.sh` read the jsonl through `thermal_state.py` or not at all).
- `Prediction: none` is justified: the change touches no emulator code and no scored path.
