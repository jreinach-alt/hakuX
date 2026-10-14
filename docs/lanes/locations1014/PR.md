# A tracked listing of which title is where, keyed by title_id

State: draft

Lane: locations1014            Issue: #433
Base: master @ 76bef8b162
Files: docs/testing/title_locations.py, docs/testing/selftest_title_locations.py, docs/lanes/locations1014/NOTES.md, docs/lanes/locations1014/PR.md
Prediction: none: analysis-only, no device/pixel claim
Needs device: no    Needs NDK: no

Release note (performance|stability|rendering|other|none): none

## What this is

`docs/testing/title_locations.py`: a new, generated `pm/title-locations.tsv`
(one row per copy of a title: title_id, location, path, bytes, sha256,
id_source, seen_utc, mtime, stale), keyed by title_id only -- never a name.
`build`/`check`/`show`/`copies`/`dcandidates` CLI, plus a library surface
(`read_table`, `copies()`, `copy_exists_elsewhere()`) for other tools to call.

id_source records how each row's id was actually read, in trust order:
`xbe-cert` (the default.xbe certificate, read directly -- for a `.7z` this
streams the archive's `.iso` member through `7z.exe x -so` into a
forward-only reader that never writes a decompressed disc image to the
Linux disk, and gives up past a byte cap rather than draining a whole
multi-GB image), `name-prefix` (this project's own `<TID>-name` filename
convention), `manifest` (a pre-verified catalog row this lane didn't itself
re-read: `xiso/manifest.csv`, `titles/console-inventory-*.csv`), `push-log`
(the Thor's last push listing, offline, nothing to re-read live).

Work in progress: still writing up Part 1's live-data report and Part 3
(dcandidates demonstration run + host-tools copy). Part 2 (table format,
`check`, `copies`, the deletion gate, selftest with the brief's falsifier
pairs and a mutant) is done and green -- see NOTES.md.
