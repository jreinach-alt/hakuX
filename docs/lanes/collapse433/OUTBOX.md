## #433 -- 2026-10-01 23:40 PDT

[lane.collapse433] Battlefield 2: MC and Blood Wake, diagnosis (branch
lane/collapse433, `docs/lanes/collapse433/NOTES.md`).

**Battlefield 2 (Nova) does not collapse; it is GPU-bound in heavy views.**
In three perflog soaks (`1-1790919561-...-390126` default,
`-601955` sysmem, `-967641` max), frames with ~1,800+ draws need 35-40 ms
of GPU against the 33.4 ms that 30 fps allows. They take 3 VBLANKs and read
16-21 fps. Light views (~900 draws) run near 30. The 514 s confirmation's
66.5% is that mix.
- Not heat, not the PGRAPH lock, not compiles, not the UBO ring.
- Turnip sysmem leaves heavy-view GPU time unchanged.
- The default regimen keeps the Nova's GPU at 401 of 680 MHz. Under max it
  holds 615, but heavy-view GPU time falls only 12-17% and still no heavy
  window reaches 30.
- GPU time runs ~12-14 us per draw, and that does not shrink with clock: a
  per-draw stall or memory fetch on the GPU. That is the lever, and NOTES
  section 8 names the next lane's first measurements. No fix was built
  tonight.
- The player was moving and firing in the soaks' frames. The route ends
  facing a wall with an empty gun, so the 514 s run's late all-30 stretch is
  probably not representative.

**The Thor collapses were heat.** Both runs used MAX and fell 5-7x in one
step 5-8 min after launch, with a clean VBLANK clock. That is the
thermal-pause signature. No thermal record exists for those runs.

**Blood Wake: the accepted Playable needs a second look.** In
`1790876348-autoverdict-2155592`, from mark+131 s to the end (~536 of
667 s) every counter goes flat: guest idle 0 in one loop, no new code, a
third of the vertex traffic. That is very probably a static screen the blind
route never leaves. The 10:44:51 audio burst is the transition into it, not
a gameplay stall. No post-mark frame exists to confirm. Recommend a re-run
with `--frames-every` before counting it.

Nova runs used tonight: 3 of 3.
