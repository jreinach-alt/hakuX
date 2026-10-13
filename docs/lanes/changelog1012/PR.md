# changelog1012: changelog to 0.5.0, version numbers for official-build users, credits (#433, 0.5)

State: ready

Lane: changelog1012          Issue: none (#433 umbrella)
Base: lane/pubdocs1012 @ 13756ce96a
Files: CHANGELOG.md, README.md, android/MIGRATING.md, docs/lanes/changelog1012/PR.md
Prediction: none (docs only)
Needs device: no    Needs NDK: no

CHANGELOG.md was last updated for v0.3.3-j1. Added short, summarized entries
for v0.4.0-j1, v0.4.1-j1 and v0.5.0, each linking to its release notes, dated
from the release tags (v0.5.0 dated 2026-10-12 per the brief). v0.5.0's entry
carries the new device floor: Android 10 and an ARMv8.2 CPU with LSE atomics.

README.md: added a "Version numbers" paragraph to Installing, so someone
coming from the official hakuX knows this fork's numbers (v0.3.3-j1, v0.4.0-j1,
v0.4.1-j1, now 0.5.0) are its own, not the official line's (currently 0.3.1),
and that a later official release could reuse a number. Added a Credits
section beside Lineage, crediting xemu (Matt Borgerson and contributors, with
a Patreon link), X1 BOX (izzy2lost), hakuX (rfandango), ItsRetroPup (this
fork's immediate upstream, whose stale-launch fix is in this tree), and
nxdk_pgraph_tests (abaire, whose real-hardware captures the rendering work is
measured against). Added ItsRetroPup/hakuX to the Lineage line between
rfandango/hakuX and this fork.

android/MIGRATING.md: added a short section on the device floor — an official
build still runs on Android 8 and older ARMv8.0 parts (Snapdragon 835, 660,
665, 460) where this fork now shows "Unsupported CPU" and exits, so such a
device should keep the official build.

No new figures: every number carried into CHANGELOG.md came from
docs/releases/v0.4.0-j1.md, docs/releases/v0.4.1-j1.md or the v0.5.0 draft
notes at /home/justin/hakux-work/wt/release05/docs/releases/v0.5.0.md (read
only, not edited). The 0.3.1 official-release figure and the ARMv8.0 device
list came from the brief and already appear in README's existing Installing
text.

Release note (none): docs only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
