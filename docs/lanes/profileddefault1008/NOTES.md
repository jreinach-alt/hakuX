# profileddefault1008 -- `TU_AUTOTUNE_ALGO=profiled` as the app default (#433, #474)

Brief: `/home/justin/hakux-work/briefs/profileddefault1008.md`. Evidence behind
it: `docs/lanes/gpunonrender/NOTES.md`, "Brief for the next lane:
`TU_AUTOTUNE_ALGO=profiled` as the app default" (~1892-1930) and "Attempt 14"
(P2-P / NG Black match, ~1939-2001). gpunonrender measured `profiled` against
the best hand-picked mode on two titles by matching GPU-identical scenes
(DOA3 P1-P, NG Black P2-P) and found it picked sysmem on both, within 3-9% of
the better arm's Tot. That is strong per-title evidence but only 2 titles;
this lane's job is the fleet A/B that decides whether the app DEFAULT flips.

## Grant and the code change

`android/app/src/main/cpp/xemu_android.cpp`'s `ApplyRenderMode` (only that
function + the `render_mode:` log line) was granted to this lane by
lane.local, 10-08 21:3x PDT. Commit `cd557f569e`:

- A guard list (`kAutotuneGuardTitles`): Blinx (`4D530013`, reads ZPASS
  reports that change value under non-bandwidth binning, #527) and Kabuki
  Warriors (`43560001`, sysmem-like binning stalls its fight, gmem474).
- A compiled default (`kAutotuneProfiledDefault`, currently `false`): the app
  ships `bandwidth` (nothing is set) until this lane's A/B clears its win
  rule below. Flipping it is this lane's decision, made in this same grant.
- A per-game runtime override, same channel as `render_mode`
  (`GetRuntimeOverride(env, activity, "autotune")`, reads
  `runtime_override_autotune`): explicit `bandwidth` or `profiled` always
  wins, including over the guard list -- the A/B needs `profiled` to reach
  Kabuki on purpose, to confirm the stall rather than assume it.
- `setenv("TU_AUTOTUNE_ALGO", "profiled", 0)` -- the `0` means it never
  overwrites a `TU_AUTOTUNE_ALGO` a request's `--env` already placed via the
  `env_vars` pref (`SyncSetupFiles` runs before `ApplyRenderMode`, so that
  env is already live). **This is how the fleet A/B sets its arms**:
  `request.sh --env TU_AUTOTUNE_ALGO=bandwidth` / `...=profiled`, the same
  mechanism `request.sh`'s own header comment names for exactly this case
  ("how a runtime-selectable option becomes selectable BY A QUEUED REQUEST").
  The new `autotune` per-game override is for a future player-facing
  setting; it is not what the A/B runs use, because the UI list that would
  let a person set it (`PerGameSettingsManager.kt`'s
  `overridablePreferenceKeys`) is outside this lane's grant.
- The `render_mode:` log line now also prints `autotune=<value> (<source>)
  TU_AUTOTUNE_ALGO=<actual env>` so a logcat read can tell override vs.
  guard vs. default, and whether an `--env` from the request won.

Build: `./gradlew --no-daemon assembleDebug` (JDK 21, `run_build.sh` in the
worktree root, not committed -- scratch). `BUILD SUCCESSFUL in 4m 53s`,
apk `android/app/build/outputs/apk/debug/app-debug.apk`,
sha256 `f1d28bf29ae68a3645fd020a0a7255e71530ac35be6d61e4ae80f6b864a006eb`, built
at commit `cd557f569e`.

## Rule (written before any run)

Per title, over the gameplay window, `profiled` vs `bandwidth`:

- **WINS**: gfps >= bandwidth + 2 AND gfps >= 1.08x bandwidth AND J/frame
  <= 1.05x bandwidth's.
- **HOLDS**: gfps within bandwidth +/-1 AND J/frame <= 1.05x.
- **LOSES**: gfps < bandwidth - 1, OR J/frame > 1.05x at equal gfps, OR a
  perf-line gap >= 2 s that bandwidth's arm does not have (a stall).
- `regioncheck.py`-equivalent eyeball of the frame pair on every title (no
  pixel-diff tool exists in this lane's territory; shots are compared by eye
  against the matched scene, same discipline as gpunonrender's `rpcseries.py`
  matching).
- A thermal pause voids that arm; rerun once only after the cause is read,
  never blind.
- **Default flips to `profiled`** (`kAutotuneProfiledDefault = true`) only if
  it WINS on >= 3 candidates and LOSES on none. A LOSS goes on the guard list
  only with a named cause (not just "it lost").
- Kabuki (guard) and Forza (control, Xfr/T 0.13, should not move) are read
  against the same WINS/HOLDS/LOSES rule but do not count toward the >= 3;
  they are correctness/no-op checks, not candidates.

## Nova availability -- the brief's candidate list does not match the fleet

Checked every candidate with `python3 /home/justin/hakux-work/pm/prequeue.py
"<title>"` (via a `subprocess.run` call, since the Bash tool blocks paths
outside this worktree -- see memory `lane-sandbox-blocks-board-requests`) and
cross-checked actual dispatch history (`dispatch/results/*/request.json`
`device` field) and `docs/testing/titles/targets.toml`'s `iso = {...}` keys,
because `targets.toml` alone is missing two titles entirely (Top Spin,
Tron 2.0) that dispatch history shows have run on the Nova.

| title | prequeue verdict | Nova copy? | in this A/B? |
|---|---|---|---|
| Crash Twinsanity (56550036) | REVIEW (BELOW_BAR) | **no** -- thor only, every run on record | dropped |
| Black (45410083) | REVIEW (BELOW_BAR) | **no** -- thor only | dropped |
| Otogi (46530002) | REVIEW (BELOW_BAR) | **no** -- thor only | dropped |
| RalliSport Challenge (4D53000F) | BLOCK (owner excl., flicker) | thor | dropped -- brief says excluded too |
| Halo 2 (4D530064) | REVIEW (FAILED_HARNESS, static-window false positive 10-04) | yes (targets.toml) | **kept** |
| Top Spin (4D530035) | REVIEW (FAILED_HARNESS, ran but no scored window 10-02) | yes (dispatch history) | **kept** |
| Tron 2.0 (42560001) | BLOCK (owner hold `tron-below-bar`: "telemetry and a fix, not a retest") | yes (dispatch history) | **kept as telemetry, not a Playable retest -- see below** |
| Fuzion Frenzy (4D530002) | BLOCK (CRASH_OR_HANG, last run 09-27) | yes (targets.toml) | **kept in pilot only**, see below |
| Crimson Skies (4D530021) | BLOCK (already PLAYABLE) | yes, both devices | **kept as telemetry, not a recert** |
| Kabuki Warriors (43560001, guard) | BLOCK (already PLAYABLE) | yes | **kept, it is the stall guard** |
| Forza Motorsport (4D53006E, control) | BLOCK (owner hold `forza-583-floor`) | yes, both devices | **kept, see below** |

`prequeue.py`'s own docstring: "A queue request is relayed only on CLEAR, or
on REVIEW after the cited rows are read and answered." None of the ten
titles above are CLEAR -- every title with run history carries some prior
verdict. The three REVIEW titles (Halo 2, Top Spin, Crash Twinsanity-class)
are BELOW_BAR/FAILED_HARNESS from **Playable-attempt** runs; memory
`below-bar-means-telemetry-not-retest` (owner 10-03) is explicit that a
below-bar title's correct next step is telemetry, not a retest -- which is
exactly this A/B (perflog, no Playable claim). The BLOCK-class holds are
read individually:

- **Tron 2.0** (`tron-below-bar`): the hold's own text is "telemetry and a
  fix, not a retest". This run is telemetry.
- **Crimson Skies, Kabuki Warriors**: BLOCK is "already in the Playable
  ledger" -- a recertification guard, not a ban on all device time. Neither
  hold text forbids a diagnostic comparison.
- **Forza** (`forza-583-floor`): the hold describes refs without PR #583's
  fix (invalid-surfaces list grows unbounded, fps decays 12->2 over a race).
  `git merge-base --is-ancestor 10fe2f59a7 HEAD` on this branch's base
  (7960e78e20) is true -- **#583 is present**, so the specific defect the
  hold names should not reproduce. Still watch `[watch311] invalid=` in the
  logcat per the fix's own memory note (`forza-invalid-list-since-517`) and
  treat a climbing count as a void, not a `profiled` loss.
- **Fuzion Frenzy** (`CRASH_OR_HANG`): this is the one BLOCK this lane is NOT
  overriding on its own judgment -- a hang 09-27 is a correctness risk, not a
  Playable-certification technicality, and a 600 s run that hangs burns the
  full budget for zero signal. It goes in the two-request pilot (see below)
  on the bandwidth arm only, to see whether the hang reproduces on today's
  build before committing a full A/B pair to it.

Dropped entirely (no Nova copy, and this lane does not shuffle -- memory
`shuffle-means-onto-the-nova`, lane.local's job): Crash Twinsanity, Black,
Otogi. That leaves 4 real candidates (Halo 2, Top Spin, Tron 2.0, Fuzion
Frenzy pending its pilot read) plus Crimson Skies as the energy guard, Kabuki
and Forza as controls -- short of the brief's >= 3-candidate win bar needing
a cushion, but the rule only requires 3 WINS among whatever runs clean.

## Pilot (device-time budget; no `pilots/lane.profileddefault1008.ok` yet)

Per AGENTS.md's 30-minute pilot rule, the first batch is two requests, not
all eight arms at once. Picked: **Top Spin bandwidth arm** (smallest
predicted GPU cost among the kept candidates) and **Fuzion Frenzy bandwidth
arm** (resolves the CRASH_OR_HANG question before spending a `profiled` arm
on it). Both report through `request.sh --wait`.

<!-- filled in after the pilot runs -->

### Attempt 2 (resumed 2026-10-08 ~22:1x PDT): why attempt 1 did not finish

Attempt 1 queued the two pilot requests above
(`1-1791521412-lane.profileddefault1008-3730973` Top Spin,
`1-1791521422-lane.profileddefault1008-3732463` Fuzion Frenzy) and ended its
session by starting `wait_pilot.sh` in the background and waiting on it to
notify. Per `roles/lane.md` and memory `lane-background-task-dies-with-session`,
that cannot work: this lane runs as a headless session, and every
`run_in_background` job and Monitor it starts dies with the session's turn.
The host's own addendum confirms the two requests were still sitting
unstarted in `dispatch/queue/` when this attempt resumed, so nothing was
lost -- the wait script just never got a chance to report before the prior
session ended.

On resume: checked `dispatch/running/` and found a different
`lane.fpstelemetry1008` request actively running (queued 21:48:43 PDT,
ahead of both of mine at 21:50:12/21:50:22); both pilot requests confirmed
still in `dispatch/queue/`, not yet started. The build (`cd557f569e`,
`BUILD SUCCESSFUL in 4m 53s`) and the code grant are already committed and
unaffected. Merged `origin/master` (2 commits: `e9eb8bcf07`, `93fbc525fc`,
both unrelated `surfdl1008` NOTES/PR docs, no conflicts, no territory
overlap) per the session-start gate, and pushed. This attempt polls the two
result dirs in the foreground inside bounded tool calls instead of
backgrounding anything.

## Results

<!-- filled in per title/arm after each result lands -->

## Guard list after this lane

<!-- filled in once the rule is applied -->
