# lane.lanepath1009 -- lane.sh gives each lane unit a shim-first PATH with --setenv (#433, 0.5)

PR: none yet (opening after this commit). Branch `lane/lanepath1009`, based on master `96852d8144`.
No issue: a harness fix dispatched directly by lane.local under the #433 umbrella. No prediction: no
pixels, no device run -- docs and harness only.

## Resume (attempt 2): why attempt 1 did not finish

Attempt 1 completed the brief, Addendum 1 and Addendum 2 (`lane_path()`, the footer, `99-lane-path.sh`
with its four mutants, the real-systemd-run check, the targeted-fragment regression table), wrote
`OUTBOX.md` naming three files outside its then-current territory that needed a one-line `mkdir -p`
fix each, and set `State: ready` without those fixes applied -- correct at the time, since
`docs/testing/jobs/selftest.sh` was not yet in territory. The fold then ran the full suite on
`69aa814fe1` at 03:13 and found 112 failures (Addendum 3, landed 04:50 PDT, after attempt 1's session had
already ended): the exact 15 lane.sh-dependent fragments attempt 1 had already identified and sized in
`OUTBOX.md`/`NOTES.md`. Addendum 3 put `selftest.sh` in territory and asked for the fixture fix to be
applied directly (preferred shape: one global stub + `HAKUX_SHIM_BIN`, not three separate `mkdir -p`
edits) rather than left in `OUTBOX.md`. That work is this attempt's addition, below.

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

## Addendum 3 (lane.local 04:50 PDT): fixtures' shim dir fixed directly, `selftest.sh` now in territory

The fold's full-suite run on `69aa814fe1` at 03:13 failed: 3090 passed, 112 failed, all 112 in the 15
lane.sh-dependent fragments attempt 1 had already named in `OUTBOX.md`/`NOTES.md`
(`87-fold-stale-ci`, `88-window-budget`, `96-fleet-registry`, and the `99-handback-*`/`99-lane-model-file`/
`99-limits-env` family -- a superset of the 7 files attempt 1's isolated `SELFTEST_ONLY` runs had found,
since the full suite exercises a few more call sites of `lane.sh start`/`resume` that isolation skips).
Cause confirmed as before: `lane_path()` correctly refuses when the shim dir is missing, and no fixture
created one.

**Applied the brief's preferred shape, not `OUTBOX.md`'s three-file patch.** Rather than adding
`forge/shim/bin` to three separate fixtures' own `mkdir -p` lines (which only covers the fragments that
exist today, and misses any future fragment that builds its own private `$WORK`), `lane.sh` now reads the
shim dir from one variable with a default:

```
LANE_SHIM_BIN="${HAKUX_SHIM_BIN:-$WORK/forge/shim/bin}"
```

and `selftest.sh`'s fake-host setup (now in territory) creates one stub shim dir under the run's own `$T`
and exports `HAKUX_SHIM_BIN` to it, once, right after the existing fixture `mkdir -p`/`export` block:

```
mkdir -p "$T/shim/bin"
export HAKUX_SHIM_BIN="$T/shim/bin"
```

