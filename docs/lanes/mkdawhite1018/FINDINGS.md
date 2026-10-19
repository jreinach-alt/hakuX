# Mortal Kombat: Deadly Alliance (4D57000C): arena floors/walls draw flat white (#1058)

## Summary

The defect the owner saw on 2026-10-17 still reproduces on Turnip (PurpleVK), on the current build
(`0.5.0-1018-da6e8949dc`). It is not a universal renderer bug and not per-run noise: it is tied to
specific arena floor/wall materials. Across seven sampled fights (six dispatch runs plus the original
Step-1 run), five land on an arena whose floor renders flat white (23-56% of the frame's pixels read
pure white) and two land on an arena that renders correctly (0.02-0.07%, consistent with incidental
highlights, not a defect). Two of the five broken instances are the exact same arenas ("Stone
courtyard, red banners" and "Hall with carved heads") the original 10-06 stock-driver sighting named,
now reproduced with different opponents -- the strongest evidence this is a real per-asset defect, not
routing noise or a stock-driver artifact.

No register-level dump has yet been taken of a confirmed-broken arena's floor-paint draw. The one
register-level dump this lane obtained (`1792403678`) landed, by the blind route's luck, on one of the
two *correctly-rendering* arenas, so its findings (below) describe a non-defective instance and do not
confirm or refute any standing hypothesis for the real defect.

## Step 1: does it still show on Turnip

Yes. Settled first in `0-1792377843-mkdawhite1018-4522138` (logcat: `Driver: PurpleVK`, `[gpl569]
mode=3`): the Stone courtyard arena (Shang Tsung vs Johnny Cage) draws its floor flat white, 30.36% of
`route-frames/230209-gameplay.png`'s sampled pixels read pure white. Reconfirmed on four more Turnip
runs (see the table below). The stock driver is not the cause, or not the only cause.

## Step 2: which arena, and what does the dump of a clean arena show

### Arena scope (new this attempt, zero additional device time)

`mkda-arcade.route` fires `shot round`/`shot gameplay` at a fixed point in the script regardless of
the `XEMU_FRAME_DUMP` env spec, so every dispatch run to date already holds a full-colour screenshot
of whichever fight it reached. These were never opened before this attempt. Opening all seven and
measuring the white-pixel fraction of each `*-gameplay.png` (RGB all > 235, PIL, sampled every other
pixel):

| Run | Opponent | Arena | White px | Floor |
|---|---|---|---|---|
| `0-1792377843-mkdawhite1018-4522138` | Johnny Cage | Stone courtyard, red banners, braziers | 30.36% | **white** |
| `1792390708-mkdawhite1018-4087588` | Mavado | Snowy mountain pass, heavy blur/fog | 23.16% | ambiguous |
| `1792394397-mkdawhite1018-1306972` | Li Mei | Hall with carved heads | 31.90% | **white** |
| `1792395921-mkdawhite1018-2024860` | Bo Rai Cho | Kuatan Palace | 56.40% | **white** (wall too) |
| `1792399140-mkdawhite1018-2541099` | Sonya | Stone courtyard, red banners, braziers | 32.34% | **white** |
| `1792399836-mkdawhite1018-2687998` | Kenshi | Stone temple interior, tiled floor | 0.02% | correct |
| `1792403678-mkdawhite1018-3048897` | Sub-Zero | Ice temple, reflective floor | 0.07% | correct |

"Stone courtyard" and "Hall with carved heads" are the same arenas the original 10-06 stock-driver
sighting named (`NOTES.md` section 1, rows 1-2), now reproduced on Turnip with different opponents.
The Mavado instance is flagged ambiguous rather than white: its lower frame is heavily blurred/foggy
(a depth-of-field or motion-blur post effect is visible), not a clean flat white like the other four,
and has not been confirmed as the same defect.

### Register-level dump (describes a correct arena, not the defect)

`1792403678`'s `gd`+`rtt` dump (`framedump_1792406162.jsonl`, 600 frames, landed on the Sub-Zero/ice-
temple arena -- one of the two correct instances) showed:

- The floor-glow composite chain this lane traced across sections 9-11 (a large backbuffer draw
  live-sampling a small offscreen surface via `tex_surface_direct`/`bv:"d"`) is an exact, byte-
  identical no-op in all 24 observed instances: `pre` and `post` readback of the large target never
  differ. The raw `NV_PGRAPH_BLEND` register on the relevant draws (`0x0000050a`) decodes to
  `SFACTOR=ZERO`, `DFACTOR=ONE_MINUS_SRC_ALPHA`, `EQN=ADD`, `EN=1` -- consistent with a
  near-zero contribution, though not fully explaining the *exact*-zero diff on the ~5% of source
  texels with full alpha (a clip/scissor/depth-test rejection is the remaining open possibility,
  unconfirmed).
- No dummy-texture evidence: `th` (texture-cache hash) matches `gh` (guest VRAM hash) on every one of
  ~10 representative large-target draws checked across frame 0.

Both findings are true of a correctly-rendering arena and say nothing about the defect itself.

## Step 3: the lever for a fix lane

`mkda-arcade.route`'s character-select input is blind: seven sampled fights landed on six different
opponent/arena pairings, with no way to choose the arena in advance. **The next lever is a targeting
problem, not a code hypothesis**: a fix lane needs a `gd`+`rtt`+`images` dump taken while
deterministically on one of the three confirmed-broken arenas (Stone courtyard, Hall with carved
heads, or Kuatan Palace), so the floor-paint draw's register state and a visual frame are captured
together. Two ways to get there:

1. A save state that starts past character select, already in one of the three broken arenas.
2. A route that drives the select screen deterministically (rather than the current blind mash)
   toward one of those three pairings.

Without deterministic targeting, another register dump through the existing route is a coin flip (2
of 7 sampled fights so far landed on a correct arena) that risks re-deriving exactly what this attempt
already found for the wrong arena.

The standing candidate mechanism from earlier in this lane -- `create_surface_image`
(`hw/xbox/nv2a/pgraph/vk/surface.c:4138-4240`) never clears a freshly-created or pool-recycled Vulkan
surface image, so a skipped or under-covered bake draw into such a surface would read back as
undefined or as a different surface's stale content rather than a defined colour -- remains plausible
but **unconfirmed**: it was reasoned from a dump of a different, inconclusive surface (NOTES.md
section 11) and has never been checked against a confirmed-broken arena's actual floor-paint draw.

## Already tried

See `NOTES.md` section 3 for the full table (UBO offsets, vertex-RAM hazard, dummy-texture binds,
undecodable formats, LRU/retired views, pad-alpha/component-map, s2t layout/pitch/view, texel
expansion, palette, border colour, swizzle, stock driver, blend-chain tests, prior MK Deadly
Alliance/Armageddon passes). None of those closed issues match this symptom (uniform flat white,
per-arena, present on Turnip); this attempt's own register-level work (above) does not match either,
because it examined a correct instance.

## Recommendation

1. Update tracker row #1058's `status_note` (proposed text in `PR.md`) to record the Turnip
   confirmation and the per-arena scope, so a fix lane does not re-run Step 1 or re-discover the
   arena-specific framing from scratch.
2. A fix lane's first task is deterministic arena targeting (save state or scripted select-screen
   input), not another blind register dump.
3. Once targeted, check the floor-paint draw's own colour output first (is the bake itself producing
   white, or is a correct bake being overwritten/misread downstream) before assuming the
   `create_surface_image` no-clear lever is the mechanism -- it is a candidate, not a confirmed cause.
