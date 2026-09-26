# lane.titlerun: the title ruler

PR #307. Brief: scripted play through the queue, and a verdict per run
(the owner's 1.0 ruler, 2026-09-25).

## What exists now

| piece | file | what it does |
|---|---|---|
| pad | `docs/testing/perf/pad.sh` | evdev input only; `SERIAL` required; pad node auto-detected and cached per serial |
| routes | `docs/testing/titles/route.sh`, `titles/routes/*.route` | a small route language, parsed in full before anything is sent |
| queue | `request.sh --route <name>`, `dispatcher.sh` | the route TEXT goes into the request; the worker writes `route.txt` and passes `ROUTE_FILE` |
| soak | `docs/testing/soak_title.sh` | plays the route beside the hold; liveness retries adb (host defect 19) |
| judge | `docs/testing/title_verdict.py` | writes `verdict.json` and a contact sheet per run |
| table | `docs/testing/titles/table.py` | latest verdict per (title, device, ref); `--judge` fills in missing verdicts |
| targets | `docs/testing/titles/targets.toml` | keyed on the CSV's canonical `title_id`; ISO per device, own target fps, route |
| proof | `docs/testing/jobs/selftest.d/89-title-verdict.sh` | 24 checks: six fixtures, four mutants, the liveness path against a fake adb, `request.sh --route` |

## Pad nodes (read-only `getevent -pl`, 2026-09-25)

| device | serial | node | name |
|---|---|---|---|
| Nova | ee317437 | `/dev/input/event7` | Retroid Pocket Controller |
| Thor | bdc158a5 | `/dev/input/event9` | Odin Controller |

Both pads differ from what `pad.sh` used to assume, in three ways:

- `getevent` names code 304 `BTN_GAMEPAD`, not `BTN_A` or `BTN_SOUTH`. A
  detector that matched only the brief's two names found no pad on either
  device. It now accepts all three names.
- The sticks run from -32767 to 32767, centred on 0. The old comment said
  "centre 128 on this pad", which is no longer true of either device.
- The right stick is on `ABS_Z`/`ABS_RZ`, not `ABS_RX`/`ABS_RY`. The
  triggers are on `ABS_BRAKE`/`ABS_GAS`.

So routes name logical axes (`LX LY RX RY LT RT HATX HATY`). `pad.sh`
resolves each one against the axes the pad actually lists, and `min|max|mid`
read the cached range. A route written this way is the same file on both
handhelds.

## Decisions the verdict makes, and why

- **Frame rate is measured by the clock, not taken from G.** `hakuX-perf` is
  printed once every 60 FLIP_STALLs (`g_nv2a_stats.frame_count` counts guest
  flips; `pgraph/profile.c`). So the time between two lines is exactly how
  long those 60 guest frames took, and 60/dt is that window's frame rate.
  - `G` is an exponential average (x0.8 + x0.2 per frame). It carries the
    past into every window.
  - `gfps` is the count over the last ~250 ms, a quarter-second sample of a
    two-second window.
  - Both are reported; neither is judged. The "judge by G" mutant passes a
    20 fps run whose G still reads 33.3 ms, and the `below` fixture catches
    it.
- **The share is weighted by time.** A 60-frame window at 10 fps lasts six
  times as long as one at 60 fps, so counting windows under-weights exactly
  the slow stretches. `fps_ok_window_share` (by count) is reported beside it.
- **Windows straddling the mark are not counted.** Only pairs of lines that
  are both after `mark gameplay` count.
- **Tolerance.** A window counts as at 30 fps from 28.5 fps up (`fps_tolerance
  = 0.95`). NTSC vblank is 59.94 Hz, so a title locked to half of it runs at
  29.97, and that is the bar met.
- **Hang.** No perf line for more than 10 s after the mark means fewer than
  60 flips in 10 s. That reads a sustained 6 fps or slower as a hang. Such a
  run fails on fps anyway, so the two criteria overlap and never contradict
  each other.
- **Audio, "no dropouts", made mechanical.** Short callbacks as a share of all
  callbacks, from the `starve:` lines stamped more than 10 s after the mark.
  - The default maximum is **0.1%** (`audio_starve_max_share` in
    `targets.toml`). That is a decision; set it to 0.0 for a literal zero.
  - No `starve:` line at all means the instrument said nothing
    (`audio_measured: false`), and that run fails. A ruler that cannot hear
    must not pass a title.
- **Crash.** A crash is any of:
  - an E or F line from `hakuX-crash` (the kernel BugCheck dump);
  - `libc:F` or `DEBUG:F`;
  - a real exit, i.e. `guest exited` in run.log.

  `hakuX-crash` W lines (`NULL FAULT RETRY`) are retries. They are counted in
  `crash_warnings` and not failed.
- **Duration.** A screening run needs 600 s after the mark, a confirmation
  run 1200 s. The level is inferred from the run's length, or forced with
  `--require`.
- **Generic route.**
  - It writes `mark play`, never `mark gameplay`, because it cannot know it
    got there. The verdict scores from `mark play` provisionally, with
    `reached_gameplay: null`, and cannot pass the run until a reviewer who
    has looked at `contact.png` reruns it with `--reviewed-gameplay yes`.
    That run records `gameplay_by: review`.
  - Frames come from the route's `mark`/`shot` steps: about 10 screencaps in
    10 minutes, not the once-a-second `--frames-every` that costs frame rate.
- **Ratings.**
  - `rating_candidate` is `Playable` at `surface_scale=1` and `Playable (2x)`
    at 2. The scale is read from the app's own `hakuX: surface_scale=N`
    line, not from the request.
  - `human_review` is written empty, and nothing fills it.
  - `below_own_target` flags a title whose own target is 60 that meets 30
    but not 60.

## Snapshot deploy: the first re-exec after this folds will miss two files

Host memory "a new snapshot file misses the first re-exec" applies directly
here.

- **What happens.** `SCRIPT_DEPS` and `snapshot_scripts` now both list
  `titles/route.sh` and `perf/pad.sh`, and the copy loop makes their
  subdirectories. But the re-exec after the fold is carried out by the OLD
  worker, whose copy loop has neither the new names nor the `mkdir`.
- **What it looks like.** `soak_title.sh` refuses to guess: it writes
  `ROUTE NOT PLAYED: ... missing from this snapshot` to run.log, and the
  verdict fails the run with that reason.
- **The fix.** After the fold, run
  `mkdir -p $DISPATCH_DIR/bin/{titles,perf}` and `cp` the two files from the
  serving tree. That is exactly what the new `snapshot_scripts` would do.

## What this does not do yet

- **Set `surface_scale` 2 for a queued run.** No queue path writes the pref
  today; `apply_env_pref` handles `env_vars` only. The verdict records the
  scale the app logged, so a 2x run is judged correctly once something sets
  it. That is a `request.sh`/`dispatcher.sh` change, which belongs to
  lane.toolsmith after this PR.
- **Run the verdict inside the dispatcher.** The worker writes the result;
  `titles/table.py --judge` (or `title_verdict.py <dir>`) judges it. Putting
  the verdict into the worker would touch lines that were not lent.
- **Parse `hakuX-pace` properly.** Its format was not in the tree on
  2026-09-25 (lane.perfbase). The verdict records the line count, the first
  `late`/`worst`/`stall` figures it can find, and the last line, and does not
  judge any of them.
- **The Galleon, DOA3 and JSRF routes**: PR 2, on the Thor.

## Device budget (the owner's scale)

- **The target.** 1.0 needs 855 of xemu's 950 Playable+ titles, about 145
  validated per minor version.
- **Cost of one screening run.** Install and start take ~1 min, boot and
  menus to the mark take ~2-3 min, then 10 min of gameplay: **about 14
  device-minutes**. So 145 screenings are **about 34 device-hours**, not 24.
  The 10-minute figure leaves out boot.
- **Confirmations.** Only titles that pass screening get one, at about 24
  minutes each. If half pass, that is 72 × 24 min ≈ **29 device-hours**.
- **Total.** About **63 device-hours per minor version**.
- **What the queue can sustain.** On 2026-09-25 the Thor was carrying two
  100-suite sweeps and the Nova had ~15 lane requests waiting. If each
  handheld gives titles about 8 hours a day, 145 screenings plus
  confirmations take **about 4 days per minor version**. That leaves
  pgraph/arms work the other 16 hours a day. Running titles around the
  clock would halve it, at the cost of every arm queued meanwhile.
- **What can cut it.**
  - A screening that fails early stops early. A crash or a guest exit
    already ends the hold, and a missing gameplay mark could too, since the
    route knows when it gave up.
  - Screening at 5 minutes, confirming at 20, would cut the screening pass
    in half.
  - Generic-route runs cost a reviewer's look at a contact sheet, seconds
    per title.

## Why attempt 1 did not finish (recorded 2026-09-26, attempt 2)

- **The implementation commit was never pushed.** `2695e09853` sat only in
  the worktree, so PR #307's head stayed at `0239b7e1cd` (notes only). CI went
  green on that head, but on a head that carried none of the work.
- **The real run never started.** `scratch/realrun.sh` waits for a moment when
  the Nova has no hold and no running request. The Nova was busy with lane
  requests the whole time. The script's log was empty when the session ended,
  and no run directory was ever made.
- **The PR was left in draft** with no waiting comment, which is what the
  handback job found.

Attempt 2 merged `origin/master`. The conflict in `dispatcher.sh`'s
`snapshot_scripts` is resolved by keeping master's write-beside-and-rename
(dispatch defect 13). The temporary file is made in the target's own
directory, because `titles/route.sh` and `perf/pad.sh` live in
subdirectories. Attempt 2 then pushed, and retried the real run.

## Real run

(recorded below once the Nova is free; see PR #307)