Every fragment that calls real `lane.sh start`/`resume` inherits this through normal environment
inheritance (`export VAR=...; bash ...` subshells, or `env VAR=... bash ...` -- neither clears the
parent's exported vars), whether it uses the shared default `$HAKUX_WORK` or builds its own private one
(`$LW/work`, `$WB/work`, ...). Checked `96-fleet-registry.sh` and `88-window-budget.sh`: neither uses
`env -i` or unsets `HAKUX_SHIM_BIN`, so the inherited export reaches them unmodified -- no fragment
needed editing beyond `99-lane-path.sh` itself. (The brief's fallback -- "if a fragment clears its
environment ... fix that fragment instead" -- did not apply to any of the 15.)

**`99-lane-path.sh` can't rely on the shared stub for its own assertions** (it needs the shim present/
absent on command, for the happy path, the refusal path, and five mutants), so `lp_start`/`lp_resume` now
always pass `HAKUX_SHIM_BIN="${LP_SHIM_BIN:-$LP_SHIM}"` explicitly in their `env` call, overriding
whatever `selftest.sh` exported globally. The happy-path and refusal-path sections are unchanged (they
already created/removed `$LP_SHIM` on disk and relied on `LP_SHIM_BIN` being unset, i.e. defaulting to
`$LP_SHIM`); only the refusal case inside the new mutant (e) sets `LP_SHIM_BIN` to a path that never
exists on disk at all (`$LP/no-such-shim`), so that leg doesn't depend on `$LP_SHIM`'s on-disk state.

**Mutant (e), per Addendum 3's "adds a mutant that drops the refusal"**: `lp_mutant norefusal` deletes
the `if [ ! -d "$LANE_SHIM_BIN" ]; then ... exit 78; fi` block from a throwaway copy of `lane.sh`, then
runs `lp_start` against it with `LP_SHIM_BIN` pointed at a directory that does not exist. Re-running
`99-lane-path.sh` alone with this mutant added: **32 passed, 0 failed** (up from the 29/0 above, which
predates mutant (e)):

```
  ok   mutant (e) norefusal: the sed applied
  ok     ...and reached systemd-run anyway (not refusing for some other, unrelated reason)
  ok   mutant (e) norefusal: the refusal is gone, start proceeded anyway, and this leg is red
selftest: 99-lane-path.sh took 4s

selftest: 32 passed, 0 failed, PARTIAL: 1 of 130 fragments
```

Inside the actual fragment's own fixture (full `lp_fresh`/`lp_start` setup -- real repo, dispatch dir,
briefs dir), the mutant reaches `systemd-run` (checked explicitly, not just inferred from a non-78 exit
code) and the refusal is confirmed gone. Positive-assertion confirmation, same method as mutants a-d, run
through a standalone throwaway harness (own cruder fixture: just a repo, a logging `systemd-run` shim,
no dispatch/fleet state) with the assertion written as a plain `check`, not if/else, so the literal
`FAIL` line is read directly:

```
--- against GOOD lane.sh (expect: refuses, RC=78)
  ok   start refuses (exit 78) when the shim dir is missing
--- mutant (e): refusal dropped -- positive assertion, should now FAIL
  FAIL start refuses (exit 78) when the shim dir is missing
mutant RC=76
```

(RC 76, not 78: with the refusal gone, this cruder standalone fixture's `start` fails for some other,
unrelated reason further into `lane.sh` -- expected, since this throwaway harness skips setup the real
fragment's fixture does, and is not a claim this mutant reaches `systemd-run` on its own. The thing being
proven is narrower and sufficient: the mutant's exit code is not 78, so the refusal itself is gone. The
real fragment's own fixture, which does have that setup, is the one that shows the mutant proceeding all
the way to `systemd-run`.)

**Verification, targeted subset only** (Addendum 3's explicit instruction -- not the full ~60 min suite,
same reasoning as Addendum 2):

```
$ SELFTEST_ONLY="87-fold-stale-ci 88-window-budget 96-fleet-registry 99-handback 99-handback-branch \
  99-handback-draft 99-handback-idle 99-handback-lane-line 99-handback-merged 99-handback-parked \
  99-handback-resolved 99-handback-runs 99-handback-strand 99-lane-model-file 99-limits-env \
  99-lane-path" bash docs/testing/jobs/selftest.sh
...
selftest: 495 passed, 0 failed, PARTIAL: 16 of 130 fragments
real    ~4m30s
```

| | before (fold, full suite, `69aa814fe1`) | after (this subset, this branch, with mutant (e) added) |
|---|---|---|
| passed | 3090 | 495 |
| failed | 112 | 0 |

(The two "passed" totals aren't directly comparable -- the fold ran all 130 fragments, this run only the
16 named by Addendum 3, and this run's own `99-lane-path.sh` has one more check than the fold's (mutant
(e), added after the fold's run) -- but every one of the 112 failures the fold found lives inside those
16, and all 16 are now clean, including `99-lane-path.sh`'s own 5 mutants.) The fold reruns the full
suite on this head; that is what checks the other 114 fragments, consistent with Addendum 2's reasoning
for not duplicating that run here.

No `~/.config` or systemd-unit edit, no real lane started/stopped/resumed, no `pkill -f`/`pgrep -f`.
`OUTBOX.md` updated to record this is resolved, not left as an open ask.
