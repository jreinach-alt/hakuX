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

**Symptom:** The wizard appears to hang when importing a hard disk image.

**Cause:** Copying an 8 GB image through the Storage Access Framework is slow and
the copy is not incrementally reported.

**What to do:** Wait. It is progressing.

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
