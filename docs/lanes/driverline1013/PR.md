# driverline1013: the compatibility page and README name the GPU driver the ratings were measured on (#433, 0.5)

State: ready

Lane: driverline1013          Issue: #433
Base: master @ 3c2338eb2b
Files: docs/COMPATIBILITY.md, docs/compatibility.csv, docs/testing/compat_page.py, docs/testing/compat_page_selftest.py, README.md, docs/lanes/driverline1013/**
Prediction: none (docs only)
Needs device: no    Needs NDK: no

## What this is

The owner, 2026-10-13: "Yes name the driver we tested on. That's important."

Every rating on the compatibility page was measured with a custom Turnip
driver, not the handhelds' own Qualcomm driver. Neither page said so. A player
on the stock driver would compare their results against numbers taken on a
different driver.

- `docs/testing/compat_page.py`: a "What it was tested on" section at the end
  of the definitions. It names the SoC and GPU (Snapdragon 8 Gen 2, Adreno
  740), Android 13, and the driver, **Turnip Adreno Driver T30
  (@Mr_Purple_666)**, Mesa 26.3.0-devel, build git-62ac221a33. It says where a
  player installs a driver (Settings → Graphics → GPU Driver) and that other
  drivers may give different results.
- `docs/COMPATIBILITY.md`: regenerated. The only change is that section.
- `README.md`: the "Will it run on my device?" bullet names the same GPU,
  Android version and driver. Its Last updated line moves to 2026-10-13.

## Where the driver name comes from

- The Nova's own startup log, 2026-10-13 08:58 PDT, at a title launch: `GPU: PurpleVK-public Adreno (TM) 740 (git-62ac221a33) |
  Driver: PurpleVK public driver (PurpleVK 26.3.0-devel (git-62ac221a33)) |
  API: 1.4.359`. `ro.product.model` is `Retroid Pocket Nova` and
  `ro.build.version.release` is `13`.
- The driver package's display name, "Turnip Adreno Driver T30
  (@Mr_Purple_666)", is from its `meta.json`, quoted in
  `docs/investigations/adreno-driver-landscape.md`.
- The Thor: the same GPU and driver string appear in its logcats
  (`docs/lanes/flip474/sysmem.md`, the table row "Same GPU and driver as the
  Thor?"), and T30 is its resting state in `docs/testing/drivers/swap_driver.sh`.
  T30 was installed on both handhelds by 2026-09-20 (drvab77); the earliest
  Playable rating is dated 2026-09-26.

## How the page was regenerated

The data is unchanged on purpose. The page was rebuilt from the inputs it was
last built from: the registry snapshot `docs/lanes/compatpage1012/registry.tsv`
and the first 52 rows of the playable ledger. With those inputs and master's
generator, `docs/compatibility.csv` is byte-identical, and the only diff in
`docs/COMPATIBILITY.md` is the new section.

The ledger now has 56 Playable rows. Adding the four newer titles to the page
needs a `compat_notes.tsv` row for each and a fresh registry build, which is a
separate change.

`docs/testing/compat_page_selftest.py`: 19 tests, OK.

Release note (docs): The compatibility page and the README now name the handhelds' GPU and the GPU driver every rating was measured with.
