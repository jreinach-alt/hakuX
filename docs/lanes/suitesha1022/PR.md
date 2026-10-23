# suitesha1022: a disc run boots the harness's disk, and a run on any other disk is refused by name

State: ready

Lane: suitesha1022            Issue: none (harness defect, dispatched directly)
Base: master @ b944110629
Files: docs/lanes/suitesha1022/PR.md, docs/testing/{dispatcher.sh,run_disc.sh,extract_results.py,dispatch_doctor.sh}, docs/testing/jobs/selftest.d/99-disc-hdd.sh, docs/testing/jobs/selftest.sh (shard table)
Prediction: none: dispatcher plumbing, no pixels. The proof is the P10 depth-suite pair re-queued after this folds: its
  `logcat1.txt` reads `Prefs hddPath=.../x1box/hdd.img`, `captures1/` is not empty, and `hddPath` on the Nova reads
  `hdd-owner-1018.img` again when the request is done. Falsified by a pgraph disc result with 0 captures whose
  logcat names any HDD other than hdd.img and whose ERROR is not `WRONG HDD:`
Needs device: no (the proof is queued by lane.local, not run here)    Needs NDK: no
Selftest: 99-disc-hdd -- the disc path against a fake adb whose prefs say `hddPath=.../hdd-owner-X.img`; the
  mutants (a disc run that trusts `hddPath`; a run_disc.sh with no HDD check) must fail it

## Step 0: already tried

Sources: `git log -i -E --grep='hddPath|hdd_pref|titles.qcow2|titlestate|hddcrash|STALE LOG|0 files|extract'` and
`git log -S` on run_disc.sh (`STALE LOG`, `PULL_CHECK`, `CAPTURE_LOG`) and dispatch_doctor.sh (`dd_classify`);
docs/lanes/{titlestate,hddcrash,hddperm,hddsplit,devpushro1018}/; the vsh ledger comment in run_disc.sh (:227-247);
the three failing runs' `run1.log`, `ERROR`, `doctor.md` and `logcat1.txt` under dispatch/results/, and the last good
one (1-1792410252-fpsdata1018-texscan2d-reverify-fix-3955885).

