# board request: lane.blinx372 (#372) -- 2026-09-26

**Ask: add `hakuX-pace:I hakuX-stall:I xemu-gpu:I` to the LOGCAT_SPEC default at
docs/testing/dispatcher.sh:1356** (lane.titlerun's file, released at ready in
PR #307). The change is one line and adds three tokens before `*:S`. Nothing
else changes.

Why:
- `hakuX-pace` (profile.c:622, PR #310) is emitted by every build and is
  dropped from every dispatched soak. The allow-list never gained the tag, so
  any brief asking for "the hakuX-pace line" cannot be met through the
  dispatcher. Verified on 5 Blinx soaks today: 0 pace lines, 60-150
  `hakuX-perf` lines each.
- `hakuX-stall` (draw.c:984, perflog builds only) carries the per-site
  SURFACE_DOWN counters (`sd[ev noCb dl cDef cDefC pDl dDl]`, `dlSrc[...]`)
  and RPBreaks. #372's bound is two synchronous Sd finishes per guest frame
  (~32 ms of a 68 ms frame, docs/investigations/perf-blinx-372.md), and this
  line is the only thing that names which of the seven sites fires.
- `xemu-gpu` (profile.c:654, perflog only): the GPU line, same reason.

After it lands, lane.blinx372 (or a successor) queues ONE perflog Blinx soak on
the Thor to name the site. That measurement decides whether there is a small
lever.
