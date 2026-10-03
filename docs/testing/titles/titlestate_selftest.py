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


class FakeAdb:
    """titlestate.Adb against a directory: files/x1box is FS, x1box_prefs.xml
    a string. A push leaves 0644 as adb does (the #622 crash)."""

    def __init__(self, fs, x):
        self.fs, self.x, self.calls = fs, x, []
        self.prefs_xml = ('<?xml version="1.0"?>\n<map>\n    <string name="hddPath">'
                          f'{x}/hdd.img</string>\n</map>\n')
        self.nochmod = False

    def p(self, path):
        return path.replace(self.x, self.fs)

    def sh(self, cmd, timeout=60, data=None):
        self.calls.append(cmd)
        return ""

    def sha(self, path):
        import titlestate
        return titlestate.sha256_file(self.p(path)) if os.path.exists(self.p(path)) else ""

    def nbytes(self, path):
        return os.path.getsize(self.p(path)) if os.path.exists(self.p(path)) else -1

    def mode(self, path):
        return "%o" % (os.stat(self.p(path)).st_mode & 0o777) if os.path.exists(self.p(path)) else ""

    def pull(self, src, dst, want):
        import shutil
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(self.p(src), dst)
        return self.sha(src) == want

    def make_660(self, path):
        if not self.nochmod:
            os.chmod(self.p(path), 0o660)
        return self.mode(path) == "660"

    def push(self, src, dst):
        import shutil, titlestate
        self.calls.append("push " + dst)
        shutil.copyfile(src, self.p(dst))
        os.chmod(self.p(dst), 0o644)
        if not self.make_660(dst):
            raise SystemExit("not 660")
        if titlestate.sha256_file(self.p(dst)) != titlestate.sha256_file(src):
            raise SystemExit("sha")

    def prefs(self):
        return self.prefs_xml

    def set_hdd(self, want):
        import titlestate
        was = titlestate.re_hdd(self.prefs_xml)
        self.prefs_xml = self.prefs_xml.replace(f">{was}<", f">{want}<")
        return was


