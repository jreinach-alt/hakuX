# The nightly timer

Installed as a **systemd user timer**, not as a cron job in an agent session:
an in-session scheduler dies with the session and expires after seven days,
which is not a nightly.

    cp docs/systemd/hakux-nightly.* ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now hakux-nightly.timer
    loginctl enable-linger "$USER"      # or the timer stops with your last shell

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
