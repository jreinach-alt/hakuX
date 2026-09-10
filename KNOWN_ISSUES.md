# Known Issues

**Defect tracking has moved to [GitHub issues](https://github.com/jreinach-alt/hakuX/issues).**

This file previously served as the tracker. It is kept for the handful of items
that are user-facing behaviour rather than defects to be fixed — things worth
knowing before you file a bug.

Everything else that lived here is now an issue, classified by whether it is
inherited from upstream or introduced by this fork. See
[#18](https://github.com/jreinach-alt/hakuX/issues/18) for the re-confirmation
pass over the older entries.

---

## Setup Wizard appears to freeze while copying the HDD image

**Fixed.** The wizard shows a progress dialog for the duration of the copy now —
determinate when the provider reports a size, indeterminate when it does not —
and says so rather than silently dropping a second selection while a copy runs.

Kept here because the symptom is memorable and the old builds are still out
there: on those, importing a retail image off an exFAT card left the screen
apparently frozen with Next dead, for minutes, and re-selecting the file did
nothing. It was progressing. If you see it, update.

---

## Networking must be enabled for anything that uses the guest network

**Symptom:** A guest program that expects a network hangs indefinitely rather
than failing — the pgraph suite's FTP upload sits at "Initializing network..."
forever.

**Cause:** The emulator's networking switch is off by default. The guest waits
on DHCP that will never complete.

**What to do:** Settings → Online / Insignia → enable online networking. Note the
pgraph harness no longer needs this; results are read out of `hdd.img` directly
by `docs/testing/extract_results.py`.

---

## Two builds can install side by side and are easy to confuse

**Symptom:** Settings changed in one build appear to have no effect.

**Cause:** Debug and release builds now use distinct application IDs and labels
(`hakuX (debug)` vs `hakuX (fork)`). Older builds shared a label, so two installs
were indistinguishable in the launcher.

**What to do:** Check which one you opened. Their save data, HDD images and
settings are entirely separate.
