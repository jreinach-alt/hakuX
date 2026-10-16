# status_html: titles05 crashed on a registry name the catalog spells differently

State: ready

Lane: statusfix1016            Issue: #433
Base: master @ 15a72e10dc
Files: docs/testing/jobs/status_html.py, docs/lanes/statusfix1016/PR.md
Prediction: none: host tooling, no device/pixel claim
Needs device: no    Needs NDK: no

Release note (performance|stability|rendering|other|none): none

## What this is

The status render's lane block has exited 1 on every run since 10-14 23:42 PDT
(KeyError: 'Crimson Skies: High Road to Revenge', status_html.py titles05). The
degraded-render guard refused every publish, so the `home` branch (GitHub's
landing page) and its STATUS.md stayed on the 10-14 22:39 render: 77 Playable
while the ledger says 87.

titles05 adds each registry title through `add()`, which resolves the name
through the shared catalog (the catalog's spelling wins since titledb1014),
and then read `where[t["name"]]` with the registry's own spelling. For this
title the two differ. The lookup now goes through the same `canon()`.

## Proof

`status_html.py lanes` against the live registry, before: exit 1, KeyError.
After: exit 0, lanes.json written (801 KB).
