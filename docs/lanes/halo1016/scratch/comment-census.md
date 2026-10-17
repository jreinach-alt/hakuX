[lane.halo1016] census verdict (halo1016-census.json, judged by censusread.py as committed in 7a960726d8, before either arm ran)

- A = 0-0-x-1792222165-halo1016-1341449 (214445e90e, perflog + frametrace + probe1010)
- B = 0-0-x-1792222171-halo1016-1341994 (the same + `HAKUX_S2T_CVT=1`)

| Leg | Result | Measured over [mark+131, mark+191] |
|---|---|---|
| O overlap eviction | MISS | `[ovl1018]` draw-dirty 0.00/f against 49.28 downloads/f |
| K texture path | **HIT** | txr dl 49.28/f = every download; txdl reason `cvt` 50261, all others 0 |
| R CPU range read | MISS | 0.00/f |
| C `HAKUX_S2T_CVT` | **HIT** | B: 0 downloads; 59.3 -> 41.9 ms a frame (0.71 x) |

Every plateau download is the #986 MKSM mechanism: a draw-dirty 2-byte colour surface sampled as a 5/6-bit texture, refused by #59's guard and read back with a submit and fence wait. `HAKUX_S2T_CVT` (fps1015, default off) removes all of them.

It does not clear the plateau. With the downloads gone (B), the shots still run 40-61 ms a frame, and the guest never idles: the vCPU is the second bound. In those windows 97% of the TB exits that return to the main loop (1.4-2.2 M per 2 s) are one guest instruction, `fldcw` in the title's CRT `_control87`, and the loop's own time is 11-16% of the vCPU's wall against 2-6% at 30 fps. hakuX's FP JIT ends every TB after FLDCW (translate.c:3423, the precision bit is a TB flag). The next chase is that exit, then the plateau's longjmps. Details in docs/lanes/halo1016/NOTES.md, "#1018 census verdict" and "the guest-CPU half".
