# suitesha1022: a disc run boots the harness's disk, and a run on any other disk is refused by name (#433)

State: draft

Lane: suitesha1022            Issue: none (harness defect, dispatched directly)
Base: master @ b944110629
Files: docs/lanes/suitesha1022/PR.md, docs/testing/{dispatcher.sh,run_disc.sh,extract_results.py,dispatch_doctor.sh}, docs/testing/jobs/selftest.d/99-disc-hdd.sh
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
