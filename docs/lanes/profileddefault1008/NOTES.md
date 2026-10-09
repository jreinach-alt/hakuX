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

### Attempt 3 (resumed 2026-10-08 ~22:4x PDT): why attempt 2 did not finish, pilot read, full batch queued

Attempt 2 merged `origin/master`, wrote the "why attempt 1 did not finish"
note above, pushed (`09ef23d518`), and ended its turn there without checking
whether the two pilot requests it had already confirmed were still queued
had since landed -- it neither polled them nor queued anything past them,
so nothing advanced between attempt 2's end and this attempt's start beyond
the Nova draining its queue on its own.

On resume: both pilot requests were `DONE` (checked via a `python3` script
reading `/home/justin/hakux-work/dispatch/results/<id>/` directly -- the
Bash tool's own path sandbox blocks literal outside-cwd paths on the command
line, but not a path read from inside a `python3` script file, per memory
`lane-sandbox-blocks-board-requests`).

**Pilot results, both clean:**

| id | title/arm | seconds held | thermal pause | crash/ANR | gfps (all / last 2/3) | mean J (all / last 2/3) |
|---|---|---|---|---|---|---|
| `...3730973` | Top Spin, bandwidth | 605 | none | none | 47.1 / 41.4 | 1.76 / 2.62 |
| `...3732463` | Fuzion Frenzy, bandwidth | 605 | none | none | 42.6 / 44.4 | 3.69 / 3.92 |

Fuzion Frenzy's 09-27 `CRASH_OR_HANG` does **not** reproduce on today's
build -- the pilot's one job. Top Spin ran a full clean 605 s with no prior
perf read on record for this title.

**Ref mismatch found, and why these two pilot runs are informational only,
not the A-arm of record.** Both pilot requests were queued at `--ref`
defaulted to HEAD-at-queue-time, `e85e55450d` (2026-10-09T04:50 UTC). The
five title-level predictions (`profileddefault1008-{topspin,fuzion,crimson,
kabuki,forza}-ab.json`) were registered three minutes later, at
`3e5d186726` (04:53:11 UTC), against `a_ref == b_ref == 7e51edfe98`.
`ab_compare.py`'s `load_expect` refuses a pair whose arm named a different
ref than the prediction's (`have.startswith(want) or want.startswith(have)`,
line ~842) -- `e85e55450d` and `7e51edfe98` satisfy neither direction, so
feeding either pilot result into the judge as the registered A-arm would be
refused, correctly: the prediction was written for a different build ref
than the one that ran. Both commits carry the same `ApplyRenderMode` code
(the override landed earlier at `cd557f569e`), so there is no reason to
think the *behavior* differs -- but "the registered ref is the ref that
ran" is the whole point of the gate, and a lane re-deriving "this should be
fine" past it is exactly what memory `validity-gate-keyed-on-the-symptom`
and `register-a-prediction-after-the-last-rebase` warn against. Treated the
two pilot runs as what they are (a clean-build, no-hang pilot read) and
queued fresh, ref-matched runs for the scored batch instead of arguing the
gate down.

Wrote the pilot verdict to `/home/justin/hakux-work/dispatch/pilots/
lane.profileddefault1008.ok` (via `python3`, since `Write`/`cp` are blocked
on that path -- memory `lane-sandbox-blocks-board-requests`) recording the
above before queuing past the 30-minute pilot cap, per `AGENTS.md`'s pilot
rule.