def test_goldens(tmp):
    """lane.savestate433: one golden profile per title; a run's disk is
    composed from the goldens; a route's declared state must match it.
    Each guard has the void it closes reproduced first."""
    print("== titlestate.py goldens: every run starts from the golden, not the last harvest")
    os.environ["TITLESTATE_DIR"] = os.path.join(tmp, "ts")
    os.environ["DISPATCH_DIR"] = os.path.join(tmp, "dispatch")
    os.makedirs(os.environ["DISPATCH_DIR"])
    import importlib
    import titlestate as ts
    importlib.reload(ts)
    TRON, GTA = "42560001", "54540082"
    fix = os.path.join(tmp, "fix")
    # Tron's two states: a disk with its autosaves (Auto Load first on the
    # menu) and the bare title data (New Game first). The 10-02 18:46 void
    # was the second meeting a route written on the first.
    gold_d, gold = make_save(os.path.join(fix, "g"), TRON, {
        f"UDATA/{TRON}/TitleMeta.xbx": b"Tron", f"UDATA/{TRON}/3CE27F2A2215/SaveMeta.xbx": b"SaveGame01introb",
        f"TDATA/{TRON}/prefs.bin": b"\1" * 64})
    bare_d, bare = make_save(os.path.join(fix, "b"), TRON, {f"TDATA/{TRON}/prefs.bin": b"\2" * 64})
    gta_d, gta = make_save(os.path.join(fix, "c"), GTA, {f"UDATA/{GTA}/TitleMeta.xbx": b"GTA SA"})
    # The world the void came from: hdd.img carries Tron's autosave; a run
    # then leaves the bare state on the titles disk.
    hdd = os.path.join(tmp, "hdd.img")
    saves.build(hdd, [gold_d, gta_d])
    ts.seed("nova", hdd, "seed-run")
    g = ts.golden(TRON)
    check("seed proposes the shared disk's save as Tron's golden",
          g and g["save"] == gold["save_id"] and g["status"] == "proposed", str(g))
    played = os.path.join(tmp, "played.qcow2")
    saves.build(played, [bare_d, gta_d])
    ts.after_run("nova", played, "run-1", ts.sha256_file(played))
    row = ts.load("nova")["titles"][TRON]
    check("VOID REPRODUCED: the device registry now names the run's bare save for Tron",
          row["save"] == bare["save_id"], str(row))
    check("  ... which is what the pre-golden disk (wanted()) would carry next",
          ts.wanted(ts.load("nova")).get(TRON) == bare["save_id"])
    want, info = ts.compose("nova", TRON, "returning")
    check("GUARD: the composed disk carries the golden, not the last harvest",
          want.get(TRON) == gold["save_id"] and info["loaded"] == "golden", str(info))
    check("  ... the harvest went to `latest` and the golden is unchanged",
          ts.load_goldens()["titles"][TRON]["latest"]["save"] == bare["save_id"]
          and ts.golden(TRON)["save"] == gold["save_id"])
    want, info = ts.compose("nova", TRON, "first-run")
    check("a first-run disk carries no Tron save, and the other titles' goldens",
          TRON not in want and want.get(GTA) == gta["save_id"] and info["loaded"] == "none", str(want))

    # targets.toml's canonical id vs the disk's: DOA3 is 4D53002D in targets,
    # 54430001 on the disk. A first-run under the targets id keeps the save.
    want, _ = ts.compose("nova", "4D53002D", "first-run")
    check("VOID REPRODUCED: with no alias, a first-run under the targets id keeps the disk id's save",
          want.get(GTA) == gta["save_id"])
    ts.set_alias("4D53002D", GTA)
    want, info = ts.compose("nova", "4D53002D", "first-run")
    check("GUARD: with the alias, the first-run disk drops it",
          GTA not in want and info["disk_title_id"] == GTA, str(info))
    check("  ... and the golden is found under the targets id", ts.golden("4D53002D")["save"] == gta["save_id"])
    # The status page and choose() list the store under the targets id: with
    # no alias lookup Gunvalkyrie (49470017 / 5345000B) read "no save" and was
    # listed for the #397 profile-save stage while the store held one.
    check("the store's saves are listed under the targets id",
          ts.store_saves("4D53002D") == ts.store_saves(GTA) != [], str(ts.store_saves("4D53002D")))
    check("  ... and each one's directory is found under it",
          all(ts.store_dir("4D53002D", s) == ts.store_dir(GTA, s) for s in ts.store_saves(GTA)))
    with ts.Goldens() as gl:
        gl["aliases"] = {}

    print("== titlestate.py plan(): a disk a run wrote to is never booted again")
    st = {"device": "nova", "titles": {}, "rejected": {},
          "image": {"sha256": "aa", "device_sha256": "bb", "built_from": {TRON: gold["save_id"],
                                                                         GTA: gta["save_id"]}}}
    os.makedirs(os.path.join(tmp, "ts", "devices"), exist_ok=True)
    reg = os.path.join(tmp, "ts", "devices", "nova.json")
    json.dump(st, open(reg, "w"))
    p = ts.plan("nova", 1000, "bb", title_id=TRON, state="returning")
    check("VOID REPRODUCED + GUARD: harvested but written (device sha != pushed sha): build, not keep",
          p["action"] == "build", str(p))
    st["image"]["device_sha256"] = "aa"
    json.dump(st, open(reg, "w"))
    check("a pristine disk of exactly the composed goldens is kept",
          ts.plan("nova", 1000, "aa", title_id=TRON, state="returning")["action"] == "keep")
    check("  ... and rebuilt for a first-run of the same title",
          ts.plan("nova", 1000, "aa", title_id=TRON, state="first-run")["action"] == "build")
    st["image"]["last_pull"] = {"sha256": "cc", "errors": {TRON: "short read"}}
    json.dump(st, open(reg, "w"))
    p = ts.plan("nova", 1000, "cc", title_id=TRON, state="returning")
    check("a disk whose harvest failed is preserved whole, not kept and booted", p["action"] == "preserve", str(p))
    ts.preserved("nova", "cc", os.path.join(tmp, "kept.qcow2"))
    check("  ... after which it is rebuilt",
          ts.plan("nova", 1000, "cc", title_id=TRON, state="returning")["action"] == "build")
    p = ts.plan("nova", 1000, "cc", title_id="4D53FFFF", state="returning")
    check("a returning run of a title with no golden is refused before the push",
          p["action"] == "refuse" and "no golden" in p["reason"], str(p))

    print("== titlestate.py goldens: only promote replaces one; nothing is deleted")
    try:
        ts.set_golden(TRON, bare["save_id"], by="t", how="t")
        check("set_golden over an existing golden is refused", False)
    except SystemExit:
        check("set_golden over an existing golden is refused", True)
    r = ts.first_run_saved(TRON, bare["save_id"], "run-2")
    check("a first-run's profile-saved never replaces an existing golden",
          not r["changed"] and ts.golden(TRON)["save"] == gold["save_id"])
    ts.promote(TRON, "owner", latest=True, note="test")
    rec = ts.load_goldens()["titles"][TRON]
    check("promote --latest replaces it, and the old one is in history",
          rec["golden"]["save"] == bare["save_id"] and rec["golden"]["status"] == "golden"
          and rec["history"][-1]["save"] == gold["save_id"], str(rec))
    check("  ... both saves are still in the store",
          all(os.path.isdir(ts.store_dir(TRON, s)) for s in (gold["save_id"], bare["save_id"])))
    # Castlevania, 10-01 17:01: the golden it would have had (its newest
    # harvest) is title data only, and the returning route took New Game.
    try:
        ts.compose("nova", TRON, "returning")
        check("VOID REPRODUCED + GUARD: a returning disk from a settings-only golden is refused", False)
    except ts.NoGolden as e:
        check("VOID REPRODUCED + GUARD: a returning disk from a settings-only golden is refused",
              "no save directory" in str(e) and "# state: any" in str(e), str(e))
    ts.promote(TRON, "owner", save=gold["save_id"])
    check("  ... promoting the save with a save directory back clears it",
          ts.compose("nova", TRON, "returning")[1]["save"] == gold["save_id"])
    # propose-all prefers a harvest with a save directory over a newer one
    # without, and a refresh moves only a proposed golden.
    cv1_d, cv1 = make_save(os.path.join(fix, "cv1"), "4D53AAAA", {
        "UDATA/4D53AAAA/TitleMeta.xbx": b"CV", "UDATA/4D53AAAA/33682ED35D55/SaveMeta.xbx": b"save data"})
    cv2_d, cv2 = make_save(os.path.join(fix, "cv2"), "4D53AAAA", {"UDATA/4D53AAAA/TitleMeta.xbx": b"CV2"})
    ts.import_save(cv1_d)
    ts.import_save(cv2_d)
    ts.set_golden("4D53AAAA", cv2["save_id"], by="old propose", how="propose", status="proposed")
    ts.note_latest("4D53AAAA", cv2["save_id"], "run-c", "nova")
    ts.propose_all("selftest", refresh=True)
    check("propose-all --refresh moves a proposed golden to the harvest with a save directory",
          ts.golden("4D53AAAA")["save"] == cv1["save_id"], str(ts.golden("4D53AAAA")))
    ts.promote("4D53AAAA", "owner", save=cv2["save_id"])
    ts.propose_all("selftest", refresh=True)
    check("  ... and never moves a confirmed one", ts.golden("4D53AAAA")["save"] == cv2["save_id"])
    new_d, new = make_save(os.path.join(fix, "n"), "4D53EEEE", {"UDATA/4D53EEEE/TitleMeta.xbx": b"new"})
    tid, sid = ts.import_save(new_d)
    r = ts.first_run_saved(tid, sid, "run-3", route="x.first-run")
    check("a first-run's profile-saved on a title with no golden makes it the golden",
          r["changed"] and ts.golden(tid)["how"] == "first-run" and ts.golden(tid)["status"] == "golden")
    bad_d, bad = make_save(os.path.join(fix, "x"), "4D53DDDD", {"UDATA/4D53DDDD/TitleMeta.xbx": b"x"})
    with open(os.path.join(bad_d, "UDATA", "4D53DDDD", "TitleMeta.xbx"), "wb") as fh:
        fh.write(b"y")
    try:
        ts.import_save(bad_d)
        check("MUST MOVE: a save whose bytes differ from its save.json is not imported", False)
    except SystemExit:
        check("MUST MOVE: a save whose bytes differ from its save.json is not imported", True)
    # propose-all: the newest harvest that verifies.
    p1_d, p1 = make_save(os.path.join(fix, "p1"), "4D53CCCC", {"UDATA/4D53CCCC/TitleMeta.xbx": b"old"})
    p2_d, p2 = make_save(os.path.join(fix, "p2"), "4D53CCCC", {"UDATA/4D53CCCC/TitleMeta.xbx": b"new"})
    ts.import_save(p1_d)
    ts.import_save(p2_d)
    ts.note_latest("4D53CCCC", p2["save_id"], "run-9", "thor")
    with open(os.path.join(ts.store_dir("4D53CCCC", p2["save_id"]), "UDATA", "4D53CCCC", "TitleMeta.xbx"), "wb") as fh:
        fh.write(b"rot")
    out = dict((t, s) for t, s, _ in ts.propose_all("selftest"))
    check("propose-all skips a newest harvest that no longer verifies, proposes the next",
          out.get("4D53CCCC") == p1["save_id"] and ts.golden("4D53CCCC")["status"] == "proposed", str(out))

    print("== titlestate.py resolve-route: the declared state must match the composed disk")
    rd = os.path.join(tmp, "routes")
    os.makedirs(rd)
    for n, body in (("fam.returning", "# state: returning\npress A\n"),
                    ("fam.first-run", "# state: first-run\npress START\n"),
                    ("ret-only.returning", "# state: returning\npress A\n"),
                    ("tron-newgame", "# Tron New Game\n# state: returning\npress A\n"),
                    ("bare", "# a route with no state line\npress A\n"),
                    ("survey", "# state: any\npress A\n")):
        open(os.path.join(rd, n + ".route"), "w").write(body)
    r = ts.resolve_route("fam", TRON, "nova", rd)
    check("a family resolves to .returning when the title has a golden",
          r["route_name"] == "fam.returning" and not r["refuse"], str(r))
    r = ts.resolve_route("fam", "4D53BBBB", "nova", rd)
    check("  ... and to .first-run when it has none", r["route_name"] == "fam.first-run" and not r["refuse"], str(r))
    r = ts.resolve_route("fam", "4D53AAAA", "nova", rd)
    check("  ... and to .first-run when its golden is title data only (Black, GoldenEye, 10-02)",
          r["route_name"] == "fam.first-run" and not r["refuse"], str(r))
    # Star Wars Ep. III, 10-03 08:12: its route was confirmed twice on a disk
    # carrying its settings-only golden, was headed `returning`, and was
    # refused; the reason named no way forward, so the queue dropped it.
    open(os.path.join(rd, "sw3.route"), "w").write("# state: returning\npress A\n")
    open(os.path.join(rd, "sw3-any.route"), "w").write("# state: any\npress A\n")
    r = ts.resolve_route("sw3", "4D53AAAA", "nova", rd)
    check("a returning route on a settings-only golden is refused, and the reason names `# state: any`",
          bool(r["refuse"]) and "no save directory" in r["refuse"] and "# state: any" in r["refuse"], str(r))
    r = ts.resolve_route("sw3-any", "4D53AAAA", "nova", rd)
    check("  ... the same route headed `any` queues",
          not r["refuse"] and r["state"] == "any", str(r))
    check("  ... and its disk carries that golden unchanged",
          ts.compose("nova", "4D53AAAA", "any")[1]["save"] == cv2["save_id"])
    r = ts.resolve_route("ret-only.returning", "4D53BBBB", "nova", rd)
    check("VOID REPRODUCED + GUARD: a returning route on a title with no golden is refused",
          bool(r["refuse"]) and "golden" in r["refuse"], str(r))
    r = ts.resolve_route("bare", TRON, "nova", rd)
    check("a route that declares no state is refused", bool(r["refuse"]) and "declares no" in r["refuse"], str(r))
    r = ts.resolve_route("tron-newgame", TRON, "nova", rd)
    check("a returning route on a title with a golden is accepted", r["state"] == "returning" and not r["refuse"])
    r = ts.resolve_route("tron-newgame", None, "nova", rd)
    check("  ... refused when the title cannot be identified", bool(r["refuse"]))
    check("an `any` route needs no golden", not ts.resolve_route("survey", "4D53BBBB", "nova", rd)["refuse"])
    with ts.Registry("thor") as st2:
        st2["rejected"][TRON] = [gold["save_id"]]
    r = ts.resolve_route("tron-newgame", TRON, "thor", rd)
    check("a golden the pinned device rejected does not count", bool(r["refuse"]) and "rejected" in r["refuse"], str(r))

    print("== titlestate.py prepare/release: a held session boots the composed disk")
    x = "/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box"
    fs = os.path.join(tmp, "devfs")
    os.makedirs(fs)
    import shutil
    shutil.copyfile(hdd, os.path.join(fs, "hdd.img"))
    adb = FakeAdb(fs, x)
    quiet = lambda m: None
    try:
        ts.prepare("nova", "4D53BBBB", "returning", "held-0", adb, quiet)
        check("a held returning session of a title with no golden is refused", False)
    except SystemExit as e:
        check("a held returning session of a title with no golden is refused", "golden" in str(e), str(e))
    check("  ... before any push and before hddPath moved",
          not any(c.startswith("push") for c in adb.calls) and f"{x}/hdd.img" in adb.prefs_xml)
    rec = ts.prepare("nova", TRON, "returning", "held-1", adb, quiet)
    check("prepare points hddPath at titles.qcow2", f"{x}/titles.qcow2" in adb.prefs_xml)
    check("  ... with Tron's golden loaded, recorded",
          rec["loaded"] == "golden" and rec["save"] == gold["save_id"] and rec["state"] == "returning", str(rec))
    check("  ... the disk is mode 660, not the 0644 a push leaves",
          adb.mode(f"{x}/titles.qcow2") == "660")
    check("  ... and the marker holds hdd.img, the dispatcher's own",
          open(ts.marker("nova")).read() == f"{x}/hdd.img")
    check("  ... the golden verifies on the device's disk",
          not saves.verify(os.path.join(fs, "titles.qcow2"), ts.store_dir(TRON, gold["save_id"])))
    saves.build(os.path.join(fs, "titles.qcow2"), [bare_d, gta_d])     # the session saved
    out = ts.release("nova", "held-1", adb, quiet)
    check("release harvests what the session wrote, to latest",
          out["harvested"] and ts.load_goldens()["titles"][TRON]["latest"]["save"] == bare["save_id"], str(out))
    check("  ... leaves the golden alone", ts.golden(TRON)["save"] == gold["save_id"])
    check("  ... and puts hddPath back on hdd.img, marker gone",
          f"{x}/hdd.img" in adb.prefs_xml and not os.path.exists(ts.marker("nova")))
    adb.nochmod = True
    try:
        ts.prepare("nova", TRON, "first-run", "held-2", adb, quiet)
        check("a disk that cannot be made 660 fails the prepare", False)
    except SystemExit:
        check("a disk that cannot be made 660 fails the prepare", f"{x}/hdd.img" in adb.prefs_xml)
    for k in ("TITLESTATE_DIR", "DISPATCH_DIR"):
        os.environ.pop(k, None)


