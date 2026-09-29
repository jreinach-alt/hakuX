#!/usr/bin/env python3
"""The per-device title-state registry: which titles have a profile on which
handheld, since when, and from which save; and, from that, which device and
which route variant a title run should use.

    titlestate.py show [--device D] [--json]
    titlestate.py record --device D --title-id T --observed OBS --run ID
                         [--save SAVE_ID] [--note TEXT]
    titlestate.py harvest --device D --title-id T --image IMG --run ID
    titlestate.py no-save --device D --title-id T --reason TEXT --run ID
    titlestate.py build-image --device D OUT.qcow2 [--add T:SAVE_ID ...]
    titlestate.py pushed --device D --image OUT.qcow2 --device-path PATH
    titlestate.py plan --device D --device-bytes N [--device-sha SHA]
    titlestate.py seed|after-run --device D --image IMG --run ID [--device-sha SHA]
    titlestate.py rebuild --device D
    titlestate.py choose --title-id T [--devices nova,thor]
    titlestate.py route --title-id T --variant first-run|returning|survey

OBS is what the run SAW, from its frames or its route's marks:

    created    the run made a profile and saved it (a first-run route that
               reached its `mark profile-saved`)
    loaded     the run found a profile and loaded it (a returning route)
    none       the title reported no profile on the disk
    rejected   the title called an imported save damaged or would not load
               it: that save is not portable to this device (a save signed
               with another console's HDD key does this)
    unknown    the run ended before it could tell

WHERE IT LIVES: $TITLESTATE_DIR, default $DISPATCH_DIR/titlestate
(/home/justin/hakux-work/dispatch/titlestate), beside the dispatcher's
per-device prefs cache (.prefs.<device>.xml), because it is the same kind
of thing: a fact about a physical device, written by the host after every
run. It is not in the repo: a commit per title run would be noise on master,
and master is fold-lagged, so a branch copy would be stale by the time a
dispatcher read it. The CODE and the selftest are in the repo.

    devices/<device>.json    per-device state (schema below)
    saves/<TID>/<save_id>/   a save pulled off a disk by saves.py
                             (UDATA/, TDATA/, save.json)
    images/                  titles disks built by build-image

A device's state describes the TITLES DISK on it: a small qcow2 that
build-image makes from the save store and the dispatcher points `hddPath` at
for a title run, leaving the nxdk results disk (hdd.img) to the test discs.
Until a titles disk has been pushed, `image` is null and every title is
`unknown`: the device's hdd.img carries whatever the pass-1 runs left on it.

THE DISPATCHER DRIVES IT (dispatcher.sh, titles_disk_prepare / _after). Before
a title run it asks `plan` with the device file's size and sha256: `seed`
(pull hdd.img once, harvest every title on it), `harvest` (the disk holds
writes no harvest read), `build` (rebuild from the store, push, `pushed`),
or `keep`. After the run it pulls the disk and `after-run` harvests it. A
disk is rebuilt when the store's saves differ from what it was built from,
or it grew past TITLES_DISK_CAP_BYTES (512 MiB); never over a failed harvest
below TITLES_DISK_CEILING_BYTES (4 GiB).

    {"device": "thor",
     "image": {"host_copy": ".../images/thor-<sha12>.qcow2", "sha256": ...,
               "device_path": ".../files/x1box/titles.qcow2",
               "built_from": {"4541005B": "<save_id>"}, "pushed_utc": ...},
     "titles": {"4541005B": {"profile": true, "origin": "created",
                             "since_utc": ..., "save": null | "<save_id>",
                             "by_run": "<request id>", "observed_utc": ...,
                             "observed": "created", "note": ...,
                             "save_na": {"reason": ..., "by_run": ...,
                                         "utc": ...}}},
     "rejected": {"4541005B": ["<save_id>", ...]}}
"""

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import saves  # noqa: E402

DEVICES = ("nova", "thor")
VARIANTS = ("first-run", "returning", "survey")
OBSERVED = ("created", "loaded", "none", "rejected", "unknown")


