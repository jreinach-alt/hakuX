# tronhang672: Tron 2.0 hangs entering the first level (Nova)
State: draft

Lane: tronhang672            Issue: #672 [#433]
Base: master @ 4c76e80bd3
Files: accel/tcg/cpu-exec.c, target/i386/tcg/system/seg_helper.c, docs/lanes/tronhang672/NOTES.md, docs/lanes/tronhang672/OUTBOX.md, docs/lanes/tronhang672/PR.md
Prediction: none yet (instrument only; the fix will register docs/testing/predictions/tronhang672-*.json)
Needs device: yes    Needs NDK: yes

Work in progress. The hang is a guest-side spin after the level-load disc
reads: the guest never idles again, submits nothing to the GPU, and runs a
call/ret loop inside chained TBs. This head adds a read-only instrument,
`[spin672]`/`[spin672r]`, to name the loop. See NOTES.md.

Release note (none): diagnostic logging only.
