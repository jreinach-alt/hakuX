#!/usr/bin/env python3
"""Decompose the exactly-zero samples in an APU PCM capture.

Why this exists
---------------

`audio_measure.py` reports one number for this: "zeros %". On the first real
capture off the device that number was 9.78%, which reads as a tenth of the
output being missing and is the first thing anyone points at. It was not a
defect -- it was 3.25 s of boot silence, one 5.76 s silent stretch in the
program material, and about 1,400 single-frame zero crossings.

A percentage cannot tell those apart, and the three have completely different
meanings:

- **Boot and program silence** are content. Nothing to do.
- **Periodic short gaps** would be a producer-side dropout: the output buffer
  `monitor.frame_buf` is filled in eight 32-frame slices per 256-frame block
  (`vp.c` on the monitor path, `dsp/gp_ep.c` on the GP path) and zeroed after
  each push, so a slice that never gets written leaves a 32-frame hole. That is
  a real failure mode of the frame slicing and it is invisible in a percentage.
- **Isolated single zeros** are zero crossings of ordinary audio. A signal
  that crosses zero between samples lands exactly on 0 occasionally; the count
  scales with level and frequency content and means nothing.

So the question is never "how many zeros" but "what shape are they". This
prints the shape: run lengths, where the runs start relative to the 32-frame
slice and the 256-frame block, and the per-block zero histogram.

What to look for
----------------

A producer-side dropout has a signature that content does not:

- run lengths clustered at **32** (one missed VP slice) or a multiple of it;
- run starts clustered at **one residue modulo 32**, rather than spread;
- many *partially* zero blocks with the same zero count.

Content silence is one or a few long runs of arbitrary length at arbitrary
offsets, plus a scatter of length-1 runs. If the output looks like that, the
zeros are the title being quiet and there is nothing here.

A frame is counted as zero only when **both** channels are zero. A zero on one
channel alone is not a gap -- it is a hard-panned or mono-ish moment -- and
counting per sample conflates the two.

Usage
-----

    audio_zero_structure.py CAPTURE.pcm [--channels N]
    audio_zero_structure.py --selftest

Format defaults match the capture in `hw/xbox/mcpx/apu/apu.c`: signed 16-bit
host-endian, 2 channels, interleaved, 48000 Hz. Reads the `.json` sidecar for
rate and channel count when it is next to the file.

numpy is used when importable, purely for speed; the stdlib path produces the
same numbers and `--selftest` checks that it does.
"""

import argparse
import array
import json
import os
import sys
from collections import Counter

try:
    import numpy as _np
except ImportError:
    _np = None

DEFAULT_RATE = 48000
DEFAULT_CHANNELS = 2
# Buffer geometry, from apu_int.h / apu_regs.h. A gap in the producer shows up
# at one of these two granularities and nowhere else.
SLICE_FRAMES = 32
BLOCK_FRAMES = 256


def read_sidecar(path):
    """Rate and channels from the capture's own sidecar, when present."""
    try:
        with open(path + ".json") as fh:
            side = json.load(fh)
    except (OSError, ValueError):
        return {}
    return side


def zero_frame_mask(samples, channels):
    """True where every channel of the frame is exactly zero.

    `samples` is a flat interleaved sequence. Returns a list/array of bools of
    length n_frames.
    """
    n = len(samples) // channels
    if _np is not None:
        a = _np.asarray(samples).reshape(-1, channels)[:n]
        return (a == 0).all(axis=1)
    out = bytearray(n)
    for f in range(n):
        base = f * channels
        for c in range(channels):
            if samples[base + c]:
                break
        else:
            out[f] = 1
    return out


def runs_of_true(mask):
    """(start, length) for each maximal run of True in `mask`."""
    if _np is not None:
        m = _np.asarray(mask, dtype=bool).astype(_np.int8)
        d = _np.diff(_np.concatenate(([0], m, [0])))
        starts = _np.flatnonzero(d == 1)
        ends = _np.flatnonzero(d == -1)
        return list(zip(starts.tolist(), (ends - starts).tolist()))
    out = []
    start = None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - start))
            start = None
    if start is not None:
        out.append((start, len(mask) - start))
    return out


