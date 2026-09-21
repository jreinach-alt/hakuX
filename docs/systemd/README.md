# The nightly timer

**The unit files live in `docs/testing/systemd/`, and
`docs/testing/jobs/install-host.sh` installs them.** This directory used to
hold a second copy of `hakux-nightly.service` and `.timer`, and they were
deleted rather than fixed:

- Both copies installed to the same `~/.config/systemd/user/`, so whichever
  was copied last won, and they had already drifted (`AccuracySec=1min` vs
  `30s`, no `Unit=` at all in this one).
- The copy here still carried `WorkingDirectory=/home/justin/hakuX` and
  `ExecStart=.../nightly_build.sh`, which is precisely the defect that made
  `nightly-2026-09-20` and `nightly-2026-09-21` both ship a 09-19 sha. So the
  install command in this file was a documented way to reinstate a bug after
  it had been fixed.

`selftest.d/87-nightly-trunk.sh` now asserts that no installable unit in the
repository ExecStarts `nightly_build.sh` directly, so a third copy cannot
quietly appear.

The prose below is the part of this file that was worth keeping.

    bash docs/testing/jobs/install-host.sh     # installs and enables every unit
    loginctl enable-linger "$USER"             # or the timer stops with your last shell

`systemctl --user list-timers hakux-nightly.timer` shows the next firing.

## Two things that will stop it, and what is done about them

**The user instance exits with your last session.** `loginctl enable-linger`
keeps it alive; without it the timer simply is not running at 00:30. It is
enabled on this machine.

**WSL is not always up at 00:30.** Nothing inside Linux can fix that, so the
timer sets `Persistent=true`: a window missed because the VM was down runs at
the next start instead of being skipped, so a day still gets a build even if it
is late.

## What it deliberately does not do

**It does not run tests.** A nightly that grabbed the Nova at half past
midnight would collide with an overnight sweep, and device work belongs in the
dispatcher's queue. Build and publish only.

**It does not hide provenance.** If HEAD is not on the remote, the release says
"built from **unpushed** `<sha>`" — a release nobody else can rebuild should
say so. If tracked files are modified, it says the binary is not exactly that
commit.

**It does not fail quietly.** Build failure, missing APK and publish failure
each exit with a distinct code and a line in
`~/hakux-work/nightly/<date>.log`. A silent failure reads as a day with no
work, which is worse than no nightly.
