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
