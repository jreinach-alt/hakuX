#!/usr/bin/env python3
"""Selftest for saves.py, titlestate.py and nav.py. No device, no network,
stdlib only (the jobs-selftest runner has no numpy or PIL).

    python3 docs/testing/titles/titlestate_selftest.py

Each check says what world it would fail in, and the must-move checks
(a changed byte, a rejected save) prove the passing ones are not blind.
"""

import contextlib
import io
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import saves  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def make_save(root, tid, files):
    """A save dir as saves.pull writes one: UDATA/TDATA trees + save.json."""
    d = os.path.join(root, tid)
    entries = []
    dirs = set()
    for rel, data in files.items():
        parts = rel.split("/")
        for k in range(2, len(parts)):
            dirs.add("/".join(parts[:k]))
        p = os.path.join(d, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        import hashlib
        entries.append({"path": rel, "dir": False, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "times": [1, 2, 3, 4, 5, 6]})
    for dd in sorted(dirs):
        entries.append({"path": dd, "dir": True, "times": [7, 8, 9, 10, 11, 12]})
    m = {"title_id": tid, "entries": entries, "source": {}}
    m["save_id"] = saves.save_id(m)
    with open(os.path.join(d, "save.json"), "w") as fh:
        json.dump(m, fh)
    return d, m


def test_saves(tmp):
    print("== saves.py: build a disk, read every save back")
    big = bytes(range(256)) * 200                      # 51200 B: 4 clusters of 16 KiB
    many = {f"UDATA/AAAA0001/SAVE{i:04d}/SaveMeta.xbx": f"meta {i}".encode() for i in range(300)}
    many["UDATA/AAAA0001/TitleMeta.xbx"] = b"title A"
    a, ma = make_save(tmp, "AAAA0001", many)           # a 301-entry dir: a 2-cluster chain
    b, mb = make_save(tmp, "BBBB0002", {"UDATA/BBBB0002/TitleMeta.xbx": b"title B",
                                        "UDATA/BBBB0002/0123456789AB/data.bin": big,
                                        "UDATA/BBBB0002/0123456789AB/empty.bin": b"",
                                        "TDATA/BBBB0002/vars.cfg": b"x=1\n"})
    c, mc = make_save(tmp, "CCCC0003", {"UDATA/CCCC0003/TitleMeta.xbx": b"title C",
                                        "TDATA/CCCC0003/prefs.bin": b"\0" * 1024})
    img = os.path.join(tmp, "t.qcow2")
    n = saves.build(img, [a, b, c])
    # 300 directories and 300 files are 600 clusters of 16 KiB, so this one
    # is ~10 MiB; a real title's save is a few files (1.8 MiB for three).
    check("build of 601 entries stays near its cluster count (under 16 MiB)", n < 16 << 20, str(n))
    one = saves.build(os.path.join(tmp, "one.qcow2"), [c])
    check("a disk with one small save is under 2 MiB", one < 2 << 20, str(one))
    for d, m in ((a, ma), (b, mb), (c, mc)):
        bad = saves.verify(img, d)
        check(f"verify {m['title_id']}: every file byte for byte", not bad, "; ".join(bad[:3]))
        out = os.path.join(tmp, "pulled-" + m["title_id"])
        os.makedirs(out)
        pm = saves.pull(img, m["title_id"], out)
        check(f"pull {m['title_id']} gives the same save id", pm["save_id"] == m["save_id"],
              f"{pm['save_id']} vs {m['save_id']}")
        times = {e["path"]: e["times"] for e in pm["entries"]}
        want = {e["path"]: e["times"] for e in m["entries"]}
        check(f"pull {m['title_id']} keeps the raw FATX times",
              all(times.get(p) == t for p, t in want.items()))
    listed = saves.list_titles(saves.open_e(img))
    check("list sees exactly the three titles", sorted(listed) == ["AAAA0001", "BBBB0002", "CCCC0003"],
          str(sorted(listed)))
    check("list counts the 300 save dirs of the chained directory",
          len(listed["AAAA0001"]["UDATA"]["saves"]) == 300)

    print("== saves.py: the checks can fail")
    p = os.path.join(b, "TDATA", "BBBB0002", "vars.cfg")
    with open(p, "wb") as fh:
        fh.write(b"x=2\n")
    mb2 = json.load(open(os.path.join(b, "save.json")))
    import hashlib
    for e in mb2["entries"]:
        if e["path"].endswith("vars.cfg"):
            e["sha256"] = hashlib.sha256(b"x=2\n").hexdigest()
    json.dump(mb2, open(os.path.join(b, "save.json"), "w"))
    check("verify refuses a save whose content differs from the image's",
          saves.verify(img, b) == ["content TDATA/BBBB0002/vars.cfg"], str(saves.verify(img, b)))
    with open(p, "wb") as fh:
        fh.write(b"x=9\n")                             # now also disagrees with save.json
    try:
        saves.load_save(b)
        check("load_save refuses a file that no longer matches save.json", False)
    except saves.SaveError:
        check("load_save refuses a file that no longer matches save.json", True)

    print("== saves.py: the qcow2 is laid out as qemu-img lays one out")
    raw = open(img, "rb").read()
    (magic, ver, _bo, _bs, cbits, size, _cr, l1n, l1o, rco, rcc, _ns, _so) = \
        struct.unpack(">IIQIIQIIQQIIQ", raw[:72])
    order, hlen = struct.unpack(">II", raw[96:104])
    check("header: qcow2 v3, 64 KiB clusters, 8 GiB, refcount order 4",
          (magic, ver, cbits, size, order, hlen) == (0x514649FB, 3, 16, 8 << 30, 4, 104))
    check("header: refcount table at 0x10000, L1 at 0x30000, 16 L1 entries",
          (rco, rcc, l1o, l1n) == (0x10000, 1, 0x30000, 16))
    ncl = len(raw) // 65536
    rcb = struct.unpack(">%dH" % 32768, raw[0x20000:0x30000])
    check("every host cluster has refcount 1, and no other cluster has one",
          all(r == 1 for r in rcb[:ncl]) and not any(rcb[ncl:]))
    l1 = struct.unpack(">16Q", raw[l1o:l1o + 128])
    ok = True
    for e in l1:
        if not e:
            continue
        off = e & 0x00FFFFFFFFFFFE00
        ok &= bool(e >> 63) and off < len(raw)
        for x in struct.unpack(">8192Q", raw[off:off + 65536]):
            if x:
                ok &= bool(x >> 63) and (x & 0x00FFFFFFFFFFFE00) < len(raw)
    check("every L1/L2 entry is COPIED and points inside the file", ok)


def run_ts(env, *args):
    buf = io.StringIO()
    old = dict(os.environ)
    os.environ.update(env)
    try:
        import importlib
        import titlestate
        importlib.reload(titlestate)
        with contextlib.redirect_stdout(buf):
            titlestate.main(list(args))
    finally:
        os.environ.clear()
        os.environ.update(old)
    return buf.getvalue()


def test_registry(tmp):
    print("== titlestate.py: device choice follows the recorded state")
    tdir = os.path.join(tmp, "ts")
    tgt = os.path.join(tmp, "targets.toml")
    with open(tgt, "w") as fh:
        fh.write('[titles."4541005B"]\nname = "Burnout 3"\nroute = "burnout3"\n'
                 'iso = { nova = "b3.iso", thor = "b3.iso" }\n'
                 '[titles."45410083"]\nname = "Black"\nroute = "black"\niso = { thor = "black.iso" }\n'
                 '[titles."5A440004"]\nname = "Alien Hominid"\nroute = "alien-hominid"\niso = { thor = "ah.iso" }\n')
    env = {"TITLESTATE_DIR": tdir, "TITLE_TARGETS": tgt}

    def choose(tid, devices=None):
        a = ["choose", "--title-id", tid] + (["--devices", devices] if devices else [])
        return json.loads(run_ts(env, *a))

    c = choose("4541005B")
    check("nothing known: survey, not a blind first-run", c["variant"] == "survey", str(c))
    check("survey falls back to survey.route", c["route"].endswith("/survey.route"), c["route"])
    run_ts(env, "record", "--device", "thor", "--title-id", "4541005B", "--observed", "none", "--run", "r1")
    c = choose("4541005B")
    check("thor known clean: first-run on thor", (c["device"], c["variant"]) == ("thor", "first-run"), str(c))
    check("first-run picks the title's first-run variant",
          c["route"].endswith("/burnout3.first-run.route"), c["route"])
    run_ts(env, "record", "--device", "nova", "--title-id", "4541005B", "--observed", "created", "--run", "r2")
    c = choose("4541005B")
    check("a profile on nova beats a clean thor: returning on nova",
          (c["device"], c["variant"], c["import"]) == ("nova", "returning", None), str(c))
    c = choose("45410083", "nova,thor")
    check("a title only thor holds is never sent to nova", c["device"] in ("thor",), str(c))

    # the store: a save the devices do not hold is imported, unless rejected
    run_ts(env, "record", "--device", "nova", "--title-id", "4541005B", "--observed", "none", "--run", "r3")
    store = os.path.join(tdir, "saves", "4541005B")
    d, m = make_save(os.path.join(tmp, "st"), "4541005B", {"UDATA/4541005B/TitleMeta.xbx": b"b3"})
    os.makedirs(store)
    os.rename(d, os.path.join(store, m["save_id"]))
    c = choose("4541005B")
    check("no device has a profile, the store has one: import it, returning",
          (c["variant"], c["import"]) == ("returning", m["save_id"]), str(c))
    first = c["device"]
    run_ts(env, "record", "--device", first, "--title-id", "4541005B", "--observed", "rejected",
           "--run", "r4", "--save", m["save_id"])
    c = choose("4541005B")
    other = "thor" if first == "nova" else "nova"
    check("a save rejected on one device is offered to the other",
          (c["device"], c["import"]) == (other, m["save_id"]), str(c))
    run_ts(env, "record", "--device", other, "--title-id", "4541005B", "--observed", "rejected",
           "--run", "r5", "--save", m["save_id"])
    c = choose("4541005B")
    check("rejected everywhere: back to a first-run", c["variant"] == "first-run" and not c["import"], str(c))

    # build-image + pushed: a device given a titles disk knows exactly what is on it
    img = os.path.join(tmp, "thor.qcow2")
    built = json.loads(run_ts(env, "build-image", "--device", "thor", img,
                              "--add", f"4541005B:{m['save_id']}"))
    check("build-image carries the added save", built == {"4541005B": m["save_id"]}, str(built))
    check("the built disk holds it", not saves.verify(img, os.path.join(store, m["save_id"])))
    run_ts(env, "pushed", "--device", "thor", "--image", img, "--device-path", "/x/titles.qcow2",
           "--built-from", json.dumps(built))
    st = json.loads(run_ts(env, "show", "--device", "thor", "--json"))["thor"]
    row = st["titles"]["4541005B"]
    check("pushed: the title is imported, with its save and a time",
          row["profile"] and row["origin"] == "imported" and row["save"] == m["save_id"]
          and row["since_utc"], str(row))
    c = choose("45410083")
    check("a device with a titles disk and no row for a title is known clean",
          (c["device"], c["variant"]) == ("thor", "first-run"), str(c))

    # no-save: a read disk with no save stands in for one, until a harvest finds one
    row = json.loads(run_ts(env, "no-save", "--device", "thor", "--title-id", "4541005B",
                            "--reason", "New Game route", "--run", "r6"))
    check("no-save records its reason", row["save_na"]["reason"] == "New Game route", str(row))
    run_ts(env, "harvest", "--device", "thor", "--title-id", "4541005B", "--image", img, "--run", "r7")
    row = json.loads(run_ts(env, "show", "--device", "thor", "--json"))["thor"]["titles"]["4541005B"]
    check("a harvested save clears no-save", "save_na" not in row and row["save"] == m["save_id"], str(row))

    # a title with one route runs it, whatever the state says
    c = choose("5A440004")
    check("single route, nothing known: the route, not survey",
          c["variant"] == "single" and c["route"].endswith("/alien-hominid.route"), str(c))
    run_ts(env, "record", "--device", "thor", "--title-id", "5A440004", "--observed", "created", "--run", "r8")
    c = choose("5A440004")
    check("single route with a profile: still the route, not survey",
          (c["device"], c["variant"]) == ("thor", "single") and c["route"].endswith("/alien-hominid.route"), str(c))


def test_nav(tmp):
    print("== nav.py: the path taken becomes the route")
    env = dict(os.environ, NAV_DRY="1", NAV_DIR=os.path.join(tmp, "nav"))
    nav = os.path.join(HERE, "nav.py")

    def n(*a):
        return subprocess.run([sys.executable, nav, *a], env=env, capture_output=True, text=True)

    n("start", "burnout3", "--variant", "first-run")
    for step in (["shot", "title"], ["press", "START"], ["shot", "lang"], ["axis", "LY", "min"],
                 ["axis", "LY", "mid"], ["press", "A"], ["mark", "gameplay"],
                 ["play", "axis", "RT", "max"], ["play", "wait", "0.2"], ["shot", "check"],
                 ["play", "axis", "RT", "mid"]):
        r = n(*step)
        if r.returncode:
            check(f"nav.py {' '.join(step)}", False, r.stderr.strip())
    route = n("route").stdout
    lines = [ln.strip() for ln in route.splitlines() if ln.strip() and not ln.startswith("#")]
    gi = lines.index("mark gameplay") if "mark gameplay" in lines else -1
    check("the route has the inputs in order before the mark",
          [ln for ln in lines[:gi] if not ln.startswith(("wait", "shot"))] ==
          ["press START", "axis LY min", "axis LY mid", "press A"], str(lines))
    check("frames before the mark are kept", "shot title" in lines[:gi] and "shot lang" in lines[:gi])
    check("no frame after `mark gameplay`", gi > 0 and not any(ln.startswith("shot") for ln in lines[gi:]),
          str(lines[gi:]))
    check("the play pattern repeats forever",
          lines[gi + 1:] == ["repeat forever {", "axis RT max", "wait 0.2", "axis RT mid", "}"],
          str(lines[gi + 1:]))
    p = os.path.join(tmp, "nav.route")
    open(p, "w").write(route)
    r = subprocess.run(["bash", os.path.join(HERE, "route.sh"), "--check", p], capture_output=True, text=True)
    check("route.sh accepts the emitted route", r.returncode == 0, r.stderr.strip())
    n("end")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        test_saves(os.path.join(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_registry(tmp)
    with tempfile.TemporaryDirectory() as tmp:
        test_nav(tmp)
    print(f"\n{'FAILED: ' + ', '.join(FAILS) if FAILS else 'all checks passed'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
