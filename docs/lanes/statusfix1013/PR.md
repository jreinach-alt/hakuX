# status: Playable is the ledger; chart 1 marks when 0.5's targets were met

State: ready

Lane: statusfix1013            Issue: #433
Base: master @ 2c06371519db3f7a6a13b2dbc386956b127fcf67
Files: docs/testing/jobs/status_html.py, docs/testing/release-0.6.toml, docs/testing/jobs/selftest.d/66-status-titles.sh, docs/testing/jobs/selftest.d/68-status-curve.sh, docs/lanes/titles05/fixture/synth.py, docs/lanes/statusfix1013/**
Prediction: none: no arm (status page, not emulator or device code)
Needs device: no    Needs NDK: no

Release note (none): the status page is published from the host, not shipped in the APK.

The status page counted 68 Playable titles; the accepted list has 67.

- A title whose soak passed but whose frames were never reviewed read
  Playable (Buffy). Playable now comes from the accepted list only; a
  passing soak reads "review frames for Playable".
- KOF: Maximum Impact - Maniax was two rows, one per spelling of its
  name. A push now takes the registry's name for its title ID.

Chart 1 ("How close is 0.6?") never drew its "0.5 published" line: the
release config's publish date was dropped on its way to the page. It now
arrives as an epoch. Chart 1 also marks when both 0.5 targets were met
(145 Measured on Oct 7, 50 Playable on Oct 12), read from
`prior_measured_target` and `prior_playable_target` in release-0.6.toml.
Its rotated labels now read down from the top of the chart; they had run
up and off it.

Tests: fragment 66 accepts the new next-step phrase; the titles05 fixture
gains an accepted list and a passing title with no review ("Zz Unreviewed",
expected "soak pending"). Fragment 68 checks that the publish date survives
lanes.json and that chart 1 draws both markers with their labels inside.
Selftests 66 and 68 pass. A render against live data reads Measured
203 / 300 and Playable 67 / 110, with KOF as one row.
