#!/usr/bin/env python3
"""Measure a PCM capture from the APU audio harness.

Why this exists
---------------

Audio on this project has had no oracle. A submix-headroom fix predicted to
make output exactly 2x louder (+6.02 dB) landed tagged "unverified by ear",
which is not a verification strategy: nobody can hear 6 dB reliably, nobody can
hear whether it is 6.02 or 5.1, and nobody can hear the difference between
"louder" and "louder and now clipping". Those are all measurements.

This script turns a capture into numbers. It reports levels, clipping, DC and
silence, per channel, and -- in `--compare` mode -- the level *shift* between
two captures, which is the form the headroom prediction actually takes.

Input format
------------

Headerless PCM as written by the capture in `hw/xbox/mcpx/apu/apu.c`:
signed 16-bit host-endian, 2 channels, interleaved L,R. 48000 Hz. The capture
writes a `<file>.json` sidecar recording exactly that; this script reads the
sidecar when it is present and falls back to those defaults when it is not.
Both are overridable with `--rate` and `--channels`.

Conventions, stated because a dBFS number is meaningless without them
--------------------------------------------------------------------

- Full scale is 32768 (2**15). A peak of 32767 therefore reads -0.0003 dBFS,
  not 0.0. This is the usual convention and it keeps +/- symmetric.
- `dBFS` on an RMS figure is relative to a full-scale *square* wave, not a
  sine. A full-scale sine measures -3.01 dBFS RMS. If you are eyeballing
  whether a mix is "loud", that 3 dB is the reference point.
- "Clipped" counts samples at or beyond full-scale *magnitude*, i.e.
  `abs(s) >= 32767`. The threshold is 32767 and not 32768 on purpose: the
  float-to-short conversion clamps to +/-1.0 and scales by 32767
  (`android/app/src/main/cpp/samplerate_stub.c:161-197`), so negative
  saturation arrives as -32767, and a test written against -32768 would count
  none of it.
- "Wrap suspects" counts adjacent samples differing by more than full scale.
  This is a separate failure from clipping and it matters here: the per-voice
  conversion saturates, but the monitor mix then sums voices with `+=` into an
  `int16_t` (`hw/xbox/mcpx/apu/vp/vp.c:1887-1888`), and that accumulator can
  *wrap* rather than saturate. Wrapping flips the sign of a loud sample, which
  no band-limited 48 kHz signal does, so a non-zero count is a strong hint of
  accumulator overflow. It is a hint and not a proof: genuinely square content
  can trip it too.
- RMS is reported both as-is and with DC removed. A DC offset inflates raw RMS
  without being audible, so the AC figure is the one to compare.

Usage
-----

    audio_measure.py CAPTURE.pcm
    audio_measure.py CAPTURE.pcm --json
    audio_measure.py --compare BEFORE.pcm AFTER.pcm
    audio_measure.py --selftest

Dependencies: standard library only. numpy is used when importable, purely for
speed; `--selftest` checks that both backends agree, so the numbers do not
depend on which one ran.
"""

import argparse
import array
import json
import math
import os
import sys

try:
    import numpy as _np
except ImportError:
    _np = None

FULL_SCALE = 32768.0
S16_MAX = 32767
S16_MIN = -32768

# Below this, a channel is reported as effectively silent. -90 dBFS is about
# 1 LSB of a 16-bit sample, i.e. indistinguishable from a dead channel.
SILENCE_DBFS = -90.0

DEFAULT_RATE = 48000
DEFAULT_CHANNELS = 2
DEFAULT_WINDOW_MS = 50.0

PERCENTILES = (5, 25, 50, 75, 95)


def db(x, reference=FULL_SCALE):
    """Amplitude ratio to dB. Returns -inf for zero rather than raising."""
    if x <= 0:
        return float("-inf")
    return 20.0 * math.log10(x / reference)


