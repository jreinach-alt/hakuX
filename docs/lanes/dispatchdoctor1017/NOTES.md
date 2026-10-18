# dispatchdoctor1017

## Resume (attempt 2, 2026-10-17 09:00 PDT)

Attempt 1 ended its turn at 07:31 with a background selftest still running
(a `run_in_background` Bash call). A headless session ends the instant its
turn ends: nothing after that point ran, and nothing from that run was
committed, which is why `git status` at the top of this attempt still shows
Section 1's edits (`devices.sh`, `dispatcher.sh`, `98-dispatch-doctor.sh`,
this NOTES.md) sitting uncommitted exactly as attempt 1 left them -- the code
itself was written, only the verify-and-commit step never happened. This
attempt runs the selftest in the foreground (one `timeout`-bounded Bash call,
polling its own log if needed, never `run_in_background` for anything this
session needs to see the result of before ending), fixes whatever it finds,
then commits and pushes before moving on to 1b/1c/Section 2/3.


Brief: `/home/justin/hakux-work/briefs/dispatchdoctor1017.md`, owner's word via
lane.local 2026-10-17 ~07:00 PDT, amended mid-lane by lane.local into three
sections (1/1b/1c staging+route+profile fast path, 2 Sonnet doctor, 3
visibility). This file tracks Section 1; later sections get their own
`## Section N` heading as they land, not a new file (lane.md: one NOTES.md
per lane, root-level NOTES.md would collide on every fold).

## Section 1 -- the deterministic staging fast path (in progress)

The evidence the brief opens with: of the last ~5000 dispatch results, ~45
ERRORed "title not on device" while the ISO sat on a host D: staging root the
whole time -- the dispatcher looked at the device and gave up, never at
the host paths it had every right to check. That is the single largest
ERROR class by a wide margin (next is "0 captures", 14), so it is the one
this session did first (owner 2026-09-28, memory `balanced-not-cheap-first`:
rank by probability x size of the win, not by what is cheapest to try).

### What changed

