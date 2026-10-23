# savestate-req1019 -- load a save state through request.sh (#433)

## Mechanism chosen

(a), no APK change, as the brief's preferred order asks for first. The
dispatcher parks every save-state file that would compete with the target
slot (rename aside with a `.hld` suffix -- `hxs_newest_loadable()` picks by
the state file's own internal `saved_at` metadata, not filesystem mtime, so
merely overwriting a slot does not make it win), sets
`savestate_auto_load=1` in `x1box_prefs.xml` for the run, launches, and waits
on logcat for `[savestate] op=load slot=<N> ok=1`. Both the parked file and
the pref are restored after the run, pass or VOID, with a byte-for-byte
read-back check on the state file. (b) (a launch extra / env var read in
xemu_android.cpp) was not needed; no `android/` files are touched.

## Request shape

- `request.sh --scene <name>` resolves a row from `docs/testing/scenes.tsv`
  (name, title_id, slot, state_file, default_hold) into `--load-state` +
  `--hold-trigger`, so a GTA III in-car scene is one flag:
  `--scene gta3-incar` == slot 5, title `5454000e`, state `device` (the
  file already on the device, not pushed from the host), hold `rt:60`.
- `--load-state <slot-or-file>` and `--hold-trigger rt:<seconds>` are also
  usable directly, for a one-off that is not in the table yet.
- `--load-state` refuses at queue time (exit 2, before anything reaches
  `queue/`) when the slot is not 0-9/10/auto and is not an existing file.

## VOID logic (`scene_verdict`, dispatcher.sh)

Priority, highest first: any `[savestate] op=save` line anywhere in the
run's logcat -> VOID (never silently accept a run that might have
overwritten a slot); no `op=load ... ok=1` within the load-wait window ->
`LOAD_TIMEOUT`; an `op=load ... ok=0` (version/schema refusal) ->
`LOAD_REFUSED`; otherwise, if the wait loop never saw a load line at all
(e.g. nothing to parse) -> "no load window observed". `scene.json` carries
`load_slot`, `apk_sha`, `void`, `rt_down`, `rt_released`, `rt_hold_log`. The
load-wait is 30 s by default; `SCENE_LOAD_TIMEOUT` overrides it (selftest
only -- no production caller sets it).

## score2.py's RT_DOWN format

score2.py (a by-hand lane capture artifact, not a repo file) reads
`RT_DOWN`/`RT_RELEASED` as device-clock wall time, `HH:MM:SS.mmm` -- not
epoch seconds. `_device_clock()` is a new, separate function from the
existing integer-epoch `_device_epoch()`; `start_scene_watch` logs with the
former.

## Falsifier (`jobs/selftest.d/99-load-state.sh`)

Fake dispatch dir, fake device filesystem under a scratch tree (guarded to
stay under `/tmp`), and a minimal fake `adb` (`shell`/`run-as`/`am
force-stop`/`push`) sufficient to drive the real `set_scene_pref`,
`start_scene_watch`, `scene_verdict`, `restore_scene_pref` functions
unmodified. `perf/pad.sh` already has a `ROUTE_DRY=1` dry-run mode (its
`sh_adb`/`detect`/`load` all branch on it) that synthesizes gamepad axis
ranges with zero device I/O, so the RT hold did not need its own fake --
exporting `ROUTE_DRY=1` was enough.

Cases, all passing (27 checks, 0 failed):
- (a) load ok: result carries the load line and an `RT_DOWN`/`RT_RELEASED`
  window in device-clock format; `scene.json` has `void=null`.
- (b) no load line within the window: VOID with a stated reason.
- (c) a later `op=save` line: VOID even though an earlier `op=load ok=1`
  also appears.
- (d) the parked state file and the pref are restored byte-for-byte /
  exactly after every case above, including after (b) and (c)'s VOID.
- (e) `request.sh --load-state <missing file>` refuses at queue time
  (exit 2, naming the file) and nothing lands in `queue/`.
