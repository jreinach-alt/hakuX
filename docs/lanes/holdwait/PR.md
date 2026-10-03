# holdwait: hold.sh wait-idle -- a hold-holder waits for the device's running request before touching it

State: ready

Lane: holdwait            Issue: none (harness defect, dispatched directly)
Base: master @ 8e3b1f2ad2
Files: docs/testing/jobs/hold.sh, docs/testing/jobs/selftest.d/99-hold-take.sh, docs/lanes/holdwait/PR.md, docs/lanes/holdwait/NOTES.md, docs/lanes/holdwait/mutants.sh
Prediction: none: harness script, no arm
Needs device: no    Needs NDK: no

`hold.sh take` stops new claims on a device but not the run already there. The "then wait for running/
to empty yourself" half was only a comment, and it has now been skipped three times. On 2026-10-01 at
21:58 PDT lane.titleroutes session 61 force-stopped lane.ibcache's #507 run at 132 of 420 s. On
2026-09-27 at 20:01 PDT titleroutes session 27 killed an arm the same way.

**Added:**
- **`hold.sh wait-idle <label> <timeout_s>`.** Exit 0 only when three things are true in one poll:
  - the hold exists;
  - the device's worker has seen it: `lanes/<label>` is gone, or it names no live `dispatcher.sh`;
  - no `running/*.owner` holds `<label>`.

  It exits 3 on timeout, naming each blocker and keeping the hold. It exits 1 if there is no hold. The
  worker condition closes the race that a one-time check of running/ misses: a claim can land seconds
  after the take, during the worker's last unheld queue walk. `coldslot.sh` logged one on 09-28: hold
  at 19:53:17, claim at 19:53:18.
- **`take` and `wait` print `NOT IDLE:` on stderr when the device they just took is busy.** The notice
  names the run. Exit codes, stdout and the hold files are unchanged.

The decisions of `take`, `release`, `who` and `wait` are unchanged. Legs a-f pass, and pass under every
mutant.

**Proof:** `selftest.d/99-hold-take.sh` has new legs g1-g8, which include the brief's three. Run alone:
45 passed, 0 failed. `docs/lanes/holdwait/mutants.sh` runs the legs against 8 broken hold.sh copies. Each
copy fails at least one leg, and each new leg fails under at least one copy (table in NOTES.md).
`wait-idle` was also run against a copy of the live `running/` and `lanes/`, read-only. It named both
the Nova's worker pid and the titleroutes run in flight.

**Found on the way:** `briefs/titleroutes.md` ADDENDUM 14's by-hand check
(`grep -l '"device": *"nova"'` over the owner files) matched nothing, because owner files hold a bare
label. ADDENDUM 7(a) said `hold.sh wait` waits for the run in flight, and it does not. Both are
corrected in place in the brief, which is outside the repo. After this folds, those lines become the
single `take && wait-idle` path; see NOTES.md, "The titleroutes convention".

Release note (none): harness tooling only; no emulator code.

`docs/testing/jobs/hold.sh` and `selftest.d/99-hold-take.sh` return to [lane.toolsmith] on fold.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
