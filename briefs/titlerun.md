# The title instrument: scripted play through the queue, and a verdict per run

Lane: titlerun            Issue: none (harness; the owner's 1.0 ruler, 2026-09-25)
Base: origin/master
Files: docs/testing/soak_title.sh, docs/testing/perf/pad.sh, docs/testing/titles/**,
docs/testing/title_verdict.py, docs/testing/jobs/selftest.d/89-title-verdict.sh, docs/lanes/titlerun/**.
**Lent from lane.toolsmith for this lane's first PR only:** docs/testing/request.sh and
docs/testing/dispatcher.sh. Limit those edits to the few lines named below, and nothing else in
either file. They return to toolsmith when your first PR folds.
Needs device: yes, the **Nova** (`ee317437`) under bounded holds; the Thor is running the 0.5
release sweeps until about 20:30 PDT. Needs NDK: no. Prediction: none; this is harness work,
proven by selftest fixtures and a real run.

## Why

The owner set 1.0 as a games target: ≥90% of a fixed list of xemu's top-ranked Playable titles must
be **playable on our handhelds**, judged mechanically:
- reaches gameplay by a scripted route;
- 20 minutes of scripted play with no crash, hang or abort;
- full speed (the title's own 30/60 target in ≥90% of gameplay windows);
- no dropouts in audio.

pgraph pixels stay the regression gate. Titles become the ruler. **This lane builds that ruler.**

Programmed input already exists and has done real work:
- `docs/testing/perf/pad.sh` injects evdev gamepad events with `sendevent`;
- `run_perf.sh` pressed through Crimson Skies' intro (which exposed the crash fixed in `fe418afedf`)
  and drove the Galleon runs.

What is missing is plumbing and a judge:
- A soak queued through the dispatcher (`request.sh --title`) plays **no input**
  (`soak_title.sh:92-98`), so it only ever sees intros, attract demos and menus.
- `pad.sh` hardcodes the Nova's serial and `event7`.
- Nothing turns a soak's logcat into a verdict.

## The job

1. **`pad.sh`, device-agnostic.**
   - `SERIAL` required from env (no default).
   - `PAD_DEV` auto-detected when unset: the `/dev/input/event*` node whose `getevent -pl` lists
     `BTN_SOUTH`/`BTN_A` and `ABS_X`. Cache it per serial under `$HAKUX_WORK/pad-dev.<serial>`.
   - Record the Thor's node once it is free (read-only `getevent -pl` is fine while it runs a
     sweep).
   - Keep `press`, `axis`, `mash`, `startmash`. Add `hold <BTN>` / `release <BTN>`.
   - **Never `input keyevent 96` or any non-gamepad key: it exits the app.**
2. **Routes.**
   - A route is a small text file in `docs/testing/titles/routes/<name>.route`, run by
     `docs/testing/titles/route.sh`:
     - `wait <s>`
     - `press <BTN> [ms]`
     - `hold`/`release`
     - `axis <code> <val>`
     - `mash <BTN> <n> <gap_s>`
     - `mark <label>`
     - `repeat <n> { ... }`
   - Each step is logged with a timestamp.
   - `mark` also writes a logcat line (`adb shell log -t hakuX-route "mark <label>"`), so the verdict
     can find the gameplay window in logcat time. **`mark gameplay` starts the scored window.**
   - Write `crimson-skies.route` from `run_perf.sh` and `fuzion-frenzy.route` from `bench_ff.sh`
     first. Then write routes for Galleon, DOA3 and JSRF when the Thor is free: they are the §11
     soak titles.
3. **Queue plumbing (the lent lines only).**
   - `request.sh --route <name>` reads the route file from YOUR tree at queue time and embeds its
     TEXT in the request JSON as `route`, so the request is self-contained and records exactly what
     was played. It is valid only with `--title`.
   - `dispatcher.sh` writes `route` to `$rdir/route.txt` and passes
     `ROUTE_FILE="$rdir/route.txt"` to `soak_title.sh`.
   - It adds `hakuX-route:I` and `hakuX-pace:I` to `LOGCAT_SPEC`, and `titles/route.sh
     perf/pad.sh` to `SCRIPT_DEPS`.
   - Read host memory "A new snapshot file misses the first re-exec" before you touch
     `SCRIPT_DEPS`.
4. **`soak_title.sh`.**
   - When `ROUTE_FILE` is set, start `route.sh` in the background after `am start`, and stop it
     when the hold ends.
   - **Fix the liveness check:** one failed `adb ps` (a WSL `UtilAcceptVsock` error) currently
     ends the soak as "guest exited" (`:115`). It ended a 180 s Ghoulies soak at 35 s today while
     the emulator was running. Retry up to three times, 2 s apart. Count adb failures separately
     and write `adb_failures=N` to `run.log`.
   - This is host defect 19, moved here from lane.toolsmith because the file is yours.
5. **`title_verdict.py <result-dir>`.**
   - Reads `run.log`, `logcat.txt`, `request.json` / `result.json` and `titles/targets.toml` (per
     title: ISO names per device, target fps, route, notes).
   - Writes `verdict.json` beside them and prints one line.
   - **Fields:**
     - `booted`
     - `reached_gameplay` (the route's `mark gameplay` plus at least one guest flip after it)
     - `crash` (`hakuX-crash`, `libc:F`, `DEBUG:F`, or a real exit)
     - `hang` (no `hakuX-perf` line for more than 10 s after the mark while the process lived)
     - `fps_ok_share` (the share of `hakuX-perf` windows after the mark at or above target)
     - `pace` (from lane.perfbase's `hakuX-pace` line when present: late frames per 100, and the
       worst stall)
     - `audio_starve_share` (short callbacks after the first 10 s, from the `starve:` lines)
     - `pass`, with the failing criterion named.
   - Read the `hakuX-perf` format from `pgraph/profile.c:577-661`. **G is a smoothed average**:
     judge windows by the per-window numbers, not by G. Say which field you use and why.
6. **A table.** `docs/testing/titles/table.py` prints the latest verdict per (title, device, ref)
   from the results directory, for the owner's per-title table.

## Proof

- **`selftest.d/89-title-verdict.sh`**, built on fixture result dirs:
  - one that passes;
  - one that crashes;
  - one that hangs after the mark;
  - one with no `mark gameplay`;
  - one below target;
  - one with an adb failure that is **not** a guest exit.
- **Mutants** (each must turn the fragment red):
  - judge by G;
  - count pre-mark windows;
  - treat one adb failure as an exit;
  - drop the hang check.
- **A real Nova run** of the Crimson Skies route through your own scripts, under a hold of at most
  60 minutes (read AGENTS.md "Working with a device" first; wake the screen with
  `KEYCODE_WAKEUP`). Record `verdict.json`.
- `bash docs/testing/jobs/selftest.sh`: all green, with the totals in the PR body.

## Do not

- **Edit anything in `request.sh` or `dispatcher.sh`** beyond the lines in step 3. They are lane.toolsmith's.
- **Hold the Nova while another lane's request is running there,** or for more than 60 minutes.
- **Change emulator settings globally,** or leave any setting changed on a device.
- **Trigger CI as a self-check.**

## Done when

- **PR 1:** steps 1 and 3-5, the fragment and mutants, and one real verdict. Preflight passes and
  the PR is marked ready. It touches the dispatcher's serve path, so expect `needs-audit-1`.
- **PR 2:** the Galleon, DOA3 and JSRF routes, each with a real verdict on the Thor once it is
  free.

## The owner's criteria and the scale (2026-09-25, supersedes "full speed" above)

**Ratings, decided by the owner:**
- **Playable** means at least **30 fps at 1x surface scale** in at least 90% of the gameplay windows.
  The title must also reach gameplay, run 20 minutes with no crash, hang or abort, and play its
  audio with no dropouts.
- **Playable (2x)** is the same bar, met at 2x surface scale. It is a separate rating: the run must
  set `surface_scale` 2 and record it.
- **Perfect** comes only from a human's review. The machine never assigns it. `verdict.json` has a
  `human_review` field the machine leaves empty.
- **Flag, do not fail:** a title whose own target is 60 that reaches 30 but not 60. Many Xbox games
  tie game speed to the frame rate, so such a title may be running in slow motion. Record
  `target_fps` and `below_own_target: true` so a human can check.

**The scale:**
- 1.0 needs 855 of xemu's 950 Playable+ titles, which is about 145 validated per minor version, 0.5
  included (a stretch). Hand-written routes do not scale to that. So PR 1 also carries a **generic
  route**, used when a title has none:
  - boot;
  - alternate START and A through the attract screen and menus, with pauses long enough for FMVs
    and skippable intros;
  - then a generic "play" pattern: left stick forward, A every few seconds, and a camera nudge.
- The verdict writes a **contact sheet** (a grid of frames) for every run. A reviewer (an agent that
  reads PNGs, or the owner) judges "reached gameplay" in seconds. Record `gameplay_by: route|review`.
- Runs come in two passes:
  - a **10-minute screening** for every title;
  - the **20-minute confirmation** only for titles that pass screening.
- Budget the device time in NOTES: about 145 titles at 10 minutes is about 24 device-hours. Say
  what the queue can sustain.
- **The master list:** `/home/justin/hakux-work/titles/xemu-compat-2026-09-25.csv` (1,104 titles,
  950 Playable+). Its `title_id` is the XBE certificate's. Key `targets.toml` on it.
- lane.xbox is inventorying the console's storage against the same list. The host will stage ISOs
  onto the handhelds in batches from what it finds. Staging is the host's; you don't copy ISOs.
