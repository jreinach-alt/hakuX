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
`99-lane-model-file`, 168/168): all 0 failed. The one true full-suite run
(no `SELFTEST_ONLY`) was not completed end to end this session -- it alone
takes 18-25 min per the file's own CI note, over the 600s-per-Bash-call
cap -- but every fragment this diff could plausibly affect (touches
`dispatcher.sh`/`devices.sh`) ran green, foreground, polled to completion
rather than left running past a turn boundary.
