# holdpid1022: hold.sh's owner-play capture never confirms itself, because systemd expands `$` in the script before bash sees it

State: draft

Lane: holdpid1022            Issue: none (harness defect, dispatched directly)
Base: master @ b944110629
Files: docs/lanes/holdpid1022/PR.md, docs/testing/jobs/hold.sh, docs/testing/jobs/selftest.d/99-ownerplay-capture.sh
Prediction: (filled in after the observation below)
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
| 10-10 | 69aa814fe1, fold 07937793af (lanepath1009) | lane.sh gives each lane unit a shim-first PATH with `--setenv` | Unrelated to `$`; touches the same `systemd-run` shape in lane.sh | lane.sh has the same shape and a script with `\$rc`; checked below under "other calls" |
| 09-19..09-26 | cloud.sh, handback.sh commits (cloudtail, handbackwaiter) | `systemd-run` with `bash -c` and `bash <file>` | Not about `$` expansion | `cloud.sh:799` and `lane.sh:365,398` carry `\$(...)`, `\$?` and `\$rc` inside the script: checked below |

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
