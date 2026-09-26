# #31 on silicon: #244 confirmed on the one capture that separates it

**Measured 2026-09-25.** Pre-registered on #31
(https://github.com/jreinach-alt/hakuX/issues/31#issuecomment-5841608810)
before the run. The silicon reference is the console capture from
[`xbox-wbuf31-clipf300-2026-09-25.md`](xbox-wbuf31-clipf300-2026-09-25.md).

**The run.** The ClipF-300-008 XBE (`wbuf31_clipf300.patch`), with the same
12 tests as the console run, on the Thor at master `dd6e2d095b` (contains
#244; APK `2e456253f762`). It completed normally with no crash signal.

**The before arm.** The same XBE on the same Thor at `84a67b9cf8`, before
#244 (`1790346648-xbox-wbuf31c300-dryrun-2923513`, APK `a7b9d28e6b84`).

## Legs

- **M (holds).** hakuX's ClipF-300-008 t0 offset is `[98712.4342, 98712.4440]`
  against silicon's `[98713.0111, 98713.0198]`. They are 0.57 apart, inside
  the 1.0 bound, so t0 anchors at 10 as on silicon. For t1 the gap is 0.15,
  and it anchors at 34.
- **Pixels (hold).** Depth px against the console capture, before and after:

| triangle | px | before #244: ±1 / >1 | after #244: ±1 / >1 |
|---|---:|---|---|
| **ClipF-300-008 t0** | 24,952 | 0 / **24,952** | 15,642 / **0** |
| ClipF-300-008 t1 | 126,348 | 16,860 / 0 | 16,860 / 0 |
| ClipF-150-008 t1 | 191,860 | 174,057 / 17,803 | 174,057 / 17,803 |
| 15 more triangles on the eight ClipF-150 captures | | 0 beyond ±1 | identical |

#244 moved exactly one triangle, from every pixel wrong to every pixel within
±1, and changed nothing else on these captures.

**The residual left: ClipF-150-008 t1, 17,803 px beyond ±1, before and
after.** The anchor is right. The offset sits 1.10 from silicon's interval.
The fix lane predicted it (about 16,600 in its float32 simulation) but could
not arm it, because the capture is not on the golden disc.

Scored with `docs/lanes/xbox/score_clipf300.py --ours <result>` plus a
per-triangle depth count using `wbuf_anchor_recover.py`'s own `decode24` and
`coverage`.
