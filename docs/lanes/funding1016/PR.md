# GitHub Sponsors on the landing page and the Sponsor button (#433)

State: ready

Lane: funding1016            Issue: #433
Base: master @ 4bf47129b1
Files: README.md, .github/FUNDING.yml, docs/lanes/funding1016/PR.md
Prediction: none: docs only, no device or pixel claim
Needs device: no    Needs NDK: no

Release note (none): none

## What this is

The owner's GitHub Sponsors profile is up (10-16). `.github/FUNDING.yml` still
carried the inherited `patreon: mborgerson`, so the repository's Sponsor button
sent visitors to the xemu author's Patreon.

- `.github/FUNDING.yml`: `github: jreinach-alt`.
- `README.md`: a Sponsor link in the top row and a short "Support the project"
  section before Credits. The xemu Patreon link stays in Credits, where it
  credits the emulator underneath, and the new section points to it.

`home` is built from these two files by `home_page.py` (FUNDING.yml is copied
as is, the README links are rewritten), so the landing page picks the change up
on the next status render.

Not changed: the README still says "Android 10 or newer" and "72 Playable"
(master's figure; `home` replaces the count). The minimum moves to Android 13
with sign1016, and that line belongs with the 0.5.1 release docs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
