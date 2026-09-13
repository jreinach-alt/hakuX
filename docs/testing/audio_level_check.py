#!/usr/bin/env python3
"""Check the in-emulator level meter against audio_measure.py, on real PCM.

Why this exists
---------------

There are now two instruments for the audio output level:

  1. `audio_measure.py` over a PCM capture pulled off the device. Authoritative,
     re-analysable with questions nobody has thought of yet, and expensive: it
     needs a marker file armed on the device, a FUSE-backed write from the audio
     thread, an 18-24 MB pull, and a dispatcher that actually honours the
     request. That chain has failed silently three times for three different
     reasons.

  2. The level meter in `hw/xbox/mcpx/apu/apu.c`, which computes the same
     statistics from the same samples at the same tap point and prints them to
     logcat under tag `hakuX-audio`. Cheap enough that a second title costs
     nothing but device time -- and only able to answer the questions compiled
     into it.

A cheap instrument that disagrees with the authoritative one is worse than no
instrument, because its numbers look exactly as usable. This keeps them honest:
it extracts the meter's code **byte-for-byte** out of apu.c, compiles it
standalone, runs it over a capture that `audio_measure.py` has also measured,
and compares. No emulator build, no device, no toolchain beyond `cc`.

It is deliberately an extraction and not a reimplementation. A second copy of
the arithmetic would drift, and the drift would land on whichever number
someone was about to trust.

Usage
-----

    audio_level_check.py CAPTURE.pcm [--keep] [--cc gcc]

Exit status is 1 if any statistic disagrees by more than its tolerance, so it
can gate a commit that touches the meter.

Tolerances, and why they are what they are
------------------------------------------

- Peak, DC, clipped, zeros, wrap suspects and largest jump must match
  **exactly**. They are integer counts or exact ratios computed from the same
  samples; any difference is a bug, not a rounding.
- AC RMS must match within **0.01 dB**. Both sides compute it in double from
  identical sums; the residual is floating-point summation order.
- Window percentiles must match within **0.06 dB**. The meter bins windows at
  0.1 dB rather than sorting them -- an unbounded run cannot keep every window
  on the audio thread -- and reports the bin centre, so half a bin is the
  expected disagreement and the tolerance is half a bin plus a hair.
- The count of counted (non-flat) windows must match **exactly**. This is the
  one that catches a real class of error: `audio_measure.py` drops windows whose
  AC variance is exactly zero rather than binning them at -inf, and a meter that
  counted them instead would report a different p5 while every other number
  still agreed. The published Galleon baseline counts 1,677 of 1,856 windows.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APU_C = os.path.join(REPO, "hw", "xbox", "mcpx", "apu", "apu.c")

# The meter is delimited by its own macro definition and by the function that
# follows it. Both anchors are asserted rather than searched loosely: if either
# moves, this must fail loudly instead of silently testing the wrong bytes.
BEGIN = "#ifdef __ANDROID__\n#define APU_LVL_LOG"
END = "static void se_frame(MCPXAPUState *d)"

HARNESS_HEAD = """#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>
#include <string.h>
"""

HARNESS_TAIL = """
int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s CAPTURE.pcm\\n", argv[0]);
        return 2;
    }
    FILE *fp = fopen(argv[1], "rb");
    if (!fp) {
        perror("open");
        return 1;
    }
    static int16_t block[256][2];
    while (fread(block, sizeof(block), 1, fp) == 1) {
        apu_level_observe(block, 256);
    }
    fclose(fp);
    /* Force one report regardless of the wall-clock cadence the emulator uses. */
    apu_level.last_ms = 1;
    apu_level_report(1 + APU_LVL_REPORT_MS);
    return 0;
}
"""

LINE_RE = re.compile(
    r"level (?P<ch>[LR]): (?P<secs>[-0-9.]+) s\s+"
    r"peak (?P<peak>\d+) \((?P<peakdb>[-0-9.]+) dBFS\)\s+"
    r"acrms (?P<acrms>[-0-9.]+) dBFS\s+"
    r"dc (?P<dc>[-0-9.]+) %FS\s+"
    r"p5/25/50/75/95 (?P<p5>[-0-9.]+)/(?P<p25>[-0-9.]+)/(?P<p50>[-0-9.]+)/"
    r"(?P<p75>[-0-9.]+)/(?P<p95>[-0-9.]+)\s+"
    r"windows (?P<counted>\d+) counted (?P<flat>\d+) flat\s+"
    r"clipped (?P<clipped>\d+)\s+zeros (?P<zeros>\d+)\s+"
    r"wrap (?P<wrap>\d+)\s+maxjump (?P<maxjump>\d+)")


def extract(cc, workdir):
    src = open(APU_C).read()
    if BEGIN not in src:
        sys.exit("cannot find the meter's opening anchor in %s -- it has been "
                 "renamed or removed, and this check is testing nothing" % APU_C)
    if END not in src:
        sys.exit("cannot find the meter's closing anchor (%r) in %s" % (END, APU_C))
    body = src[src.index(BEGIN):src.index(END)]
    if "apu_level_observe" not in body or "apu_level_report" not in body:
        sys.exit("the extracted region does not contain the meter; anchors are stale")

    c_path = os.path.join(workdir, "apu_level_extracted.c")
    bin_path = os.path.join(workdir, "apu_level_extracted")
    with open(c_path, "w") as f:
        f.write(HARNESS_HEAD)
        f.write("\n/* Extracted verbatim from hw/xbox/mcpx/apu/apu.c. Do not edit. */\n\n")
        f.write(body)
        f.write(HARNESS_TAIL)
    # -Werror on purpose: the meter runs on the audio thread of a shipping
    # build, and a warning there is worth failing a check over.
    cmd = [cc, "-O2", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
           "-o", bin_path, c_path, "-lm"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        sys.exit("the extracted meter does not compile cleanly")
    return c_path, bin_path


def run_meter(bin_path, pcm):
    p = subprocess.run([bin_path, pcm], capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        sys.exit("the extracted meter failed on %s" % pcm)
    out = {}
    for line in p.stderr.splitlines():
        m = LINE_RE.search(line)
        if m:
            out[m.group("ch")] = m.groupdict()
    if set(out) != {"L", "R"}:
        sys.stderr.write(p.stderr)
        sys.exit("could not parse both channels out of the meter's output")
    return out


def run_reference(pcm):
    p = subprocess.run([sys.executable,
                        os.path.join(HERE, "audio_measure.py"), pcm, "--json"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        sys.exit("audio_measure.py failed on %s" % pcm)
    return json.loads(p.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("--cc", default=os.environ.get("CC", "cc"))
    ap.add_argument("--keep", action="store_true",
                    help="keep the extracted .c and binary for inspection")
    args = ap.parse_args()

    workdir = tempfile.mkdtemp(prefix="apu-level-check-")
    c_path, bin_path = extract(args.cc, workdir)
    meter = run_meter(bin_path, args.capture)
    ref = run_reference(args.capture)

    # audio_measure.py --json shape: per_channel is a list, index 0 = L, and
    # each entry carries its own window percentiles and counted-window total.
    chans = ref["per_channel"]
    names = ["L", "R"]
    failures = []
    rows = []

    for i, name in enumerate(names):
        r = chans[i]
        m = meter[name]
        pct = r.get("window_rms_percentiles_dbfs")

        def check(label, got, want, tol, integer=False):
            if want is None:
                rows.append((name, label, got, "n/a", "skip"))
                return
            if integer:
                ok = int(got) == int(want)
                delta = int(got) - int(want)
            else:
                ok = abs(float(got) - float(want)) <= tol
                delta = float(got) - float(want)
            rows.append((name, label, got, want, "ok" if ok else "FAIL"))
            if not ok:
                failures.append("%s %s: meter %s vs reference %s (delta %s, "
                                "tolerance %s)" % (name, label, got, want,
                                                   delta, tol))

        check("peak", m["peak"], r["peak"], 0, integer=True)
        # The meter prints two decimals, so compare against the reference
        # rounded the same way: 0.01 dB is the print resolution, not a
        # disagreement in the arithmetic.
        check("ac_rms dBFS", m["acrms"], round(r["ac_rms_dbfs"], 2), 0.005)
        check("dc %FS", m["dc"], round(r["dc_offset_pct_fs"], 3), 0.0005)
        check("clipped", m["clipped"], r["clipped"], 0, integer=True)
        check("zeros", m["zeros"], r["zeros"], 0, integer=True)
        check("wrap", m["wrap"], r["wrap_suspects"], 0, integer=True)
        check("maxjump", m["maxjump"], r["max_sample_jump"], 0, integer=True)
        check("windows counted", m["counted"], r["windows_counted"], 0,
              integer=True)
        if pct:
            for p in (5, 25, 50, 75, 95):
                check("p%d" % p, m["p%d" % p], pct[str(p)], 0.06)

    width = max(len(r[1]) for r in rows)
    for ch, label, got, want, verdict in rows:
        print("%s  %-*s  meter %12s   reference %12s   %s"
              % (ch, width, label, got, want, verdict))

    if not args.keep:
        for f in (c_path, bin_path):
            try:
                os.unlink(f)
            except OSError:
                pass
        try:
            os.rmdir(workdir)
        except OSError:
            pass
    else:
        print("\nkept: %s" % workdir)

    if failures:
        print("\n%d DISAGREEMENT(S):" % len(failures))
        for f in failures:
            print("  " + f)
        return 1
    print("\nthe in-emulator meter agrees with audio_measure.py on every "
          "statistic, within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
