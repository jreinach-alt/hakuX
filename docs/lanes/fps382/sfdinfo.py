#!/usr/bin/env python3
"""What rate a Sofdec (.sfd, MPEG program stream) movie is made to present at.

    sfdinfo.py <file.sfd> [--bucket S]

Demuxes the video PES (stream 0xE0) and reads the elementary stream:
  - sequence header: size, frame_rate_code -> native frame rate; MPEG-1 or 2
    (a sequence extension, 00 00 01 B5 id 1, marks MPEG-2)
  - every picture header: coding type (I/P/B) and the bytes up to the next
    picture, i.e. how much data the decoder has to chew for that picture
  - the PES PTS span, which with the picture count gives the stream's own
    presentation rate independent of the header's frame_rate_code
Per bucket of S seconds of movie time (default 10) it prints the picture count,
the share of near-empty pictures (< 1% of the median I picture, the way an
encoder codes a repeated frame) and the mean bytes per picture. A stretch that
is natively 10 fps content inside a 30 fps stream shows as 2 of every 3
pictures near-empty; a stream coded at 10 fps shows it in the PTS instead.
"""
import sys

path = sys.argv[1]
bucket = float(sys.argv[sys.argv.index("--bucket") + 1]) if "--bucket" in sys.argv else 10.0
d = open(path, "rb").read()

RATES = {1: 24000 / 1001, 2: 24, 3: 25, 4: 30000 / 1001, 5: 30, 6: 50, 7: 60000 / 1001, 8: 60}


def pts_of(b, i):
    return (((b[i] >> 1) & 7) << 30 | b[i + 1] << 22 | (b[i + 2] >> 1) << 15 |
            b[i + 3] << 7 | b[i + 4] >> 1)


# 1. demux the program stream
es = bytearray()
pts = []          # (es offset, pts in 90 kHz)
streams = {}
i = 0
n = len(d)
while i + 4 <= n:
    if not (d[i] == 0 and d[i + 1] == 0 and d[i + 2] == 1):
        i += 1
        continue
    sid = d[i + 3]
    if sid == 0xBA:                      # pack header
        if (d[i + 4] >> 6) == 1:         # MPEG-2 pack
            i += 14 + (d[i + 13] & 7)
        else:
            i += 12
        continue
    if sid == 0xB9:
        break
    if sid < 0xBB:
        i += 4
        continue
    ln = d[i + 4] << 8 | d[i + 5]
    body = i + 6
    end = body + ln
    streams[sid] = streams.get(sid, 0) + ln
    if sid == 0xE0:
        j = body
        if (d[j] >> 6) == 2:             # MPEG-2 PES header
            flags = d[j + 1]
            hl = d[j + 2]
            if flags & 0x80:
                pts.append((len(es), pts_of(d, j + 3)))
            j += 3 + hl
        else:                            # MPEG-1 PES header
            while d[j] == 0xFF:
                j += 1
            if (d[j] >> 6) == 1:
                j += 2
            if (d[j] >> 4) in (2, 3):
                pts.append((len(es), pts_of(d, j)))
                j += 5 if (d[j] >> 4) == 2 else 10
            else:
                j += 1
        es += d[j:end]
    i = end

print("file %s: %d bytes; streams %s" % (path, n, {hex(k): v for k, v in sorted(streams.items())}))

# 2. the elementary stream
pics = []   # (es offset, type)
seq = None
mpeg2 = False
gops = 0
k = 0
m = len(es)
while True:
    k = es.find(b"\x00\x00\x01", k)
    if k < 0 or k + 8 > m:
        break
    c = es[k + 3]
    if c == 0xB3 and seq is None:
        w = es[k + 4] << 4 | es[k + 5] >> 4
        h = (es[k + 5] & 15) << 8 | es[k + 6]
        seq = (w, h, es[k + 7] >> 4, es[k + 7] & 15)
    elif c == 0xB5 and (es[k + 4] >> 4) == 1:
        mpeg2 = True
    elif c == 0xB8:
        gops += 1
    elif c == 0x00:
        pics.append((k, (es[k + 5] >> 3) & 7))
    k += 4

w, h, asp, frc = seq
rate = RATES.get(frc, 0)
print("video: %dx%d, %s, frame_rate_code %d = %.3f fps; %d pictures, %d GOPs" % (
    w, h, "MPEG-2" if mpeg2 else "MPEG-1", frc, rate, len(pics), gops))
if pts:
    span = (pts[-1][1] - pts[0][1]) / 90000.0
    # pictures between the first and last PTS-bearing packet
    npics = sum(1 for p in pics if pts[0][0] <= p[0] < pts[-1][0])
    print("PTS: first %.3f s, last %.3f s, span %.2f s over %d pictures -> %.3f pictures/s" % (
        pts[0][1] / 90000.0, pts[-1][1] / 90000.0, span, npics, npics / span if span else 0))
print("duration at the header rate: %.1f s" % (len(pics) / rate))

sizes = [(pics[q + 1][0] if q + 1 < len(pics) else m) - pics[q][0] for q in range(len(pics))]
types = [p[1] for p in pics]
isz = sorted(s for s, t in zip(sizes, types) if t == 1)
imed = isz[len(isz) // 2] if isz else 1
tiny = imed * 0.01
print("median I picture %d bytes; 'near-empty' threshold %d bytes" % (imed, tiny))
print("%7s %5s %5s %5s %5s %6s %9s" % ("t(s)", "pics", "I", "P", "B", "empty", "B/pic"))
per = int(round(bucket * rate))
for q in range(0, len(pics), per):
    ts = types[q:q + per]
    ss = sizes[q:q + per]
    print("%7.0f %5d %5d %5d %5d %5.0f%% %9.0f" % (
        q / rate, len(ts), ts.count(1), ts.count(2), ts.count(3),
        100.0 * sum(1 for s in ss if s < tiny) / len(ss), sum(ss) / len(ss)))
