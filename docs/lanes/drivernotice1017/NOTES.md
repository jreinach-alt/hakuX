# drivernotice1017 -- every release note names the one tested GPU driver (#433)

Owner, 2026-10-17: "We need to broadcast that this is the only tested driver and link to
it in every release note we do." The Turnip Adreno Driver T30 (@Mr_Purple_666) is the only
driver hakuX is tested with. The phone's own Qualcomm driver draws some games wrongly (the
THPS4 / Max Payne 2 bind pose, #1043, appears only on it).

## What changed

- New public page `docs/gpu-driver.md` (listed in `docs/testing/public_docs.txt`, dated
  2026-10-17 for 0.5.2): the T30-only statement, that other drivers are untested, that a
  new install has no driver until one is installed, the Settings > Graphics > GPU Driver
  steps, and the two log lines that show it loaded. No download URL (see TODO).
- A short blockquote notice with the link in every release note
  (`docs/releases/v0.4.0-j1.md` .. `v0.5.2.md`), each `CHANGELOG.md` entry's header block,
  `docs/releases/README.md`, `README.md` and `docs/COMPATIBILITY.md`. The notice is
  present-tense, so it is true of the older notes too. Release notes, CHANGELOG and the
  nightly body use the absolute `blob/home` URL because they are read on GitHub release
  pages; docs inside the tree use relative links.
- Future releases:
  - `docs/testing/release_build.sh` refuses (exit 10) a plain X.Y.Z build whose
    `docs/releases/vX.Y.Z.md` is missing or does not contain `docs/gpu-driver.md`. -rc and
    other suffixed builds have no note of their own and are not held to it.
    `release_build_selftest.sh` gains three cases (no note, note without the link, -rc
    needs none).
  - `docs/testing/docs_freshness.py` reports `NO-DRIVER-LINK` for any
    `docs/releases/v*.md` without the link and exits 1. `docs_freshness_selftest.py` gains
    two cases.
  - `android/RELEASING.md` "Before tagging" gains step 3.
  - `docs/testing/nightly_build.sh` writes the same one-line notice into the GitHub nightly
    body; `jobs/selftest.d/86-nightly-notes.sh` asserts the body links
    `docs/gpu-driver.md`.

## Checks

- `bash docs/testing/release_build_selftest.sh`: all green. Run with `SCRIPT=` pointed at
  the master copy of `release_build.sh`, the six new note cases FAIL, so they do test the
  new refusal.
- `python3 docs/testing/docs_freshness_selftest.py`: all cases pass.
- `python3 docs/testing/docs_freshness.py --release 0.5.2`: `public docs: 12 OK, 0 not`;
  `release notes: 5 link docs/gpu-driver.md, 0 do not`.
- `SELFTEST_ONLY="86-nightly-notes 87-nightly-trunk" bash docs/testing/jobs/selftest.sh`:
  139 passed, 0 failed. `86-release-build`, `88-nightly-sign` and `99-release-note-line`
  also pass. These are the fragments that read `release_build.sh`, `nightly_build.sh` or
  the release notes. (87 alone fails six checks because it uses a helper defined in 86;
  run with 86 they pass.) `55-localtime` fails "arms.sh wrote no tick log" in a partial
  run; it reads none of the files changed here and was not checked against master.
  The full run was stopped after 20 minutes, so the other fragments were not run.

## TODO (owner)

The page says where to install the driver from (Settings > Graphics > GPU Driver) but
gives no download link: the repo holds none for T30. The source files are only at
`~/hakux-work/turnip_t30/` on the host (sha256
`1d80dfa019659b008e4669311db5b1e4a02af59ff1d5458a98e2f5fe18ed013b`). Once the owner says
where the T30 zip is published, add one line with the URL to the "Installing it" section
of `docs/gpu-driver.md`.
