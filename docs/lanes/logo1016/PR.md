# logo1016-banner: the new hakuX CE banner at the top of the README

State: ready

Lane: logo1016          Issue: #433
Base: master @ 37ba9bd8bf
Files: .github/hakux-logo.svg, docs/lanes/logo1016/PR.md
Prediction: none: docs only
Needs device: no    Needs NDK: no

Owner 10-16: new iconography for the portal, to make hakuX CE look distinct
from Microsoft's Xbox identity. The owner supplied the file
(`hakux-work/svg/hakux-new-icon.svg`): a 400x140 banner with the hakuX
wordmark, "COMMUNITY EDITION", "ORIGINAL XBOX • ANDROID", and a green
lowercase h inside two rings.

`.github/hakux-logo.svg` is replaced by that file, byte for byte. It has the
same 400x140 box as the logo it replaces, so the README `<img>` (width 640)
and its alt text need no change, and `host-tools/home_page.py` already carries
that path to the landing page.

Fold: one SVG under .github/ (not a workflow) plus docs/lanes/, so no
selftest and no device run. The classifier's harness pattern would match
.github/, so this fold depends on the existing exemption for .github/*.svg
(added 10-16); with that removed it would start a full selftest.

This branch reuses [lane.logo1016]'s claim on .github/hakux-logo.svg and
replaces the PR.md of the logo1016-count PR.

The app's launcher icon (the owner's other two files) is a separate lane,
lane.icon1016.

Release note (other): none -- docs only, no emulator/app code touched.
