# logo1016-count: the Playable count as a running total, apart from the download

State: ready

Lane: logo1016          Issue: #433
Base: master @ 3a44935839
Files: README.md, docs/lanes/logo1016/PR.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Owner 10-16: release notes keep the count as of the release (52, already in
docs/releases/v0.5.0.md, the release index and CHANGELOG.md); the READMEs
show the current count, from one source. The landing page put the live
count (87) beside "Download 0.5.0" and in the release Highlights, which
reads as "0.5.0 plays 87 games". 35 of the 87 were accepted after the
release, on a mix of builds, so the page should not promise that.

README.md: the count leaves the download line and the Highlights bullet
and becomes its own line, "Games rated Playable so far", linking to
STATUS.md on the home branch (the one source; master carries no number).
The Highlights bullet becomes "Rated by play", the rule a Playable rating
means, with the same named titles.

`host-tools/home_page.py` (live on the host) turns that line into
"**N games rated Playable so far.** [The list, with progress charts.]
(STATUS.md)" on the landing page, and keeps the old edits for master as it
is now, so landing builds before and after this fold. Checked on a scratch
clone against both. The old edits come out after the fold.

Fold: README.md and docs/lanes/ only, so no selftest and no device run.

This branch reuses [lane.logo1016]'s claim on README.md (its first PR,
the logo, folded as 2c4e054562) and replaces that PR's PR.md.

Release note (other): none -- docs only, no emulator/app code touched.
