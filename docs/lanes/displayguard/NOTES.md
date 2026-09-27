# lane.displayguard (#494)

## Attempt 3 (2026-09-27, from ~13:20 PDT): why attempt 2 stopped short

Attempt 2 built the foreground guard, marked #495 ready and ended at ~12:40.
Addendum 3 (the focus read, 12:45) was written after that session had read
the brief, so its `hakux_in_front` still read `dumpsys window`: the first
`topResumedActivity`, then `mTopFocusedDisplayId` and that display's
`mCurrentFocus`. hostops measured at 12:43 that `dumpsys window` and
`dumpsys activity` both list the Thor's display 4 first. Audit pass 1
(four LOW) landed at 13:1x. Attempt 3 does both.

### Addendum 3: the focus read comes from `dumpsys input`

`devices.sh` `hakux_in_front` now makes one call,
`dumpsys input | grep -E '^  [A-Za-z][A-Za-z]*:|displayId=[0-9]+, name='`,
and reads `FocusedDisplayId: N`, then the `FocusedApplications:` and
`FocusedWindows:` entries by their `displayId=`. It tracks sections, so the
`FocusRequests:` entries (the same `displayId=D, name='...'` form) are not
read as focus. No `dumpsys window` and no `topResumedActivity` any more.

| answer | when |
|---|---|
| `in-front: <s> app=<pkg> focus=<pkg> display=0` (0) | N = 0 and display 0's focused window is `com.jreinach.hakux*` (and its focused application, if listed, too) |
| `not-foreground: <pkg> (input focus is on display N ...)` (1) | N != 0 |
| `not-foreground: <pkg> (the focused application on display 0 ...)` (1) | display 0's application is not hakuX |
| `not-foreground: <pkg> (holds input focus on display 0 ...)` (1) | display 0's focused window is not hakuX's (e.g. `NotificationShade`) |
| `foreground-unknown: ...` (2) | no `FocusedDisplayId`, or display 0 has no focused window |

Every fixture lists display 4 (SecondaryDisplayLauncher) first and ends with
a `FocusRequests:` entry naming Lime3DS on display 0. Legs: (a) Lime3DS
focused, (b) FocusedDisplayId 4, shade, no window, (c) hakuX, silence.
Mutants: **first-entry** (each section's first entry read as display 0's):
leg (c) reads `not-foreground: com.android.launcher3` and turns red;
**application only** (the focused-display and focused-window checks
removed): leg (b) reads `in-front` and turns red.

### Audit pass 1

- **L1 fixed.** Black frames now split in two at the end of the hold,
  while hakuX is still up: the soak re-runs `display_clear` and
  `hakux_in_front`. **Both clear** -> `render-black: ... hakuX drew black`,
  which title_verdict.py does NOT void: the fps stands and the run fails on
  that line (a title failure, not a re-queue). **Anything else**, unknown
  included -> `display-black: ... display 0 was not hakuX's at the end of the
  hold (<both lines>)`, void as before. For a run.log from before this
  change, the frames alone still void unless run.log has `render-black:`.
  (The audit suggested "void only without a `display-clear:` line"; I kept
  void for a run.log with `display-clear:` and no end-of-hold line, which
  is a soak that was killed before its end, so a rerun is the safe answer.)
  Residual: a black screen that neither check can see (not an overlay, not a
  focus change) reads as render-black. The first such case is the one to
  compare against a screencap.
- **L2 fixed.** `hakux_in_front` uses `ADB_RETRIES=1`: one retry, 2 s later,
  on an adb failure only. A single vsock drop no longer counts as an
  unknown; two consecutive failed reads (each already retried) still abort.
  Worst unwatched window: ~2 s poll + ~2 s retry, twice, about 8 s.
- **L3 fixed.** When the watcher sees something else in front, it stops
  the route first (input must not reach the launcher either), then reads
  `ps -A -o NAME`. If `$PKG:xemu` is gone it logs `ROUTE STOPPED: ... the
  guest exited (...)`, raises no flag and writes no `not-foreground:` line,
  and the hold loop's `alive()` reports `guest exited`. Leg: the guest dies
  at the 5th foreground read, and Lime3DS is in front. (`probe()` is defined
  after the watcher forks, so the read is inline.)
- **L4 declined.** The remedy re-issues the title's VIEW intent because
  Addendum 2 prescribes exactly that one non-input remedy. An intent
  without `rom_path` is unmeasured on a device and could land on the library
  screen, where the route would then play. It is rare (it needs the remedy
  path), it happens before any input, and run.log already carries
  `FOREGROUND: re-issuing am start on display 0` for whoever reads boot
  timing.

### Measured (attempt 3)

- `99-display-covered.sh` standalone: 22 of 22 under gawk, mawk and busybox
  awk (after merging master @ `origin/master` of 13:2x, 22 of 22 again).
