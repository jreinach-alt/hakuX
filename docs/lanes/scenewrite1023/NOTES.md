# scenewrite1023: notes

Lane tree /home/justin/hakux-work/wt/scenewrite1023, branch lane/scenewrite1023, base master 1b616ee718. The lane
touched no device. Everything below about the device is lane.local's measurement (09:47-09:49 PDT, 10-23, in the
brief) or the reading of the code; where the fragment's fake stands in for the device, that is said.

## The permission fix (commit 1)

### What set_scene_pref does to a closed directory

1. Probe `states/<ttid>/` as the shell user (`[ -w ]`): writable, closed, missing, or unknown (adb did not answer).
2. Reads that work on a closed dir come first: the listing, and the sha256 of the file a push will displace.
3. The plan goes into the scene marker (`.scene_files.<device>`) BEFORE the first write: dir, slot, files to park,
   whether a push is coming, the displaced file's sha256, whether this call opens the dir, and the dir's mode before.
4. Closed: `run-as <pkg> chmod g+w <dir>`, then the probe again. One log line names the dir and the mode before and
   after: `SCENE: opened <dir> for adb shell: 2750 -> 2770 (run-as chmod g+w)`.
5. Still closed: the chmod is put back if it changed anything, nothing is written, and the run fails with exactly
   `<sdir> is not writable by adb shell; run-as chmod g+w did not open it` (the request's ERROR carries it through
   SCENE_WHY). The marker is dropped, since nothing was changed.
6. Then the writes: the backup copy, the push, the parks, the pref.

### What restore_scene_pref does

Check the dir is writable (open it again if something closed it meanwhile), put the pushed file back (the backup moved
over it and its sha256 checked against the one taken before the push, or the pushed file dropped when the slot was
empty), unpark, list the dir to confirm each parked file is back and no `.hld` is left, and then close the dir again
with `run-as chmod g-w` -- only if this scene opened it, and only if every step before it succeeded. A restore that
failed leaves the dir open so the rest can be put back by hand with plain `adb shell`, and says so in the log. A dir
that was already writable (the Blinx 2 dir, 4d530065) is never touched: the marker says `opened: false`.

### A failed park

A park is `mv slotN.hxs slotN.hxs.hld`. The old code was `mv ... && parked+=("$f")`: a failed mv fell through the `&&`,
the file was not recorded and not parked, and the run went on with a newer slot file in the dir. `hxs_newest_loadable`
picks by saved_at, so that file could win the auto-load and the scene would load the wrong state with no sign. Now a
failed `mv` calls `scene_abort`: it undoes what was done (restore_scene_pref) and returns 1 with the named reason
`could not park <f> (<dir>/<f>.hld): another slot file could win the auto-load`. The adb status of a `mv` is not
trusted alone either: after the loop the dir is listed again, and any slot file other than the wanted one fails the run
(`after parking, <f> is still in <dir>`). A `mv` that says it worked and did not is the case the status cannot see.

### Decisions

- **A missing directory is refused, not created.** A title with no saved state has no `states/<ttid>/` (the app makes
  it on the first save: hxs.c st_mkdir :284-290, called at :2232). `states/` itself is closed to shell, so making the
  dir would be a `run-as mkdir` plus, to leave the device as found, a `run-as rmdir` afterwards: two writes nothing has
  measured on the device. A scene exists to load a state, and a title with no dir has no state on the device, so the
  scene watch would report no-load anyway. The refusal says so: `<dir> does not exist: the title has no saved state on
  this device (the app makes the directory on a title's first save; a scene does not create it)`. A host-file push into
  a missing dir failed before this too (adb push has no parent), but with a bare "push failed".
