# lane.lanepath1009 -- lane.sh gives each lane unit a shim-first PATH with --setenv (#433, 0.5)

PR: none yet (opening after this commit). Branch `lane/lanepath1009`, based on master `96852d8144`.
No issue: a harness fix dispatched directly by lane.local under the #433 umbrella. No prediction: no
pixels, no device run -- docs and harness only.

## What was built

1. `docs/testing/lane.sh`: a single `lane_path()` function, built from two variables set once
   (`LANE_SHIM_BIN="$WORK/forge/shim/bin"`, `LANE_PATH_TAIL="<fixed system tail>"`), called from both
   `start)` and `resume)` right before each does anything stateful (same spot as the existing `LANE_MAX`
   refusal, before the fetch/worktree/registry work). It sets `LANE_PATH` for both `systemd-run` blocks'
   `--setenv=PATH="$LANE_PATH"`, or refuses with **exit 78** and a message naming the missing directory
   if `$LANE_SHIM_BIN` does not exist. Never the caller's own `$PATH` -- that is the weaker rule the brief
   names as what this replaces, and it is never read.
2. Addendum 1's headless-session footer: `LANE_SESSION_FOOTER`, one string, appended to both the start
   and resume prompts (`\n\n$LANE_SESSION_FOOTER` before the closing quote, immediately before `--model`).
3. `docs/testing/jobs/selftest.d/99-lane-path.sh`, new. 29 checks: the happy path (shim dir first in both
   start's and resume's logged `--setenv=PATH=`, byte-identical between the two, footer present in both),
   four structural "exactly one assignment" checks guarding against a second copy that merely agrees
   today, the refusal path (missing shim dir -> exit 78, `systemd-run` never reached, both for start and
   for resume), and the four required mutants (three from the brief, one from Addendum 1).

## The three mutants, plus Addendum 1's footer mutant -- verbatim FAIL output

All four made by `sed`-editing a throwaway copy of `lane.sh` left beside the real one (not a copy of the
whole `jobs/` tree -- `99-lane-model-file.sh`'s own `lm_mutant` comment explains why: a copied `jobs/`
puts `remote-lane.sh` two directories from a real git checkout, every mutant run then refuses before
`systemd-run` ever runs, and every log stays empty -- which the `check "...actually reached systemd-run"`
assertion exists specifically to rule out as a false red). Full fragment run (`SELFTEST_ONLY="99-lane-path.sh"`),
29 passed, 0 failed:

```
== lane.sh: a lane unit's PATH puts the forge shim first, from one definition
  ok   a real start's --setenv=PATH puts the forge shim dir first
  ok   ...and the start actually reached systemd-run (not an early exit)
  ok   the start's prompt carries the headless-session footer
  ok   a resume's --setenv=PATH ALSO puts the forge shim dir first
  ok   the resume's prompt carries the headless-session footer too
  ok   resume's PATH is byte-identical to start's -- one definition, not two
  ok   lane.sh has exactly one LANE_SHIM_BIN= assignment
  ok   lane.sh has exactly one LANE_PATH_TAIL= assignment
  ok   lane.sh has exactly one lane_path() definition
  ok   lane.sh has exactly one LANE_SESSION_FOOTER= assignment
  ok   no shim: start refuses (exit 78), not any other code
  ok   no shim: start never reached systemd-run (log stays empty)
  ok   no shim: start says so on stderr
  ok   no shim: resume ALSO refuses (exit 78)
  ok   no shim: resume never reached systemd-run either
  ok   mutant (a) noresumepath: the sed applied
  ok     ...and does not touch the start leg
  ok     ...and resume still reached systemd-run (not an early exit)
  ok   mutant (a) noresumepath: resume's --setenv=PATH is gone, and the resume leg is red
  ok   mutant (b) callerpath: the sed applied
  ok     ...start still reached systemd-run
  ok   mutant (b) callerpath: PATH is the caller's own (shim not first), and this leg is red
  ok   mutant (c) shimafter: the sed applied
  ok     ...start still reached systemd-run
  ok   mutant (c) shimafter: the shim dir sits after /usr/bin, and this leg is red
  ok   mutant (d) noresumefooter: the sed applied
  ok     ...and does not touch the start leg's footer
  ok     ...and resume still reached systemd-run
  ok   mutant (d) noresumefooter: resume's footer is gone, and this leg is red
selftest: 99-lane-path.sh took 3s

selftest: 29 passed, 0 failed, PARTIAL: 1 of 130 fragments
```

