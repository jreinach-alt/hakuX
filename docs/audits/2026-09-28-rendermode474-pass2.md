# Audit pass 2: PR #530, lane/rendermode474 (#474)

Head verified: `cadde7e207` (pass 1's audited head `f95b6a2729` plus the pass-1 file only;
`git diff --stat f95b6a2729 cadde7e207` touches `docs/audits/` and nothing else).

**Verdict: clean. No HIGH or MEDIUM, in pass 1 or on re-reading. The four pass-1 LOWs still
apply; none of them blocks the fold.** GitHub reports the PR `MERGEABLE` / `CLEAN` against
master, and both `build` checks pass on this head.

## Pass-1 scenarios, re-checked against the code

Pass 1 found no HIGH or MEDIUM, so there was no remediation to verify. I re-read
`ReadDiscTitleId`, `HasCsvToken` and `ApplyRenderMode` (`xemu_android.cpp:795-938`) to make sure
none of the LOWs is worse than pass 1 rated it.

- **LOW-1 (space-separated `TU_DEBUG`)** still fires. `HasCsvToken` still splits on `','` only
  (`:879`), so `TU_DEBUG=gmem flushall` on DOA or AUF still gets `,sysmem` appended (`:929-931`).
  It stays LOW: it needs one of two titles plus a debug env var written with spaces, and the
  result is the mode the table would pick anyway.
- **LOW-2 (per-game `gmem` does not force GMEM)** still fires. `gmem` falls through both branches
  at `:927-932` and writes nothing. It stays LOW because no settings control writes
  `render_mode` yet. It must be fixed, or the value renamed, before a UI exposes the key.
- **LOW-3 (certificate bound wraps)** still fires. `cert_addr - base_addr + 12` is still a u32
  sum (`:846`). It stays LOW. The read offset is u64 (`:848`, `xbe` is `uint64_t`), so the wrap
  cannot read out of bounds in memory. It only moves a 4-byte pread on a corrupt image, and that
  read either fails (which gives `auto`) or has to match one of two IDs by chance.
- **LOW-4 (DOA occlusion-query frames partly unread)** is a limit of the evidence, not a defect
  in the diff. It is unchanged.

## Re-checked from "checked, no finding"

- Sector arithmetic: `root_sector * kSector` and `xbe_sector * kSector` both promote to u64
  (`kSector` is `uint64_t`, `:799`). `off + 14 + name_len` is at most 0x3FFFC + 269, well inside
  a u32.
- Every early return in `ReadDiscTitleId` gives 0. A 0 title never matches the table (`:916`),
  so a failed read leaves the driver's default.
- A per-game `auto` sets `source = "per-game"` and skips the table, so a user can opt a tabled
  title out.

## Recommendation

`fold-ready`. The LOW-1 and LOW-2 fixes are small and belong with whatever change first adds a
`render_mode` control.
