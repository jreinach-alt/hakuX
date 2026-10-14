# title_locations_report.py -- hourly-report section (#433, Part 3)

This directory is a lane-owned copy. It does NOT write to the real
`/home/justin/hakux-work/host-tools/` (the brief says not to), and nothing
here is wired into the live `hourly_report.sh` yet -- that is a one-line
splice for whoever folds this lane (lane.local, or the `host-tools`
maintainer) to make once `docs/testing/title_locations.py` has folded to
`$R` (`/home/justin/hakuX`, the checkout `hourly_report.sh` itself reads).

## What it is

`title_locations_report.py` is read-only: it reads whatever
`pm/title-locations.tsv` the last `title_locations.py build` wrote and
prints a summary (table age, rows + UNRESOLVED count per location, and a
`dcandidates`-style count). It never runs a scan itself -- a `build` can
run a multi-minute 7z xbe-cert pass per `d-archive` title, which is a
background job (see NOTES.md), not something an hourly timer should ever
trigger.

If `docs/testing/title_locations.py` has not folded to `$R` yet, it prints
one line saying so and exits 0 -- safe to install before the fold lands.

## How to install

In `/home/justin/hakux-work/host-tools/hourly_report.sh`, add one section
in the same style as the existing `echo "--- <section>"` blocks (for
example right after the `"--- PLAYABLE"` section, around line 33):

```bash
  echo "--- title locations (pm/title-locations.tsv, #433)"
  timeout 60 python3 $H/host-tools/title_locations_report.py --root "$H" --repo "$R" 2>&1
```

Then copy `title_locations_report.py` from this directory into the real
`$H/host-tools/` (i.e. `/home/justin/hakux-work/host-tools/`) alongside
`harness_health.py` and friends -- this lane does not write there itself.

No other change is needed: the script takes `--root`/`--repo` exactly the
way `hourly_report.sh` already names `$H`/`$R`, and fails soft (prints a
one-line reason, exits 0) if the table or the module isn't there yet.
