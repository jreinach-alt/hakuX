# holdpid1022: hold.sh's owner-play capture never confirms itself, because systemd expands `$` in the script before bash sees it

State: ready

Lane: holdpid1022            Issue: none (harness defect, dispatched directly)
Base: master @ b944110629
Files: docs/lanes/holdpid1022/PR.md, docs/testing/jobs/hold.sh, docs/testing/jobs/selftest.d/99-ownerplay-capture.sh
Prediction: written after section 1 and before any edit. (1) With a `systemd-run` fake that applies systemd's expansion, master's hold.sh fails the fragment at the pidfile (`$$` -> `$`), so `take` exits 6. (2) A launch that gives systemd no script text (a file) passes the same legs. (3) Each mutant turns exactly its own leg red: plain `bash -c` launch, double-quoted trap, cmdline identity, no orphan cleanup, no `set -f`. Result: all three held (section 3).
Needs device: no (every run is a selftest fixture with its own DISPATCH_DIR and a fake adb)
Needs NDK: no
Selftest: 99-ownerplay-capture

## Step 0: already tried

Sources: `git log -i -E --grep='capture_ensure|ownerplay|owner-play|holdcap|systemd-run|pidfile'` on master,
`git log --all --oneline | grep holdcap`, `docs/lanes/holdcap1018/NOTES.md` (read at 40fa84e632), a grep of
`docs/testing` and `host-tools` for `systemd-run`, and `git log -i -E --grep='dollar|expand-environment|ExecStart'`.

| Date | Commit / doc | What it measured or changed | Verdict | Meaning here |
|---|---|---|---|---|
| 10-18 | 40fa84e632 (holdcap1018 Step 0) | Read the harness's global `systemd-run`/`systemctl`/`adb` shims and found them inert: `systemd-run` only logs its argv, `systemctl is-active` answers `active` for any unit | Correct, and it is why the fragment brought its own shims | The local shims it then wrote are the fake this lane has to make honest |
| 10-18 | 5bc67eb7af, fold f98feca3ba (holdcap1018) | Added `capture_ensure`: `systemd-run --user --unit ... --setenv=... bash -c "$script"` with a restart loop, `trap ... TERM`, `echo "$$" > "$PIDFILE"`; detection by pidfile plus `/proc/<pid>/cmdline` containing `logcat` | Passes its own fragment; fails in production (10-22, `take` exit 6) | The defect is in this launch. The comment above the script says every `$` stays literal until the capture's bash evaluates it, which is false under systemd |
| 10-18 | 99-ownerplay-capture.sh (same commit) | Local `systemd-run` shim: strips `--setenv=`, `--unit`, then `setsid env ... bash -c "$script"` | Never applied systemd's command-line expansion, so `$$`, `$cur`, `$rc` and `$VAR` passed through untouched | The fake passes where the real thing fails. Legs (a)-(g) and the mutant all ran through it |
| 10-22 | lane.local, by hand | Wrote the unit's `MainPID` into the pidfile to unblock `take` | Worked once, not a fix | The pidfile is not the capture's own `$$` after the workaround; nothing stops the next `take` failing the same way |
| 10-10 | 69aa814fe1, fold 07937793af (lanepath1009) | lane.sh gives each lane unit a shim-first PATH with `--setenv` | Unrelated to `$`; touches the same `systemd-run` shape in lane.sh | lane.sh has the same shape and a script with `\$rc`; audited in section 4, no defect |
| 09-19..09-26 | cloud.sh, handback.sh commits (cloudtail, handbackwaiter) | `systemd-run` with `bash -c` and `bash <file>` | Not about `$` expansion | `cloud.sh:792` and `lane.sh:358,391` carry `\$(...)`, `\$?` and `\$rc` inside the script: audited in section 4, no defect (line numbers as of b944110629) |

