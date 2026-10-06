# lane.waitread1006: notes (#433, 0.5)

## Attempt 1 of this lane (the resume): why the previous attempt did not finish

The worktree held no artifacts from an earlier attempt. The branch was at
origin/master `bf85412b88`, with no commit of its own, no `NOTES.md`, no `OUTBOX.md`,
no `PR.md`, and no PR (`gh pr list --head lane/waitread1006` was empty). So the
previous attempt wrote nothing durable. The worktree cannot show why it stopped,
and I did not find a transcript on disk that does. That is the whole of what I
can say about it.

## What this attempt did (offline; data already on disk)

1. Found the four 10-05/06 measured runs in `~/hakux-work/dispatch/results/`:
   `1791267037-hostops-measured-tron`, `1791267038-hostops-measured-starwars3`,
   `1791272940-hostops-2038851-c3a0` (GTA SA), `1791272941-hostops-2039487-c3a0`
   (D&D Heroes). All on ref `c3a0c70ace`.
2. Wrote three readers, all under `tools/` and all offline:
   - `summ_verdicts.py`: verdict and result fields;
   - `run_waits.py`: per-run phase medians, pace windows, vblank histogram,
     `[shd413]` sums and the stall windows, optionally from a gameplay time on;
   - `sd_share.py`: the share of non-deferred PFIFO finishes (sd), which is the
     GPU-stamp over-count's exposure (5c35880d0a).
3. Checked the stamp rules before reading any GPU row:
   - `5c35880d0a` is NOT in `c3a0c70ace` (`git merge-base --is-ancestor` says no);
   - `sd` share in gameplay: GTA 0%, SW3 0%, Tron 0.5%, D&D 17.6%. Only D&D's
     GPU rows need the re-read.
4. Read the instruments' fields from source before naming a wait:
   `profile.c:1011` (Fin/Sub/Fen, Idle/Fr/St, GPU R/X/RP), `pfifo.c:1030`
   (cblat), `cputlb.c:380` (tcg787: `tf` is a fill count, `tfus` is us).
5. Named the waits per title (REPORT.md §1) and read the Tron 1.06 s stall at
   `logcat.txt:39104-39106` and `:38763`, `:39101-39102`.
6. The SW3 range: `7a090b6fa2..c3a0c70ace` (676 commits, 46 touching
   hw/accel/android). The 10-02 SW3 figure on disk is 87.7%, not 96%.

## What is not done, and why

- **Family rows (#839-#846):** the issue titles name the pathfind sweep runs
  (`pathfind/docs/lanes/pathfind/runs/sweep-*`); `tools/family_read.py` re-reads
  their pace and vblank lines. NHL 2K3's run dir was not found. The vCPU
  (`decompose.py`) figures are the issues' own; not re-read here.
- **#851 (1.01 s):** is the Marvel Nemesis r3 run, `sweep-4541038A-r3` (1014 ms, dpc 0, dsm 0).
- **Castlevania 1.43 s stall:** not on disk.
- **Split issues:** filed as #863-#867 with `gh` (the forge answers `gh` here, and
  the draft PR is #862). `tools/file_split_issues.py` did it once; do not re-run it.
- **The 96% SW3 figure:** not on disk. Stated as 87.7% in REPORT.md §0.

## Next lane should not repeat

- Do not read D&D's `GPU_R` without the 5c35880d0a re-read (17.6% of its finishes are `sd`).
- Do not call the Tron 1.06 s stall "shader": the counter sums to 188 of 1063 ms.
- Do not call GTA's load-time `dpc` a gameplay cost: 38 ms in gameplay, 7.9 s run-wide.
- Do not compare a 10-02 survey with a 10-06 run without naming the env change (`HAKUX_FRAMETRACE=1` is on in the 10-06 runs and off in the survey).
- Do not read the family's vCPU/renderer split from the issue titles as measured here: those figures come from `decompose.py` on the pathfind runs, and this lane re-read only the pace and vblank lines.
