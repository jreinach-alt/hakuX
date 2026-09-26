# The nightly's systemd units, in the repo

    systemctl --user daemon-reload
    systemctl --user enable --now hakux-nightly.timer
    systemctl --user list-timers hakux-nightly.timer

Install by copying both files to `~/.config/systemd/user/`.

## Why these live here and not only in ~/.config

Because on 2026-09-13 the orchestrator **overwrote both of them without
reading them first**, having concluded from an empty `CronList` that nothing
was scheduled. `CronList` only sees jobs created by that tool in that session;
the nightly had been on a systemd timer since 2026-09-12 and had run
successfully at 00:30 that same morning. Two errors compounded: a negative
read from the wrong instrument, and then a blind overwrite of the thing it was
wrong about.

The units were unversioned, so the originals are unrecoverable. That is the
whole argument for this directory: a scheduled job that runs the repo's own
script is part of the repo, and it should be reviewable, diffable and
restorable like anything else. `~/.config` is where it gets *installed*, not
where it should only exist.

## Why a timer and not a cron line

This host is WSL2 and is shut down whenever its owner closes it. A cron entry
at 00:30 silently misses every night the box was not running, and a missing
nightly is indistinguishable from a day with no work. `Persistent=true`
records the last elapse and fires once on the next boot if 00:30 was missed;
cron cannot do that.

`Linger=yes` is set for the user, which is what lets a user timer run without
an active login. `gh` and `git` both resolve credentials from `$HOME` in a
minimal environment, which a user unit provides -- checked, not assumed.

## What the timer does NOT do

It does not run tests and never touches a device: a nightly that grabbed a
handheld at half past midnight would collide with an overnight sweep, and
running belongs to the dispatcher. It publishes a PRERELEASE, so the tagged
release stays Latest. It never triggers CI.