Nothing in the log mentions systemd's `$` expansion, `--expand-environment` or `$$` escaping for this harness
(`git log -i -E --grep='dollar|expand-environment'` finds only unrelated ExecStart commits), so no earlier result
is repeated or contradicted here.

Stop rule read: the same failure twice for one cause means stop and report. This is the first fix attempt for this
cause.

## 1. What systemd 255 does to the argv, observed before any edit

Host: systemd 255 (255.4-1ubuntu8.18), user manager running. Every probe is
`systemd-run --user --wait --collect --pipe -q [--setenv=...] <command>` on a command that prints and touches no
device. `--expand-environment=BOOL` exists (man systemd-run: "Added in version 246").

**The production failure, reproduced with the real systemd-run** (hold.sh's first two script lines, `PIDFILE` by
`--setenv`):

    trap -- 'kill  2>/dev/null; exit 0' SIGTERM
    bash pid is 210739
    pidfile now holds: [$]

**Which `$` forms systemd rewrites.** One probe per word, `--setenv=A="x y"`, command `printf '<%s>' <word> END`,
plus in-script probes where bash reassigns a variable and reads it back (so a rewrite by systemd is
distinguishable from bash's own evaluation):

| Word, as it appears in argv | What the command receives | Who evaluated it |
|---|---|---|
| `$$` (anywhere in a word) | `$` | systemd: `$$` is an escaped `$` |
| `a$$b`, `$$$`, `$$$$` | `a$b`, `$$`, `$$` | systemd |
| `${A}` (anywhere in a word) | the --setenv value, or empty if unset | systemd |
| `$A` as a whole separate argument | the value, split on whitespace into 0..n arguments; an unset name drops the argument | systemd |
| `$` alone, `$(echo)`, `$1`, `$?`, `$A$A`, `$A:z` as a whole argument | dropped (read as a variable name that is not set) | systemd |
| `pre$A`, `a$`, `${A`, `${A:+b}` | unchanged | bash, later |
| bare `$SERIAL`, `$cur`, `$rc`, `$PIDFILE`, `$LOG`, `$SPEC`, `$?`, `$!`, `$(...)` inside a longer word | unchanged | bash evaluates them. `SERIAL=reassigned; echo $SERIAL` printed `reassigned`; `cur=42; echo $cur` printed `42`; `echo ${SERIAL}` printed the --setenv value, not the reassigned one |
| `%H`, `%n`, `%%`, `%s`, `date +%Y-%m-%dT%H:%M:%SZ` | unchanged | no specifier expansion in a transient command |

So the brief's list is half right. Against hold.sh's script (one argv word, `bash -c "$script"`):
- `$$` -> `$`: yes, and it is the only rewrite. `echo "$$" > "$PIDFILE"` became `echo "$" > "$PIDFILE"`; the pidfile
  holds a literal `$`; `capture_running` needs `^[0-9]+$`; `take` exits 6. This is the whole production failure.
- `$SERIAL`, `$LOG`, `$SPEC`, `$PIDFILE`: NOT substituted by systemd. They sit inside a longer word, and systemd
  rewrites a bare `$VAR` only when it is the entire argument. bash evaluates them from the unit's environment, which
  is what the comment above the script wanted.
- `$cur`, `$rc`: NOT expanded to nothing by systemd (`rc=7; echo $rc` printed 7).
- The script has no `${...}`, so nothing else is rewritten. A future edit that adds one would be.

**A second defect, independent of systemd.** The trap line is
`trap "kill $cur 2>/dev/null; exit 0" TERM`, double-quoted. bash expands `$cur` when `trap` runs, when `cur` is
unset, so the stored trap is `kill  2>/dev/null; exit 0` (output above, from the real unit; the same line comes out of
a plain `bash -c`). SIGTERM to the capture's bash therefore never kills the adb child. Evidence on this host: each run
of the unfixed 99-ownerplay-capture fragment (29 passed) leaves four orphaned `sleep 100000` (the fake adb) behind
(`pgrep -c -x -f 'sleep 100000'` read 48 after my one baseline run; the four newest pids are that run's, 44 are older). Production hides it only because `systemctl --user stop` kills the whole
cgroup; the `kill "$pid"` half of `capture_release` leaves a live `adb logcat` appending to the file.

**Why the fragment passed.** Its local `systemd-run` does `setsid env ... bash -c "$script"` with the argument
untouched, so `$$` reaches bash as `$$`. Its (e) leg asserts `oc_dead` by re-reading the pidfile that `release` has
just removed, which is true of any state.

## 2. The fix (docs/testing/jobs/hold.sh)

**Launch.** `capture_ensure` writes the capture script to `$D/hold/<label>.capture.sh` and runs
`systemd-run --user --unit <unit> --collect --setenv=SERIAL=... --setenv=LOG=... --setenv=SPEC=... --setenv=PIDFILE=... bash <that file>`.
systemd is given no script text, so it has no `$` to rewrite; every `$` in the file is bash's. Why a file and not the
two smaller changes:
- `--expand-environment=no` works on this host (systemd 255, flag added in 246) but ties the script to a flag, and the
  next host with an older systemd refuses the unit.
- Doubling every `$$` is correct today and wrong the day someone adds a `${...}` or a whole-argument `$VAR`, both of
  which systemd rewrites by different rules (section 1). A file has one rule: nothing to escape.

The comment above the script said every `$` stays literal until the capture's bash evaluates it. That was the false
premise; it now says what systemd does, with the observed table, and why the launch passes no `$`.

**Identity.** `capture_running` used to accept a pid that answered `kill -0` and whose `/proc/<pid>/cmdline` contained
`logcat`. Any `adb logcat`, `tail logcat.txt` or `grep logcat` passes that, and so does a recycled pid. New helper
`cap_owns <label> <pid>`: `/proc/<pid>/environ` must contain the exact line `PIDFILE=<this label's pidfile>`, which
only a unit started by `capture_ensure` for this label carries (it is the `--setenv` value). `capture_running` and the
new `capture_stop` both use it, so `release` also refuses to kill a stale pidfile's pid that is something else. A
capture started by the previous `bash -c` launch carries the same `PIDFILE` and is still recognised.

**The script itself** (`capture_script`, a quoted heredoc so hold.sh's own shell expands nothing):
- `trap 'kill "$cur" 2>/dev/null; exit 0' TERM`, single-quoted, so `$cur` is read when TERM arrives (the second defect
  in section 1).
- The 2 s gap between restarts is `sleep 2 &` then `wait`, so a TERM during the gap is handled at once.
- `set -f`: `$SPEC` ends in `*:S` and is word-split unquoted into adb's arguments; without it a file called `x:S` in the
  unit's working directory would replace the pattern.

**Failure paths.** A unit systemd accepted but that never wrote its pidfile used to be left running, holding the unit
name and appending to a log nobody was told about. `capture_ensure` now calls `capture_stop` (TERM to the owned pid,
then `systemctl --user stop <unit>`) and removes the pidfile, the path record and the script before `take` exits 6.
`capture_release` uses the same `capture_stop` and removes the script. The confirm loop's bound (25 tries of 0.2 s,
as before) is now `HOLD_CAPTURE_CONFIRM_TRIES`, so the orphan leg does not wait five seconds.

## 3. The fragment (docs/testing/jobs/selftest.d/99-ownerplay-capture.sh), run three ways

**The fake `systemd-run` now does what systemd does.** It expands each argv word by the rules in section 1 (`$$` -> `$`,
`${NAME}` from the unit's environment, a whole `$NAME` word split or dropped, everything else left to bash), honours
`--expand-environment=`, gives the unit a clean environment plus the `--setenv` values, runs it detached in its own
session in a working directory that holds a decoy `*:S`-matching file, writes the expanded argv to `units/<unit>.argv`,
and refuses a unit name whose process is still alive, as systemd does. Its fake `systemctl stop` signals the unit's
process group. Leg (l) feeds a table of 23 argv words to the fake and, where a user manager answers, to the real
`/usr/bin/systemd-run`, and requires them to agree, so the fake is checked against systemd and not against section 1.
Leg (m) runs the file launch and the `bash -c` launch through real transient units (`RuntimeMaxSec=60`) and requires the
first to write a pid and the second to write a literal `$`.

Legs (a)-(g) are the earlier ones (take, who, second take refused, failed start leaves no hold, release, wait-idle) and
now assert the unit was exec'd as `bash <file>`, that the pidfile is digits, and that `*:S` reached adb as written and
was not globbed. New legs: (h) the capture's bash exits on TERM and so does its adb child; (i) the restart loop appends
(two start markers, the first still the first line) with a gap marker carrying adb's rc, in the same bash; (j) a decoy
that mentions `logcat` on its command line is not reported by `who` and is not killed by `release`; (k) a unit that
never confirms is stopped and its name is free for the next `take`.

**With the fix:** `SELFTEST_ONLY=99-ownerplay-capture bash docs/testing/jobs/selftest.sh`

    selftest: 99-ownerplay-capture.sh took 20s
    selftest: 76 passed, 0 failed, PARTIAL: 1 of 160 fragments (fake host removed, was /tmp/hakux-selftest.fkSIjn)

The mutant lines of that run, each of which builds a copy of hold.sh with one weaker rule and requires the matching
leg to go red (all `ok` means the leg did go red):

    ok   mutant built: hold.sh with the plain bash -c "$script" launch
    ok   mutant launch: take exits 6 and who has no capture (leg (a) is not vacuous)
    ok   mutant launch: the script bash was exec'd with has its pid line rewritten to echo "$" (the 10-22 symptom, as the unit received it)
    ok   mutant launch: take says the unit never confirmed running
    ok   mutant built: hold.sh with the double-quoted trap
    ok   mutant trap: the capture's bash still exits on TERM (so only the child distinguishes it)
    ok   mutant trap: the adb child survives TERM (leg (h) is not vacuous)
    ok   mutant built: hold.sh with the cmdline-mentions-logcat identity
    ok   mutant ident: who reports a capture for the decoy (leg (j) is not vacuous)
    ok   mutant ident: release kills the decoy
    ok   mutant built: hold.sh that leaves an unconfirmed unit running
    ok   mutant orphan: take still exits 6
    ok   mutant orphan: the unit's process is still running
    ok   mutant orphan: the next take is refused for the unit name (leg (k) is not vacuous)
    ok   mutant built: hold.sh without set -f
    ok   mutant glob: *:S is globbed against the working directory (leg (a) is not vacuous)

**With the mutant that reinstates `bash -c "$script"`** as the whole of hold.sh under test (the fragment's `OC_HOLD_SH`
points at a copy; it must have `HERE=` pinned and `device_build.py` beside it, because `take` runs
`python3 "$(dirname "$0")/device_build.py"`). The copy is the fixed hold.sh with only the launch line replaced by
`bash -c "$(cat "$cs")" "$cs"`:

    selftest: 99-ownerplay-capture.sh took 48s
    selftest: 38 passed, 38 failed, PARTIAL: 1 of 160 fragments (fake host in /tmp/hakux-selftest.VjcNDd)

The failures start at the first assertion that needs a capture: `(a) take for an owner-play tag exits 0 and names the
capture on stdout`, `(a) the pidfile holds the capture's pid (digits, not a literal $)`, `(a) who also reports the
capture while it is held`, then (b), (d)-(g) (their setup `take` exits 6), `(h) the capture's bash exits on TERM`, all
of (i), and (j) (`the decoy would pass the old check`, a setup check, goes red because that leg's own `take` exits 6),
then (k) `the next take gets the unit name and a capture`. The 38 that pass either hold trivially when no capture ever
starts (leg (c): a failed start leaves nothing behind; the `gone` checks of (e); `who` reports nothing in (j); `take`
exits 6 and the unit is stopped in (k)) or do not go through hold.sh's launch line: the fake-versus-real table of (l),
the real units of (m), and the mutant checks whose edit is elsewhere in the file.

**With master's hold.sh (b944110629, `HERE=` pinned) and the honest fake:**

    selftest: 99-ownerplay-capture.sh took 49s
    selftest: 33 passed, 43 failed, PARTIAL: 1 of 160 fragments (fake host in /tmp/hakux-selftest.E2obug)

It fails (a) pidfile/who/live/exec shape, (b), (d), (e), (f), (g), (h) both legs (TERM to the bash leaves the adb
child), (i) the same-bash check, (j) release, (k) both legs, and the (m) real-systemd file leg. The "mutant built" lines also fail there, since
the mutants edit lines that only the fixed file has; that is expected and not a finding.

Before this change the same fragment against master's hold.sh with its own old fake read 29 passed, 0 failed, and left
four orphaned `sleep 100000` per run.

Leaks after all three runs: no process of mine is left (checked by cwd under `/tmp/hakux-selftest.*` and under this
worktree); the three kept failing-run fixture dirs were moved out of `/tmp`.

## 4. Every other `systemd-run` call in docs/testing and host-tools

`grep -rn systemd-run docs/testing host-tools` at b944110629 plus this change. host-tools has no call. In docs/testing:

| Call | Launch shape | `$` systemd could rewrite | Verdict |
|---|---|---|---|
| `jobs/hold.sh:313` | `bash <file>` (this lane) | none: no script text | fixed here |
| `lane.sh:358` (start) | `bash -c "claude -p \"\$(cat '...')...\"; rc=\$?; ...; exit \$?"` | after the caller's own expansion the script carries `$(cat`, `$?`, `$rc`: all inside longer words, no `$$`, no `${`. `$LANE_SESSION_FOOTER` has no `$` | no defect |
| `lane.sh:391` (resume) | same shape, plus a literal `\n\n` inside the prompt | same | no defect |
| `jobs/cloud.sh:792` | `--property=ExecStopPost="/bin/bash $SJOBS/cloud.sh finish $kind $num"` and `bash -c "claude -p \"\$(cat '...')\" ...; rc=\$?; ...; exit \$rc"` | `$(cat`, `$rc`, `$?` only; the ExecStopPost value is expanded by the caller and carries no `$` | no defect |
| `jobs/handback.sh:609` | `bash "$PARK_WAITER" "$name" "$name" "$hours"` | none: a file, three plain arguments | no defect |

Every other `systemd-run` hit in the tree is a comment, a log line, or the selftest's inert shim
(`selftest.sh:225`, which only logs its argv).

The lane.sh shape is not argued from the rules alone. A script with the same forms (`"$(cat 'F')` over two lines,
`rc=$?`, `printf '<%s>' $rc`, `exit $rc`) run as `bash -c "$S"` and as
`systemd-run --user --wait --collect --pipe -q bash -c "$S"` printed identical output and the same exit code (1) on
this host.

Latent, not a defect today: lane.sh and cloud.sh pass the whole script as one `bash -c` word. A future edit that adds
`$$` or `${...}` to either script string would be rewritten by systemd exactly as hold.sh's was, and no selftest would
notice, because the shim logs its argv and runs nothing. The same file launch would remove the hazard; it is left for a
lane that touches those scripts, since changing them is outside this brief and a launch change there cannot be
exercised without starting a real lane.

## 5. Not done

- No real hold was taken and no device touched: the real-systemd legs (l), (m) start only transient units with their own
  names (`hakux-selftest-ownerplay-*`), a fake `adb` and `RuntimeMaxSec=60`.
- Nothing pushed, folded or requested on the board.
