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

## Issues filed (forge, via `gh`; drafts in `issues/split-drafts.md`)

- #863 [#747] Star Wars III: fence-bound at 36 render passes a frame
- #864 [#747] GTA SA: guest-bound; shader compile is load-time
- #865 [#747] Tron 2.0: three gameplay stalls; two have no shader work
- #866 [#746] D&D Heroes: submit-bound; the GPU time behind it is unverified
- #867 [#746] D&D Heroes: CPU shader bind is 8.1 ms a frame (not compile)

Lane PR: #862 (draft, `lane/waitread1006`). Filed by `tools/file_split_issues.py`.

## Family and #851 (added after the first filing)

- The family issue titles name the pathfind sweep runs. Re-read here (pace and vblank
  only; `tools/family_read.py`): NFS MW #843, LOTR #845, Hulk #846 are guest-bound;
  Spider-Man 2 #842 and MC2 #844 are renderer-side per their issues. NHL 2K3 #839's
  run dir was not found.
- #851 is Marvel Nemesis r3 (`sweep-4541038A-r3`): one 1014 ms frame with dsm 0 and dpc 0.
  Tron's 1063 ms has 188 ms of shader work. Both are the same size; only one is shader.

## Gaps

- NHL 2K3 (#839): run dir not found in the pathfind worktree.
- Castlevania 1.43 s stall: not on disk.
- Spider-Man 2 and MC2 have no 10-06 gameplay row here, only the issues' and gpunonrender's figures.

## Spend

Not readable from this session.
