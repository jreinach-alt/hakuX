#!/usr/bin/env python3
"""Cut an s16le 48 kHz stereo capture to a WAV file, for listening.

  pcm_wav.py PCM OUT.wav [--from SECONDS] [--to SECONDS]

Times are seconds into the capture (pcm_windows.py's start_s column).
"""
import sys
import wave

RATE, CH, BYTES = 48000, 2, 2


def main():
    src, out = sys.argv[1], sys.argv[2]
    a = sys.argv[3:]
    t0, t1 = 0.0, None
    while a:
        k = a.pop(0)
        v = float(a.pop(0))
        if k == "--from":
            t0 = v
        elif k == "--to":
            t1 = v
    frame = CH * BYTES
    with open(src, "rb") as f:
        f.seek(int(t0 * RATE) * frame)
        data = f.read(-1 if t1 is None else int((t1 - t0) * RATE) * frame)
    with wave.open(out, "wb") as w:
        w.setnchannels(CH)
        w.setsampwidth(BYTES)
        w.setframerate(RATE)
        w.writeframes(data[: len(data) // frame * frame])
    print(f"{out}: {len(data) // frame / RATE:.1f} s from {t0:.1f} s")


if __name__ == "__main__":
    main()