| Date | Commit / doc | What it measured or changed | Verdict | Meaning here |
|---|---|---|---|---|
| 09-12 | 567067d2e4 (CAPTURE_LOG) | run_disc.sh streams the guest's logcat into a file the dispatcher keeps as `logcat<r>.txt` | kept | The run's own log already carries `Prefs hddPath=` and `HDD resolved:` (xemu_android.cpp:1042, :1094). Nothing reads either line, so the disk the guest booted was always recoverable and never asked |
| 09-25 | c69f380e32 (defect 15) | run_disc.sh pulls hdd.img, compares its md5 with the device's, pulls again on a mismatch | kept | It proves the host's copy is the device's hdd.img. In the failing runs it said "md5 matches the device's image": the copy was faithful and was the wrong file. It checks the pull, not which disk the guest wrote |
| 09-25 | 14612833b9 (vsh STALE LOG, PR #229 M1) | vsh keeps a per-device ledger of the last `log.txt` created time and refuses a log the previous run left | kept, vsh only | Wrong-disk detection by accident, for vsh alone: a vsh run on the wrong disk pulls an image holding an old log. It fires after the pull and the extract, and says "this run never started the program", not which disk. pgraph has no ledger, and extract failed first |
| 09-29 | fa2e37531b (hddsplit, #397) | Title runs point `hddPath` at titles.qcow2 through `set_hdd_pref`, a marker restores it; dispatcher.sh:790 states "every other run leaves `hddPath` on hdd.img"; `hdd_img_guard` bounds hdd.img's size before a disc run | kept | The rule is a sentence, not a check. `hdd_img_guard` and every disc-path line name hdd.img by path and never read `hddPath`, so a pref that points elsewhere is invisible to it. The marker is written by `titles_disk_prepare` only (:1702) |
| 09-29 | 84a86029e1 (hddsplit M1) | The marker is written before the pref; titles.qcow2 is never recorded as the original, hdd.img in its place | kept | The helper this change reuses. A marker already there is not overwritten, so two kinds of run cannot clobber each other's original |
| 09-29 .. 10-04 | docs/lanes/hddcrash/NOTES.md (9b274b6be3), f3bd87638e (hddperm) | Pushed disks left 0644 crashed the app at boot; dev_push sets mode 660 and removes `<path>.new` on failure | different cause | Looks at the mode and bytes of the disk the dispatcher pushed; none of it asks which file the app opens. Its 0-capture runs were app crashes with a crash line in logcat; these have a clean 225 s run |
| 10-17 | 75b1d3475d (dispatchdoctor1017 s2) | `dd_classify` names the failure classes the doctor knows, keyed on `head -1 ERROR`; `ran but produced 0 captures` goes to a model session; anything else gets `give-up: not a class the doctor recognises` with no session | kept | This is where the doctor's give-up text comes from. The failing ERROR was the generic 0-capture line, so the model read `run1.log` and `logcat.txt` (the doctor's brief reads that name; a disc run's log is `logcat1.txt`, so it never saw the HDD lines) and called `d98f15f not found` "a host-side lookup" |
| 10-18 | 62181bc0a9 (devpushro1018) | dev_push gets a read-only mode for the Nova's SD-card disc pushes | unrelated | The ISO push, not the HDD |
| 10-19 | fpsnext1019 NOTES.md:935 | Fable recon on the Nova: `hdd-owner-1018.img` is "already the active hddPath" | the cause, noticed in passing | By 10-19 12:29 the owner's image was the `hddPath`; the last good disc run (10-19 05:10 logcat) still read `hdd.img`. Nothing put it back, and nothing was meant to: the owner's play is outside the dispatcher |
| 10-19 .. 10-22 | dispatch/results/1-1792713057-p10fragdepth1022-3101183, `...-3101257`, 1-1792728809-drive1022-8129 | pgraph disc runs on the Nova, 225 s of frames and a clean exit each | void | `run1.log`: `error: d98f15f: d98f15f not found`. The extractor's `resolve()` looking for the per-run guest dir `d98f15f` (an `md5sum` of the request id and run number, `dispatcher.sh:2807`) on the pulled hdd.img. `logcat1.txt`: `Prefs hddPath=.../hdd-owner-1018.img`, `HDD resolved: ... size=3657893514`. The guest wrote into the owner's image |

Nothing in the table enforced "a disc run boots hdd.img", and nothing before this change recorded a disc run's
`hddPath`. The two guards that could have seen it (the pull's md5, the vsh ledger) both look at the host's copy of
hdd.img, which is the one file the guest did not write.

Consequences for this change, from the table:
- the owner's image is never touched by the harness: the pref moves, the file does not; the guest's output dir
  (`e:/d...`) already sits in `hdd-owner-1018.img` from the void runs, and this lane leaves it;
- `set_hdd_pref` / `restore_hdd_pref` and the one marker are reused, not copied (fa2e37531b, 84a86029e1);
- a missing `HDD resolved:` line is "HDD unknown", never a pass (the table's md5 row is what a pass without a
  check looks like).

## Mechanism

A disc run (pgraph or vsh) now boots the harness's disk on purpose, and a run on any other disk is refused by name.

dispatcher.sh, around the run loop in `serve_one`:
- `disc_hdd_prepare` reads the app's `x1box_prefs.xml` (`hdd_pref_fetch`: run-as cat). `hddPath` already
  `$(x1box_dir)/hdd.img` is `kept`: one read, no write, no marker. Anything else, an absent key included, is
  `set` through the existing `set_hdd_pref <want> <marker>` (the marker is written first and never overwritten; the
  write is verified by read-back). Prefs that cannot be read (a release package, no run-as) are `unread`: the run goes
  on and `run_disc.sh`'s log check is the only guard. A readable pref that differs and cannot be moved is `failed`: the
  request is refused (`could not point hddPath at hdd.img for this disc run (it names <path>)`) and no guest is launched.
- `disc_hdd_after` runs after the run loop and in the refusal paths: `restore_hdd_pref`, which writes back exactly what the
  marker holds (byte for byte when the key existed; the key removed when it was absent). A failed restore logs a
  WARNING and leaves the marker, so the next request's start-of-request restore retries it.
- `hdd_disc.json` in the result dir (`action`, `was`, `want`, `restored`) and `meta.hdd_disc` / `meta.hdd_verdicts` in
  result.json say what happened.
- A `WRONG HDD:` or `HDD UNKNOWN:` line in any `run*.log` becomes the request's ERROR, ahead of the generic
  `ran but produced 0 captures` branch, so a wrong disk is never scored as 0 captures.

run_disc.sh: `hdd_check` reads every `HDD resolved:` line of this run's `CAPTURE_LOG`. All equal to the pulled path
(`DEVHDD`) passes. Another path prints `WRONG HDD: guest wrote <path>, harness pulls <DEVHDD>` and exits 1 (checked
early, so the guest is stopped seconds in; and again before the pull, so nothing is pulled or extracted). No line is
`HDD UNKNOWN: ... has no 'HDD resolved:' line`, exit 1, never a pass. A caller with no `CAPTURE_LOG` gets a non-fatal
`HDD UNCHECKED` (only direct callers; the dispatcher always sets one). A pass prints which disk the log named.

extract_results.py: the not-found error names the directory looked for, the path walked, and the root dirs the image
does hold (`... not found -- looked for 'dX' in / and it holds 1 directories (dOLDRUN) and 0 files`).

dispatch_doctor.sh: `dd_classify` returns `wrong-hdd` for `WRONG HDD:`, `HDD UNKNOWN:` and the could-not-point ERROR;
`dd_diagnose` answers it deterministically (a `give-up:` verdict naming the disk, `doctor.md`, a lesson), with no model
session, no gate and no TSV row (rows count against the doctor's session cap).

Never done by this change: no read, move, rewrite, push-over or `rm` of the owner's image; no other app data touched
(the pref edit is an in-place regex edit of one `<string name="hddPath">` element).

## Checks

- `bash -n` on the three shell files, `python3 -I -m py_compile` on the extractor.
- `SELFTEST_ONLY=99-disc-hdd` with the fix: 44 passed, 0 failed, 74 s. The same fragment on the unfixed base tree
  (b944110629 + only the fragment): 6 passed, 38 failed, S1 red first.
- Regression fragments run with this change (touch dispatcher.sh, run_disc.sh, the extractor or the doctor):
  51 57 58 84 85 86-build-stamp 89-verdict-perflog 94-arms-disc-narrow 95 97-dispatch-{deploy,snapshot-drive,snapshot-rename}
  98-dispatch-{doctor,late-device} 99-{auto-route,battery-admit,build-gate,dev-push-ro-disc,dev-push-wslpath,
  fleet-battery-gate,folder-pref,hdd-split,hitch-report,hold-take,hold-tiers,iso-roots,ownerplay-capture,profile-gate,
  restore-priority} 56-desktop-worker 61 62-routerefs: all green except 51's E and E2, which read what
  50-arms-requeue leaves behind (`clear_markers`, `finish_queue` are defined there) and fail identically on the base
  tree when run alone. 51's F (serve_one 0-capture requeue), G (run_disc crash naming) and H (cache clearing) pass.
- `selftest.sh --check-shards 4`: all 161 fragments covered once (`99-disc-hdd:70` added to the shard table).

## Selftest: 99-disc-hdd

Fake adb whose device is a directory: prefs say `hddPath=.../hdd-owner-1018.img`; the fake app reads `hddPath` when
`am start` arrives, boots that image, writes its output dir into the disk it booted (so hdd.img lacks the dir when the
owner image is booted, as in the incident), and logs `Prefs hddPath=` / `HDD resolved:`. Real run_disc.sh, real
`serve_one`, real extractor, real doctor.

With the fix: 44 ok, 0 FAIL. The legs: D1-D4 (run_disc.sh alone), S1-S7 (serve_one), the extractor, the doctor, the
wiring order, and six mutants that each turn a named leg red. S1 is the falsifier: `hddPath` reads hdd.img when the
guest starts, the prefs file is byte for byte the owner's afterwards, the owner's image sha is unchanged and no adb call
names it.

With the mutant `if ! disc_hdd_prepare "$rdir"; then` -> `if false; then` (a disc run trusts `hddPath`) applied to the
worktree's dispatcher.sh: rc=1, 27 passed, 17 failed, with `FAIL S1 (FALSIFIER): hddPath read hdd.img when the guest
started, though it named the owner's image on arrival` first (S1's other six legs, S2, S4-S7 and the wiring check
follow). The edit was reverted with `git checkout`.

## Risks

- Cost: one `run-as cat` of the prefs per disc request, and one write pair when `hddPath` differs.
- A release package (no run-as) cannot be read: the run goes on unguarded by the pref and guarded by the log check, which
  refuses a wrong disk but cannot move the pref.
- A disc run on the wrong disk is now the request's ERROR (`WRONG HDD: ...`), not a 0-capture result. The P10 pair
  that was voided on 10-19..10-22 is for lane.local to re-queue after this folds.
- An app build that does not log `HDD resolved:` (every build since 09-12 does) would make each disc run `HDD UNKNOWN`:
  that is the intended failure, not a pass.
- The doctor's model brief reads `logcat.txt`; a disc run's log is `logcat1.txt`. Not changed here (the wrong-hdd class
  needs no model), but any other disc-run diagnosis still does not see the HDD lines.
- The 10-19..10-22 voided runs left output dirs (`e:/d...`) inside `hdd-owner-1018.img`. Not touched.

## Marker interplay (lane.local, before folding)

The disc path shares one marker with the title path: `$DISPATCH_DIR/.hdd_pref.<label>` (`.hdd_pref.nova` for the Nova).
`serve_one` restores at the start of every request, so a marker a died title run or disc run left is restored and
cleared before either kind of run records its own original: each run sees the true original, and the shared marker is
safe. A pref already at hdd.img costs a read and no marker. Residual window (same as title runs): if the worker dies
mid-disc-run the owner's path sits in the marker until the next request starts; an owner launching the app in that window
boots hdd.img. Do not clear `.hdd_pref.*` by hand while a request is running.
