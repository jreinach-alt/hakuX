# Audit pass 2 -- PR #216 `claude/handoff-on-hardware`

Head verified: `894d4c1fd9` (remediation over pass 1 at `99dd6c1305`).
Pass 1: `docs/audits/2026-09-24-claude/handoff-on-hardware-pass1.md`.

Verdict: **clean -> fold-ready.** Every pass-1 scenario was re-run against the
new head, and none of them can happen any more. One new LOW, in the PR body only.

## MEDIUM-1 -- marker truncation: can no longer occur

Scenario: the 55-char label `Vertex shader independence tests::MAC_ILU_Independence`
is cut at 63 bytes and the newline is lost, so the PMC canary line is fused onto it.

- The patch now builds the marker as
  `std::string("PGRAPH-DIFF ") + label + "\n"`. Nothing puts it in `line[64]`.
  So the newline is always the last byte, whatever the label's length.
- I checked every sink it reaches for a second fixed buffer:
  - `PrintMsg` (`src/debug_output.h:19-26`) measures with `snprintf_(nullptr, 0, ...)`
    and then sizes a `std::string`.
  - `Logger::Log() <<` is a stream.
  - `FTPLogger::LogProgress` (`src/ftp_logger.cpp:133`) takes a `std::string`.
  - None of these truncates.
- The two fixed buffers left in the patch only ever hold fixed-width formats:
  - `line[96]` holds `PMC %s 0x%08X = 0x%08X\n`. `%s` is at most `BOOT_0(canary)`, so the line is at most 43 chars.
  - `line[64]` holds `0x%08X: 0x%08X => 0x%08X\n`, which is 37 chars.
  - Neither buffer can take a label.
- `<string>` is already added to `pgraph_diff_token.cpp`'s includes by the patch.
- The hunk header was updated from `+86,46` to `+86,49`. The new patch passes
  `git -C ~/nxdk_pgraph_tests apply --check` on `6743b6a`, and that checkout is still clean.

## MEDIUM-2 -- uncorrected gap-list row: can no longer occur

Scenario: a session briefing #110 reads the list-A row "PVIDEO overlay composition"
as current and briefs a lane to implement it.

- The row is removed from table A. `grep` for `PVIDEO overlay`, `enable_overlay`
  and `overlay_draw_line` in `nv2a-hardware-gap-list.md` now matches only the
  dated "Struck 2026-09-24" note under the table. That note tells the reader
  "Do not brief a lane to 'implement overlay composition'".
- The note's citations match the tree:
  - `pgraph/gl/display.c:216` is `if (pvideo_enable)` in the display shader.
  - `:328` is the `NV_PVIDEO_BUFFER_0_USE && SIZE_IN != 0xFFFFFFFF` gate.
  - `pgraph/vk/display.c:350` is the Vulkan shader's `if (pvideo_enable)`.
  - `:1353` is its matching gate.
- The surviving size/pitch row (`pvideo_write` stores the value unmasked) is kept.
- The PR body's `Files:` line now names `docs/testing/nv2a-hardware-gap-list.md`.

## LOWs from pass 1

- LOW-1: the sections run 1-8 with no duplicate number; the second §7 is now §8.
- LOW-2: §1 now says the sibling checkout "has since been reverted and is clean"
  and the patch is the only copy. §2 says a rebuild without the patch loses the
  instrument. Both statements match the checkout: `git status` shows only
  untracked build directories.
- LOW-3: the §6 table now carries a date ("As of 2026-09-24 23:30 PDT ... read
  the PRs, not this"). The labels in it were refreshed too.

## New

- LOW: the PR body still says "Two files." (body line 9), but the `Files:` line
  above it lists three. This is in the PR body only, not in the tree, so it has
  no effect on fold.
