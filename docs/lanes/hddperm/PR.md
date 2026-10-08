# hddperm: dev_push removes <path>.new on a failed push; push-level mode-failure legs (#397)

State: ready

Lane: hddperm              Issue: #397
Base: master @ 10f14d301d (origin/master merged into the branch, 60cfcf03d7)
Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-hdd-split.sh, docs/lanes/hddperm/NOTES.md, docs/lanes/hddperm/PR.md, docs/lanes/hddperm/OUTBOX.md, docs/audits/2026-09-29-hddperm-pass1.md, docs/audits/2026-09-29-hddperm-pass2.md
Prediction: none: dispatcher plumbing, no pixels.
Needs device: no    Needs NDK: no

Release note (none): dispatcher plumbing only; no emulator change.

The brief's core fix, a pushed titles.qcow2/hdd.img left 0644 that xemu cannot open read-write, landed on master through lane.hddcrash (9b274b6be3, 09-29 20:27 PDT) while this branch sat unfolded: GitHub was suspended and this lane had no PR.md. This branch merges master and takes master's `dev_push`/`dev_make_660` and fragment whole. On top of master it keeps only:

- **`dev_push` removes `<path>.new` on every failure before the rename** (audit pass 1, L1). Master's version leaves a stale full-size disk image on the device when a push, the sha check, the chmod or the rename fails.
- **Push-level legs in 99-hdd-split.sh.** The fake adb gains `chmodnoop` (chmod exits 0 and does nothing). For both `nochmod` and `chmodnoop`, `dev_push` must fail, hdd.img's bytes and mode must be unchanged, hdd.img.new must be removed, and the log must name the mode the chmod left. Master covers a refused chmod only through the prepare's kept-disk path.

Audit: pass 2 on e9e62ee32e was clean and fold-ready (docs/audits/2026-09-29-hddperm-pass2.md). The merge since then drops this lane's own `dev_push` body in favour of master's. The only code still this lane's is the four-line `dev_push_drop` cleanup and its legs.

**Local checks (no CI offline):**

| check | result |
|---|---|
| `SELFTEST_ONLY=99-hdd-split selftest.sh`, umask 022 | 72 passed, 0 failed |
| same, umask 002 | 72 passed, 0 failed |
| falsifier: master's dispatcher.sh with this fragment, umask 022 | 70 passed, 2 failed (the two `hdd.img.new is removed` legs) |
| full `selftest.sh`, shards 0-3 of 4, umask 022, on 60cfcf03d7's tree | 125 of 125 fragments; 284 + 956 + 948 + 884 = 3072 passed, 0 failed |
| `preflight.sh --allow-tracker` | passed |

**Next:** nothing in this lane. The real-device proof of the 660 fix is master's: it has been live since 9b274b6be3 folded.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