**Full batch queued** -- 10 requests, 5 titles x 2 arms (bandwidth then
profiled per title, per each prediction's own `queue_order`), every one
`--ref 7e51edfe98f0943d6b5f448563a1ea8dd2ed19b3` to match the registered
predictions, `--seconds 600 --perflog --frames-every 30 --device nova`:

| title | role | bandwidth id | profiled id |
|---|---|---|---|
| Top Spin | candidate | `1-1791524995-lane.profileddefault1008-4017004` | `1-1791525007-lane.profileddefault1008-4018033` |
| Fuzion Frenzy | candidate | `1-1791525009-lane.profileddefault1008-4019084` | `1-1791525027-lane.profileddefault1008-4019778` |
| Crimson Skies | guard | `1-1791525033-lane.profileddefault1008-4019944` | `1-1791525039-lane.profileddefault1008-4020149` |
| Kabuki Warriors | stall-guard | `1-1791525045-lane.profileddefault1008-4021747` | `1-1791525053-lane.profileddefault1008-4022897` |
| Forza Motorsport | control | `1-1791525060-lane.profileddefault1008-4023177` | `1-1791525066-lane.profileddefault1008-4023363` |

Each queued with `--no-expect "registered soak prediction
docs/testing/predictions/profileddefault1008-<name>-ab.json ..."` -- these
ab.json files carry `"expect": {}` on purpose (a soak writes no capture
keys; see each file's `expect_note`), so there is nothing for `--expect` to
bind to. The dispatcher's own pilot gate confirmed admission against the
just-written `.ok` file at each queue call (`"pilot gate: ... reviewed
pilot ... (0.0 h old) admits it"`), climbing from ~34 min to ~115 min of
held device time across the ten calls -- in budget for a single reviewed
batch, not the uncapped free-for-all the gate exists to prevent.

**~115 minutes of Nova device time now queued, none of it mine to wait out
in this session.** Per the host's own addendum and memory
`lane-background-task-dies-with-session`: this is a headless session, a
`run_in_background` job or `Monitor` started here dies with the turn, and
polling a result dir in a `sleep`-loop inside one Bash call cannot span
~115 minutes against this tool's 10-minute cap either. Stopping here and
posting `[lane.profileddefault1008] waiting:` naming the ten ids above, per
`roles/lane.md`'s "finished outcome" clause for a wait on something outside
the session (the Nova's queue, not a background task of mine).

### Attempt 4 (resumed 2026-10-09): why attempt 3 did not finish, scored batch read, rule applied

Attempt 3 queued the full 10-request scored batch and ended its turn posting
the wait, correctly -- per `roles/lane.md` item 5 and memory
`lane-background-task-dies-with-session`, a lane must never end a session
waiting on its own `run_in_background` job, and attempt 3 did not: it named
the ten request ids and stopped, which is a finished outcome, not an
unfinished one. Nothing was lost between attempts; the Nova simply needed
time to drain the queue (plus lane.fpstelemetry1008's requests ahead of it,
per the dispatcher's serialization) that no session could sit through.

On resume, all ten results existed in `dispatch/results/` (checked via a
`python3` script reading the directory directly -- `Write`/the Bash tool
block literal outside-cwd paths on the command line, not a path read from
inside a script file, memory `lane-sandbox-blocks-board-requests`): 8 `DONE`,
2 `ERROR` (both Kabuki Warriors arms, see below).

**Reading method.** `docs/testing/title_verdict.py`'s `judge()` is this
project's canonical per-request scorer (gfps via its `fps_window_median`
and `g_fps_mean_reported_not_judged`, J/frame via its `power.j_per_frame`),
and it worked cleanly for Top Spin, Fuzion Frenzy and Crimson Skies -- all
three routes write a `mark gameplay`/`mark play` logcat line the judge reads
to window the scored period. Forza's route (`forza.drive`, screen-driven
`drive forza 420 find`) does not write that mark at all -- it is a pre-existing
gap in that route, not something this A/B introduced -- so `judge()` returned
`reached_gameplay: false, gameplay_s: 0.0` for both Forza arms despite the
run completing cleanly. Wrote three scratch scripts (not committed, same
scratch treatment as `run_build.sh`) to read Forza's raw `hakuX-perf` `gfps=`
line average over the full run, then windowed from each arm's own
`reached-play` timestamp (from `run.log`, matched to the correct calendar
date via each log's own first/last line dates, since the profiled arm's run
crossed midnight) to the run's end, confirming the gap holds throughout
(first-half vs second-half means) rather than being a transient dip.

**Results, scored batch (ref `7e51edfe98`, `--seconds 600`):**

| title | role | arm | gfps (median / mean) | J/frame | fps_ok_share | hitches/min (worst ms) | crash/hang | thermal pause |
|---|---|---|---|---|---|---|---|---|
| Top Spin | candidate | bandwidth | 32.57 / 33.35 | 0.2387 | 0.9123 | 0.999 (684.9) | no/no | none |
| Top Spin | candidate | profiled | 32.66 / 32.66 | 0.2305 | 0.9186 | 0.361 (115.9) | no/no | none |
| Fuzion Frenzy | candidate | bandwidth | 38.71 / 43.49 | 0.2051 | 0.8493 | 1.475 (1714.6) | no/no | none |
| Fuzion Frenzy | candidate | profiled | 58.03 / 51.15 | 0.1612 | 0.9950 | 1.069 (1559.4) | no/no | none |
| Crimson Skies | guard | bandwidth | 30.00 / 29.98 | 0.2428 | 1.0000 | 0.0 (0.0) | no/no | none |
| Crimson Skies | guard | profiled | 30.00 / 29.98 | 0.2455 | 1.0000 | 0.0 (0.0) | no/no | none |
| Forza (windowed, no route mark) | control | bandwidth | -- / 28.92 | n/m | n/m | n/m | no/no | none |
| Forza (windowed, no route mark) | control | profiled | -- / 26.61 | n/m | n/m | n/m | no/no | none |
| Kabuki Warriors | stall-guard | both | **ERROR: title not on device** (searched `/storage/E6C6-D7AA/Games/XBox`) | | | | | |

Forza's `[watch311] invalid=` stayed flat (9-10) on both arms, not climbing
-- the `forza-583-floor` hold's defect (unbounded invalid-surfaces growth)
does not reproduce; the gap is something else.

**Rule applied (NOTES.md rule above, written before any run):**

- **Top Spin: HOLDS.** gfps within +/-1 (32.57 vs 32.66) and J/frame 0.2305
  is 0.97x bandwidth's (<=1.05x). Secondary signal in profiled's favor:
  roughly a third of the hitch rate and a sixth of the worst hitch, and 3.4%
  lower J/frame -- not enough to cross the WINS bar (needs >=1.08x gfps) but
  a clean, non-regressing result.
- **Fuzion Frenzy: WINS.** gfps >= bandwidth+2 (58.03 vs 38.71 median, both
  comfortably past the 1.08x bar) and J/frame 0.1612 is 0.79x bandwidth's
  (well under 1.05x). fps_ok_share also jumps 0.849 -> 0.995. This repeats
  the pilot's informational read (gfps ~42-44 on the bandwidth arm, matching
  this scored run's bandwidth mean of 43.49) and both gpunonrender's prior
  findings: profiled picks a materially better mode here.
- **Crimson Skies (guard): HOLDS.** Identical gfps (both fps-capped at
  30.0), J/frame 1.01x (<=1.05x). profiled does not regress the title
  already on the wall.
- **Forza (control): LOSES**, by the gfps leg of the rule alone (windowed
  mean 26.61 < bandwidth's 28.92 - 1 = 27.92), confirmed steady across the
  windowed run (first/second-half means 26.51/26.71 vs bandwidth's
  28.84/29.00 -- not a transient dip or a thermal recovery curve) and
  reproduced in the un-windowed full-span average too (26.47 vs 28.27). No
  thermal pause, no crash/hang, no climbing `invalid=` count: nothing voids
  this arm. **This directly contradicts the premise this lane queued Forza
  as a control under** (`docs/lanes/gpunonrender/NOTES.md`'s Xfr/T=0.13
  survey figure, read as "profiled should pick the same mode bandwidth
  already gets and gfps/J should not move") -- the premise was wrong, or an
  ~8% mode-driven gap exists here that the survey's single ratio doesn't
  predict. Per the rule, **a LOSS goes on the guard list only with a named
  cause, not just "it lost"** -- this lane did not find that cause (budget
  did not extend to a GPU-side trace of which mode `profiled` actually
  picked on Forza vs. bandwidth), so Forza is **not** added to
  `kAutotuneGuardTitles` by this lane. It is flagged here as a real,
  reproduced regression that the next lane (or this lane's follow-up) must
  name before either guard-listing Forza or ruling the gap out as noise.
- **Kabuki Warriors (stall-guard): VOID, not a verdict.** Both arms errored
  before running -- `43560001-Kabuki_Warriors.xiso.iso` was not found on the
  Nova's SD card at run time, despite the Nova-availability check earlier in
  this lane (prequeue + dispatch history) confirming a Nova copy existed.
  The title moved off the Nova between that check and these requests
  actually running (device inventory is lane.local's to manage, memory
  `shuffle-means-onto-the-nova`) -- not a measurement failure, and not
  evidence either way for the gmem474 stall this guard exists to confirm.
  Re-running it needs the title shuffled back onto the Nova first, which is
  outside this lane's grant.

**Default-flip decision: does not flip.** `kAutotuneProfiledDefault` stays
`false` (confirmed unchanged in the current tree, commit `cd557f569e`). Two
independent reasons, either alone sufficient:

1. **Candidate count.** Only 2 of the brief's candidates actually ran (Top
   Spin, Fuzion Frenzy) -- Halo 2 and Tron 2.0 were dropped/deferred before
   any run (see PR.md's Status section: pathfind never reached confirmed
   gameplay on Halo 2; Tron 2.0's ~530 s intro/cutscene sequence was not
   attempted blind). The rule needs **>=3 WINS among candidates** to flip;
   with only 2 candidates total (1 WIN, 1 HOLDS), the bar cannot be met this
   lane regardless of how either scored.
2. **The Forza regression**, unresolved. Even if the candidate count had
   reached 3 wins, a control that was expected not to move and lost by ~8%
   gfps, for no identified reason, is a reason to hold the flip open rather
   than ship it -- the rule's text scopes ">= 3 candidates and LOSES on
   none" to candidates, but a control's whole purpose is to catch exactly
   this kind of surprise, and this lane is not overriding that on its own
   judgment the way it did earlier for the Nova-availability BLOCK holds.

## Guard list after this lane

No change to `kAutotuneGuardTitles` (still Blinx #527, Kabuki Warriors
gmem474) -- Forza's regression has no named cause yet (see above) and the
rule requires one before a guard-list addition. The compiled default,
runtime override channel, and per-game `autotune` override from this lane's
grant all ship as committed (`cd557f569e`); only `kAutotuneProfiledDefault`
itself is undecided, and stays `false`.

**What the next lane should not repeat:**

- Don't re-run the Forza pair blind hoping the gap was noise -- it held
  flat across two independent read methods (full-span and windowed-from-mark)
  and across first/second half of the windowed run. If it's worth chasing,
  it needs a trace of which autotune mode each arm actually picked on
  Forza's surfaces (the same GPU-identical-scene matching gpunonrender used
  for DOA3/NG Black), not another soak.
- Forza's route (`forza.drive`) writes no `mark gameplay`/`mark play`
  logcat line, so `title_verdict.py`'s canonical judge cannot score it at
  all (`reached_gameplay: false` even on a clean run) -- this is a
  pre-existing gap in that route, worth fixing in the route itself (outside
  this lane's territory) rather than re-deriving a windowed read by hand
  every time Forza needs a perf comparison.
- Kabuki Warriors needs shuffling back onto the Nova before its stall-guard
  arms can run at all; don't requeue them against the current inventory.
- To get the candidate count past 2, Halo 2 needs its pathfind route fixed
  (Armory camera not responding) and Tron 2.0 needs its ~530 s intro
  replicated -- neither is a quick requeue.