- Mutants: first-entry, application-only (both in the fragment); and two
  ad hoc on soak_title.sh: no end-of-hold check -> the render-black leg red;
  no guest-exit probe -> the guest-exit leg red (`VOIDED no-exit-line`).
- Neighbours: 84-perf-regimen 21/21, 89-title-verdict 36/36,
  99-iso-roots 10/10, 99-title-state 9/9 (new on master).

### Still not verified on a device

The `dumpsys input` layout comes from hostops' 12:43 Thor read (quoted in
Addendum 3) and devwatch.py's read of the same text; the fixtures follow it.
If the Nova's text differs, the answer is `foreground-unknown` and route
soaks abort with no input sent. The first route soak after the fold is the
pilot: its run.log must show `in-front: <serial> app=com.jreinach.hakux...
focus=com.jreinach.hakux... display=0` before `ROUTE started`.

## Attempt 2 (2026-09-27, from 12:35 PDT): why attempt 1 stopped short

Attempt 1 started at 11:55 PDT from the brief as it stood then: the display
check only. It built that, marked #495 ready at ~12:18, and ended. Addendum 1
(the route drives other apps; 12:05) and Addendum 2 (check input focus;
12:35) were written into the brief after the session had read it, and a
running lane does not re-read its brief. hostops put #495 back in draft at
12:31 and resumed the lane. Attempt 2 builds the foreground guard below in
the same PR.

## The foreground guard (attempt 2)

| where | what |
|---|---|
| `docs/testing/devices.sh` `hakux_in_front <serial>` | **Superseded in attempt 3 (reads `dumpsys input`; see above).** Attempt 2: one adb call: the first `topResumedActivity=` of `dumpsys activity activities`, and from `dumpsys window` the `mTopFocusedDisplayId=` line and the `mCurrentFocus=` of that display (the per-display blocks start `Display: mDisplayId=N`; with no blocks, the first `mCurrentFocus`). Prints `in-front:` (0), `not-foreground: <pkg> (<why>)` (1) or `foreground-unknown:` (2). In front means: top activity is `com.jreinach.hakux*`, top-focused display is 0, and the focused window is hakuX's. No retries: the caller polls. |
| `docs/testing/soak_title.sh` `fg_wait` | before the route's first input: poll every `FG_POLL_S` (2 s) for up to `FG_WAIT_S` (30 s), then ONE remedy that sends no input (the same `am start` with `--display 0`), then `FG_REMEDY_S` (15 s) more. Still not in front: `ROUTE ABORTED: not foreground (<pkg>)`, a `not-foreground:` line, `ROUTE NOT PLAYED`, no route process at all, exit 5 through `release()` (force-stop hakuX, REST, lease). Never a tap or a key. |
| `docs/testing/soak_title.sh` `fg_watch` | beside the route, every `FG_POLL_S` while route.sh is alive (not a zombie): one `not-foreground`, or two unknowns in a row, TERMs route.sh, logs the same two lines and writes a flag. The hold loop sees the flag at its next poll, logs `soak aborted: not-foreground after Ns`, and the soak exits 5. It aborts; it never resumes. |
| `docs/testing/title_verdict.py` | a `not-foreground:` line voids the run the same way as `display-covered:` / `display-black:`. |
| `99-display-covered.sh` | legs (a) Lime3DS on top, (b) hakuX on top with focus on display 4's SecondaryDisplayLauncher, a flat-focus and a null-focus variant, (c) both hakuX, silence; the soak legs for (a), (b), (c) and mid-route; the verdict. |

**route.sh is TERMed by PID, not by process group.** The brief says "kill
the route process group". A group kill reaches pad.sh between a press's
key-down and key-up (pad.sh sleeps 60 ms between them) and leaves the button
held down on the owner's app. TERM to route.sh alone runs its trap as soon
as the press in flight returns (its `wait` on a sleep returns at once),
stops there, and sends only releases for buttons the route was holding. The
worst case after the abort is one press already in flight, which a group
kill cannot prevent either: the adb call carrying it has already been sent.

**Dry routes are not checked.** `ROUTE_DRY=1` sends no input, and
89-title-verdict drives a dry route against a fake adb that answers no
dumpsys. Under the guard those legs would wait 45 s and abort. The soak logs
`FOREGROUND: not checked: ROUTE_DRY, the route sends no input`.

**Unknown is not in front.** Before the first input, an unknown answer
waits like a wrong one, then aborts. While the route plays, two unknowns in a
row (about 4 s) abort. A WSL vsock drop can therefore void a route soak; a
void run costs a re-queue, and input with nobody watching can cost the
owner's save.

### Measured (attempt 2)

- `99-display-covered.sh` standalone: 18 of 18 under gawk, mawk and busybox
  awk (10 display legs from attempt 1, 8 foreground legs).
