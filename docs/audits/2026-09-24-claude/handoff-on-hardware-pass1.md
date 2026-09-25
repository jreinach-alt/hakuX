# Audit pass 1 -- PR #216 `claude/handoff-on-hardware`

Head audited: `33f7b8273a`. Diff: `docs/testing/handoff-on-hardware.md` (+186),
`docs/testing/patches/pgraph-per-test-instrument.patch` (+242).

Verdict: **2 MEDIUM, 3 LOW -> needs-remediation.**

## What was checked and holds

- The overlay correction (§5) is right. `hw/xbox/nv2a/pgraph/gl/display.c:216-227`
  composites `pvideo_tex` in the display shader, gated at `:328` on
  `NV_PVIDEO_BUFFER_0_USE` (and `SIZE_IN != 0xFFFFFFFF`, which the doc omits,
  harmlessly); `pgraph/vk/display.c` carries `pvideo_enable` too. The only
  `enable_overlay` / `overlay_draw_line` hits are the commented lines at
  `pvideo.c:61,70` and `nv2a.c:1302`. `docs/investigations/2026-09-18-pvideo-overlay-limits.md:29`
  reached the same conclusion earlier.
- The patch applies cleanly: `git -C ~/nxdk_pgraph_tests apply --check` on
  `6743b6a` ("Adds more fog tests") passes all four files.
- §3 traps spot-checked: `resources/sample-config.json` lists 34 `Texture format`
  and 11 `Attrib float` entries; `main.cpp:365-378` tries `RUNTIME_CONFIG_PATH`
  before `d:\nxdk_pgraph_tests_config.json`.
- The patch's member order (`pgraph_diff_per_test_` declared after
  `pgraph_diff_`, before `enable_progress_log_`) matches its initializer list;
  `ftp_logger_` is assigned in the constructor body, after members are built.

## MEDIUM-1 -- the marker buffer truncates long labels and fuses the canary onto the marker line

`pgraph-per-test-instrument.patch`, `DumpDiff()`: `char line[64]` is used for
`snprintf(line, sizeof(line), "PGRAPH-DIFF %s\n", label)`. Any label over 50
characters is cut at 63 and **loses its trailing newline**; the very next thing
appended to `remote` (and printed / logged) is the PMC watch block.

Scenario, from the tests tree this handoff targets: suite
`"Vertex shader independence tests"` (`vertex_shader_independence_tests.cpp:74`)
with test `"MAC_ILU_Independence"` gives the 55-char label
`Vertex shader independence tests::MAC_ILU_Independence`. The collector
receives

```
PGRAPH-DIFF Vertex shader independence tests::MAC_ILU_IndependePMC BOOT_0(canary) 0xFD000000 = 0x02A000A3
```

A parser keyed on `^PGRAPH-DIFF (.*)$` attributes the diff to a garbled test
name, and one keyed on `^PMC BOOT_0` finds no canary for that test -- so by the
instrument's own rule ("a value other than 0x02A000A3 ... the whole row must be
discarded") the row is either thrown away or, worse, silently matched to no
test. This hits every suite+test pair over 50 chars, and the handoff tells the
next session the instrument is "built and calibrated ... if a future run
disagrees, suspect the run, not this". The 5-test Texture format run in §7
would not have exercised it.

Remediation: build the marker as a `std::string` (or size `line` for the
label), keep the 64-byte buffer only for the fixed-width register lines, and
regenerate the patch.

## MEDIUM-2 -- the correction is stated, not made, where briefs are read

§5 says list A's PVIDEO overlay row "is wrong and should be struck", but the PR
does not touch `docs/testing/nv2a-hardware-gap-list.md`. Line 41 on this head
still reads `PVIDEO overlay composition | d->vga.enable_overlay = true is
**commented out** ...` under "A. Modelled nowhere -- confirmed on silicon", and
line 44 of that same file says the table "is where PMC briefs are written from".

Scenario: a session briefing #110 opens the gap list (not a handoff file named
for the console), reads the row as current, and writes a lane to "implement
overlay composition" -- the same shape as the stale-row finding in
`docs/audits/2026-09-21-pmc188-pass1.md`, which was MEDIUM for this reason.

Remediation: edit row 41 in this PR -- move it out of "modelled nowhere", keep
the surviving half (unmasked `pvideo_write` default, already its own row at 42),
cite `display.c:216/:328` -- and add the file to the body's `Files:` line.
Answering the #110 comment with a correcting comment is optional.

## LOW-1 -- two sections numbered 7

"## 7. Verified working at handoff" and "## 7. A note on choosing the next
thing". Renumber the second to 8.

## LOW-2 -- §1's "lives as uncommitted modifications" is no longer true on this host

At audit time `git -C ~/nxdk_pgraph_tests diff --stat` is empty and `src/`
contains neither `pgraph_diff_per_test_` nor `PGRAPH-DIFF`: the tree was
reverted after the session. The patch file is now the **only** copy of the
instrument, which strengthens the PR's reason to exist but makes §1 and the
§2 "built artifacts" line misleading -- a successor who rebuilds
`build-xbe/` from that tree gets an uninstrumented XBE. (Whether the existing
`default.xbe` still carries the instrument could not be read from this
sandbox.) Say "apply the patch first; the checkout is clean".

## LOW-3 -- the §6 state table is already stale

It says #203 `needs-audit-2` and #206 `needs-audit-1`; at audit time #203 is
`fold-ready` and #206 `needs-audit-2`. Date the table ("as of 2026-09-24
<time>") or point at the PRs rather than restating their labels.