def fmt_db(x):
    if x == float("-inf"):
        return "  -inf"
    return f"{x:7.2f}"


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def read_sidecar(path):
    """Return format info from the capture's .json sidecar, or {}."""
    for candidate in (path + ".json", os.path.splitext(path)[0] + ".json"):
        if os.path.exists(candidate):
            try:
                with open(candidate) as fh:
                    return json.load(fh)
            except (OSError, ValueError) as exc:
                print(f"warning: could not read sidecar {candidate}: {exc}",
                      file=sys.stderr)
    return {}


def read_pcm(path, channels):
    """Read interleaved s16 host-endian PCM, return a list of per-channel seqs."""
    size = os.path.getsize(path)
    if size == 0:
        raise SystemExit(
            f"{path} is empty. The capture produced no samples: either it was "
            f"never enabled (XEMU_AUDIO_CAPTURE=1), or the run never reached "
            f"audio output."
        )

    frame_bytes = 2 * channels
    if size % frame_bytes:
        print(f"warning: {path} is {size} bytes, not a whole number of "
              f"{channels}-channel frames; ignoring the trailing "
              f"{size % frame_bytes} bytes", file=sys.stderr)

    if _np is not None:
        raw = _np.fromfile(path, dtype="<i2" if sys.byteorder == "little"
                           else ">i2")
        usable = (len(raw) // channels) * channels
        raw = raw[:usable].reshape(-1, channels)
        return [raw[:, c] for c in range(channels)]

    raw = array.array("h")
    with open(path, "rb") as fh:
        raw.frombytes(fh.read(size - (size % frame_bytes)))
    if sys.byteorder == "big":
        # array('h') is host-endian, and so is the file; nothing to swap.
        pass
    return [raw[c::channels] for c in range(channels)]


# --------------------------------------------------------------------------
# Statistics. Two backends; --selftest asserts they agree.
# --------------------------------------------------------------------------


def channel_stats(samples):
    """Peak, RMS, DC, clipping and zero counts for one channel."""
    n = len(samples)
    if n == 0:
        raise SystemExit("channel has no samples")

    if _np is not None:
        s = samples.astype(_np.float64)
        total = float(s.sum())
        sumsq = float((s * s).sum())
        peak = int(max(abs(int(s.max())), abs(int(s.min()))))
        clipped = int((_np.abs(s) >= S16_MAX).sum())
        zeros = int((samples == 0).sum())
        vmax, vmin = int(samples.max()), int(samples.min())
        if n > 1:
            diff = _np.abs(_np.diff(s))
            wrap_suspects = int((diff > FULL_SCALE).sum())
            max_jump = int(diff.max())
        else:
            wrap_suspects, max_jump = 0, 0
    else:
        total = 0.0
        sumsq = 0.0
        clipped = 0
        zeros = 0
        wrap_suspects = 0
        max_jump = 0
        vmax = -32769
        vmin = 32768
        prev = None
        for v in samples:
            total += v
            sumsq += v * v
            if v >= S16_MAX or v <= -S16_MAX:
                clipped += 1
            if v == 0:
                zeros += 1
            if v > vmax:
                vmax = v
            if v < vmin:
                vmin = v
            if prev is not None:
                jump = abs(v - prev)
                if jump > max_jump:
                    max_jump = jump
                if jump > FULL_SCALE:
                    wrap_suspects += 1
            prev = v
        peak = max(abs(vmax), abs(vmin))

    mean = total / n
    rms = math.sqrt(sumsq / n)
    # RMS with DC removed: var = E[x^2] - E[x]^2
    ac_var = max(sumsq / n - mean * mean, 0.0)
    ac_rms = math.sqrt(ac_var)

    return {
        "samples": n,
        "peak": peak,
        "peak_dbfs": db(peak),
        "min": vmin,
        "max": vmax,
        "rms": rms,
        "rms_dbfs": db(rms),
        "ac_rms": ac_rms,
        "ac_rms_dbfs": db(ac_rms),
        "dc_offset": mean,
        "dc_offset_pct_fs": 100.0 * mean / FULL_SCALE,
        "dc_offset_dbfs": db(abs(mean)),
        "clipped": clipped,
        "clipped_pct": 100.0 * clipped / n,
        "wrap_suspects": wrap_suspects,
        "max_sample_jump": max_jump,
        "zeros": zeros,
        "zeros_pct": 100.0 * zeros / n,
        "silent": db(ac_rms) < SILENCE_DBFS,
    }


def window_rms_dbfs(samples, window):
    """Per-window AC RMS in dBFS. Windows shorter than `window` are dropped."""
    out = []
    n = len(samples) // window * window
    if _np is not None and n:
        s = samples[:n].astype(_np.float64).reshape(-1, window)
        mean = s.mean(axis=1)
        var = _np.maximum((s * s).mean(axis=1) - mean * mean, 0.0)
        rms = _np.sqrt(var)
        with _np.errstate(divide="ignore"):
            return [float(x) for x in
                    (20.0 * _np.log10(_np.where(rms > 0, rms, _np.nan)
                                      / FULL_SCALE))]
    for start in range(0, n, window):
        chunk = samples[start:start + window]
        total = 0.0
        sumsq = 0.0
        for v in chunk:
            total += v
            sumsq += v * v
        mean = total / window
        var = max(sumsq / window - mean * mean, 0.0)
        out.append(db(math.sqrt(var)))
    return out


def percentiles(values):
    """Percentiles of the finite entries, ignoring silent windows (-inf/nan)."""
    finite = sorted(v for v in values
                    if v == v and v not in (float("-inf"), float("inf")))
    if not finite:
        return {}, 0
    result = {}
    for p in PERCENTILES:
        # Nearest-rank; no interpolation, so the number is an observed window.
        idx = min(int(round(p / 100.0 * (len(finite) - 1))), len(finite) - 1)
        result[p] = finite[idx]
    return result, len(finite)


def leading_trailing_silence(channels, rate):
    """Seconds of all-zero frames at the start and end of the file."""
    n = len(channels[0])

    def frame_is_zero(i):
        return all(ch[i] == 0 for ch in channels)

    lead = 0
    while lead < n and frame_is_zero(lead):
        lead += 1
    if lead == n:
        return n / rate, n / rate
    trail = 0
    while trail < n and frame_is_zero(n - 1 - trail):
        trail += 1
    return lead / rate, trail / rate


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def measure(path, rate=None, channels=None, window_ms=DEFAULT_WINDOW_MS):
    side = read_sidecar(path)
    rate = rate or side.get("sample_rate") or DEFAULT_RATE
    channels = channels or side.get("channels") or DEFAULT_CHANNELS

    chans = read_pcm(path, channels)
    frames = len(chans[0])
    window = max(1, int(rate * window_ms / 1000.0))

    per_channel = []
    for idx, ch in enumerate(chans):
        st = channel_stats(ch)
        st["channel"] = "LR"[idx] if channels == 2 and idx < 2 else str(idx)
        pct, counted = percentiles(window_rms_dbfs(ch, window))
        st["window_rms_percentiles_dbfs"] = pct
        st["windows_counted"] = counted
        per_channel.append(st)

    lead, trail = leading_trailing_silence(chans, rate)

    return {
        "file": path,
        "bytes": os.path.getsize(path),
        "sample_rate": rate,
        "channels": channels,
        "frames": frames,
        "duration_s": frames / rate,
        "window_ms": window_ms,
        "full_scale": FULL_SCALE,
        "sidecar": side or None,
        "leading_silence_s": lead,
        "trailing_silence_s": trail,
        "all_silent": all(c["silent"] for c in per_channel),
        "per_channel": per_channel,
        "backend": "numpy" if _np is not None else "stdlib",
    }


def print_report(m):
    print(f"file          {m['file']}")
    print(f"format        s16 x{m['channels']} interleaved @ {m['sample_rate']} Hz"
          f"   (full scale = {int(m['full_scale'])})")
    print(f"size          {m['bytes']} bytes, {m['frames']} frames, "
          f"{m['duration_s']:.3f} s")
    if m["sidecar"]:
        sc = m["sidecar"]
        print(f"sidecar       volume_limit={sc.get('audio_volume_limit')} "
              f"use_dsp={sc.get('audio_use_dsp')} tap={sc.get('tap')!r}")
    else:
        print("sidecar       none found -- format above is the default, "
              "not something this file asserted")
    print(f"backend       {m['backend']}")
    print()

    head = (f"{'ch':>3}  {'peak':>6} {'pk dBFS':>8}  {'rms dBFS':>9} "
            f"{'ac dBFS':>8}  {'DC':>8} {'DC %FS':>7}  "
            f"{'clipped':>9} {'clip %':>8}  {'zeros %':>8}")
    print(head)
    print("-" * len(head))
    for c in m["per_channel"]:
        print(f"{c['channel']:>3}  {c['peak']:>6} {fmt_db(c['peak_dbfs']):>8}  "
              f"{fmt_db(c['rms_dbfs']):>9} {fmt_db(c['ac_rms_dbfs']):>8}  "
              f"{c['dc_offset']:>8.2f} {c['dc_offset_pct_fs']:>7.3f}  "
              f"{c['clipped']:>9} {c['clipped_pct']:>8.4f}  "
              f"{c['zeros_pct']:>8.3f}")
    print()

    print(f"per-window AC RMS, {m['window_ms']:.0f} ms windows (dBFS), "
          f"silent windows excluded:")
    for c in m["per_channel"]:
        pct = c["window_rms_percentiles_dbfs"]
        if not pct:
            print(f"  {c['channel']}: no non-silent windows")
            continue
        cells = "  ".join(f"p{p}={fmt_db(pct[p]).strip()}" for p in PERCENTILES)
        print(f"  {c['channel']}: {cells}   ({c['windows_counted']} windows)")
    print()

    print(f"silence       leading {m['leading_silence_s']:.3f} s, "
          f"trailing {m['trailing_silence_s']:.3f} s")
    for c in m["per_channel"]:
        if c["silent"]:
            print(f"  WARNING: channel {c['channel']} is effectively silent "
                  f"(AC RMS {fmt_db(c['ac_rms_dbfs']).strip()} dBFS < "
                  f"{SILENCE_DBFS} dBFS)")
    if m["all_silent"]:
        print("  WARNING: every channel is silent. Nothing about levels can be "
              "concluded from this capture.")

    clipped_any = [c for c in m["per_channel"] if c["clipped"] > 0]
    if clipped_any:
        print()
        for c in clipped_any:
            print(f"  NOTE: channel {c['channel']} has {c['clipped']} samples "
                  f"at or beyond full scale ({c['clipped_pct']:.4f}%)")

    print()
    print("accumulator overflow check (adjacent-sample jumps > full scale):")
    for c in m["per_channel"]:
        note = ""
        if c["wrap_suspects"] > 0:
            note = ("   <-- suspect: the int16 accumulator at vp.c:1887 may be "
                    "wrapping")
        print(f"  {c['channel']}: {c['wrap_suspects']} jumps, largest jump "
              f"{c['max_sample_jump']}{note}")


# --------------------------------------------------------------------------
# Compare: the form the headroom prediction actually takes
# --------------------------------------------------------------------------


def print_compare(before, after):
    print("=" * 72)
    print("COMPARISON")
    print("=" * 72)
    print(f"before  {before['file']}  ({before['duration_s']:.2f} s)")
    print(f"after   {after['file']}  ({after['duration_s']:.2f} s)")
    print()

    if before["sample_rate"] != after["sample_rate"]:
        print("WARNING: sample rates differ; these captures are not comparable.")
    if before["channels"] != after["channels"]:
        print("WARNING: channel counts differ; these captures are not "
              "comparable.")

    print("Level shift, after minus before (dB). A pure gain change moves")
    print("every one of these by the same amount.")
    print()
    head = (f"{'ch':>3}  {'d peak':>8}  {'d rms':>8}  {'d ac rms':>9}   "
            + "  ".join(f"{'d p' + str(p):>7}" for p in PERCENTILES))
    print(head)
    print("-" * len(head))

    deltas = []
    for b, a in zip(before["per_channel"], after["per_channel"]):
        row = [f"{a['channel']:>3}"]
        for key in ("peak_dbfs", "rms_dbfs", "ac_rms_dbfs"):
            d = a[key] - b[key]
            deltas.append(d)
            row.append(f"{d:>8.2f}" if abs(d) != float("inf") else f"{'n/a':>8}")
        bp = b["window_rms_percentiles_dbfs"]
        ap = a["window_rms_percentiles_dbfs"]
        for p in PERCENTILES:
            if p in bp and p in ap:
                d = ap[p] - bp[p]
                deltas.append(d)
                row.append(f"{d:>7.2f}")
            else:
                row.append(f"{'n/a':>7}")
        print("  ".join(row))
    print()

    finite = [d for d in deltas if abs(d) != float("inf") and d == d]
    if finite:
        lo, hi = min(finite), max(finite)
        mean = sum(finite) / len(finite)
        print(f"all shifts    mean {mean:+.2f} dB, range {lo:+.2f} .. {hi:+.2f} dB, "
              f"spread {hi - lo:.2f} dB")
        print()
        print("How to read the spread: a uniform gain change (which is what")
        print("removing a headroom divisor predicts) shows a small spread --")
        print("every statistic moves together. A large spread means the change")
        print("altered the *shape* of the signal, not just its level, and")
        print("'2x louder' would then be the wrong description of it.")

    print()
    wb = sum(c["wrap_suspects"] for c in before["per_channel"])
    wa = sum(c["wrap_suspects"] for c in after["per_channel"])
    print(f"wrap suspects before {wb}, after {wa}")
    if wa > wb:
        print("  The change introduced adjacent-sample jumps larger than full")
        print("  scale. Doubling the level into the int16 accumulator at")
        print("  vp.c:1887-1888 can make it wrap, which is audible as harsh")
        print("  distortion and is a different defect from clean clipping.")

    print()
    cb = sum(c["clipped"] for c in before["per_channel"])
    ca = sum(c["clipped"] for c in after["per_channel"])
    print(f"clipped       before {cb}, after {ca}")
    if ca > cb:
        print("  The change introduced clipping. A level gain that saturates is")
        print("  not the same change as a level gain that does not: past full")
        print("  scale the extra gain becomes distortion instead of loudness,")
        print("  and the measured dB shift understates the predicted one.")
    elif cb == ca == 0:
        print("  Neither capture clips, so a measured shift is a real level")
        print("  change and not saturation eating the difference.")

    print()
    print("Caveat that limits every number above: these are two runs of a")
    print("non-deterministic guest. They are not sample-aligned and the")
    print("program material is not identical, so treat a difference under")
    print("about 1 dB as noise. The percentile columns exist because a")
    print("distribution survives misalignment better than a mean does.")


# --------------------------------------------------------------------------
# Self-test. Oracle: arithmetic on signals whose answers are known.
# --------------------------------------------------------------------------


def selftest():
    import struct
    import tempfile

    failures = []

    def check(name, got, want, tol):
        ok = abs(got - want) <= tol
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}: got {got:.4f}, "
              f"want {want:.4f} (+/-{tol})")
        if not ok:
            failures.append(name)

    def write(frames):
        fh = tempfile.NamedTemporaryFile(suffix=".pcm", delete=False)
        for l, r in frames:
            fh.write(struct.pack("<hh", l, r))
        fh.close()
        return fh.name

    rate = 48000

    # 1. Full-scale square wave: peak 0 dBFS, RMS 0 dBFS, no DC.
    print("full-scale square wave (1 kHz):")
    frames = []
    for i in range(rate):
        v = S16_MIN if (i // 24) % 2 else S16_MAX
        frames.append((v, v))
    path = write(frames)
    m = measure(path, window_ms=50)
    c = m["per_channel"][0]
    check("peak dBFS", c["peak_dbfs"], 0.0, 0.001)
    check("rms dBFS", c["rms_dbfs"], 0.0, 0.01)
    check("duration s", m["duration_s"], 1.0, 0.001)
    check("dc offset", c["dc_offset"], -0.5, 1.0)
    os.unlink(path)
    os.path.exists(path + ".json") and os.unlink(path + ".json")

    # 2. Full-scale sine: peak 0 dBFS, RMS -3.01 dBFS.
    print("full-scale sine (1 kHz):")
    frames = []
    for i in range(rate):
        v = int(round(S16_MAX * math.sin(2 * math.pi * 1000 * i / rate)))
        frames.append((v, v))
    path = write(frames)
    c = measure(path, window_ms=50)["per_channel"][0]
    check("peak dBFS", c["peak_dbfs"], 0.0, 0.01)
    check("rms dBFS", c["rms_dbfs"], -3.0103, 0.01)
    check("dc %FS", c["dc_offset_pct_fs"], 0.0, 0.01)
    os.unlink(path)

    # 3. Half-amplitude sine: exactly -6.02 dB below case 2. This is the
    #    headroom prediction's shape, verified on a signal we constructed.
    print("half-scale sine -- the +/-6.02 dB case:")
    frames = []
    for i in range(rate):
        v = int(round((S16_MAX / 2) * math.sin(2 * math.pi * 1000 * i / rate)))
        frames.append((v, v))
    path = write(frames)
    c2 = measure(path, window_ms=50)["per_channel"][0]
    # -3.0103 (sine crest) - 6.0206 (half amplitude) = -9.0309. The amplitude
    # here is S16_MAX/2 = 16383.5 rather than 16384, worth -0.0003 dB more.
    check("rms dBFS", c2["rms_dbfs"], -9.0312, 0.01)
    check("shift vs full-scale sine", c["rms_dbfs"] - c2["rms_dbfs"],
          6.0206, 0.02)
    os.unlink(path)

    # 4. Channels measured independently: L loud, R silent.
    print("asymmetric channels:")
    frames = [(S16_MAX if (i // 24) % 2 == 0 else S16_MIN, 0)
              for i in range(rate)]
    path = write(frames)
    m = measure(path, window_ms=50)
    check("L rms dBFS", m["per_channel"][0]["rms_dbfs"], 0.0, 0.01)
    print(f"  {'ok  ' if m['per_channel'][1]['silent'] else 'FAIL'}  "
          f"R flagged silent: {m['per_channel'][1]['silent']}")
    if not m["per_channel"][1]["silent"]:
        failures.append("R silent flag")
    print(f"  {'ok  ' if not m['all_silent'] else 'FAIL'}  "
          f"file not flagged all-silent: {not m['all_silent']}")
    if m["all_silent"]:
        failures.append("all_silent")
    os.unlink(path)

    # 5. Clipping and DC are counted, not inferred.
    print("clipping and DC:")
    frames = [(S16_MAX, 8192)] * 1000 + [(1000, 8192)] * 1000
    path = write(frames)
    m = measure(path, window_ms=10)
    check("L clipped count", m["per_channel"][0]["clipped"], 1000, 0)
    check("L clipped pct", m["per_channel"][0]["clipped_pct"], 50.0, 0.001)
    check("R dc offset", m["per_channel"][1]["dc_offset"], 8192.0, 0.001)
    check("R dc %FS", m["per_channel"][1]["dc_offset_pct_fs"], 25.0, 0.001)
    check("R ac rms (DC removed)", m["per_channel"][1]["ac_rms"], 0.0, 0.001)
    os.unlink(path)

    # 5b. Negative saturation lands at -32767, not -32768, because
    #     src_float_to_short_array scales a clamped +/-1.0 by 32767. A clip
    #     test written against -32768 counts none of it; this check exists
    #     because the first version of this script had exactly that bug.
    print("negative saturation at -32767 is counted as clipping:")
    frames = [(-32767, -32768)] * 500
    path = write(frames)
    m = measure(path, window_ms=10)
    check("L clipped (-32767)", m["per_channel"][0]["clipped"], 500, 0)
    check("R clipped (-32768)", m["per_channel"][1]["clipped"], 500, 0)
    os.unlink(path)

    # 5c. Wrap suspects: a full-scale sign flip is not something a band-limited
    #     signal does, and the int16 accumulator at vp.c:1887 can produce one.
    print("accumulator wrap detection:")
    frames = [(20000, 0), (-20000, 0)] * 500   # jumps of 40000 > 32768
    path = write(frames)
    m = measure(path, window_ms=10)
    check("L wrap suspects", m["per_channel"][0]["wrap_suspects"], 999, 0)
    check("L max jump", m["per_channel"][0]["max_sample_jump"], 40000, 0)
    check("R wrap suspects (flat)", m["per_channel"][1]["wrap_suspects"], 0, 0)
    os.unlink(path)

    print("a loud clean sine raises no wrap suspects:")
    frames = []
    for i in range(rate):
        v = int(round(S16_MAX * math.sin(2 * math.pi * 1000 * i / rate)))
        frames.append((v, v))
    path = write(frames)
    m = measure(path, window_ms=50)
    check("wrap suspects", m["per_channel"][0]["wrap_suspects"], 0, 0)
    os.unlink(path)

    # 6. Leading and trailing silence.
    print("leading/trailing silence:")
    frames = [(0, 0)] * 4800 + [(10000, 10000)] * 4800 + [(0, 0)] * 9600
    path = write(frames)
    m = measure(path, window_ms=10)
    check("leading s", m["leading_silence_s"], 0.1, 0.0001)
    check("trailing s", m["trailing_silence_s"], 0.2, 0.0001)
    os.unlink(path)

    # 7. Backends agree, so the report does not depend on numpy being present.
    print("numpy vs stdlib backend agreement:")
    global _np
    if _np is None:
        print("  skip  numpy not installed; only the stdlib backend exists here")
    else:
        frames = [(int(3000 * math.sin(i / 7.0)), int(-2000 * math.cos(i / 11.0)))
                  for i in range(20000)]
        path = write(frames)
        with_np = measure(path, window_ms=50)
        saved, _np = _np, None
        try:
            without = measure(path, window_ms=50)
        finally:
            _np = saved
        for i, (a, b) in enumerate(zip(with_np["per_channel"],
                                       without["per_channel"])):
            for key in ("peak", "rms", "ac_rms", "dc_offset", "clipped",
                        "zeros", "wrap_suspects", "max_sample_jump"):
                check(f"ch{i} {key}", float(b[key]), float(a[key]),
                      abs(float(a[key])) * 1e-9 + 1e-9)
            for p in PERCENTILES:
                pa = a["window_rms_percentiles_dbfs"].get(p)
                pb = b["window_rms_percentiles_dbfs"].get(p)
                if pa is not None and pb is not None:
                    check(f"ch{i} p{p}", pb, pa, 0.0001)
        os.unlink(path)

    print()
    if failures:
        print(f"SELFTEST FAILED: {len(failures)} check(s): "
              f"{', '.join(failures)}")
        return 1
    print("SELFTEST PASSED")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Measure an APU PCM capture.",
        epilog="Full scale is 32768; RMS dBFS is relative to a full-scale "
               "square wave, so a full-scale sine reads -3.01.")
    ap.add_argument("capture", nargs="?", help="captured .pcm file")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="measure two captures and report the level shift")
    ap.add_argument("--rate", type=int,
                    help=f"sample rate (default: sidecar, else {DEFAULT_RATE})")
    ap.add_argument("--channels", type=int,
                    help=f"channels (default: sidecar, else {DEFAULT_CHANNELS})")
    ap.add_argument("--window-ms", type=float, default=DEFAULT_WINDOW_MS,
                    help=f"window for per-window RMS (default "
                         f"{DEFAULT_WINDOW_MS:g})")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--selftest", action="store_true",
                    help="verify the measurements against known signals")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.compare:
        results = [measure(p, args.rate, args.channels, args.window_ms)
                   for p in args.compare]
        if args.json:
            json.dump({"before": results[0], "after": results[1]},
                      sys.stdout, indent=2, default=str)
            print()
            return 0
        for r in results:
            print_report(r)
            print()
        print_compare(results[0], results[1])
        return 0

    if not args.capture:
        ap.error("give a capture file, --compare, or --selftest")

    m = measure(args.capture, args.rate, args.channels, args.window_ms)
    if args.json:
        json.dump(m, sys.stdout, indent=2, default=str)
        print()
    else:
        print_report(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