def percentile(sorted_vals, q):
    """Linear-interpolated percentile, matching numpy's default."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * (q / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def analyse(mask, rate):
    """Everything this tool reports, as a dict. `mask` is per-frame."""
    n = len(mask)
    total = int(sum(1 for v in mask if v)) if _np is None else int(_np.sum(mask))

    # Leading silence is boot, not a gap, and it would dominate every other
    # statistic here. Report it and then exclude it.
    all_runs = runs_of_true(mask)
    lead = all_runs[0][1] if all_runs and all_runs[0][0] == 0 else 0

    body = [r for r in all_runs if not (r[0] == 0 and r[1] == lead)]
    lengths = sorted(r[1] for r in body)
    res = {
        "frames": n,
        "rate": rate,
        "zero_frames": total,
        "zero_pct": 100.0 * total / n if n else 0.0,
        "leading_silence_frames": lead,
        "leading_silence_s": lead / float(rate) if rate else 0.0,
        "runs": len(body),
        "run_len_hist": Counter(lengths).most_common(12),
        "run_len_p50": percentile(lengths, 50),
        "run_len_p95": percentile(lengths, 95),
        "run_len_p99": percentile(lengths, 99),
        "run_len_max": lengths[-1] if lengths else 0,
        "start_mod_slice": Counter(r[0] % SLICE_FRAMES for r in body).most_common(6),
        "start_mod_block": Counter(r[0] % BLOCK_FRAMES for r in body).most_common(6),
        "len_is_slice_multiple": sum(1 for L in lengths if L and L % SLICE_FRAMES == 0),
        "frames_in_long_runs": sum(L for L in lengths if L >= SLICE_FRAMES),
        "long_runs": sum(1 for L in lengths if L >= SLICE_FRAMES),
        "singleton_runs": sum(1 for L in lengths if L == 1),
    }

    # Per-block zero counts, over the body only.
    nb = n // BLOCK_FRAMES
    if _np is not None:
        m = _np.asarray(mask, dtype=bool)[: nb * BLOCK_FRAMES]
        bz = m.reshape(nb, BLOCK_FRAMES).sum(axis=1).tolist()
    else:
        bz = [sum(mask[b * BLOCK_FRAMES:(b + 1) * BLOCK_FRAMES]) for b in range(nb)]
    res["blocks"] = nb
    res["blocks_full"] = sum(1 for v in bz if v == BLOCK_FRAMES)
    res["blocks_partial"] = sum(1 for v in bz if 0 < v < BLOCK_FRAMES)
    res["block_hist"] = Counter(bz).most_common(8)
    return res


def verdict(res):
    """The shape call, stated as a rule rather than left to the reader.

    Deliberately conservative: it reports SUSPECT only on the signature a
    producer-side gap actually has, because a tool that cries dropout at
    ordinary silence would be ignored within a day.
    """
    reasons = []
    long_runs = res["long_runs"]
    # A handful of long runs is program silence. Many of them, most of whose
    # lengths are slice multiples, is the frame slicing dropping work.
    if long_runs >= 8 and res["len_is_slice_multiple"] >= 0.5 * long_runs:
        reasons.append(
            "%d runs of >= %d frames, %d of them a multiple of the %d-frame "
            "VP slice" % (long_runs, SLICE_FRAMES, res["len_is_slice_multiple"],
                          SLICE_FRAMES))
    # Run starts piling onto one residue mod 32 is the other half of it.
    if res["runs"] >= 32 and res["start_mod_slice"]:
        top, cnt = res["start_mod_slice"][0]
        if cnt >= 0.5 * res["runs"]:
            reasons.append(
                "%d of %d run starts land on offset %d within the %d-frame slice"
                % (cnt, res["runs"], top, SLICE_FRAMES))
    return reasons


def report(path, channels_override=None):
    side = read_sidecar(path)
    rate = int(side.get("sample_rate") or DEFAULT_RATE)
    channels = int(channels_override or side.get("channels") or DEFAULT_CHANNELS)

    with open(path, "rb") as fh:
        raw = fh.read()
    if _np is not None:
        samples = _np.frombuffer(raw, dtype="<i2")
        usable = (len(samples) // channels) * channels
        samples = samples[:usable]
    else:
        a = array.array("h")
        a.frombytes(raw[: (len(raw) // (2 * channels)) * 2 * channels])
        if sys.byteorder != "little":
            a.byteswap()
        samples = a

    mask = zero_frame_mask(samples, channels)
    res = analyse(mask, rate)

    print("file          %s" % path)
    print("format        s16 x%d interleaved @ %d Hz" % (channels, rate))
    print("frames        %s  (%.3f s)" % (format(res["frames"], ","),
                                          res["frames"] / float(rate)))
    print("zero frames   %s  (%.3f%%)   [both channels exactly zero]"
          % (format(res["zero_frames"], ","), res["zero_pct"]))
    print("leading       %s frames = %.3f s of silence before the guest speaks"
          % (format(res["leading_silence_frames"], ","),
             res["leading_silence_s"]))
    print()
    print("after the leading silence:")
    print("  runs                %s" % format(res["runs"], ","))
    print("  singleton runs      %s   (zero crossings; expected, means nothing)"
          % format(res["singleton_runs"], ","))
    print("  run length p50/p95/p99/max   %.0f / %.0f / %.0f / %s"
          % (res["run_len_p50"], res["run_len_p95"], res["run_len_p99"],
             format(res["run_len_max"], ",")))
    print("  runs >= %d frames    %d, holding %s frames (%.3f s)"
          % (SLICE_FRAMES, res["long_runs"],
             format(res["frames_in_long_runs"], ","),
             res["frames_in_long_runs"] / float(rate)))
    print("  lengths that are a multiple of the %d-frame slice   %d of %d"
          % (SLICE_FRAMES, res["len_is_slice_multiple"], res["runs"]))
    print("  top run lengths (len x count)  %s"
          % ", ".join("%dx%d" % (L, c) for L, c in res["run_len_hist"]))
    print("  run start mod %d   %s" % (SLICE_FRAMES,
          ", ".join("%d:%d" % kv for kv in res["start_mod_slice"])))
    print("  run start mod %d  %s" % (BLOCK_FRAMES,
          ", ".join("%d:%d" % kv for kv in res["start_mod_block"])))
    print()
    print("blocks of %d frames   %s total, %s wholly zero, %s partially zero"
          % (BLOCK_FRAMES, format(res["blocks"], ","),
             format(res["blocks_full"], ","),
             format(res["blocks_partial"], ",")))
    print("  zero-count histogram  %s"
          % ", ".join("%d:%d" % kv for kv in res["block_hist"]))
    print()

    reasons = verdict(res)
    if reasons:
        print("SUSPECT producer-side gap:")
        for r in reasons:
            print("  - " + r)
        print("  Look at the frame slicing: monitor.frame_buf is filled in eight")
        print("  32-frame slices and zeroed after each push, so a slice that is")
        print("  never written leaves exactly this shape.")
    else:
        print("No producer-side gap signature. The zeros are silence in the")
        print("program material plus ordinary zero crossings.")
    return res


# --------------------------------------------------------------------------
# Self-test. The oracle is construction: signals whose answer is known because
# the zeros were placed deliberately.
# --------------------------------------------------------------------------

def _pcm(frames, channels=2):
    a = array.array("h")
    for f in frames:
        for c in range(channels):
            a.append(f[c] if isinstance(f, (list, tuple)) else f)
    return a


def _selftest():
    checks = []

    def ck(name, got, want):
        ok = got == want
        checks.append(ok)
        print("%-52s %s  (got %r, want %r)"
              % (name, "ok" if ok else "FAIL", got, want))

    # 1. A signal with no zeros at all.
    s = _pcm([1000] * 1000)
    m = zero_frame_mask(s, 2)
    ck("no zeros: mask empty", int(sum(m)), 0)

    # 2. Leading silence is measured exactly and excluded from the body.
    s = _pcm([0] * 480 + [1000] * 1000)
    r = analyse(zero_frame_mask(s, 2), 48000)
    ck("leading silence frames", r["leading_silence_frames"], 480)
    ck("leading silence seconds", round(r["leading_silence_s"], 3), 0.01)
    ck("leading silence not counted as a run", r["runs"], 0)

    # 3. One zero on ONE channel is not a zero frame. This is the distinction
    #    a per-sample count gets wrong.
    s = _pcm([(0, 1000)] * 100 + [(1000, 1000)] * 100)
    ck("one-channel zero is not a gap", int(sum(zero_frame_mask(s, 2))), 0)

    # 4. Run lengths and starts are exact.
    body = [1000] * 100 + [0] * 32 + [1000] * 100 + [0] * 32 + [1000] * 100
    r = analyse(zero_frame_mask(_pcm(body), 2), 48000)
    ck("two runs found", r["runs"], 2)
    ck("both runs are 32 long", r["run_len_max"], 32)
    ck("both lengths are slice multiples", r["len_is_slice_multiple"], 2)
    ck("no leading silence here", r["leading_silence_frames"], 0)

    # 5. The dropout verdict fires on the signature and not on silence.
    #    Ten slice-aligned 32-frame gaps at a constant offset: SUSPECT.
    frames = []
    for _ in range(10):
        frames += [1000] * 32 + [0] * 32
    frames += [1000] * 32
    r = analyse(zero_frame_mask(_pcm(frames), 2), 48000)
    ck("aligned 32-frame gaps flagged", len(verdict(r)) > 0, True)

    #    One long stretch of silence in the middle: NOT suspect. This is the
    #    real capture's shape and the tool must stay quiet on it.
    frames = [1000] * 10000 + [0] * 276480 + [1000] * 10000
    r = analyse(zero_frame_mask(_pcm(frames), 2), 48000)
    ck("one long silence not flagged", verdict(r), [])
    ck("long silence length exact", r["run_len_max"], 276480)

    #    A scatter of single zeros: NOT suspect, however many.
    frames = []
    for i in range(2000):
        frames += [1000, 0, -1000]
    r = analyse(zero_frame_mask(_pcm(frames), 2), 48000)
    ck("zero crossings not flagged", verdict(r), [])
    ck("all runs are singletons", r["singleton_runs"], r["runs"])

    # 6. Block accounting.
    frames = [0] * BLOCK_FRAMES + [1000] * BLOCK_FRAMES
    r = analyse(zero_frame_mask(_pcm(frames), 2), 48000)
    ck("block count", r["blocks"], 2)
    #    The all-zero block here is leading silence, so it is excluded from
    #    runs but still counted as a block -- these are different questions.
    ck("wholly-zero blocks", r["blocks_full"], 1)
    ck("partially-zero blocks", r["blocks_partial"], 0)

    # 7. numpy and stdlib agree. The numbers must not depend on which ran.
    global _np
    if _np is not None:
        frames = [1000] * 500 + [0] * 64 + [1000] * 300 + [0] * 1 + [1000] * 135
        s = _pcm(frames)
        with_np = analyse(zero_frame_mask(s, 2), 48000)
        saved, _np = _np, None
        try:
            without = analyse(zero_frame_mask(s, 2), 48000)
        finally:
            _np = saved
        for key in ("zero_frames", "runs", "run_len_max", "blocks_full",
                    "blocks_partial", "leading_silence_frames",
                    "len_is_slice_multiple", "singleton_runs"):
            ck("backends agree on %s" % key, without[key], with_np[key])
    else:
        print("numpy not importable; backend-agreement checks skipped")

    print("\n%d checks, %d passed, %d failed"
          % (len(checks), sum(checks), len(checks) - sum(checks)))
    return 0 if all(checks) else 1


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", nargs="?", help="captured .pcm file")
    ap.add_argument("--channels", type=int, help="override channel count")
    ap.add_argument("--selftest", action="store_true",
                    help="run the built-in checks and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.capture:
        ap.error("need a capture, or --selftest")
    if not os.path.exists(args.capture):
        sys.exit("no such file: %s" % args.capture)
    report(args.capture, args.channels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
