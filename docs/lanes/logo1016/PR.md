# logo1016: hakuX CE logo at the top of the README

State: ready

Lane: logo1016          Issue: #433
Base: master @ 3ceee93982
Files: README.md, .github/hakux-logo.svg, docs/lanes/logo1016/PR.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

The owner-approved Community Edition logo goes at the top of README.md,
centred, 640 px wide: `.github/hakux-logo.svg`, a 400x140 SVG on its own
dark card so it reads on GitHub's light and dark themes. The owner checked
it on the preview branch `preview/logo1016` on desktop and mobile, light
and dark (10-16: "Yes, the CE is what I want. It renders fine.").

README.md also drops its fixed Playable count (72, written at 0.5.0) from
the link row and the Highlights bullet. The landing page (`home`) already
replaces that number with the live count from STATUS.md (87 today), so the
two READMEs showed different numbers; with no number on master they no
longer disagree.

`host-tools/home_page.py` (already live on the host) keeps a relative
`src="..."` relative and copies that file into home at the same path, since
GitHub renders no image from a /blob/ URL, and its two count patterns
accept the README lines with or without a number. Checked against this
branch on a scratch clone: home builds, the logo's src stays relative, the
SVG is in home's tree, and every README rewrite matches exactly once.

Release note (other): none -- docs only, no emulator/app code touched.
