# lane.doa413c -- #413: DOA Ultimate stage-transition stall (0-2 fps, up to 76 s)

Issue: #413 (0.5, fps-focus)
Base: origin/master f82e7e87fe

DOA2 Ultimate (disc `54430006-Dead_or_Alive_1_Ultimate.xiso.iso`) runs the
fight itself at ~16 fps on the Nova, then a ring-out stage transition drops
to 0-2 fps for up to 76 s without crashing (run
`0-0-y-1790433159-titleplay-p1-doa1u`, ref `a5b5b628f2`, evidence at
`$DISPATCH_DIR/results/0-0-y-1790433159-titleplay-p1-doa1u/` -- logcat.txt,
route-frames/). PR #440 (doa413b) already refuted the surface_update
lazy-completion theory for the general slowdown; #462's remedies
(lane.rendermode474 PR #530, lane.drain474 PR #517, lane.forza414 PR #518,
lane.idlehalt #525) target other games/mechanisms and none names this
specific multi-second stage-transition hang. Do not re-propose the
surface_update theory PR #440 already refuted.

Goal: find the concrete mechanism behind the 0-2 fps, up to-76s hang
specifically in the post-ring-out stage transition -- not the general 16 fps
fight rate. Use the Nova (device hold is lifted), logcat + a fresh profiled
run over the transition window (simpleperf or the existing perflog
instrumentation) to see what the guest/host are doing during the hang:
blocked GPU wait, asset/texture upload burst, disk/ISO read stall, or
something else. Quantify frame time and correlate with whatever signal you
find; do not guess from the frame PNGs alone.

Files: none held yet -- this is measurement-first. Claim only
`docs/lanes/doa413c/**` and `docs/testing/predictions/doa413c-*.json` to
start; if a fix mechanism is found and needs a code file, ask for it by name
(check territory.toml first -- vk/surface.c, vk/texture.c, vk/draw.c are
lent/held elsewhere right now) rather than taking it outright.

Falsifier: name the mechanism and the reading that would refute it before
profiling (e.g. "if flip stalls do NOT line up with a texture upload or lock
hold in the profile during the hang window, this mechanism is wrong").
Register a prediction for the profiled reading before you look at it.

Done when: either (a) a named mechanism with a quantified px/ms impact and a
proposed fix (register the fix as a separate claim, do not take a held file
outright), or (b) a written refutation of the mechanism(s) you tried, with
what you ruled out and what to try next, in NOTES.md.