- Mutants, each run in a scratch copy:
  - the focus checks removed from `hakux_in_front` (the top activity only):
    leg (b) reads `in-front:` and turns red.
  - the watcher not started (`fg_watch &` -> `: &`): the route presses B
    into Lime3DS 2 s in, and the mid-route leg turns red on `B-PRESSED`.
  - the pre-route wait removed (`fg_wait || return 1` -> `: || return 1`):
    soak legs (a) and (b) turn red on `INPUT-SENT route-started`, and (c)
    turns red on its missing `in-front:` line. 15 of 18.
- Neighbours unchanged against master: 84-perf-regimen 21/21,
  89-title-verdict 36/36, 99-iso-roots 10/10.

### The dual-screen overlay after the reboot (Addendum 1's last paragraph)

hostops found the root cause at 12:10-12:15 PDT:
`settings system dual_screen_display_mode` was 2, set, it seems, by injected
route input. It persists across a reboot, and under it the assistant's
`primaryScreenTopLayout` covers display 0 (display-0 screencaps are black
with hakuX on top). hostops set it to 0, and `harness_health.py`'s
`covered:` check, the same rule `display_clear` ports, cleared. gta482 then
saw GTA render at 59 fps. So the window attributes the rule keys on do
separate the two states: under mode 2 the window really covers hakuX, and
refusing the run is right. A lane cannot read the device, so I have not
compared the window's attributes in both states myself. If a clean-display
soak is ever refused with `display-covered: primaryScreenTopLayout`, that is
the case to compare, with the black-screencap test as the fallback.

### Not verified on a device

