# tronhang672: Tron 2.0 hangs entering the first level (Nova)
State: draft

Lane: tronhang672            Issue: #672 [#433]
Base: master @ 4c76e80bd3
Files: accel/tcg/cpu-exec.c, target/i386/tcg/system/seg_helper.c, docs/lanes/tronhang672/NOTES.md, docs/lanes/tronhang672/OUTBOX.md, docs/lanes/tronhang672/PR.md, docs/lanes/tronhang672/tron-newgame.route
Prediction: none yet (instrument only; the fix will register docs/testing/predictions/tronhang672-*.json)
Needs device: yes    Needs NDK: yes

Blocked (see OUTBOX 15:35 PDT). The hang is reproduced on demand: with cold
Vulkan pipelines (`HAKUX_PREBUILD=0 HAKUX_PLC_WIPE=1`) on the New Game path, it
hangs 2 of 2; with warm pipelines it hangs 0 of 3. At the post-load "Press A to
continue", ~50 pipelines compile synchronously in ~13 s. After that stall, a game
thread spins forever in a list walk with budget arithmetic (0x3eb16b-0x3eb3be).
No fix is built. The next step is an owner decision: one run with
`HAKUX_GPL=3` (#569) plus a loop dump.

This head carries only the read-only `[spin672]`/`[spin672r]` instrument
(1 in 4096 `helper_lookup_tb_ptr` targets, top 8 with code bytes, and
registers/IRQL/thread/stack at the 2-s tick). It is what named the loop.
Local checks: both edited files syntax-checked with the desktop build's flags
(`-fsyntax-only`; the only errors were in unrelated `hakux_ibc` code, from that
tree's stale headers). The APK built and ran from 16f09aa346 in six Nova soaks.
Not foldable as is: no dispatch run from the exact head sha.

Release note (none): diagnostic logging only.