- **chmod, not a run-as copy (Build 4).** The alternative is to leave the dir closed and do every write as the app:
  `run-as <pkg> cp` for the backup, the push, the parks. The chmod is smaller and keeps what already works. A run-as
  copy has two shapes for the pushed state (the file the host-file path exists for, tens to hundreds of MB): `adb push`
  cannot write the closed dir, so the file is either streamed through `run-as sh -c 'cat > ...'` (the way the prefs
  file goes, but at that size, over the shell channel with no sync-protocol checks), or staged in a place shell can
  write and then `run-as cp`'d in. Either way `dev_push`'s `.new`, sha256 and mode checks (hddperm, devpushro) would
  need a second implementation for the last step, and every other write to the dir (backup, park, unpark, drop) would
  need its own run-as form, each a place to be wrong and each needing a fake that refuses it. The chmod keeps `dev_push`
  and every other step as they are, and one step to be wrong. Its cost is that it changes the app's directory mode, which
  is why restore puts the mode back and logs both. Not built both, as the brief says.
- **Lower-case ttid.** The app names the dir `%08x` (hxs_jni.cpp:228). The device's shared storage matches names without
  case, so the 10-23 request's `5454000E` read and wrote the same dir as `5454000e`, but the log and the marker should
  name the real one. `scene_state_dir` lowers it. An empty title id fails with a named reason; before it, `states//`
  would have been listed.
- **Plan first.** The marker is written before the chmod and before the backup, so a worker that dies partway leaves
  restore_scene_pref the dir, the mode, and the files to look for. Restore acts on what it finds on the device, so a step
  the plan names that was never reached is a no-op.
- **The backup is `chmod 660`'d.** The Android shell's umask can leave a `cp`'d file restrictive; the backup is the file
  the app reads again after restore moves it back, so it gets the mode dev_push gives a pushed file.

### How the fragment tests it (99-load-state.sh)

The fake device now has app-only directories: title dirs are host mode 555, and the fake adb pushes with `cp` as the
host user, so a write into a closed dir fails with EACCES the way the device's does. The fake adb's `run-as <pkg> chmod
g+w|g-w` becomes a host `chmod u+w|u-w`; other run-as commands open a closed dir for their own duration, as the app
could. Fault files, `$LS_FAKE.stuck` (the chmod does nothing), `.failmv` (a plain-shell `mv` of a matching name fails)
and `.failmv.lie` (it fails but says it worked), keep the fake honest about the two cases the brief names.

Cases: k0 (the fake itself: a plain-shell write into the closed dir fails, run-as writes, chmod opens and closes, the
fault files act), k1 (a closed dir, a host file pushed: opened, pushed, parked, loaded, restored, closed; the log line
names the dir and both modes; the marker says `opened`), k1b (the same on an already-open dir: never touched), k2 (a
dir run-as cannot open: the exact named failure, nothing written, nothing changed, the marker gone), k3 (a park that
fails loudly: run fails, named reason, everything put back, no competing slot file), k3b (a park that lies), k5
(upper-case ttid), k6 (a missing dir), k7 (an empty ttid).

Mutants, each by exact substitution and cmp-verified: `dropopen` (no chmod step) turns k1 red; `noclose` (restore never
closes it again) turns k1 red; `silentpark` (the old `&& parked+=` and no listing check) turns k3 and k3b red;
`nolisting` (the listing check alone removed) turns k3b red, and k3 stays green, because a loud failure is caught by the
status alone. That last mutant is what shows the listing check is not redundant.

### Things lane.local should know

- **The live dispatcher runs the old code until the fold lands and it restarts.** Only 5454000e is open on the Nova by
  hand; every other title's dir is closed and is opened by this change on the first scene for it.
- **restore_scene_pref removes its marker on rc=1 too.** serve_one's message on a failed restore says "scene slots not
  restored; the next request retries". The retry is the stale-marker branch at the top of set_scene_pref, and that
  needs the marker, which a failed restore has already removed. So a restore that failed does not retry. This is the
  existing behaviour and not part of the fix; the dir stays open and the log says which file did not come back.
- **Unverified on the device:** `run-as chmod g-w` closing a dir on the real storage layer (the fake does it on a host
  fs), and the mode a shell `cp` leaves on the backup there. The original slot file's mode on the device was not
  measured; the fake uses 660. The first scene on a second title is the measurement.