- `docs/testing/devices.sh`: `staging_roots()` (every root in
  `HAKUX_STAGING_ROOTS`, or `STAGING_ROOTS_DEFAULT` -- the real
  `/mnt/d/hakux-staging/{sweep,xiso,nova-archive-*,lanelocal-*,staging,ingest}`
  -- one per line, so a selftest fixture can point it at a tempdir with one
  root instead), `staging_find_tid()` (first `<root>/<TID>-*.xiso.iso`,
  matched on the leading 8 hex chars case-insensitively, not the full name --
  the staged file's own region/release tag never has to match anything),
  `staging_file_sha()` (a `.sha` sidecar's content when one sits next to the
  file, a fresh `sha256sum` only when it does not -- a sidecar this host
  already trusted is never recomputed), and a `staging-find <tid>` CLI verb
  for a human or `request.sh` to use at queue time.

- `docs/testing/dispatcher.sh`:
  - `FREE_FLOOR_BYTES` (25 GiB, env-overridable like every other constant in
    the file -- this is what let the selftest fixture work in kilobytes
    instead of needing real multi-gigabyte files).
  - `dev_free_bytes <dir>`: `df -k`'s Available column, counted from the end
    (Mounted-on, Use%, Available) so a Filesystem field with spaces in it is
    never mistaken for the number.
  - `title_claimed <tid>`: true when a queued or running request names this
    title, by `title_id` or by a `title` string that resolves to it via
    `titlestate.py tid-for-iso`. The one check that makes deleting anything
    to make room safe.
  - `make_room_for_push <root> <need> <rdir>`: deletes on-device ISOs, one at
    a time, oldest-listed-first, until `need` bytes plus the floor are free
    -- but ONLY a file that (a) `title_claimed` says nothing wants and (b)
    verifies by sha256 against a copy this host also holds on D: staging.
    Anything else is left alone, whatever the floor needs (owner, 10-13:
    pushes and deletes on the Nova are fine; the floor itself and app data
    are never touched to make room -- that line is in the brief verbatim and
    is the one hard boundary in this whole section). Every deletion is logged
    to both `dispatcher.log` and `$rdir/room.log`.
  - `console_stage_tid <tid> <rdir>`: last resort, `titles/bin/stage_xiso.py`
    (outside this repo, never edited here) -- a read-only FTP mirror from the
    console itself. Respects that script's own PAUSE/STOP files, 900s
    timeout. Never itself a claim failure -- "this did not help" either way.
  - `ensure_title_staged <title> <rdir> <req>`: the fast path itself, called
    from the soak block only after `device_title_path` has already missed
    every device root. Title id from the request's own `title_id` field, or
    `titlestate.py tid-for-iso` on the title string. `staging_find_tid`, then
    `console_stage_tid` if staging came up empty, then room-check, then
    `dev_push` under the exact title string the request named (so the
    caller's immediately-following re-check of `device_title_path` finds it
    where it expects).
  - The soak block itself: `touch "$LEASE"` moved earlier (before the title
    check, not after), and the immediate ERROR-on-miss replaced with a call
    to `ensure_title_staged` and one retry of `device_title_path`, falling
    through to the SAME `device_title_miss` ERROR text, prefixed with what
    staging tried, only if the retry still misses.

### The one constraint every edit here was shaped around

`jobs/selftest.d/99-iso-roots.sh` is NOT in this lane's territory and must
not change. It `sed`-extracts the soak block's literal `local tpath ... fi`
lines out of `dispatcher.sh` and runs them standalone with only `$title`,
`$rdir`, `$req` bound under `set -u`, then asserts on `device_title_miss`'s
exact text (a Nova single-root miss: `case "$out" in MISS*"searched
$NOVA1")`, no trailing wildcard -- so `device_title_miss`'s own text has to
stay the unchanged SUFFIX of the ERROR, with anything new as a prefix. And
`sed`'s anchor for the closing `fi` is exactly 8 spaces of indent, so every
new nested `if`/`fi` inside the block had to sit at 12+ to stay inside the
extracted span.

### Selftest

`docs/testing/jobs/selftest.d/98-dispatch-doctor.sh` (new, in territory):
six legs against a fake `adb` (push case added to the existing fake-shell
pattern from `99-iso-roots.sh`; `df -k` special-cased to report
capacity-minus-actual-file-bytes, in exact bytes, so a push or a delete
moves the reported free space with no filesystem block-size rounding to
chase) --

- staging find matches by TitleID head, not the staged file's full name.
- sha sidecar: `staging_file_sha` returns a sidecar that is WRONG on
  purpose, proving it read the file rather than recomputing.
- stage: empty device, room to spare -- pushed under the request's own
  title string.
- floor refuses: empty device, capacity set exactly at the floor -- nothing
  to clear, the push does not happen.
- room: an unclaimed, D:-verified on-device ISO is deleted to clear the
  floor, logged, then the push lands.
- claimed kept: the same ISO, but a queued request names its title_id --
  kept, the push stays refused.

Ran together with `97-dispatch-deploy.sh` and `99-iso-roots.sh` via
`docs/testing/jobs/selftest.sh` (the full suite, since fragments share no
state but the run is cheap) to confirm nothing in Section 1 broke either of
the out-of-territory checks it was designed around. Result: see this file's
next revision, or the PR thread -- recorded here once the run this session
started actually finished.

### Deferred this session (still open)

1b (auto-attach a recorded route when a soak has none), 1c (restore an
existing profile backup before launch), Section 2 (`dispatch_doctor.sh`,
Sonnet-model headless diagnosis, retry/hourly cap, owner-play/battery/Halo
gating), Section 3 (richer ERROR text beyond what 1 already adds, and the
hourly-report line -- requested from lane.local, never edited directly since
it's host-tools-generated). A queue-time staging advisory in `request.sh`
(using `devices.sh staging-find`, no device call) was planned alongside
Section 1 but not yet started either.

None of this used a live device: no `request.sh`/`ab_run.sh` call was made,
no device hold taken. `Prediction: none` stands -- this is harness/fixture
work, decided by the selftest, not a soak result.

### Selftest result (attempt 2, foreground)

`98-dispatch-doctor.sh` alone (`SELFTEST_ONLY`) found two bugs in the
fixture itself, not in `dispatcher.sh`/`devices.sh`:

- its "room"/"claimed kept" legs named the old on-device title `WXYZ0002`,
  which is not valid hex (W/X/Y/Z) -- `make_room_for_push`'s own case guard
  (deliberately hex-only, titles IDs are hex) silently skipped it via its
  `*) continue ;;` arm, so nothing was ever deleted and the push never had
  room. Renamed to `FEED0002` (valid hex) throughout.
- none of the four legs that reset `$DD/fs`/`$DD/dispatch` between cases
  created `$DD/rdir` first, so the first leg to actually reach
  `make_room_for_push`'s deletion path (room.log write) failed on a missing
  directory. Added `$DD/rdir` to the same `rm -rf`/`mkdir -p` lines.

With both fixed: `98-dispatch-doctor.sh` 6/6, and, run together with its
chain so the leftover-state legs have what they need (`SELFTEST_ONLY="50-arms-requeue
51-dispatch-hardening"`, 77/77 since 51 chains off what 10-50 leave) and
alone (`97-dispatch-deploy`, `99-iso-roots`, `98-dispatch-late-device`,
`99-dispatch-gate`, `99-profile-gate`, `99-title-state`, `99-battery-admit`,
`99-lane-model-file`, 168/168): all 0 failed. A full, un-scoped run (all 147
fragments) was started and left polling across several foreground windows
(each bounded by its own `timeout`, never a bare background job past a turn
boundary) rather than scoped narrower, since it was already in flight when
Section 1b's own verification need came up -- see that section below for the
result.

## Section 1b -- auto-attach a recorded route when a soak names none (done)

The brief, verbatim: "it should know to copy ... the pathing ... to the
right locations". A request that names no `--route`, or only the generic
`survey`, now gets this title's best recorded route attached automatically,
at both the points a request could reach the device without one: queue time
(`request.sh`, before this session's existing resolve/crop-embed/`--check`/
profile-gate block) and claim time (`dispatcher.sh`'s new
`ensure_route_attached()`, for a request written before this existed, or by
a tool other than `request.sh`). Both call the same two new
`titlestate.py` subcommands, so an auto-attached route travels identically
to a user-typed `--route` from that point on -- same resolve, same `--check`,
same profile-gate re-run, same crop embedding.

### What changed

- `docs/testing/titles/titlestate.py`: `suggest_route(title_id)` -- tries
  `known_path(title_id, broad=False)` first (a route this host has actually
  PROVEN reaches gameplay, via a `mark gameplay` route text plus a judged
  `reached_gameplay` result -- the same, narrow R3 test the profile gate
  itself uses, never the broader "a pathknow session happened once"
  signal); falls back to `targets.toml`'s own configured route for the
  title (the same field `route_path()`/`single_route()` already trust);
  returns `(None, note)` when neither exists -- nothing is ever invented.
  `route_refs(route_path_, cap)` -- the reference-crop embedding logic
  (Addendum 3, #433) factored out of `request.sh` so `dispatcher.sh`'s
  claim-time attach can reuse it verbatim rather than duplicating it in
  bash. Both exposed as CLI subcommands (`suggest-route`, `route-refs`) for
  the bash callers.

- `docs/testing/request.sh`: right after `TITLE_ID` is computed, before the
  existing `if [ -n "$ROUTE" ]` block -- if `$TITLE_ID` is known and `$ROUTE`
  is empty or literally `survey`, and none of `--find-route`/
  `--remake-profile`/`--path-broken` was also given, call `suggest-route`
  and, if it names one, set `ROUTE` to it (logged to stderr) before the rest
  of the block runs. No separate opt-out flag exists or was added: an empty
  `--route` with no suggestion available still runs with no scripted input,
  and a deliberate `--route survey` with no suggestion available still
  resolves to the real, generic `survey.route`, exactly as before this
  existed.

- `docs/testing/dispatcher.sh`: `ensure_route_attached()`, called from the
  soak block right after `ttid` is computed and before `tstate`/`tsave` are
  read (so a route it attaches is visible to everything downstream exactly
  like a user's own `--route`). Same no-override-flags guard as
  `request.sh`. Resolves the suggested route via `titlestate.py
  resolve-route` (the same path a user-chosen name takes), runs
  `route.sh --check` on it, embeds crops via `route-refs`, and only then
  mutates the request JSON in place (`route_name`, `route`, `title_state`,
  `route_refs`) via a small inline `python3 -c`. Any failure at any of
  those steps (resolve refuses, `--check` fails, crop cap exceeded) is
  logged and the request is left exactly as queued -- the soak still runs,
  on survey, same as if this never existed.

### The judgment call

Auto-attach is suppressed whenever `--find-route`, `--remake-profile`, or
`--path-broken` is also given, in both files. First version did not have
this guard and broke three legs of the out-of-territory
`99-profile-gate.sh` (A3, A4, M9): with `ROUTE` empty, auto-attach fired
*before* `admit()`'s own R3/override logic ever ran, attaching a
fixture route that then failed its own `--check` (no `# state:` line) and
masked the expected "already has a proven route, queue it instead of
finding one blind" refusal, and separately defeated `--path-broken`'s
override outright. Each of those three flags is itself a deliberate,
specific statement about how the caller wants this title's route/profile
state handled right now -- forcing a full resolve ahead of that is second-
guessing it, not helping it. Fixed by excluding all three from eligibility;
re-verified the three previously-red legs plus the rest of
`99-profile-gate.sh` green together with `97-dispatch-deploy`,
`98-dispatch-doctor`, `99-iso-roots`, `99-title-state`, `99-battery-admit`
(179 passed, 0 failed).

### Selftest

`docs/testing/jobs/selftest.d/98-dispatch-doctor.sh` grew 4 new legs (10
total): a title known only via `targets.toml` gets that route attached
("target" source); a title with a proven dispatch-history route gets that
one instead, outranking a merely-configured target ("proven" source,
confirmed to win when both exist); a title with neither recorded nor
configured gets nothing, and the request is left exactly as queued; a
request that already names its own route is never touched. All against a
fake `adb`/`log()` harness mirroring `99-iso-roots.sh`'s pattern, with
`dispatcher.sh` sourced under `TITLE_TARGETS`/`TITLE_ROUTES`/
`DISPATCH_DIR` pointed at the fixture.

The override-guard itself (no attach when `--find-route`/`--remake-profile`/
`--path-broken` is set) has no dedicated leg in `98-dispatch-doctor.sh` --
it is covered only by `99-profile-gate.sh`'s own A3/A4/M9 legs passing
(out-of-territory, not written by this lane). Worth a dedicated leg if this
file is touched again.

A full, un-scoped selftest run (no `SELFTEST_ONLY`, all 147 fragments, this
session's earlier Section-1-era run never reached this point) completed
end to end this session, polled in the foreground across several
`timeout`-bounded windows rather than left running past a turn boundary:
**3580 passed, 0 failed, all 147 fragments.** This is the first full,
complete, unscoped confirmation this lane has had -- it covers
`50-arms-requeue`/`51-dispatch-hardening` (flagged after Section 1 as still
needing re-confirmation post-1b) along with everything else.

No live device was used for this section either -- same as Section 1,
decided entirely by selftest. `Prediction: none` still stands.

## Attempt 3 (resumed), 2026-10-17 -- why attempt 2 did not finish

RESUME NOTE 2 (hostops) said attempt 2 committed 5f6e1b01ad (Sections 1 and
1b, full unscoped selftest green) and then ended its turn with PR.md still
draft, "no commit since". At this attempt's start the worktree in fact
carried a third, *uncommitted* chunk on top of that commit: Section 1c in
full -- `titlestate.py` `backup-candidates`/`restore-backup`/`store-dir`,
`dispatcher.sh`'s `ensure_profile_restored`/`verify_profile_on_device`/
`archive_backup_dir`/`device_bak_auto_dir` wired into the soak claim path,
and ten new selftest legs in `98-dispatch-doctor.sh` covering all four
backup sources, the already-golden/first-run no-ops, and both verify
outcomes. So attempt 2 did not, in fact, stop at 1b -- it went on to write
all of 1c in the same turn, then hit the same "ended turn with work
uncommitted" failure mode RESUME NOTE 1 and 2 both describe, just one
section later than the hand-off note could see (it was written from
`git log`, which cannot show uncommitted tree state). Nothing here was
reverted or is suspect; this session's job is to verify it (selftest,
foreground, this turn) and commit it before moving on to Section 2.

## Section 2 -- `dispatch_doctor.sh`, the Sonnet-model diagnosis step (done)

The owner's complaint named this directly: "The dispatcher should have
sonnet reasoning. It should troubleshoot and resolve launch failures. It
should not be just a script." Section 1/1b/1c close the deterministic gaps
a script CAN handle outright; this section is for the remainder -- a
failure whose fix is a judgement call, not a lookup.

`docs/testing/dispatch_doctor.sh` (new) sources `dispatcher.sh` the same
way `98-dispatch-doctor.sh` already does for Section 1/1b/1c (`.
dispatcher.sh dispatch-doctor-source-only`, an unmatched first argument
that runs every top-level line and falls through the bottom `case` to a
no-op, never `serve`/`worker`/`status`), so it gets every helper
(`jq_get`, `battery_level`, `ensure_title_staged`, `ensure_route_attached`,
`ensure_profile_restored`, `staging_roots`, `staging_find_tid`, `$D`) for
free, with no logic duplicated.

Contract (`classify`/`gate`/`cap` split out so the selftest, and the model
itself through `fix`, can drive each independently; `diagnose` is the only
one `dispatcher.sh` calls):

- `classify <rdir>` matches `$rdir/ERROR`'s first line against the named
  recoverable classes (`zero-captures-interop-exhausted`,
  `title-not-on-device`, `install-failed`, `titles-disk-failed`,
  `env-vars-failed`, `zero-captures-crash`, `zero-captures`), the last two
  disambiguated by a `logcat.txt` grep for `FATAL EXCEPTION|ANR in` where
  the ERROR text alone doesn't already carry the crash signature. Anything
  else exits 1 with no output -- not a class, no model session billed.
- `gate <label>` fails closed, in order, on: a `$D/hold/<label>` file
  (doubles as the stand-in for a Halo-priority window, since no dedicated
  mechanism for that exists anywhere in the codebase -- a limitation, not
  an oversight); the owner playing (`adb shell ps -A -o NAME` naming
  `com.jreinach.hakux:xemu`, the release package the dispatcher itself
  never installs); an unreadable battery level; a level under
  `battery_admit.py`'s own floor-plus-margin for that label (imported
  read-only, never duplicated -- it is outside this lane's territory and
  this is the one existing policy on when a device may be used).
- `cap <id> <rdir>` enforces an hourly cap (`DISPATCH_DOCTOR_HOURLY_CAP`,
  default 3, counted from `logs/dispatch-doctor.tsv`) and "one doctor
  attempt per request" -- simpler than an earlier `retry_of`-chain design,
  because the actual retry mechanism reuses the SAME request id (mirroring
  the existing WSL-interop one-shot requeue), so a second TSV row for that
  id never happens and a chain walk was dead code.
- `fix push-iso|attach-route|restore-profile <rdir>` are thin wrappers
  deriving `title`/`ttid`/`tstate` from `request.json` and calling
  `ensure_title_staged`/`ensure_route_attached`/`ensure_profile_restored`
  -- by construction the model has no path to adb, input injection,
  force-stop, app-data-clear, uninstall, or anything Halo-priority-related.
- `diagnose <id> <rdir>` runs classify -> gate -> cap (any refusal short-
  circuits to a `give-up` verdict with NO TSV row and NO model call --
  the cap counts sessions that actually ran, not every ERROR glanced at),
  then builds a read-only `doctor-brief.md` snapshot (request, ERROR, log
  tails, logcat tail, route/profile state, staging search results,
  `titlestate.py suggest-route`/`backup-candidates` output) so the model
  needs zero live adb access, resolves the model via `jobs/models.sh model
  dispatchdoctor` (`[kinds.dispatchdoctor]` in `models.toml`: sonnet for
  both tiers -- the owner asked for sonnet reasoning by name), and invokes
  `claude -p` headlessly exactly on `run-claude-job.sh`'s pattern
  (`--max-turns`, `--output-format json`, `--permission-mode acceptEdits`,
  a narrow `--allowedTools` file, `--append-system-prompt-file` naming its
  role). `window_limit_hit`/`window_note_limit` (sourced from
  `jobs/window.sh`) catch a usage-window hit (exit 75) and give up on the
  WINDOW, not the failure, without spending a cap slot's worth of blame on
  it; `error_max_turns` is read the same way if the model wrote no verdict
  line. The model's own `$rdir/doctor.md`, ending in exactly `retry` or
  `give-up: <reason>`, is the verdict; either way one `logs/dispatch-
  doctor.tsv` row and one `doctor-lessons.md` line are appended (by class
  and verdict only, never by request id -- the lessons file is "what fix
  works for this CLASS", not a request log, so a class that keeps needing
  the same session-costing fix can be promoted into Section 1's
  deterministic path later, per its own header comment).

`jobs/allowed-tools.doctor` (new) deliberately excludes raw `Bash(adb:*)`,
`git push`, `gh`, `rm`, and `Edit` (only `Write`, enough to create
`doctor.md` fresh) -- the model's only levers are `fix` and reading the
brief. `jobs/roles/dispatchdoctor.md` (new) is the role file: read the
brief, pick at most one fix (or none), write `doctor.md` ending in
`retry`/`give-up:`, never retry a no-progress run, never touch anything
but `doctor.md`.

`maybe_run_doctor <id> <rdir>` (new function in `dispatcher.sh`, right
after `adb_error()`) is the one thing `dispatcher.sh` itself gained: called
after `$rdir/ERROR` and `request.json` both exist, at exactly the 5
ERROR sites that are real failures -- install-failed, env-vars-failed,
title-not-on-device, titles-disk-failed (the `trc!=0` branch only), and
the final 0-captures site (after the WSL-interop auto-requeue has already
had its one chance). It is explicitly NOT called at the three deliberate
`hdd.refused`/`profile.refused` safety-refusal sites (profile-gate, the
titles-disk `trc=3` refusal, the profile-verify `trc=3` refusal) --
calling the doctor on a safety stop would risk second-guessing a gate that
exists on purpose, not troubleshooting a failure. On a `retry` verdict it
requeues the SAME id (never minting a new one) by writing a
`doctor_requeued` timestamp into `request.json`, moving it back to
`queue/$id.req`, moving the current `rdir` aside to `rdir.doctor1`, and
clearing the `running/$id.owner` marker -- mirroring the existing
WSL-interop requeue code exactly, not a new mechanism.

**A bug worth flagging for the next lane that touches this area**: the
title-not-on-device call site sits inside the exact `local tpath ... fi`
block that `jobs/selftest.d/99-iso-roots.sh` sed-extracts VERBATIM and
runs with only `$title`/`$rdir`/`$req` bound (see the comment on
`ensure_title_staged`, a Section-1-era note from this same lane that this
session briefly violated). A bare `maybe_run_doctor "$id" "$rdir"` there
reads an outer-scope `$id` the extracted snippet never binds, and fails
under `set -u` with "id: unbound variable" -- caught by running the FULL
unscoped selftest, not the scoped one, since `98-dispatch-doctor.sh` has
no reason to exercise `99-iso-roots.sh`'s extraction. Fixed by deriving
the id from `rdir` itself (`$(basename "$rdir")`, which is exactly `$id`
since `rdir="$D/results/$id"` is set once at the top of the enclosing
function and never reassigned) instead of referencing the outer variable
by name. The lesson: a sed-extracted verbatim block's binding set is a
real constraint on every line inside it, not just the lines that existed
when the comment was written -- re-check it before adding a line, not
after the selftest catches it.

Deploy-snapshot closure (`97-dispatch-deploy.sh`, not territory, left
unedited): `dispatch_doctor.sh` is a new sibling `dispatcher.sh` runs
(`maybe_run_doctor` calls `bash "$HERE/dispatch_doctor.sh" ...`), and in a
worker `$HERE` IS the snapshot directory, so anything not shipped there
does not exist at runtime. Added `dispatch_doctor.sh` itself, plus
`jobs/window.sh`, `jobs/models.sh`, `jobs/allowed-tools.doctor` and
`jobs/roles/dispatchdoctor.md` (none previously shipped, because nothing
inside the dispatcher-worker closure had ever called into `jobs/` before)
to both `SCRIPT_DEPS` and `snapshot_scripts()`'s file list in
`dispatcher.sh`. The automated closure checker's regex only recognises a
literal `$HERE/`/`$SNAP/` reference to a `.sh`/`.py` sibling, so it would
never have caught the `jobs/allowed-tools.doctor` (no `.sh`/`.py`
extension) or `jobs/roles/dispatchdoctor.md` (`.md`) gaps on its own --
those two were added by inspection, not by the checker going red. Worth
knowing if a future lane adds another `$JOBS/*` reference inside
`dispatch_doctor.sh`: the checker will not see it either.

51 new selftest legs in `98-dispatch-doctor.sh` cover classify (all seven
named classes plus two "not recognised" legs), gate (hold/owner-play/
unreadable-battery/low-battery/clean-admit), cap (hourly, wider-hourly,
one-shot-per-id), fix (push-iso success and a no-staging-root failure),
and diagnose end to end (gate short-circuit with no model call and no TSV
row, a full retry round-trip through a fake `claude` binary that actually
runs `fix push-iso`, a model-chosen give-up, a simulated usage-window hit
confirmed to write to a sandboxed `$HAKUX_WORK`, and a no-verdict-written
session). A replay block re-classifies real historical `ERROR` files from
`/home/justin/hakux-work/dispatch/results/*/ERROR` (read-only) for
install-failed/titles-disk-failed/env-vars-failed/zero-captures; the one
class whose message format this lane's own Section 1 changed
(title-not-on-device) uses a synthetic example instead, documented as
such rather than overclaiming replay coverage against history that cannot
exist yet.

Three real bugs were found and fixed by actually running the selftest,
not by review alone: `classify` ran a needless logcat lookup on the
already-self-describing `"0 captures: <crash>"` message (split into its
own case arm); the selftest fixture's `DD_BATTERY_LEVEL="${DD_BATTERY_LEVEL:-90}"`
used the wrong bash parameter-expansion operator (`:-` treats an
intentionally-set empty string the same as unset, silently overriding the
"unreadable battery" leg back to 90%, which then poisoned the next leg
through `battery_level`'s 60-second cache file -- fixed to `-` without the
colon, plus `BATTERY_CACHE_S=0` in the fixture so each independent gate
leg always reads live rather than sharing one `$D`'s cache); and
`dd_req_field` had its `(rdir, field)` arguments backwards from every one
of its own call sites (fixed by swapping the body, not the callers).

A full, unscoped selftest run (no `SELFTEST_ONLY`, all 148 fragments) is
green end to end this session, polled in the foreground across several
`timeout`-bounded windows: **3651 passed, 0 failed, all 148 fragments.**

Two known, deliberate limitations, not blockers:

- The "Halo priority window" gating is only the generic hold-file check
  above -- there is no dedicated Halo-priority mechanism anywhere in the
  codebase to integrate with. If one is ever added, `dd_gate` is the one
  place to wire it in.
- No live device was used to exercise this section (same as every prior
  section) -- judged not worth the risk for a harness-only change the
  selftest's fake-adb/fake-claude fixtures already cover end to end.
  `Prediction: none` still stands.

## Attempt 4 (resumed, 2026-10-18) -- why attempt 3 did not finish

Attempt 3 committed Section 2 (75b1d3475d), merged origin/master
(0c33d7db0c), then started Section 3 and ended its turn with that work
uncommitted: `dispatcher.sh` +8 (`maybe_run_doctor` appends a `doctor: ...`
line to ERROR), `98-dispatch-doctor.sh` +61 (three `mr_env` legs), an
untracked OUTBOX.md (the hourly-report request), and a mode change making
`dispatch_doctor.sh` executable. Same failure shape as attempts 1 and 2:
the turn ended with work in the tree and no commit, so the hand-off note
(written from `git log`) could only see the last commit. No reason in the
tree says it was blocked; it simply stopped. This attempt reviews that diff,
finishes Section 3, runs the full selftest in the foreground and commits
after each step.

The mode change matters more than it looks: Section 2 was committed with
`dispatch_doctor.sh` at mode 644, and `maybe_run_doctor` opens with
`[ -x "$ddt" ] || return 0`. So as committed in 75b1d3475d the doctor never
ran at all from the dispatcher; the full selftest stayed green because
nothing reached it. Attempt 4 changes the guard to `[ -f ]` (the script is
run as `bash "$ddt"`, so the exec bit is irrelevant and a snapshot copy that
drops it must not silently turn the doctor off) and keeps the 755 mode.

## Section 3 -- a miss says where it looked, what it found, what the doctor decided (done)

The brief: "The `ERROR` text for any miss says: where it looked, what it
found in staging, and whether the doctor ran and what it decided", and
Section 1's "The dispatcher must see to all three, and say in the result
dir which it did."

**`inputs.txt`, one line per input, every outcome.** Each of the three
claim-time steps writes one `disc:`, `route:` or `profile:` line to
`<rdir>/inputs.txt` (`inputs_note`) on every path, success or not. Before
this, most outcomes only reached `dispatcher.log`, which a reader of one
result dir never opens.

| step | what the line says (examples, fixture-pinned in 98) |
|---|---|
| disc | `pushed <D: path> -> <device path> (2.0 KiB, sha checked)` · `already on the device at <path>` · `NOT STAGED: no CAFE7779-* image under <roots>; console: the console did not answer (stage_xiso.py exit 3); console-stage.log` · `NOT STAGED: found <path> (…) but did not push it: <root> has X free and must keep Y after the push; no on-device ISO was both unclaimed and verifiable against D: to delete (room.log, dispatcher.log)` · `NOT STAGED: not looked up, '<title>' has no TitleID …` · console `PAUSE`/`STOP` set → `console: not tried, <path> is set` |
| route | `attached '<name>' for <TID>, state=…, N reference crop(s); why: proven, a judged run on it reached gameplay` (or `the title's configured route in targets.toml (recorded, not yet proven)`; plus `; replaces the generic survey the request named` when it did) · `none: no proven or recorded route for <TID> (…); the generic survey does not reach gameplay for most titles; running the survey the request asked for` · `'<name>', named by the request (left as is)` · `none attached: the request carries --find-route/…, which the profile gate decides` · `REFUSED: recorded route '<name>' (target) for <TID> fails its own check: waitfor 'title_screen': no reference crop <path>` |
| profile | `restored <TID>'s first golden from a backup (store: <id>; copied, the backup is untouched)` · `<TID>'s golden (save <id>) is in the store; the titles disk is composed with it` · `<TID> has no golden and no backup was found (looked: store, hdd-reset, archive, device-bak-auto); nothing restored, no profile created` · `none loaded: a first-run route starts this title with no profile by design` · `device check: save <id> pulled back off <path> and verified (hdd.verify.json)` · `device check FAILED: save <id> is not on the pushed titles disk (…)` |

**The miss ERROR leads with what staging found.** It was always
`staging searched <roots>, none had it; title not on device: …`, even when
staging HAD found the image and the push was refused by the free-space
floor, or when the console was down. Now it is
`staging: <the disc line without "NOT STAGED: ">; title not on device: …
-- searched <device roots>`. The tail stays exactly `device_title_miss`'s
text: `99-iso-roots.sh` (not this lane's file) sed-cuts the soak block out
of `dispatcher.sh` and matches the ERROR's suffix, so nothing may follow it
on that line, and the block's own inner `if`/`fi` must stay at 12+ spaces.

**Console mirror outcome is distinguished** (`console-stage.result`, then
the disc line): the console answered but the TitleID did not come back;
the mirror timed out (rc 124, 900 s); the console did not answer
(stage_xiso.py exit N); not tried because `PAUSE`/`STOP` is set or the
script is missing. Done means #2's "a clear 'console did not answer'
ERROR" is the third.

**The doctor's decision is on the ERROR.** `maybe_run_doctor` appends
`doctor: retry (see doctor.md)`, `doctor: give-up: <model's reason> (see
doctor.md)`, or `doctor: give-up: not a class the doctor recognises` (no
false "see doctor.md" when none was written). On a retry the line moves
aside with the dir (`<rdir>.doctor1/ERROR`). The doctor's own brief now
includes `inputs.txt`, `console-stage.result`, `room.log` and
`route.refused`, so the model reads what the dispatcher already tried.

**A 1b gap closed: a recorded route that fails its check refuses the
claim.** Before, at claim time a configured route whose `route.sh --check`
failed (a crop missing from `refs/<route>/`) was logged and the soak ran on
the survey -- exactly the "fallback to mashing" the brief forbids. Now
`ensure_route_attached` writes `route.refused` and returns 3, and the soak
block ERRORs `refused before the soak: <why>` naming the crop. request.sh's
queue-time attach already exited 2 on the same `--check` failure (line
~1273), so both paths now agree. `fix attach-route` in the doctor reports
the refusal as "a route lane's to repair, not a retry".

**A crashed route lookup says so.** `suggest-route` prints JSON whether or
not it finds a route. When it crashed instead, for example on a dispatcher
snapshot with no `targets.toml` (lane.snaptargets1018's defect; it raises
FileNotFoundError), the attach parsed nothing and wrote "no proven or
recorded route". That is a claim nobody checked. It now writes `route:
none: could not look up a route for <TID>, titlestate.py suggest-route
failed (<last line>); running … as queued` and logs `ROUTE LOOKUP FAILED`.
The request still runs as queued, since the lookup's failure is not the
request's. The 98 leg "s3 route lookup crash" points `TITLE_TARGETS` at a
missing file. It rejects the old wording, so it would have failed before
the fix.

**Two latent faults found while finishing.**
- The doctor never ran from the dispatcher as committed in 75b1d3475d
  (mode 644 behind `[ -x ]`; see Attempt 4 above). Fixed: `[ -f ]`, 755.
- The 98 fixtures could reach the REAL console. `console_stage_tid` runs
  `$STAGE_XISO` (default the real `stage_xiso.py`) unless `$HAKUX_XISO_DIR`
  has a PAUSE/STOP file, and `/mnt/d/hakux-staging/xiso` has neither. Every
  fixture env (`dd_run`, `dd2_env`, `mr_env`) now sets `STAGE_XISO` and
  `HAKUX_XISO_DIR` to fixture paths; the "console answers" leg drives a fake
  `stage_xiso.py` that drops `<tid>-Console_Game.xiso.iso` into the root.

**`maybe_run_doctor` skips an empty `request.json`.** There is nothing to
requeue, so a doctor session has nothing to act on. It is also what keeps
`99-iso-roots.sh`'s cut-out soak block (which writes an empty request)
from gaining a `doctor:` line after the suffix it matches -- the guard was
added for that fixture, and holds for the reason above.

**Classify replays real history for title-not-on-device too.** `dd_classify`
matches `title not on device` anywhere in the line rather than the
`staging searched` prefix, so the ~45 pre-lane results (bare
`device_title_miss` text) classify, as do Section 1's and Section 3's
wordings. 98 now replays one real result for that class
(`0-0-c-1790377876-lane.tcgchurn-101517`) and pins both newer wordings.

**Hourly report.** `host-tools/hourly_report.sh` is lane.local's; the
block that prints `dispatch doctor: N sessions, M fixed, K gave up` from
`$D/logs/dispatch-doctor.tsv` is in `OUTBOX.md` as a request.

**Tests.** 98 gained 24 legs for Section 3: attempt 3's three ERROR-append
legs (retry, give-up, unclassified), and this attempt's 7 staging outcomes,
6 route, 5 profile lines, 1 empty-request, 1 real-history replay and 1
classify of the new wording. Scoped runs green: 98 + 99-iso-roots
85/0; 97-dispatch-deploy, 99-profile-gate, 99-title-state green. 51-dispatch-hardening
needs 50-arms-requeue's fixture before it (it FAILs alone on "fixture not
as 50 leaves it"; that is its own ordering, not this change).

Full unscoped run on 6c2a4b5fdd (merged with origin/master 4a504d9aaa),
in this session: **3683 passed, 1 failed, all 149 fragments.** The FAIL is
66-status-titles' "check --pages passes when every page agrees …": its
fixture README carries a numbered Playable line, and master's 48a6db90c5
(compat1017b) made `title_registry.py check --pages` require the
numberless form. It comes from master; this lane edits neither file, and
it is outside this lane's territory to fix (OUTBOX.md flags it for
lane.local).

PR.md names the fold's fragments (`Selftest:`): the 51 fragments whose grep
hit on a changed file is a real source/run/copy/lint, plus 50-arms-requeue
(51's fixture) and 99-title-state; PR.md lists the 11 prose-only hits and
66 that were left out, and why.

After the lookup-crash change (one function, `ensure_route_attached`), I
re-ran the fragments that drive it. 98, 99-iso-roots, 99-profile-gate and
97-dispatch-deploy: 184 passed, 0 failed. 57-vsh-disc, 61-soakvideo1011,
62-routerefs-soakvideo1011, 85-savestate, 97-dispatch-snapshot-drive,
99-display-covered, 99-folder-pref, 99-hdd-split and 99-title-state: 235
passed, 0 failed.

**preflight.sh --allow-tracker:** every gate is ok except `territory`.
That gate reads `origin/board:territory.toml` and fails on four double
claims, all the board's. The one touching this lane: `docs/testing/dispatcher.sh`
is claimed by both dispatchdoctor1017 and snaptargets1018 (STARTED by
lane.local 2026-10-18 ~01:45 PDT, to ship `targets.toml` in the dispatcher
snapshot). `--allow-tracker` cannot clear a territory overlap, and a lane
may not edit `territory.toml`. Fold order resolves it; snaptargets1018's
change is to the snapshot file list, not the functions this lane edits.

**Not done, and not this lane's:** no live device run. Done means #1-#4 are
shown against the fake adb/claude fixtures, not a device; the first real
claims after lane.local deploys the folded dispatcher are the live check.
A running dispatcher holds the version it started with, so none of this is
live until lane.local restarts it.

**Next lane, do not repeat:** do not append anything after
`device_title_miss` on the miss ERROR line (99-iso-roots); do not guard a
`bash "$x"` call on `[ -x ]`; give any fixture that can reach
`console_stage_tid` a fake `STAGE_XISO`.

## Still to come

Nothing in the brief's three sections. The hourly line waits on lane.local
(OUTBOX.md); deploy is lane.local's step after the fold.