def test_route_headers():
    """Every route on the branch declares the state it was written for."""
    print("== routes/: every route file declares `# state:`")
    import titlestate as ts
    rd = os.path.join(HERE, "routes")
    missing = [f for f in sorted(os.listdir(rd)) if f.endswith(".route")
               and (ts.route_state(os.path.join(rd, f)) or "invalid").startswith("invalid")]
    check("every routes/*.route has a valid `# state:` line", not missing, ", ".join(missing))
    bad = [f for f in sorted(os.listdir(rd)) if f.endswith((".first-run.route", ".returning.route"))
           and ts.route_state(os.path.join(rd, f)) != f.split(".")[-2]]
    check("  ... and a .first-run/.returning file declares its own variant", not bad, ", ".join(bad))


def test_nav_disk(tmp):
    """A held nav.py session on a device never starts on whatever hdd.img
    holds without saying so (gap 3: held sessions bypassed the titles disk)."""
    print("== nav.py start: a held session names its title, or says --hdd-img")
    env = dict(os.environ, NAV_DIR=tmp, SERIAL="ee317437", PATH="/nonexistent")
    env.pop("NAV_DRY", None)
    nav = os.path.join(HERE, "nav.py")
    r = subprocess.run([sys.executable, nav, "start", "tron2", "--variant", "returning"], env=env,
                       capture_output=True, text=True)
    check("start with no title and no --hdd-img is refused before any adb call",
          r.returncode == 2 and "--title-id" in r.stderr and not os.path.exists(os.path.join(tmp, "current")),
          r.stderr.strip()[-200:])
    r = subprocess.run([sys.executable, nav, "start", "tron2", "--hdd-img"], env=env,
                       capture_output=True, text=True)
    sj = os.path.join(r.stdout.strip(), "session.json") if r.returncode == 0 else ""
    check("  ... --hdd-img starts it, and the session records hand play on hdd.img",
          bool(sj) and json.load(open(sj))["hdd"]["path"] == "hdd.img", r.stderr.strip()[-200:])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        test_goldens(tmp)
    with tempfile.TemporaryDirectory() as tmp:
        test_nav_disk(tmp)
    test_route_headers()
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