Each mutant's own check line IS the FAIL-condition proof: the fragment's `check` wrapper only ever
prints `ok`, so "this leg is red" lines above are what the fragment's own `bad()`-vs-`ok()` branch would
print as `FAIL` if the mutant did NOT break the invariant -- i.e. the mutant is proven to break it by the
fragment choosing the `ok` branch that says so, not by inference. To get the literal `FAIL` line rather
than assert this, I ran each mutant a second time through a standalone throwaway harness (same
`lp_mutant`/`lp_start`/`lp_resume`/`lp_shim_first`/`lp_footer` helpers, same real `lane.sh start`/`resume`,
same systemd-run-logging shim) with the mutant's assertion written the OTHER way around: a plain `check`
call on the condition that holds on GOOD code, so it fails loudly against the mutant instead of my own
if/else quietly choosing the "red" branch:

```
--- mutant (a): --setenv=PATH dropped from resume only -- positive assertion, should now FAIL
  FAIL resume's systemd-run carries an explicit --setenv=PATH=
--- mutant (b): the weaker rule reinstated (caller's $PATH) -- positive assertion, should now FAIL
  FAIL start's --setenv=PATH puts the forge shim dir first
--- mutant (c): shim dir moved after /usr/bin -- positive assertion, should now FAIL
  FAIL start's --setenv=PATH puts the forge shim dir first
--- mutant (d), Addendum 1: footer dropped from resume only -- positive assertion, should now FAIL
  FAIL resume's prompt carries the headless-session footer
```

