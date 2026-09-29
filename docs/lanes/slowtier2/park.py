#!/usr/bin/env python3
"""Park #462 phase 2b's Thor soaks for hostops' cold slots (host-tools/coldslot.sh).

Writes one request per run under $DISPATCH_DIR/parked/slowtier2-cold-20260928/,
in the shape request.sh writes (docs/testing/request.sh, the json.dump near
"THE QUEUED RECORD"), and prints the ids in order. Run once from the lane's
worktree: `python3 docs/lanes/slowtier2/park.py <ref>`. It refuses to run
twice (a second set would double the device time).
"""
import datetime, json, os, random, sys, time

D = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"),
                 "parked", "slowtier2-cold-20260928")
RT = os.path.join(os.path.dirname(__file__), "..", "..", "testing", "titles", "routes")
REF = sys.argv[1]
COLD = "; needs a COLD start (xo <= 50 C, battery <= 36 C)"

# (short, title, seconds, route, purpose), in the order they decide things.
# seconds: the reading's own for runs 1-5 (the route reaches the mark at
# 159-493 s); 420 for the three re-measures (marks at 197-244 s).
RUNS = [
    ("otogi", "46530002-Otogi_Myth_of_Demons.xiso.iso", 550, "otogi",
     "#462 phase 2b run 1 (the pilot): Otogi perflog soak on master. The renderer split "
     "for the renderer-side group (renderer idle 9% in titleroutes-1129571): PFIFO CPU vs "
     "GPU vs downloads vs compiles"),
    ("mm3", "4D53002A-Midtown_Madness_3.xiso.iso", 580, "midtown-madness-3.returning",
     "#462 phase 2b run 2: Midtown Madness 3 perflog soak on master. Is 3.1 fps the title "
     "or a pause (the reading started warm), and is the vCPU's 92 ms/frame off-CPU its "
     "pfifo.lock wait (Lw)"),
    ("black", "45410083-Black.xiso.iso", 760, "black.returning",
     "#462 phase 2b run 3: Black perflog soak on master. vCPU off-CPU 42 ms/frame and "
     "TLB resets on other threads 17.8 ms/frame (#548): does master move them"),
    ("burnout", "41430006-Burnout.xiso.iso", 460, "burnout",
     "#462 phase 2b run 4: Burnout perflog soak on master. The renderer split for a "
     "second renderer-side title, and the 56% zero-filled audio"),
    ("alias", "41430016-Alias.xiso.iso", 450, "alias",
     "#462 phase 2b run 5: Alias perflog soak on master. vCPU on-CPU 95%: is it still "
     "guest-side on master, and what the renderer rows beside it show"),
    ("pgr", "4D530003-Project_Gotham_Racing.xiso.iso", 420, "pgr.returning",
     "#462 phase 2b re-measure 6: PGR perflog soak on master; the reading (a593d8eb85) "
     "predates #479/#518/#528/#536"),
    ("crash", "56550036-Crash_Twinsanity.xiso.iso", 420, "crash-twinsanity",
     "#462 phase 2b re-measure 7: Crash Twinsanity perflog soak on master; the reading "
     "(a593d8eb85) predates #479/#518/#528/#536"),
    ("bloodrayne", "4D4A0001-BloodRayne.xiso.iso", 420, "bloodrayne",
     "#462 phase 2b re-measure 8: BloodRayne perflog soak on master; the reading "
     "(e884ad260e) predates #479/#518/#528/#536; also its 4,234 kicks/s"),
]

os.makedirs(D, exist_ok=True)
if any(f.endswith(".req") and "lane.slowtier2" in f for f in os.listdir(D)):
    sys.exit("already parked in %s" % D)
now = int(time.time())
for k, (short, title, sec, route, purpose) in enumerate(RUNS):
    rid = "1-%d-lane.slowtier2-%s%d" % (now + k, short, random.randint(100000, 999999))
    req = {
        "id": rid, "requester": "lane.slowtier2", "purpose": purpose + COLD,
        "program": "pgraph", "suites": [], "tests": [], "skip_tests": [],
        "ref": REF, "arm": "company", "runs": 1,
        "title": title, "seconds": sec, "device": "thor",
        "pull_glob": "", "audio_capture": "", "base_iso": "",
        "perflog": "true", "only_tests": [],
        "env": ["PERF_REGIMEN=max"], "frames_every": 0,
        "route_name": route,
        "route": open(os.path.join(RT, route + ".route")).read(),
        "expect": "", "expect_sha": "",
        "no_expect": "attribution soak (#462), not an A/B arm",
        "queued_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    text = json.dumps(req, indent=2)
    json.loads(text)
    p = os.path.join(D, rid + ".req")
    with open(p + ".tmp", "w") as f:
        f.write(text)
    os.rename(p + ".tmp", p)
    print(k + 1, rid, title, sec, route)