- The dump format. The fixtures follow AOSP's `dumpsys window` layout
  (per-display `Display: mDisplayId=N` blocks with their own
  `mCurrentFocus`, `mTopFocusedDisplayId=` in the windows section) and the
  `topResumedActivity=ActivityRecord{h u0 pkg/cls t}` line that
  harness_health already parses live. gta482's `grep -m1 mCurrentFocus=`
  (PR #491) read display 4's launcher on the Thor. If the real text differs,
  the answer is `foreground-unknown`, and every route soak aborts with no
  input sent. That fails loudly and safely.
- **The first route soak after the fold is the pilot.** Its run.log must show
  `in-front: <serial> top=com.jreinach.hakux... focus=com.jreinach.hakux...
  display=0` before `ROUTE started`, and no `FOREGROUND:` lines while the
  route plays. If every route soak ends `not-foreground: unknown`, the parse
  is wrong: fix `hakux_in_front`, and do not remove the call.
- A hakuX popup or dialog that takes focus under a window title without the
  package (`PopupWindow:...`) would read as not ours and abort. None is
  known.
- Cost: every 2 s while a route plays, one `dumpsys activity activities`
  and one full `dumpsys window` run on the device. Neither is measured
  against gfps. A route soak's fps should be compared with one from before
  the guard on the same handheld and the same window before anyone reads a
  small fps change as the title's.

### Follow-ups (other lanes' files)

- **route.sh per-step check** (lane.titlestate's, PR #496): call
  `hakux_in_front "$SERIAL"` before each input step, and exit on rc != 0.
  The soak's 2 s watcher bounds the exposure to one poll. A per-step check
  bounds it to one step.
- **run_disc.sh** (lane.toolsmith's): the pgraph path sends no route input,
  so only `display_clear` applies there (see below).
- `perf/pad.sh` callers outside the soak (`capture_gta.sh` and other
  lane-local scripts) have no guard unless they call `hakux_in_front`
  themselves.

## Attempt 1: the display check

## What changed

| where | what |
|---|---|
| `docs/testing/devices.sh` `display_clear <serial>` | after the wake: `dumpsys power` must read `mWakefulness=Awake` (three reads, 1 s apart, when it reads something else), and `dumpsys window windows` must have no window block on `mDisplayId=0`, `fillxfill`, `mHasSurface=true`, `mViewVisibility=0x0`, of type BOOT_PROGRESS / SYSTEM_OVERLAY / APPLICATION_OVERLAY / SYSTEM_ALERT, whose package is not hakuX or systemui. The rule is `harness_health.py`'s `covered:` check, ported to awk. Prints `display-clear:` (0), `display-covered:` (1) or `display-unknown:` (2). |
| `docs/testing/soak_title.sh` | calls it after `KEYCODE_WAKEUP`, before audio is armed, the perf mode is set, logcat is started or `am start` runs. On covered: the line goes to run.log, the EXIT trap is cleared (no `KEYCODE_SLEEP` under the owner's app), the lease is removed, exit 4. On unknown: logged, and the run goes on. After the hold: when every route frame is under 12,288 B, it logs `display-black: all N route frames under 12288 B (largest X B)`. |
| `docs/testing/title_verdict.py` | new `void` field. It is set from a `display-covered:` or `display-black:` line in run.log, or from the route frames themselves when all are under 12,288 B, so a run.log from before this change is judged the same way. A void run has no fps windows (every fps field is null), `void: ...` is its first failure, and it does not pass. |
| `docs/testing/jobs/selftest.d/99-display-covered.sh` | the fixtures and legs listed below |

`title_verdict.py` is not on the brief's Files list. It had to be touched: the
dispatcher ignores the soak's exit code (`dispatcher.sh` ~767 runs the soak,
then always writes `result.json` and `DONE`), so the verdict is the only
reader that can void the run. No open PR claimed the file.

## What happens to a refused request

`dispatcher.sh` runs `soak_title.sh`, ignores its exit code, writes `result.json`
(0 log lines, 0 frames) and `DONE`, and moves the request into the result dir.
The request is consumed and not requeued. `title_verdict.py` then reads
`display-covered:` in run.log and writes `void: display-covered: ...` as the
first failure, with `pass: false` and every fps field null. Before this change
the same run would have failed as `booted: ...`, which is wrong about the
cause. The black runs of 09-27 would have been judged on their flips.

## Measured

- Selftest fragment, standalone: 10 of 10 pass under gawk (the host's awk),
  mawk and busybox awk.
- Mutants, each run against a scratch copy of `docs/testing`:
  - the overlay-type condition removed (in the fragment): the clear leg goes
    red, because the owner's Lime3DS `BASE_APPLICATION` window reads as a cover;
  - the soak's refusal removed: the covered leg goes red (rc 0, `am start` reached);
  - the verdict's run.log void removed: 2 legs go red;
  - the frames-on-disk void removed: 1 leg goes red;
  - the fps windows kept on a void run: 2 legs go red (`fps_ok_share` 1.0 on a black run).
- Neighbouring fragments that drive `soak_title.sh` / `title_verdict.py`:
  84-perf-regimen 21/21, 89-title-verdict 36/36, 99-iso-roots 10/10, the same
  as on master. The existing fake adbs answer `dumpsys` with nothing, which
  reads as `display-unknown`, and the run goes on. My first draft put the
  refusal flag inside `release()` and split the `perf_leave` +
  `KEYCODE_SLEEP` pair that 84's mutant anchors on. The refusal now clears the
  EXIT trap itself instead, and `release()` is unchanged.
- The same rule on the live handhelds: `host-tools/.health-state.json`
  (2026-09-27, ~19:05 UTC) holds `covered:thor` and no `covered:nova`. So the
  Python original flags the real 09-27 block and does not flag a clean Nova.

## Not done: the real-device pilot

The brief asks for a 60 s soak on a clean handheld. It could not run from this
branch:

- The dispatcher runs `soak_title.sh` and `devices.sh` from `$DISPATCH_DIR/bin`,
  a snapshot of the MASTER checkout (`snapshot_scripts`). A queued request runs
  master's soak, not this branch's. The only other way to run the soak
  would be to drive the device directly, which a lane may not do.
- Both handhelds were held all session: the Nova by the owner (charging) and
  the Thor by hostops-display (this very overlay).

So the pilot happens on the first title soak after the fold. Every soak's run.log
now carries one `display-*` line near the top. The first soak on a handheld
with a clean display must show `display-clear: <serial> Awake, no foreign
overlay on display 0 (N windows read)` and then run as before. If it shows
`display-unknown`, the awk port does not parse the real text (the run still
goes on). If it shows `display-covered` on a device whose display-0 screencap
is not black, the port disagrees with harness_health and is refusing good runs.
Revert the call in `soak_title.sh` first; the verdict change can stay.

## Follow-ups (not this lane's files)

- **pgraph path**: `run_disc.sh` (lane.toolsmith's) has no display check.
  A covered display there would presumably give black captures, scored as
  wrong pixels rather than void. Calling `display_clear "$SERIAL"` there
  before `am start` would close that gap. That file is lane.toolsmith's, so
  this lane did not edit it.
- **Unknown proceeds.** When adb cannot answer, the soak runs, and only a soak
  with a route has the black-frame backstop. A soak with no route and an
  unreadable window list on a covered display is still unguarded.
- Other fps readers that parse `gfps` straight from logcat (`perf/summarise.py`,
  `vblank_*`, `pace_check.py`) do not read `void`. Only `title_verdict.py`
  (and through it `status_html.py` / `titles/table.py`) does.

## Do not repeat

- Do not put anything between `perf_leave` and the `KEYCODE_SLEEP` line in
  `release()`: 84-perf-regimen's mutant anchors on that pair.
- The black threshold is on file size, not pixels. A 1920x1080 all-black PNG
  is 10,899 B. A title whose every route frame is a near-black loading screen
  also reads as black. In that case the route saw nothing either, so void is
  still right.