Each of the four real mutants makes its positive assertion FAIL, confirmed directly rather than by
reading my own if/else as self-evidently correct. The committed `99-lane-path.sh` keeps the if/else form
(matching `99-lane-model-file.sh`'s established convention) because it prints a message naming which half
of the mutant broke, which a bare `check` cannot; the throwaway harness above exists only to produce this
literal `FAIL` evidence for NOTES.md and was not committed.

## Real-start verification: `--setenv=PATH` reaches the spawned process, on the real systemd

The brief asks for one check against real `systemd-run`, not the selftest's logging shim, using a stub
command and a throwaway unit name, never a real Claude session. Ran directly (not through `lane.sh`, to
avoid touching any real lane or needing `HAKUX_WORK` pointed anywhere but the real host path):

```
$ systemd-run --user --unit hakux-lanepath-probe --collect \
    --setenv=PATH=/home/justin/hakux-work/forge/shim/bin:/home/justin/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin \
    --pipe -- bash -c 'echo PATH=$PATH; echo GH=$(command -v gh)'
Running as unit: hakux-lanepath-probe.service
PATH=/home/justin/hakux-work/forge/shim/bin:/home/justin/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin
GH=/home/justin/hakux-work/forge/shim/bin/gh
```

`command -v gh` inside the spawned unit resolves into the forge shim, not the real GitHub CLI, confirming
the mechanism end to end on the real systemd --user manager, not just against the selftest's shim. The
unit was `--collect` and had already exited and been garbage-collected by the time I checked
`systemctl --user show hakux-lanepath-probe.service -p Environment` a second later (empty output, "not
loaded" on `stop`/`reset-failed`) -- expected: `--collect` means a finished unit cleans itself up, and the
proof above (the process's own stdout) is the stronger evidence anyway, since it is what the process
itself saw, not a read-back of what was asked for. No real lane was started, stopped or resumed.

## The conflict this change surfaces in the rest of the selftest suite -- NOT fixed here, outside territory

Running the affected fragments individually (not yet the full ~60 min suite at the time this was written;
see the addendum below for that run) found that **lane.sh's new refusal breaks 32 checks across three
files**, none of them in this lane's territory (`docs/lanes/lanepath1009/**`, `docs/testing/lane.sh`,
`docs/testing/jobs/selftest.d/99-lane-path.sh` only). Every one of those fragments calls the REAL
`lane.sh start` or `resume` (not a stub) against a throwaway `$WORK` that has no `forge/shim/bin`
directory -- which is now, correctly, exactly what the brief asked `lane_path()` to refuse. The fragments
were written before this requirement existed, and none of them (nor the shared selftest harness itself)
ever created that directory in any fixture.

**Verified as genuine regressions**, not pre-existing breakage: each of the fragments below was run twice
-- once against this branch's `lane.sh`, once against the unmodified `master` copy (`git show
HEAD:docs/testing/lane.sh`, swapped in, tested, swapped back) -- and the baseline run is clean (0 FAIL) in
every one of these files:

| fragment | FAILs (this branch) | FAILs (baseline master) |
|---|---|---|
| `96-fleet-registry.sh` | 7 | 0 |
| `88-window-budget.sh` | 2 | 0 |
| `99-handback-branch.sh` | 2 | 0 |
| `99-handback-idle.sh` | 10 | 0 |
| `99-handback-lane-line.sh` | 1 | 0 |
| `99-handback-merged.sh` | 2 | 0 |
| `99-handback-parked.sh` | 8 | 0 |

(`99-handback-runs.sh` and `99-handback-draft.sh` also showed FAILs when run via `SELFTEST_ONLY` in
isolation, but the SAME FAILs appear against the unmodified baseline too -- confirmed pre-existing,
unrelated to this change, and most likely a `SELFTEST_ONLY`-subset ordering artifact (one fragment's
fixture depending on another's shim setup) rather than a real defect. `99-handback-waiter.sh` showed 0
FAILs either way. Neither is counted above.)

**The fix, in each case, is one line** (not applied here -- outside territory; see `OUTBOX.md`):

- `docs/testing/jobs/selftest.sh` line 170's `mkdir -p` (the shared `$T/work` every fragment gets by
  default unless it builds its own) needs `forge/shim/bin` added to the brace list. This single line
  covers all five `99-handback-*.sh` fragments above (23 of the 32 checks), since none of them override
  `HAKUX_WORK` -- they all run against the shared default.
- `docs/testing/jobs/selftest.d/96-fleet-registry.sh`'s own `mkdir -p "$LW/briefs" "$LD"` (its private
  `$LW/work` fixture) needs `"$LW/forge/shim/bin"` added.
- `docs/testing/jobs/selftest.d/88-window-budget.sh`'s own `mkdir -p "$WB/bin" "$WB/work/logs/lane" ...`
  needs `"$WB/work/forge/shim/bin"` added.

None of these are `~/.config` or a systemd unit -- the brief's one explicit no-go -- but they are files
this lane's territory does not name, and "Territory: ... Nothing else" is unambiguous. Named in
`OUTBOX.md` for lane.local, with the exact line and reasoning, rather than edited here.

## Addendum 2 (lane.local 2026-10-10 00:40 PDT): step 3 replaced -- no full-suite run here

The brief's step 3 said to run the full local selftest (~60 min, what the fold runs) and fix anything
broken. Addendum 2 (and a cross-session message from another lane relaying the same instruction while a
full run I had started was mid-flight) replaced that: a second full suite on this host slows the fold
already running tonight, and its timing-sensitive fragments flaked under that load (surfgpu1009's fold,
00:37). **I had started the full suite in the background before Addendum 2 landed; on seeing it, I killed
that run immediately (by PID, not `pkill -f`/`pgrep -f` -- both match a selftest invocation's own command
line, including this session's) rather than letting it finish.** It had reached fragment 58 of 130 (none
of the lane.sh-dependent 88-/96-/98-/99- fragments) and produced no output of its own worth keeping.

Per the replacement instruction, the evidence for this lane is the targeted-fragment runs already in this
file: `99-lane-path.sh` itself (29/0, above), plus every fragment confirmed to call the real `lane.sh`
(`96-fleet-registry.sh`, `88-window-budget.sh`, and the `99-handback-*.sh` family) run individually via
`SELFTEST_ONLY`, each also run against the unmodified baseline for comparison -- see the regression table
above. That is "run only 99-lane-path.sh and any existing fragment that exercises lane.sh" as asked; the
full-suite run the fold itself performs is what checks the rest.
