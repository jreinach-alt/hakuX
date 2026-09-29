# Audit pass 1: PR #560 (lane.remote, #557 thermal governor core)

Head audited: `8a0d7a34b7`. No HIGH or MEDIUM findings. There are five LOWs, all on paths the replay and the harness do not exercise; the PR goes to pass 2.

Read: the whole diff (`thermal_governor.c/.h`, the CMake line, the harness, `thermal557_replay.py`, the prediction file and NOTES). Run: `python3 docs/lanes/remote/thermal557_replay.py --selftest` on this head passes all 17 groups, including the harness's sysfs checks. The Android build has no `-ffast-math` or `-ffinite-math-only`, so the core's `isnan`/`isfinite`/`NAN` sentinels survive (grep of `CMakeLists.txt` and the gradle files). The prediction has no `a_ref`/`b_ref`, and `arms.sh:840` skips such a prediction structurally, so no arm is queued. That matches the PR body.

Checked and found sound:
- **Publishing a rung across threads:** opaque is stored relaxed and fn with release, then fn is loaded with acquire and opaque relaxed. A reader that sees fn also sees its opaque.
- **Ring window:** at 1 Hz it holds about 61 samples, and `window_push` evicts at 256 as well as by age.
- **Least-squares slope:** it is centred on the newest time. `sxx > 0` guards a zero span.
- **Dwell and gap logic:** a change resets both dwells. A silence longer than `gap_reset_s` resets the window, and unread samples do not advance `last_t`, so a run of them counts as a silence.
- **Rung order:** a rung registered late is engaged in order, and rungs are released in the reverse of the order they were engaged (`engaged[]`).
- **Config line buffer:** `wired[64]` holds all four names (29 chars).
- **First log line:** the first line is the config line at 30 s, which comes before the first `state` line (tested).

## LOW

**LOW-1: the `off:` line breaks the "first line waits 30 s" rule.** `gov_start()` (`thermal_governor.c:612-622`) emits `[thermal557] off: ...` on the very first tick when the zone cannot be opened. That is before any gfps line, so it becomes the first `hakuX-perf` line. Scenario: on an enforcing ROM (EACCES on `sysfs_thermal`) or with a wrong `HAKUX_THERMAL_ZONE`, a run with `HAKUX_THERMAL_ADAPT=1` starts `phase_read_split.py --window`'s origin at the first display refresh instead of the first gfps line, so every window shifts by that gap. This is bounded: it needs the opt-in and the failure path, and the shift is the gap between the first refresh and the first gfps line. The fix is to hold the line until `status_every_s`, as the config line is held.

**LOW-2: one unreadable cooling device blocks every step up.** `count_set()` returns -1 when any one device's `cur_state` fails to read, and `cool` requires `s->pause == 0`. Scenario: a pause-class device whose `cur_state` read errors persistently (for example a driver that returns an error while its CPU is offline). Once it has stepped down, the governor never steps up for the rest of the session. The PR presents this as conservative, but nothing logs which device failed. The `state` line shows `pause=-1`, and that is the only trace. Counting the readable devices and logging the unreadable count separately would keep the step up alive.

**LOW-3: a pause with xo-therm unread is dropped.** `thermal_governor_feed()` returns early when `xo_c` is not finite, before it looks at `s->pause`. Scenario: xo-therm reads fail while a pause device is set, and the governor does not count toward a pause step-down. This is unlikely, since the same sysfs tree serves both, and it is bounded by `gap_reset_s`.

**LOW-4: CLOCK_MONOTONIC does not advance across suspend.** Scenario: the device suspends mid-session with the display loop blocked. On resume, `now - last_t` can be under 10 s while xo-therm has dropped many degrees. The window then mixes pre- and post-suspend samples into a steep negative slope. The artifact leaves the 60 s window before the 300 s up-dwell can finish, so it causes no spurious change. Only the `state` lines misread for about a minute. `CLOCK_BOOTTIME` would measure the gap truthfully.

**LOW-5: unregistering an engaged rung strands it.** `thermal_governor_register_rung(r, NULL, ...)` while `r` is engaged: `step_up` finds `fn == NULL` and never calls the release, so the owner's flag stays engaged. The header does not promise unregistration. One sentence ("register once, never NULL") would close it.

## What pass 2 should verify

For each LOW, that it was either changed or deliberately deferred with a logged reason. None of them blocks the fold, because nothing calls the core yet. LOW-1 and LOW-2 matter most before the hook PR's device run.