def root():
    d = os.environ.get("TITLESTATE_DIR")
    if not d:
        d = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"),
                         "titlestate")
    return d


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def targets():
    path = os.environ.get("TITLE_TARGETS", os.path.join(HERE, "targets.toml"))
    with open(path, "rb") as fh:
        return tomllib.load(fh).get("titles", {})


def tid_norm(t):
    t = t.upper()
    if len(t) != 8 or any(c not in "0123456789ABCDEF" for c in t):
        raise SystemExit(f"titlestate: {t!r} is not an 8-hex-digit TitleID")
    return t


class Registry:
    """One device file, read and written under an exclusive lock, replaced
    atomically: two workers finishing at once must not lose either write."""

    def __init__(self, device):
        if device not in DEVICES:
            raise SystemExit(f"titlestate: unknown device {device!r}")
        self.device = device
        self.path = os.path.join(root(), "devices", f"{device}.json")

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.lock = open(self.path + ".lock", "w")
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        self.state = load(self.device)
        return self.state

    def __exit__(self, exc, *_):
        try:
            if exc is None:
                tmp = self.path + ".tmp"
                with open(tmp, "w") as fh:
                    json.dump(self.state, fh, indent=1, sort_keys=True)
                    fh.write("\n")
                os.replace(tmp, self.path)
        finally:
            fcntl.flock(self.lock, fcntl.LOCK_UN)
            self.lock.close()