- **A dir left open is harmless to the app.** The app owns it; g+w gives the group (`ext_data_rw`) write, and shell
  is already in that group. It is the mode restore puts back, not a safety property.

## A: a request that loads a state gets no recorded boot route (commit 2, coordinator addendum ce679c6d30)

The 10-23 replay of heavy2.hxs (`--load-state`, no `--route`) was void: request.sh attached `gta-3.route`. The
"dispatchdoctor1017 Section 1b" block (request.sh, before the `if [ -n "$ROUTE" ]` resolve) asks
`titlestate.py suggest-route` for a title that typed no `--route` (or `--route survey`), and GTA III's
`targets.toml` entry names `route = "gta-3"`. That route is recorded from a cold boot: A x16 and steering from 55 s.
A scene starts mid-game from a saved state, so those inputs land on a world they were not made for. A scene's own
input is `--hold-trigger`.

**request.sh** now skips the attach when `LOAD_SLOT` is set (`&& [ -z "$LOAD_SLOT" ]`, with a comment). `--load-state
<file>`, `--load-state <n>` and `--scene` all set `LOAD_SLOT` before this block. An explicit `--route <x>` still
attaches, because the attach block is only the suggestion; a named route is resolved below it as before. A
`--route survey` with a load stays the survey.

**dispatcher.sh `ensure_route_attached`** needed the same rule, and this was not in the addendum. The dispatcher
attaches a route at claim time too (serve_one, after `set_scene_pref`), for a request that carries none, from the
same `suggest-route`. A request that reached the queue without a route (queued by an older request.sh, or by hand)
would have got gta-3 there and the replay would have been void the same way. It now returns 0 before the attach when
the request has a `load_slot`, writing `none attached: the request loads a save state` to the inputs note so a
result says why it ran with no route. The request file is left byte for byte as queued. A request that named a route
is not touched on either path: only the suggestion is skipped.

**What the fragment tests (99-load-state.sh, section l).** The real request.sh runs against the real
`titlestate.py`, `targets.toml` and `routes/`; suggest-route's answer is never written by hand. The one fixture is a
scratch dispatch dir whose `titlestate/golden.json` holds a golden for GTA III, which is what lets request.sh queue
at all (the profile gate refuses a title with none). A stand-in `adb` that fails and logs sits where the device
would be; the last queue fact says it was never asked. The control (no `--route`, no load) must queue with
`route_name: gta-3` and say `attaching recorded route 'gta-3'` on stderr, so an attach is visible in this setup. Then
`--load-state <file>`, `--load-state 5` and `--scene gta3-incar` must queue with `load_slot` and no `route_name`,
`route` or `route_refs`; `--route gta-3` and `--route survey` with a load must keep what they named. At claim, the
real `ensure_route_attached` runs on a request with no load (control: gets gta-3), with `load_slot` 10 (left byte for
byte, the inputs note names the reason) and with `load_slot` and `route_name: survey` (left as is).

Two mutants, each by exact substitution and cmp-verified: `noqueueguard` (request.sh without the `LOAD_SLOT`
condition) turns the three no-route facts and the survey fact red while the control and the named route stay green;
`noclaimguard` (`ensure_route_attached`'s `load_slot` test replaced by `false`) turns the byte-for-byte and the inputs
note facts red while its control stays green. The request.sh mutant needs a tree shaped like the repo, since request.sh
finds `titles/` and `scenes.tsv` by its own path and resolves `--ref` with `git -C <its dir>/../..`: siblings by
symlink, request.sh a real mutated copy, the root a one-commit git repo in the scratch dir.

**`--load-hdd` is required with a load.** A `--load-state` without `--load-hdd` is refused by request.sh at queue
time (the scene's disk rule from 10-22), so the (l) cases pass `--load-hdd hdd-scene-gta3.img`; `--scene` takes its
disk from `scenes.tsv`. Nothing here reads that disk.
