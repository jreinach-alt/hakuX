# Top Spin: a state:any route that gets past Controller Select

State: ready

Lane: topspinroute1018            Issue: #433
Base: master @ 4a504d9aaa
Files: docs/lanes/topspinroute1018/**, docs/testing/titles/routes/gen-top-spin.route, docs/testing/titles/targets.toml
Prediction: none: no arm
Needs device: no    Needs NDK: no

`gen-top-spin` (the `# state: any` route `targets.toml` already points
`4D530035` Top Spin at) failed on every real run: `drive generic` presses A
through Main Menu, Settings, Venue and Court correctly -- `pathclass`
genuinely classifies all four as the same `ingame_menu`/`submenu` state and
A is the right input for all four -- then hits Controller Select, which the
classifier names identically but where A alone does nothing (both pads sit
in the middle with no team assigned until the hat is moved). 25 presses
later: `ROUTE FAIL ... stuck on ingame_menu ... after 25 presses`. See
`dispatch/results/z-1792314505-lanelocal-3439642/route-state.tsv` for the
real timing this is built from.

The fix splits the route in two: `drive generic 75` for boot/intro/logo/
title and the four correct menu advances (the part whose length genuinely
varies run to run -- the one recorded run took two intro-video skip cycles,
~29 s, before reaching the title screen -- which is the entire reason to
prefer the classifier over a blind wait here), then
`fps786-topspin.route`'s own steps 14-25 copied verbatim: two filler presses
(A, then START) that are no-ops on Controller Select but correct advances
if the drive step undershot, the `axis HATX min` / `axis HATX mid` / `A`
that actually clears Controller Select, and everything from Player Select
through the match intro and into gameplay, unchanged from that proven
recording. The tennis genre loop at the end is unchanged from the previous
`gen-top-spin.route`.

`targets.toml`'s `route = "gen-top-spin"` is unchanged (same file, same
name); only its `notes` line was updated to describe the fix.

| step | source | why |
|---|---|---|
| `drive generic 75` | #433 classifier opening | boot/intro/logo/title + 4 correct submenu advances; length varies run to run |
| steps 14-16 | `fps786-topspin.route`, verbatim | Controller Select: two no-op fillers, then the hat move that clears it |
| steps 17-25 | `fps786-topspin.route`, verbatim | Player Select through match intro into gameplay |
| genre loop | previous `gen-top-spin.route`, unchanged | tennis: move to the ball, swing |

**75 s is a judgment call, not a measured bound** -- this lane has no device
time. The tsv shows Controller Select first reached at t=52.5 (relative to
the `drive` step's own start) and the 25th press (FAIL) at t=123.4, a 70.9 s
gap fixed by the profile's `menu_gap_s`, not by anything that varies run to
run. 75 s clears 52.5 with 22.5 s of margin and sits under a worst-case FAIL
floor guessed at ~85-87 s (an aggressive guess that the whole boot/intro/
logo/title chain could resolve in ~14-16 s instead of the observed 38.6 s
+ ~11 s of menu advances). Full reasoning and the residual risk in
`docs/lanes/topspinroute1018/NOTES.md`. The device run after this lane
checks it for real; I did not request one.

Checked: `route.sh --check` on every file under `docs/testing/titles/routes/`
(including this one) still passes, and `titlestate.route_state()` still
reads `any` off the route's first comment line, unchanged.

Selftest: none -- one route file plus a `targets.toml` notes-line edit, no
code changed.

Release note: none -- test-infrastructure route, not emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
