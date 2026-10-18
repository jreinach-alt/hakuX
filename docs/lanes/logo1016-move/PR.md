# logo1016-move: the README logo moves to docs/images (#433)

State: ready

Lane: logo1016-move          Issue: #433
Base: master @ 61ae61dd91
Files: .github/hakux-logo.svg (moved), docs/images/hakux-logo.svg, README.md, docs/lanes/logo1016-move/PR.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

The README logo sat at `.github/hakux-logo.svg`. The fold classifier treats
`.github/` as harness, which costs the full selftest, so an exemption for
image files directly under `.github/` was added to let the logo fold as a
doc. The logo is a doc image, so it moves to `docs/images/`, the same file
byte for byte, and the README's `src` follows. After this folds the
`.github/` image exemption has nothing left to cover and can be dropped
from `offline_fold.py`.

The landing page (the `home` branch) carries whatever file the README's
`src` names, at the same path, so it follows the move with no change to
the page builder.

README also links `docs/xbox-files.md` under "What you need", the list of
files setup asks for.

Fold: the changed paths are a root doc, a `docs/` image and the move's
removal of `.github/hakux-logo.svg`. That removal is covered by the
exemption still in place, so the fold runs no selftest and no device run.
It must fold before the exemption is dropped.

Release note (other): none -- docs only, no emulator/app code touched.
