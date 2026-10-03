[job.cloud] Audit pass 2 of PR #622 (lane.hddsplit, #397): both pass-1 MEDIUM scenarios are verified fixed. Clean; the PR moves to fold-ready.

# Audit pass 2: PR #622, lane/hddsplit

- Head audited: `84a86029e1` (`origin/lane/hddsplit`), the remediation commit on top of
  the pass-1 head `fa2e37531b`.
- Remediation diff read: `git show 84a86029e1` (`docs/testing/dispatcher.sh`,
  `docs/testing/jobs/selftest.d/99-hdd-split.sh`, `docs/lanes/hddsplit/NOTES.md`).
- CI on this head: build ×2, Desktop build, and selftest (0-3) all pass
  (runs 36648824211/228/234, 2026-09-30T00:08Z).

## Method

For each pass-1 MEDIUM, I read the fixed code against the exact failure scenario pass-1
described, then ran the new selftest legs twice: once on this head (must be green), once with
`docs/testing/dispatcher.sh` swapped back to the pre-fix blob (`git show 84a86029e1~1:...`,
`titlestate.py`/`saves.py` left at the current head) via `SELFTEST_ONLY=99-hdd-split.sh` (must be
red on the legs that name the scenario, since a leg that passes against both versions verifies
nothing). The dispatcher.sh swap was done and reverted in the working tree only; nothing was
pushed from that state, and `git status` is clean before and after.

## M1 -- the restore marker is written after the pref, so a failed read-back leaves `hddPath` on titles.qcow2 with nothing to undo it

**Scenario re-checked.** `set_hdd_pref` now takes a marker argument and writes it
(`dispatcher.sh:515-518`) right after the local `was=$(hdd_pref_edit get "$tmp")`, which is
before the push to the device and before the read-back verification that can fail or hang. Read
in order:

1. The initial read of `x1box_prefs.xml` (before any write) can still fail/hang and return 1 --
   but at that point nothing has been written to the device, so there is nothing to restore. No
   regression from pass-1's scenario, which was specifically about the write landing and the
   *verification* read-back failing afterward.
2. Once past that point, the marker is written before `hdd_pref_edit set` touches the local copy
   and before the device push. A write that lands with a hung/lost read-back, or a worker that
   dies between the push and the verification, both leave the marker already in place.
3. The value recorded is never `titles.qcow2` -- `set_hdd_pref` substitutes `hdd.img` for it
   (`dispatcher.sh:519`), and `restore_hdd_pref` does the same on read (`dispatcher.sh:539`) as a
   second line of defense. This closes pass-1's "part 2" (a titles-disk value captured as the
   original becomes permanent): even a device already stuck on titles.qcow2 with no marker (the
   pre-fix fault, exercised by the selftest's `sed -i ... titles.qcow2` fixture) gets `hdd.img`
   recorded as the value to restore, and a stale marker naming titles.qcow2 restores hdd.img
   instead of re-inscribing it.

**Selftest confirms it discriminates.** Legs under "a failed hddPath read-back still leaves the
way back" (`99-hdd-split.sh`): 6 checks, all green on `84a86029e1`. Reverting only
`dispatcher.sh` to the pass-1 head turns exactly those 6 red:
`... and the marker already holds hdd.img`,
`... so the next request's restore puts hdd.img back` (got titles.qcow2),
`... byte for byte`,
`hddPath found on titles.qcow2 is never recorded as the one to put back`,
`... the run after it ends on hdd.img` (got titles.qcow2),
`a marker naming titles.qcow2 restores hdd.img` (got titles.qcow2).
Every one reproduces the exact symptom pass-1 named (titles.qcow2 left in place, or made
permanent). M1 cannot recur through this path.

## M2 -- a reset that fails deterministically is retried in full before every disc run

**Scenario re-checked.** `hdd_img_guard` now fingerprints `hdd.img` (`stat -c '%s %Y'`) before
acting, and checks it against `$D/.hdd_guard_failed.<device>` (`dispatcher.sh:687-692`). A
deterministic failure -- `saves.py reset` refusing the disk, or the on-device backup `cp` failing
-- goes through `guard_fail_final`, which records the fingerprint and the reason
(`dispatcher.sh:711-714`). While the fingerprint still matches, later requests take the short
path: log, write `hdd_guard.json` with `"repeat": true` and the original reason, and return,
paying for no sha256, no pull, no reset (`dispatcher.sh:693-699`). Any write to `hdd.img`
(size or mtime changes) re-arms the guard, and a successful reset removes the failed-marker file
(`dispatcher.sh:730`). The backup-failure path additionally removes the partial
`hdd.img.bak-auto` on the device before recording the failure (`dispatcher.sh:722-725`), closing
the "partial file eats the next attempt's headroom" half of the finding. Pull and push failures
are deliberately left unrecorded (plain `guard_fail`, no fingerprint write) since pass-1 did not
characterize those as deterministic, and retrying a transient network failure is correct.

**Selftest confirms it discriminates.** Legs under "a failed reset is not retried on the same
disk": 8 checks, all green on `84a86029e1`. Reverting only `dispatcher.sh` turns exactly the 6
that exercise the fix red:
`... and the partial hdd.img.bak-auto is removed`,
`... the failure is recorded against the disk`,
`... the next request writes the alert again, marked repeat`,
`... without pulling or hashing the disk`,
`... not retried while the disk is unchanged`,
(the two "over the limit hdd.img is reset" and "a disk saves.py refuses: an alert" /
"a write to hdd.img re-arms the guard" legs stay green on both, as expected -- they test the base
reset path, not the repeat-suppression). Every failing assertion reproduces the exact cost
pass-1 named (a full sha256+pull+reset paid again on a disk whose reset cannot succeed) or the
exact leftover (the partial backup file). M2 cannot recur through this path.

## Unrelated observation

One pre-existing leg (`HAKUX_TITLES_DISK=0: the split is off, recorded, and no adb call is made`)
also fails against the reverted `dispatcher.sh`, paired with the current `titlestate.py`/
`saves.py`. That leg is not one of the 6+6 pass-1-named legs and is not evidence of anything
outside this dispatcher.sh/titlestate.py pairing (the fixture combination pass-1's fix never
produces on the real branch); noted so the 12-of-48 count in `docs/lanes/hddsplit/NOTES.md`
(6 + 6 = 12, not counting this one) is not mistaken for a miscount -- it matches exactly.

## L1, L2 (LOW, left at the lane's discretion per pass-1's verdict)

Unchanged by the remediation commit; pass-1 left these for the lane to decide, not as a
condition of moving off `needs-remediation`. Nothing here contradicts that.

## Verdict

Both pass-1 MEDIUM findings (M1, M2) are fixed and verified: the code path pass-1 traced is
closed, and the new selftest legs discriminate the fix (red on the pre-fix code, green on the
remediation head) rather than merely existing. CI is green on the audited head. Clean.
Label: fold-ready.
