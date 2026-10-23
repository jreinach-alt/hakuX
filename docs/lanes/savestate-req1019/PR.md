# savestate-req1019: load a save state through request.sh -- no hand-driving to reach a scene (#433)

State: ready

Lane: savestate-req1019          Issue: #433
Base: master @ b4bdccd82f (the scene disk below is built on suitesha1022's hddPath helpers)
Files: docs/testing/request.sh, docs/testing/dispatcher.sh, docs/testing/scenes.tsv, docs/testing/jobs/selftest.d/99-load-state.sh, docs/testing/jobs/roles/lane.md, AGENTS.md, docs/lanes/savestate-req1019/**
Prediction: none: no arm (mechanical feature work with a falsifier fragment, not a pixel/perf claim)
Needs device: yes (one proof run)    Needs NDK: no (mechanism (a): no APK change)
Selftest: 99-load-state 50-arms-requeue 51-dispatch-hardening 99-disc-hdd -- 99-load-state: a scene boots its own
  copy of the disk (hddPath set, read back, put back), and a scene naming no disk, the owner's image, a harness disk
  or a missing file is refused before the install; six mutants. 99-disc-hdd: the disc path shares the factored
  hdd_pref_point/hdd_pref_after. 50 + 51: serve_one's branch and the queue guard (51 needs 50's fixture).

Mechanism (a) built, no APK change: `request.sh --scene <name>` (sugar for `--load-state` +
`--hold-trigger`, from `docs/testing/scenes.tsv`) and `--load-state <slot-or-file>` isolate the target
slot (park every competing file, since `hxs_newest_loadable()` picks by the state's own `saved_at`, not
mtime), set `savestate_auto_load=1` for the run, launch, and wait on `[savestate] op=load ... ok=1` in
logcat; `--hold-trigger rt:<seconds>` holds a pad axis after the load and logs device-clock down/up times
for score2.py. Any `op=save`, a load timeout, or a refused load -> VOID with a reason, never a silent run.
The parked file and the pref are restored after every run, pass or VOID. `docs/lanes/savestate-req1019/
NOTES.md` has the full design writeup.

Falsifier `jobs/selftest.d/99-load-state.sh` passes. Cases (a)-(f) cover the load, including a mutant that
drops the restore step and correctly fails case (d); the scene's disk below adds (g)-(j2) and six mutants
(88 checks, 0 failed: see Checks). Docs added: AGENTS.md ("Loading a scene without driving
the device", beside "Working with a device") and `jobs/roles/lane.md`.

**Device proof: blocked on this PR's own fold, not written yet.** `hakux-dispatcher.service` execs
`/home/justin/hakuX/docs/testing/dispatcher.sh` -- a separate, pre-fold tree with none of this code -- so
a real `--scene gta3-incar` request today is served by a dispatcher that has never heard of
`load_slot`/`hold_trigger`/`scene`. Tried it for real (tier `1-`, `--device nova`, id
`1-1792450834-savestate-req1019-3775536`): it silently ran an ordinary 60 s soak and filed the result as
the scene, with every new field null and no `op=load` line -- no error, no VOID. That is the exact
failure mode request.sh's existing `--skip-tests`/`--audio-capture`/`--only-tests` guards exist to catch
(request.sh:660-684 etc.), and `--load-state`/`--scene` was missing the same guard. Added it (checks
`scene_verdict` in both the `DISPATCH_TREE` and the `DISPATCH_DIR/bin` snapshot); the same real attempt
now correctly refuses at queue time instead of running. Selftest case (f) (3 checks) covers the new guard
directly. `NOTES.md` has the full incident writeup and the exact command to re-run once folded.

Ready without the device proof (lane.local 2026-10-23 07:55 PDT, owner: "Proceed with the next steps, you have full
control of the device"): the proof cannot run before the fold, because the service runs master's tree. It runs
first thing after the fold, on the GTA III heavy saves of 10-23 and `hdd-scene-gta3.img` (made 07:46, a byte copy
of the owner's image, sha256 44f12160...), and is recorded on #433.

Board request filed (`$DISPATCH_DIR/board-requests/savestate-req1019.md`) for the files above -- several
show as held in territory.toml by rows whose own notes say RELEASED/FOLDED and that have no live
`$DISPATCH_DIR/fleet/*.json` entry; flagged there for the board to resolve, proceeded on the brief's own
Files: line in the meantime. Mechanism (b) (android/app/src/main/cpp/xemu_android.cpp) was not needed.

## The scene's disk: a scene boots a copy of the disk its state was saved on

A state loads only on a disk that holds the snapshot it was saved with. Until this change a scene's title run went
through `titles_disk_prepare`, so it booted titles.qcow2. That disk is composed from goldens and never holds a state's
snapshot, so every `--scene` load would have VOIDed `disk-snapshot-missing`. A run whose prefs could not be pointed
would instead have booted whatever `hddPath` names, which on the Nova is the owner's image, and the load would have
rolled that image back.

### Step 0: already tried

Sources: `git log -i -E --grep='disk.snap|heavysave|goto_snapshot|hdd-owner|undo-load|startup_gc'`, `--grep='heavy|hxs'`
since 10-01; docs/lanes/{savestate1011,savestateconv1014,suitesha1022}/PR.md; `android/app/src/main/cpp/savestate/hxs.c`
on this branch and on lane/diagdrive1022 (8bf140bf88, the build the owner is driving).

| Date | Commit / doc | What it measured or changed | Verdict | Meaning here |
|---|---|---|---|---|
| 09-29 | fa2e37531b, 84a86029e1 (hddsplit, #397) | A title run points `hddPath` at titles.qcow2 through `set_hdd_pref`; one marker restores it, written first and never overwritten | kept | The pref mechanism, reused. Every title run substitutes titles.qcow2, so before this change a scene could boot no other disk |
| 10-11 | 121cde1e09, e318ae70b5 (savestate1011) | Every save takes a disk-only internal qcow2 snapshot and names it in the meta (`disk_snap`); a load refuses `disk-snapshot-missing` and `hdd-not-qcow2` | kept | A state is bound to its disk by the snapshot's name (hxs.c:1215), not by the disk's path. The format is probed from content, so a copy must be qcow2 |
| 10-14 | 76bef8b162 (savestateconv1014 B1) | The dispatcher rebuilds the titles disk from goldens on every ordinary run, discarding any state's snapshot | blocker named, not fixed | The blocker, for scenes: a scene run now bypasses titles.qcow2 instead of carrying a state through it |
| 10-14 | savestateconv1014 B5 | A snapshot's name embeds the title, not the image | kept | With `root8` (the sha of the states root, not of the disk path), a byte copy of the image keeps names the load finds |
| 10-19 | cf97e8b822 (this lane, `--scene` / `--load-state`) | Isolates the slot, sets `savestate_auto_load`, waits on `op=load ... ok=1`, VOIDs anything else | kept | Its title run still called `titles_disk_prepare`; the gta3-incar row could only VOID |
| 10-22 | 3de6a325d8 / b4bdccd82f (suitesha1022) | A disc run sets `hddPath` to hdd.img through `set_hdd_pref`, reads it back, restores it, and writes `hdd_disc.json` (`kept`/`set`/`failed`/`unread`, `restored`) | kept | The helper this change reuses: factored into `hdd_pref_point` / `hdd_pref_after`, which `disc_hdd_prepare` / `disc_hdd_after` now wrap. On the Nova `hddPath` names `hdd-owner-1018.img` |
| 10-23 | lane/diagdrive1022 8bf140bf88 (heavycap1022), the owner's drive under the Nova hold | `HAKUX_HEAVYSAVE=1` writes heavy0..3.hxs, slots 12..15, each with a disk snapshot on the booted disk | running | The saves this exists to replay. Their snapshots are inside `hdd-owner-1018.img`, which is why a replay needs a copy of it |

Nothing in the table let a title run boot a disk the state named, and nothing refused a load on the owner's image.

### Mechanism

- `docs/testing/scenes.tsv` gains a sixth column, `hdd`: a plain file name in the device's x1box dir (the directory
  that holds hdd.img and that `hddPath` points into), never a path. The gta3-incar row names `hdd-scene-gta3.img`.
  `request.sh --load-hdd <name>` sets the same field (`scene_hdd`) for `--load-state`, and overrides a scene's value.
  A row with five columns reads as an empty `hdd` and is refused for that reason, not with a traceback.
- `scene_hdd_check` (dispatcher.sh), in `serve_one` after the battery stamp and before `adb install`: a request with
  no `load_slot` and no `scene_hdd` returns 0 and makes no adb call. Otherwise it checks the name, then makes one
  `test -f` on the device. A refusal writes `ERROR` `refused before the install: <reason>`, so nothing is installed,
  launched or written to the prefs. A device that does not answer gives `could not check the scene's hdd on the device`.
- `scene_hdd_prepare` runs in place of `titles_disk_prepare` when the request names `scene_hdd`. It sets the copy
  to mode 660 first (pushed disks left at 0644 crashed the app, per hddperm), then calls `hdd_pref_point`. That is
  the disc runs' code: it writes the marker first, sets the pref, reads it back, and records
  `<rdir>/hdd_scene.json` `{action, was, want, restored}`. `unread` and `failed` both fail the run before launch:
  a load must not run on whatever the pref names. It writes `hdd.json` `{path, split: "off: scene hdd <name>",
  scene_hdd, mode_found, mode}`, and `result.json` `_hdd.pref` carries `hdd_scene.json`.
- `scene_hdd_after` runs after the soak and on every refusal and failure path after the prepare. It calls
  `hdd_pref_after`, which is `restore_hdd_pref` (the marker written back byte for byte), and sets `restored`. A
  worker that dies mid-run leaves the marker for the next request's start-of-request restore, the same as title and
  disc runs.
- `verify_profile_on_device` is skipped for a scene: the copy carries the owner's profile, not a composed save.
  `titles_disk_after` is skipped too, because nothing to harvest or rebuild was booted.
- request.sh carries a copy of `scene_hdd_name_refusal` with identical text, so a refusal by name happens at queue
  time. The device-side existence check needs the device, so only the dispatcher makes it. The stale-dispatcher
  guard token is now `scene_hdd_check`: a dispatcher without it refuses the request at queue time.

### Refusals (exact text)

At queue time (request.sh: `refusing to queue: <text>`, exit 2) and before the install (dispatcher: `ERROR`
`refused before the install: <text>`):

- no hdd: `a save-state load names no hdd: a state loads only on a disk holding the snapshot it was saved with, and
  without one the run boots titles.qcow2 (composed from goldens: no such snapshot, the load VOIDs) or whatever hddPath
  names (on the Nova the owner's image, which the load would roll back); name a copy of the disk the state was saved
  on in the scene's scenes.tsv hdd column, or pass --load-hdd <name>`
- `scene hdd '<n>' is a path; name a file in the device's x1box dir (where hdd.img is)`
- `scene hdd '<n>' is not a plain file name (letters, digits, . _ - only)` (also `.`, `..` and a leading `-`)
- owner image (`hdd-owner-*`, any case): `scene hdd '<n>' is the owner's image (hdd-owner-*): a load rolls the disk it
  boots back to the state's snapshot, so a scene boots a copy of that image, never the image itself`
- harness disk (`titles.qcow2`, `hdd.img`, any case): `scene hdd '<n>' is a harness disk (other runs rebuild and boot
  it); name a copy of the disk the state was saved on`

Dispatcher only (needs the device):

- `scene hdd '<n>' does not exist on the device (<x1box dir>/<n>); copy the disk the state was saved on there first,
  with the app stopped`
- `scene hdd '<n>' on the device (<x1box dir>/<n>) is not a file`

request.sh only: `--load-hdd names the disk for a save-state load, and this request loads none (--load-state/--scene)`.

**A load that names no hdd is refused, not defaulted.** Every save takes a disk snapshot (savestate1011), so no
state can load on a disk without that snapshot. A default could only be titles.qcow2, where the load VOIDs after an
install, a launch and a timeout, or the pref as found, which is the owner's image on the Nova and is the one outcome
this change exists to prevent. Refusing costs the requester one column. The other two options cost a wasted device
run, or the owner's data.

### Checks

- `bash -n` on dispatcher.sh, request.sh and 99-load-state.sh. Each mutant's anchor occurs once in dispatcher.sh
  (`grep -cF`). The fragment refuses a mutant whose anchor does not match exactly once, so a refactor cannot turn
  a mutant into a no-op.
- `SELFTEST_ONLY="99-load-state 50-arms-requeue 51-dispatch-hardening 99-disc-hdd"`: `selftest: 209 passed, 0 failed,
  PARTIAL: 4 of 162 fragments`. Per fragment: 50-arms-requeue 2 ok (146 s); 51-dispatch-hardening 75 ok, E and E2
  included (10 s); 99-disc-hdd 44 ok (65 s), the same count as at its fold, so the `hdd_pref_point` /
  `hdd_pref_after` factoring left the disc path as it was; 99-load-state 88 ok (30 s). After a log-text change in
  `scene_hdd_prepare` (a `kept` pref no longer logs "put back afterwards"), 99-load-state alone: `88 passed, 0 failed`.
- `selftest.sh --check-shards 4`: all 162 fragments covered once.
- 99-load-state (g)-(j2) run against a fake adb whose device is a directory. Its prefs name `hdd-owner-1018.img`,
  which holds known bytes at mode 660; the copy is at mode 644. (j) calls the real `serve_one` from a mirror tree
  (`cmp` against the real dispatcher.sh) with a soak stub that records the `hddPath` it booted, and appends a
  "rolled back" mark to that disk, as a load writes to the disk it boots. The falsifier is (j): the title booted
  the copy, the titles disk was neither prepared nor harvested, the owner's image keeps its sha256 and mode,
  the copy carries the load's write, and `x1box_prefs.xml` is byte for byte what it was.
- Mutants. Each is applied to a copy of dispatcher.sh, and each turns its named leg red:
  - `hddset`: the `set_hdd_pref` call in `hdd_pref_point` becomes `true`. (g) mid-run `hddPath` is not the copy.
  - `branch`: the scene's `scene_hdd_prepare` becomes `titles_disk_prepare`. (j): the scene boots the owner's
    image, which is the incident this change prevents.
  - `owner`: the `hdd-owner-*` refusal is renamed away. (h): the owner's image passes.
  - `exists`: the device's `none` answer returns 0. (h): a missing disk passes.
  - `nohdd`: the guard `[ -n "$load_slot$name" ]` becomes `[ -n "$name" ]`. (h): a load naming no hdd passes.
  - `after`: `scene_hdd_after` returns 0 at once. (g): `hddPath` stays on the copy after the run.
- Found while writing (h): case (a,d)'s "no stale scene marker left" checked `.scene_pref.ls`, but `device_env`
  labels serial ee317437 `nova` whatever `DEVICE_LABEL` was, so the markers are `.scene_pref.nova`. The check could
  not fail. It now checks every `.scene_(pref|files).*`, and `ls_reset_device` clears them by glob.

### What this means for the GTA III replay

- A byte copy of `hdd-owner-1018.img` keeps the snapshots the heavy saves name. The load matches the snapshot by
  name only (hxs.c:1215), and the name's `root8` comes from the states root, not the disk path, so the copy needs
  no rename or rewrite. The copy must be the qcow2 file itself; a converted image loses its internal snapshots, and
  a raw image is refused `hdd-not-qcow2`.
- Each load writes to the booted disk. It takes an `undo-load` snapshot, then calls `bdrv_all_goto_snapshot`
  (hxs.c:2527, :2675), so the copy is rolled back to the state on every replay. That is where the next replay starts
  anyway, so one copy serves any number of replays of states saved on it.
- At boot, `startup_gc` deletes this root's snapshots that no file in the states dir names, and every `undo-load`
  (hxs.c:3184). On the copy, a heavy state's snapshot survives only while some `.hxs` file (a parked `.hld` counts)
  still names it.
- The heavy saves cannot be loaded by slot. heavy0..3 are slots 12..15, and `hxs_load` refuses anything at or above
  `HXS_SLOT_COUNT` (12) with `bad-slot` (diagdrive hxs.c:2660). A replay pulls `heavyN.hxs` to the host and queues
  `--load-state <host file>` (pushed into auto, slot 10) with `--load-hdd <copy>`.
- The meta must match the build that loads it: schema, disc and controller layout (hxs.c:1205). The replay request
  must name a build with the same save-state schema as 8bf140bf88.
- `hdd-scene-gta3.img` does not exist on the Nova yet, so the gta3-incar row is refused by the existence check until
  someone makes the copy. Make it with the app stopped, after the owner's drive is scored and the hold is released
  (`cp` inside the x1box dir, then mode 660). It costs the image's size (about 3.4 GiB) against the Nova's 25 GB floor.
- A route can still attach to a scene run (`ensure_route_attached` runs). A replay that should only hold the throttle
  must not name a route.
