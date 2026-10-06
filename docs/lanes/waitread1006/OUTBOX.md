# OUTBOX: waitread1006 (#433)

## 2026-10-06: report done; the split issues are drafted, not filed

- REPORT.md: the named wait per title (four measured runs), the Tron 1.06 s
  stall read to its counters, the SW3 commit range, and the fixes ranked by P × win.
- Headline: **D&D is submit-bound** (`Sub` 38.6 of `Tot` 74.4 ms a frame), and
  its GPU stamps are inside the pre-5c35880d0a over-count (17.6% of its
  finishes are `sd`). A re-read on a build with 5c35880d0a decides the lane.
- **SW3 is fence-bound at 36 render passes a frame** (`Fen` 9.8 of `Tot` 30.8 ms
  in gameplay). The median frame is 1.8 ms over the 30-fps deadline. The 96% →
  47% fall is not yet attributed: the 10-02 figure on disk is 87.7%, and the
  676-commit range has the candidates listed in REPORT.md §3.
- **GTA is guest-bound** in gameplay (`IdleFr` 10.0, `IdleSt` 7.35 ms a frame).
  Its shader compile is a load-time cost (7.9 s run-wide, 38 ms in gameplay).
- **Tron's 1.06 s stall is not a shader stall** on the counters: pipeline
  creation is 188 ms of it. The rest has no counter yet.

## Issues: NOT FILED

- Split issues under #747 and #746 are drafted in `issues/split-drafts.md`
  (five drafts: SW3, GTA, Tron under #747; D&D ×2 under #746).
- Filing needs the forge API. This session's `curl` to 127.0.0.1:3330 needs
  an approval it did not get, and the forge data is outside the worktree.
- So there are no issue numbers to list. Whoever has the forge call should file
  the five drafts and append the numbers here.

## Gaps

- NHL 2K3 (#839), NFS MW (#843), LOTR RotK (#845), Hulk (#846): no 10-06 run on disk.
- Castlevania 1.43 s and #851 1.01 s stalls: not on disk.
- Spider-Man 2 (#842) and MC2 (#844): renderer numbers only, from gpunonrender; no 10-06 gameplay row.

## Spend

Not readable from this session.
