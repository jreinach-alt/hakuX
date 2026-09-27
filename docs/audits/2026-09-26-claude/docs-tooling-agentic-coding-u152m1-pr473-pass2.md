# Audit pass 2: PR #473 (lane.remote, #461 texture-bind count)

Head verified: `dc43033826`. Pass 1 is at `docs/audits/2026-09-26-claude/docs-tooling-agentic-coding-u152m1-pass1.md`.

**Verdict: clean.** Pass 1 found no HIGH and no MEDIUM, so no scenario had to be stopped. Its two LOWs are still open, and neither blocks the fold. Next state: `fold-ready`.

This file is keyed on the PR number. The unkeyed `-pass2.md` at this path already holds PR #449's pass 2, and this PR must not overwrite it.

## The audited code is the head code

Pass 1 read `47a3ce8e85`. `git diff --stat 47a3ce8e85 dc43033826` touches only the pass-1 file. So each "What was checked" claim in pass 1 (default-build inertness, I1 to I4, the range-scan difference, the print format, the reader) was made against the code on the head now. `tex461_read.py --selftest` prints PASS at this head. CI on this head: `build` ×2 and `check` pass.

## Pass-1 findings at this head

### LOW-1 (a reused direct view is not counted in `s2td`): still present, does not block

`txr_s2td++` is still reached only from `bind_surface_as_texture` (`texture.c:1057`) and `bind_zeta_surface_as_texture` (`:1109`). The found path's "same draw_time: reuse direct view" branch (`texture.c:2248-2252`) still sets `tex_surface_direct[texture_idx] = true` and counts nothing. `renderer.h:216` still describes the field as "surfaces bound directly as a texture". The scenario can still occur: a title that samples an unchanged render target reads near 0 `s2td`. Its reach has not grown. The field is perf-only, and no default-build path reads it.

### LOW-2 (`--window` timestamps parsed with no year): still present, does not block

`stamp()` (`tex461_read.py:59-61`) still parses `%m-%d %H:%M:%S.%f` with no year. It is called only when `--window` is given (`:69`, `:73`, `:82`). The New Year scenario can still occur.

## New at pass 2 (LOW, a sibling of LOW-2)

### LOW-3: a 29 February timestamp crashes `--window`

The parse assumes 1900, which is not a leap year. `datetime.strptime('02-29 00:00:00.000', '%m-%d %H:%M:%S.%f')` raises `ValueError: day is out of range for month`. **Scenario:** a soak captured on 29 February (next: 2028) and read with `--window` exits with a traceback, not with a count. It fails loudly and cannot mis-measure, and a run without `--window` is unaffected. Fixing LOW-2 by supplying a year (for example, the capture's year, or the current year with rollover) fixes this as well.

## Not verified

- A device run of the perflog build. Pass 1 needed none, and none is needed here.