def load(device):
    path = os.path.join(root(), "devices", f"{device}.json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"device": device, "image": None, "titles": {}, "rejected": {}}


def record(device, tid, observed, run, save=None, note=None):
    if observed not in OBSERVED:
        raise SystemExit(f"titlestate: --observed must be one of {', '.join(OBSERVED)}")
    with Registry(device) as st:
        row = st["titles"].setdefault(tid, {"profile": None})
        prev = row.get("profile")
        row.update(observed=observed, observed_utc=now(), by_run=run)
        if note:
            row["note"] = note
        if observed == "created":
            row.update(profile=True, origin="created", since_utc=now(), save=save)
        elif observed == "loaded":
            row["profile"] = True
            if not prev:            # a profile we did not know about
                row.update(origin=row.get("origin") or "found", since_utc=now())
            if save:
                row["save"] = save
        elif observed == "none":
            row.update(profile=False, origin=None, since_utc=None, save=None)
        elif observed == "rejected":
            bad = row.get("save") or save
            if bad:
                lst = st["rejected"].setdefault(tid, [])
                if bad not in lst:
                    lst.append(bad)
            row.update(profile=False, origin=None, since_utc=None, save=None)
        # unknown: the profile field stays what it was
        return row


def no_save(device, tid, reason, run):
    """Record that T's route needs no save on DEVICE, and why: the disk was
    read and holds no save for T, yet the route reaches gameplay (a New Game
    route, or a title whose only persistent data is settings). This is a
    reading of a disk, never a guess: a later harvest of a real save clears
    it."""
    if not reason:
        raise SystemExit("titlestate: no-save needs --reason")
    with Registry(device) as st:
        row = st["titles"].setdefault(tid, {"profile": None})
        row["save_na"] = {"reason": reason, "by_run": run, "utc": now()}
        return row


def store_dir(tid, save_id):
    return os.path.join(root(), "saves", tid, save_id)


def harvest(device, tid, image, run):
    """Pull T's save off a disk image into the store, and name it as the
    device's current save for T."""
    # Per device and process: both handhelds' workers harvest, and the same
    # title can come off both at once.
    tmp = os.path.join(root(), "saves", tid, f".incoming.{device}.{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        m = saves.pull(image, tid, tmp)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    dest = store_dir(tid, m["save_id"])
    try:
        if not os.path.isdir(dest):
            os.replace(tmp, dest)
    except OSError:
        if not os.path.isdir(dest):     # not the other worker's identical save
            raise
    shutil.rmtree(tmp, ignore_errors=True)
    with Registry(device) as st:
        row = st["titles"].setdefault(tid, {"profile": True, "origin": "found",
                                            "since_utc": now()})
        row.update(save=m["save_id"], harvested_utc=now(), harvested_by=run)
        row.pop("save_na", None)
        if not row.get("profile"):
            row.update(profile=True, origin=row.get("origin") or "found",
                       since_utc=row.get("since_utc") or now())
    return m["save_id"]


def wanted(st):
    """What a titles disk for this state carries: every save the device is
    recorded as holding."""
    return {t: r["save"] for t, r in st["titles"].items() if r.get("profile") and r.get("save")}


def build_image(device, out, add=()):
    """A titles disk for DEVICE: every save the device is recorded as holding,
    plus ADD (T:SAVE_ID pairs to import). Returns built_from."""
    built = wanted(load(device))
    for pair in add:
        t, _, s = pair.partition(":")
        built[tid_norm(t)] = s
    dirs = []
    for t, s in sorted(built.items()):
        d = store_dir(t, s)
        if not os.path.isdir(d):
            raise SystemExit(f"titlestate: no save {t}/{s} in the store")
        dirs.append(d)
    saves.build(out, dirs)
    return built


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pushed(device, image, device_path, built_from):
    """The dispatcher pushed IMAGE to DEVICE_PATH: the device now holds
    exactly the saves it was built from, and nothing else.

    A title's `save_na` survives the push: it says the title needs no save,
    which a disk without one for it does not contradict (status_html.py
    reads it)."""
    sha = sha256_file(image)
    with Registry(device) as st:
        old = st["titles"]
        st["titles"] = {}
        for t, s in built_from.items():
            prev = old.get(t, {})
            imported = prev.get("save") != s
            st["titles"][t] = {"profile": True, "save": s,
                               "origin": "imported" if imported else prev.get("origin", "imported"),
                               "since_utc": now() if imported else prev.get("since_utc", now()),
                               "observed": None, "by_run": None}
        for t, prev in old.items():
            if t not in st["titles"] and prev.get("save_na"):
                st["titles"][t] = {"profile": False, "save": None, "origin": None,
                                   "since_utc": None, "save_na": prev["save_na"]}
        # device_sha256: what the device's file is known to hold, and the
        # only thing plan() compares the device against. The guest writes
        # the disk on every boot, so after a run it moves, and after-run
        # moves it with it once the run's saves are harvested.
        st["image"] = {"host_copy": os.path.abspath(image), "sha256": sha,
                       "device_path": device_path, "built_from": built_from,
                       "pushed_utc": now(), "device_sha256": sha, "last_pull": None}
    return st


def harvest_all(device, image, run):
    """Harvest every title on IMAGE (E:\\UDATA, E:\\TDATA) into the store.
    A save is content-addressed, so a title the run did not touch harvests
    to the id it already had. Returns ({tid: save_id}, {tid: error})."""
    got, errors = {}, {}
    for tid in sorted(saves.list_titles(saves.open_e(image))):
        try:
            got[tid] = harvest(device, tid, image, run)
        except (saves.SaveError, saves.er.ExtractError, OSError) as e:
            errors[tid] = str(e)[:200]
    return got, errors


def seed(device, image, run):
    """The first titles disk for DEVICE carries what its hdd.img holds: every
    title's save on it goes into the store and the registry, so no profile a
    title made on the shared disk is lost by moving title runs off it."""
    got, errors = harvest_all(device, image, run)
    with Registry(device) as st:
        st["seeded"] = {"utc": now(), "run": run, "image_bytes": os.path.getsize(image),
                        "harvested": got, "errors": errors}
    return got, errors


def after_run(device, image, run, device_sha):
    """IMAGE is a pull of DEVICE's titles disk whose sha256 on the device was
    DEVICE_SHA. Harvest it. Only a clean harvest moves device_sha256: a disk
    whose saves did not all come off is never rebuilt over (plan)."""
    if device_sha and sha256_file(image) != device_sha:
        raise SystemExit(f"titlestate: {image} is not the device's disk (sha256 differs)")
    got, errors = harvest_all(device, image, run)
    with Registry(device) as st:
        img = st.get("image") or {}
        img["last_pull"] = {"utc": now(), "run": run, "bytes": os.path.getsize(image),
                            "sha256": device_sha, "harvested": got, "errors": errors}
        if not errors:
            img["device_sha256"] = device_sha
        st["image"] = img
    return {"harvested": got, "errors": errors}


CAP = 512 << 20         # a titles disk grown past this is rebuilt from the store
CEILING = 4 << 30       # ... and past this even over a failed harvest: E: fills near 5 GB


def plan(device, device_bytes, device_sha, cap=CAP, ceiling=CEILING):
    """What the dispatcher does to DEVICE's titles disk before a title run.

        seed      no titles disk yet: harvest hdd.img into the store first
        harvest   the device's disk holds writes no harvest has read
        build     rebuild from the store and push
        keep      boot the disk that is there

    DEVICE_BYTES < 0 means the file is not on the device. Never `build` over
    writes that were not harvested, unless the disk is past CEILING."""
    st = load(device)
    img = st.get("image")
    if not img:
        if not st.get("seeded"):
            return {"action": "seed", "reason": f"{device} has no titles disk and its hdd.img was never harvested"}
        return {"action": "build", "reason": f"{device} has no titles disk yet"}
    if device_bytes < 0:
        return {"action": "build", "reason": "the titles disk is not on the device"}
    if device_sha != img.get("device_sha256"):
        lp = img.get("last_pull") or {}
        if lp.get("sha256") == device_sha and lp.get("errors"):
            if device_bytes > ceiling:
                return {"action": "build", "alert": True,
                        "reason": f"ALERT: {device_bytes} B > ceiling {ceiling} B; rebuilding over "
                                  f"unharvested saves of {', '.join(sorted(lp['errors']))}"}
            return {"action": "keep", "alert": True,
                    "reason": f"harvest of this disk failed for {', '.join(sorted(lp['errors']))} "
                              f"(run {lp.get('run')}); not rebuilding over it"}
        return {"action": "harvest", "reason": "the device's disk changed since its last harvest"}
    want = wanted(st)
    if want != img.get("built_from"):
        diff = sorted(t for t in set(want) | set(img.get("built_from") or {})
                      if want.get(t) != (img.get("built_from") or {}).get(t))
        return {"action": "build", "reason": f"the store's saves differ from the disk's for {', '.join(diff)}"}
    if device_bytes > cap:
        return {"action": "build", "reason": f"the disk grew to {device_bytes} B > cap {cap} B"}
    return {"action": "keep", "reason": "the disk carries the store's saves"}


def rebuild(device, keep=5):
    """Build DEVICE's titles disk from the store into images/, verify every
    save on it, and name it by content. Keeps the newest KEEP per device."""
    d = os.path.join(root(), "images")
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{device}.building.qcow2")
    built = build_image(device, tmp)
    for t, s in sorted(built.items()):
        bad = saves.verify(tmp, store_dir(t, s))
        if bad:
            os.remove(tmp)
            raise SystemExit(f"titlestate: {t}/{s} does not verify on the built disk: {bad[:3]}")
    sha = sha256_file(tmp)
    out = os.path.join(d, f"{device}-{sha[:12]}.qcow2")
    os.replace(tmp, out)
    old = sorted((p for p in os.listdir(d) if p.startswith(device + "-") and p.endswith(".qcow2")),
                 key=lambda p: os.path.getmtime(os.path.join(d, p)), reverse=True)
    for p in old[keep:]:
        os.remove(os.path.join(d, p))
    return {"path": out, "sha256": sha, "built_from": built}


def store_saves(tid):
    d = os.path.join(root(), "saves", tid)
    if not os.path.isdir(d):
        return []
    out = []
    for s in os.listdir(d):
        if s.startswith("."):           # a harvest in flight
            continue
        p = os.path.join(d, s, "save.json")
        if os.path.exists(p):
            out.append((os.path.getmtime(p), s))
    return [s for _, s in sorted(out, reverse=True)]


def route_path(tid, variant):
    """routes/<route>.<variant>.route, else survey.route: a title with no
    route for this variant is surveyed (frames at every step, no gameplay
    mark), never played blind."""
    t = targets().get(tid, {})
    name = t.get("route")
    if name and variant in ("first-run", "returning"):
        p = os.path.join(HERE, "routes", f"{name}.{variant}.route")
        if os.path.exists(p):
            return p
    return os.path.join(HERE, "routes", "survey.route")


def single_route(tid):
    """routes/<route>.route when the title has it and no first-run or
    returning variant; else None."""
    name = targets().get(tid, {}).get("route")
    if not name:
        return None
    if any(os.path.exists(os.path.join(HERE, "routes", f"{name}.{v}.route"))
           for v in ("first-run", "returning")):
        return None
    p = os.path.join(HERE, "routes", f"{name}.route")
    return p if os.path.exists(p) else None


def choose(tid, devices=None):
    """Which device, which variant, and whether to import a save first.

    1. A device whose disk already has a profile for T: `returning` there.
    2. Else a save for T in the store that no candidate has rejected:
       import it (rebuild that device's titles disk with it) and `returning`.
    3. Else a device known to have NO profile for T: `first-run`.
    4. Else (state unknown everywhere): `survey`. A first-run route on a disk
       that may hold a profile meets prompts it was not written for.
    Candidates are the devices that hold the ISO (targets.toml `iso`), in the
    order given; a title with no targets entry may run anywhere.

    A title whose only route is routes/<route>.route (no first-run or
    returning variant) runs that route whatever the disk holds: the device
    and the import are chosen as above, the variant is `single`."""
    t = targets().get(tid, {})
    have_iso = list((t.get("iso") or {}).keys())
    cands = [d for d in (devices or DEVICES) if not have_iso or d in have_iso]
    if not cands:
        return {"title_id": tid, "device": None, "variant": None, "import": None,
                "reason": f"no candidate device holds the ISO (iso on: {', '.join(have_iso)})"}
    states = {d: load(d) for d in cands}
    rows = {d: states[d]["titles"].get(tid, {}) for d in cands}

    single = single_route(tid)

    def pick(d, variant, imp, reason):
        if single:
            return {"title_id": tid, "device": d, "variant": "single", "import": imp,
                    "route": single, "reason": reason + "; the title has one route"}
        return {"title_id": tid, "device": d, "variant": variant, "import": imp,
                "route": route_path(tid, variant), "reason": reason}

    for d in cands:
        if rows[d].get("profile"):
            return pick(d, "returning", None,
                        f"{d} has a profile ({rows[d].get('origin')} {rows[d].get('since_utc')})")
    for s in store_saves(tid):
        for d in cands:
            if s not in states[d].get("rejected", {}).get(tid, []):
                return pick(d, "returning", s,
                            f"import save {s} to {d}: no device holds a profile, the store does")
    for d in cands:
        if rows[d].get("profile") is False or (states[d].get("image") and not rows[d]):
            return pick(d, "first-run", None, f"{d} is known to have no profile")
    return pick(cands[0], "survey", None,
                "profile state unknown on every candidate; survey, do not play a first-run blind")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("--device"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("record")
    for f in ("--device", "--title-id", "--observed", "--run"):
        s.add_argument(f, required=True)
    s.add_argument("--save"); s.add_argument("--note")
    s = sub.add_parser("no-save")
    for f in ("--device", "--title-id", "--reason", "--run"):
        s.add_argument(f, required=True)
    s = sub.add_parser("harvest")
    for f in ("--device", "--title-id", "--image", "--run"):
        s.add_argument(f, required=True)
    s = sub.add_parser("build-image"); s.add_argument("--device", required=True)
    s.add_argument("out"); s.add_argument("--add", action="append", default=[])
    s = sub.add_parser("pushed")
    for f in ("--device", "--image", "--device-path", "--built-from"):
        s.add_argument(f, required=True)
    for name in ("seed", "after-run"):
        s = sub.add_parser(name)
        for f in ("--device", "--image", "--run"):
            s.add_argument(f, required=True)
        s.add_argument("--device-sha", default="")
    s = sub.add_parser("plan"); s.add_argument("--device", required=True)
    s.add_argument("--device-bytes", type=int, required=True)
    s.add_argument("--device-sha", default="")
    s.add_argument("--cap", type=int, default=int(os.environ.get("TITLES_DISK_CAP_BYTES") or CAP))
    s.add_argument("--ceiling", type=int,
                   default=int(os.environ.get("TITLES_DISK_CEILING_BYTES") or CEILING))
    s = sub.add_parser("rebuild"); s.add_argument("--device", required=True)
    s = sub.add_parser("choose"); s.add_argument("--title-id", required=True); s.add_argument("--devices")
    s = sub.add_parser("route"); s.add_argument("--title-id", required=True)
    s.add_argument("--variant", required=True, choices=VARIANTS)
    a = ap.parse_args(argv)

    if a.cmd == "show":
        devs = [a.device] if a.device else list(DEVICES)
        st = {d: load(d) for d in devs}
        if a.json:
            print(json.dumps(st, indent=1, sort_keys=True))
            return 0
        names = targets()
        for d in devs:
            img = st[d].get("image")
            print(f"{d}: titles disk " + (f"{img['sha256'][:12]} pushed {img['pushed_utc']}"
                                          if img else "none pushed (hdd.img: state unknown)"))
            for t, r in sorted(st[d]["titles"].items()):
                prof = {True: "profile", False: "no profile", None: "unknown"}[r.get("profile")]
                print(f"  {t} {names.get(t, {}).get('name', '?')[:28]:28} {prof:10} "
                      f"{r.get('origin') or '-':8} since {r.get('since_utc') or '-'}  "
                      f"save {r.get('save') or '-'}  last {r.get('observed') or '-'} "
                      f"by {r.get('by_run') or '-'}")
    elif a.cmd == "record":
        print(json.dumps(record(a.device, tid_norm(a.title_id), a.observed, a.run, a.save, a.note),
                         sort_keys=True))
    elif a.cmd == "no-save":
        print(json.dumps(no_save(a.device, tid_norm(a.title_id), a.reason, a.run), sort_keys=True))
    elif a.cmd == "harvest":
        print(harvest(a.device, tid_norm(a.title_id), a.image, a.run))
    elif a.cmd == "build-image":
        print(json.dumps(build_image(a.device, a.out, a.add), sort_keys=True))
    elif a.cmd == "pushed":
        pushed(a.device, a.image, a.device_path, json.loads(a.built_from))
    elif a.cmd == "seed":
        got, errors = seed(a.device, a.image, a.run)
        print(json.dumps({"harvested": got, "errors": errors}, sort_keys=True))
    elif a.cmd == "after-run":
        print(json.dumps(after_run(a.device, a.image, a.run, a.device_sha), sort_keys=True))
    elif a.cmd == "plan":
        print(json.dumps(plan(a.device, a.device_bytes, a.device_sha, a.cap, a.ceiling),
                         sort_keys=True))
    elif a.cmd == "rebuild":
        print(json.dumps(rebuild(a.device), sort_keys=True))
    elif a.cmd == "choose":
        devs = a.devices.split(",") if a.devices else None
        print(json.dumps(choose(tid_norm(a.title_id), devs), indent=1, sort_keys=True))
    elif a.cmd == "route":
        print(route_path(tid_norm(a.title_id), a.variant))
    return 0


if __name__ == "__main__":
    sys.exit(main())
