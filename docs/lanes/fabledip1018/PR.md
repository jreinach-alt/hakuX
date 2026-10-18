# Fable and Blinx 2: decompose the gameplay dips, find what the frame spends its time on

State: ready

Lane: fabledip1018            Issue: #433
Base: master @ bb1817defc
Files: docs/lanes/fabledip1018/NOTES.md, docs/lanes/fabledip1018/FINDINGS.md, docs/lanes/fabledip1018/PR.md
Selftest: none -- analysis only, no code
Needs device: no    Needs NDK: no

Offline decomposition of three evidence windows (Fable's owner gameplay
capture, Fable's cold-cache find-route run, Blinx 2's owner capture around
its first-door slowdown), reading `[drawrec]` (vertex-redo/SHC counters,
`hw/xbox/nv2a/pgraph/vk/draw.c`) and `[rdc]` (per-site TLB-walk timing,
`system/physmem.c`) against `gfps`/`G`/`Ri`/`Tq`.

Both titles show the gta3fps1017b dip signature (G up, renderer idle down
or already low, Tq up, redo/shc up), matching GTA III/SA. In both, the
`[rdc]` numbers show the TLB re-arm walk's own CPU time is 1-2 orders of
magnitude smaller than the render thread's added CPU during the dip (e.g.
Fable: 131us/frame of walk time inside 19.45ms/frame of render-thread CPU)
-- so neither title's dip is the walk cost drawrec1010's `tlbmap.mbox`
follow-on targets; that lever is correctly still parked. Fable's redo/dirty
ratio stays flat through its dip (the tax tracks real dirty growth); Blinx
2's climbs after the door (the bookkeeping itself falls further behind).
Fable's opening ~34s stutter is not explained by shader compile in the data
(no compile line logged until after it resolves); one later, isolated spike
at 07:01:43 is. FINDINGS.md section 3-4 ranks levers and names the one gap
every number above runs into: nothing yet times the vertex-copy or
full-path-draw CPU directly, only counts it. That is the first thing a fix
lane should build, with the exact confirming measurement spelled out.
FINDINGS.md section 4 also has two safe owner-only checks on the Nova that
need no perflog build.

Release note (performance|stability|rendering|other|none): none -- analysis only, no runtime change.
