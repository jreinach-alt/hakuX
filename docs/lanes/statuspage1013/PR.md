# status page: track 0.6, 1.0 projection chart, drop Benchmarked and C I S B

State: ready

Lane: statuspage1013            Issue: #433
Base: master @ f327d67b8f72a011f5ff53fc8fe4b1281bda38b1
Files: docs/testing/jobs/status_html.py, docs/testing/jobs/status.sh, docs/testing/release-0.5.toml, docs/testing/release-0.6.toml, docs/testing/jobs/selftest.d/60-status.sh, docs/testing/jobs/selftest.d/64-status-html.sh, docs/testing/jobs/selftest.d/65-status-objective.sh, docs/testing/jobs/selftest.d/66-status-titles.sh, docs/testing/jobs/selftest.d/67-status-measured.sh, docs/testing/jobs/selftest.d/68-status-curve.sh, docs/lanes/statuspage1013/**
Prediction: none: no arm (status page/harness tooling, not emulator or device code)
Needs device: no    Needs NDK: no

Release note (none): the status page is published from the host, not shipped in the APK.

Tracks 0.6 instead of 0.5 on the public status page: a 0.6 target and a
curve toward 1.0 (`docs/testing/release-0.6.toml`), a "How close is
0.6?" chart with the Benchmarked series dropped and a labelled 0.5-
publish line, and a new "How close is 1.0?" chart that projects each
series to 1.0 at its rolling 7-day rate with a projected-dates table.
The title table's C I S B column and legend are gone; next-step text
reads "reach gameplay" / "soak for Playable" / "below the bar"; the
fps cell reads "max perf"/"default perf"/nothing with a key above the
table. Also fixes a real bug found by rendering a fixture end to end:
`status.sh`'s `release_name`/`release_tag` defaults were hardcoded to
"0.5"/"v0.5", which would have kept the live page reading "How close
is 0.5?" even with release-0.6.toml installed -- they now come from
the active release conf.

Host-only `status_md.py`/`status_page.py`/`status_svg.py` (not in this
repo) have edited copies under `docs/lanes/statuspage1013/host-tools/`
for lane.local to review and install; `status_svg.py` is unchanged.
Tested against a real two-chart fixture render and a one-chart
(no-curve) fixture render -- see NOTES.md.

5 required mutants each confirmed to fail a test (NOTES.md). Selftests
green on every fragment this diff can reach (NOTES.md lists the full
set and the targeted-run rationale); the 11 remaining failures in a
wider run are pre-existing chain-selection artifacts unrelated to this
diff, also explained there. Branch is already at `origin/master`
(0 behind); no merge was needed.

See docs/lanes/statuspage1013/NOTES.md for the full account.
