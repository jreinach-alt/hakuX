#!/usr/bin/env python3
"""Is what is left in `Blend tests` arithmetic, or is it a channel order?

`blend_model.py` reproduces silicon exactly on the `#spot_` captures, which
makes it an oracle: anything our renderer does differently is ours. This asks
three questions of that difference, in the order that can actually settle it.

  **How big are the misses?** A precision floor is made of one-step misses. If
  nothing is off by one step, the word "precision" is wrong and no amount of
  rounding work will help.

  **Is it the quantiser?** The model takes the rounding mode at each of the two
  stores as a parameter, so the four combinations are four hypotheses about
  what we do instead of round-to-nearest. If none of them fits better than
  round/round, it is not a rounding mode either.

  **Is it the byte order?** The chain reinterprets an A8R8G8B8 render target as
  A8B8G8R8, which exchanges R and B and leaves G alone. So R and B being wrong
  far more often than G is a signature, and exchanging them in our own capture
  is the test: a miss that becomes a hit was never an arithmetic error.

Measured on 2026-09-11 this reported zero one-step misses, no better quantiser
than silicon's own, and 6,353 of 7,974 misses explained by the exchange. See
docs/investigations/blend-render-target-channel-order.md.

    blend_channel_order.py --captures <dir> --goldens <goldens>/Blend_tests

`--captures` takes a directory of `Blend_tests::<test>.png` as written by
extract_results.py.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blend_model as bm  # noqa: E402


def samples(caps, prefix="Blend_tests::"):
    """Yield (eqn, sf, df, got, want) for every sample point we have a capture for."""
    cache = {}
    for eqn, sf, df, sw, rx, ry in bm.sample_points():
        name = f"#spot_{sf}_{eqn}"
        if name not in cache:
            p = os.path.join(caps, prefix + name + ".png")
            cache[name] = bm.load(p) if os.path.exists(p) else None
        img = cache[name]
        if img is None:
            continue
        got = tuple(int(v) for v in img[bm.BLIT_Y + ry, bm.BLIT_X + rx][:3])
        want = tuple(int(v) for v in bm.predict(eqn, sf, df, sw, rx, ry,
                                                bm.QUANT["round"], bm.QUANT["round"]))
        yield eqn, sf, df, got, want


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", required=True)
    ap.add_argument("--goldens", default=os.path.expanduser(
        "~/goldens/results/Blend_tests"))
    ap.add_argument("--prefix", default="Blend_tests::",
                    help="filename prefix in the capture directory")
    args = ap.parse_args()

    print("quantiser fits (ours against the model):")
    best = None
    for qb in bm.QUANT:
        for qt in bm.QUANT:
            h, m, _ = bm.score(args.captures, args.prefix, args.goldens, qb, qt)
            print(f"  blend {qb:>5} / blit {qt:>5}: {h:>6} hit, {m:>6} miss")
            if best is None or h > best[0]:
                best = (h, qb, qt)
    print(f"  best fit: blend {best[1]} / blit {best[2]}"
          f" ({'silicon-s own' if best[1:] == ('round', 'round') else 'NOT silicon-s'})")

    hist = collections.Counter()
    swap = collections.Counter()
    missed = collections.Counter()
    chan = collections.Counter()
    n = exact = swap_fixes = still = 0
    for eqn, _sf, _df, got, want in samples(args.captures, args.prefix):
        n += 1
        d = max(abs(a - b) for a, b in zip(got, want))
        hist[d] += 1
        if got == want:
            exact += 1
            continue
        missed[eqn] += 1
        for i, c in enumerate("RGB"):
            if got[i] != want[i]:
                chan[c] += 1
        if (got[2], got[1], got[0]) == want:
            swap_fixes += 1
            swap[eqn] += 1
        else:
            still += 1

    print(f"\n|delta| against silicon, {n} samples:")
    for d in sorted(hist):
        print(f"  {d:>4}: {hist[d]}")
    one_step = hist[1] + hist[2]
    print(f"  within one or two steps: {one_step}"
          f"{'  <- no precision floor here' if one_step == 0 else ''}")

    print(f"\nchannels wrong: " +
          ", ".join(f"{c}={chan[c]}" for c in "RGB"))
    print(f"\nexact as captured         : {exact}")
    print(f"exact once R and B swapped: {swap_fixes}")
    print(f"wrong either way          : {still}")
    if swap_fixes:
        print("\nswap-explained, by equation (of missed):")
        for e in sorted(missed, key=lambda k: -swap[k]):
            print(f"  {e:>8}: {swap[e]:>5} / {missed[e]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