- Mutant: `restore_scene_pref` short-circuited to `return 0`. Case (d)'s
  checks then correctly fail (the parked file stays parked, the pref stays
  true).

All three cases that exercise the load path use `load_state_file=""` (the
"device" mode -- the state already on the device, not pushed from the
host), matching the real `gta3-incar` row in `scenes.tsv`. The selftest does
not cover the host-file-push path (`--load-state <path>` with a real file to
push); that path shares `dev_push`'s existing sha256-verified push/pull with
every other state-pushing caller in dispatcher.sh and is not new code this
lane added.

The mutant must sit beside the rest of `docs/testing/` (a bare
sed-mutated copy of `dispatcher.sh` alone fails immediately at its own
`. "$HERE/devices.sh"` line and the whole subshell silently exits before any
scene function runs, which would have made the mutant a false pass with no
one of case (d)'s checks ever exercised). The fragment builds a symlink
mirror of `$TESTING` and swaps in only the mutated `dispatcher.sh`, the same
technique `51-dispatch-hardening.sh` already uses.

The new fragment needed no `SHARD_SECS`/workflow changes: an unlisted
fragment gets the default weight and the lightest shard automatically
(`--check-shards 4` passes).

## Board / collision note (carried from PR.md)

Filed a board request for the files in this brief; several show as held in
`territory.toml` by rows whose own notes say RELEASED/FOLDED with no live
`$DISPATCH_DIR/fleet/*.json` entry. Flagged there for the board to resolve;
proceeded on the brief's own `Files:` line in the meantime since the rows
were stale by their own text.

## Prior-session incident: a live request queued by accident

While testing `--scene gta3-incar` argument parsing with `--who test`, a
request was accidentally queued for real (`1792448616-test-3611181`) before
the dispatcher-side scene code was fully wired in. Checked this session:
`request.json` for that result does carry `scene=gta3-incar`,
`load_slot=5`, `hold_trigger=rt:60`, but `result.json`'s `scene`/`void`/
`load_slot` are all `null` and the run's own logcat shows
`auto_load=0` throughout -- the scene fields were parsed into the request
but the dispatcher build that served it predates `set_scene_pref` actually
being called, so the load never happened and nothing was parked or pushed.
It ran as an ordinary 60 s GTA III soak from the title screen. No state file
or pref was touched; the only cost was one real ~60 s device run against the
30-minute pilot budget.

## Device proof: blocked on the fold, not on this lane's code

`hakux-dispatcher.service` (the live, always-running worker --
`systemctl list-units` shows it `active running`) execs a fixed path,
`/home/justin/hakuX/docs/testing/dispatcher.sh serve` -- a separate
checkout from this lane's worktree, currently at `656bcd1fe9` (this
branch's own base), with none of this lane's scene code. `request.sh`
queues correctly from *this* worktree (it resolves `--scene` and writes
`load_slot`/`hold_trigger`/`scene` into the request JSON itself), but the
request is then *served* by whatever `dispatcher.sh` lives at
`DISPATCH_TREE` (default `/home/justin/hakuX`), which only gets this
lane's code once the PR folds.

Found this by trying the real proof run first (`HAKUX_RELEASE_PRIO=1
request.sh --who savestate-req1019 --scene gta3-incar --device nova
--perflog --issue 433 --no-expect ...`, tier `1-` as asked, id
`1-1792450834-savestate-req1019-3775536`). It queued and ran -- but came
back with `scene`/`void`/`load_slot`/`rt_down` all `null`, no
`[savestate] op=load` line anywhere in its logcat, and no `rt_hold.log` or
`scene.json` at all: the live (pre-fold) dispatcher had never heard of
`load_slot`/`hold_trigger`/`scene` and just ran an ordinary 60 s soak from
the title screen, filed as though it were the requested scene -- no error,
no VOID. `GPU: PurpleVK` was present in that run's `hakuX-phase` line, for
what it's worth; nothing else about the proof's requirements was met.

**This is exactly the failure mode request.sh's existing `--skip-tests` /
`--audio-capture` / `--only-tests` guards exist to prevent** (see their
comments at request.sh:660-684, 776-813, 924-956): a new per-request field
consumed only by `dispatcher.sh`, queued against a server that predates it,
is silently ignored rather than refused, and the stale result gets filed as
the real thing. Those three fields all have this guard; `--load-state`/
`--scene` did not. **Added it** (request.sh, right after the existing
slot/file/title validation): checks `scene_verdict` for a grep match in
both `$DISPATCH_TREE/docs/testing/dispatcher.sh` (the tree) and
`$DISPATCH_DIR/bin/dispatcher.sh` (the snapshot a re-exec'd worker actually
runs, which can lag the tree even after a merge -- same two-tier check
`--only-tests` uses and for the same reason), and refuses at queue time
with one of two messages (not supported at all / merged but the running
snapshot is stale) if either is missing `scene_verdict`. Re-ran the real
attempt after adding the guard: it now correctly refuses
("`--load-state/--scene is not supported by the dispatcher that will
serve this request (/home/justin/hakuX/docs/testing)`"), exit 2, nothing
queued -- confirmed via `ls dispatch/queue/`.

Added selftest case (f) (3 sub-checks: neither tree nor snapshot has it;
tree has it but the snapshot is stale; snapshot has it and the guard does
not fire) covering this guard directly, against scratch trees under `$LS`
-- 32 checks now pass, 0 failed (was 27 before this addition).

**So the required real device proof cannot run from this lane as things
stand, and that is now enforced rather than silent.** It needs this PR
folded into `/home/justin/hakuX` and `hakux-dispatcher.service` restarted
(or `dispatcher.sh` touched to force the worker's own re-exec) before
`--scene gta3-incar` will queue for real. `PR.md` stays `State: draft`
for that reason -- the brief gates `ready` on the device proof being
recorded here, and it cannot be, yet. Prediction stays `none: no arm` (no
pixel/perf claim; the guard fix is a correctness fix proven by the
selftest and by the before/after queue attempts above, not something an
arm would score).

What is proven without the device, per the brief's own offline order
(finish the implementation, prove the unreachable paths by reading and
compiling, then wait): the falsifier fragment exercises every scene
function (`set_scene_pref`, `start_scene_watch`, `scene_verdict`,
`restore_scene_pref`) against a fake device and fake adb, unmodified from
what the real dispatcher runs; `--load-state`'s and `--scene`'s queue-time
validation (including the new guard) is proven against the real
`request.sh`, not a fake; `bash -n` passes on both scripts.

**Next lane or next session on this one, once folded:** re-run the exact
command above (`HAKUX_RELEASE_PRIO=1 request.sh --who savestate-req1019
--scene gta3-incar --device nova --perflog --issue 433 --no-expect "..."
--wait`), confirm `GPU: PurpleVK`, `op=load slot=5 ok=1`, the RT hold
window, and the `scene.json`/`rt_hold.log` outputs; feed the result's
`logcat.txt` + xemu pid + `rt_down` through
`~/hakux-work/captures/fpsnext1019/scripts/score2.py` to confirm it
scores (confirmed readable this session: it takes `<logcat> <pid>
<rt-down HH:MM:SS.mmm> [label]` and prints hold/drive fps lines -- no
code change needed there, it already expects this lane's `_device_clock()`
format). Record the result path here, then flip `State: ready`.

(Note on `request.sh --wait`'s own summary printer: the first proof
attempt's `--wait` crashed *after* the real result had already landed,
with `partial: command not found` / a python `SyntaxError` on an
`AI_AGENT=...` literal -- unrelated to this lane's files, looks like an
environment variable the session's harness sets leaking into a
quoting-unsafe spot in request.sh's existing result-summary code. Not
chased further since the result itself was already on disk and complete;
worth a separate look if it recurs outside an agent session.)
