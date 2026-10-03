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

  GOLDEN PROFILES (lane.savestate433; see "GOLDENS" below):
    titlestate.py golden [--title-id T] [--json]
    titlestate.py promote --title-id T (--save SAVE_ID | --latest) --by WHO [--note TEXT]
    titlestate.py propose-all --by WHO
    titlestate.py import-save --dir SAVEDIR      a save dir saves.py wrote, verified, into the store
    titlestate.py first-run-saved --title-id T --save SAVE_ID --run ID [--route NAME]
    titlestate.py compose --device D [--title-id T] [--state S]
    titlestate.py resolve-route --route NAME [--title-id T | --iso NAME] [--device D]
    titlestate.py tid-for-iso NAME
    titlestate.py prepare --device D (--title-id T | --iso NAME | --hdd-img) [--state S]
    titlestate.py release --device D
    titlestate.py take-hdd --device D --title-id T     pull hdd.img, harvest T as `latest`

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

GOLDENS. Until 2026-10-02 a titles disk carried, per title, whatever the
device's last run had harvested, so a title's menus changed from run to run
(Tron 2.0's New Game vs Auto Load; 187's name keyboard; Castlevania's New
Game path) and a route written for one state met another. Now every title
has at most one GOLDEN profile, in $TITLESTATE_DIR/golden.json:

    {"titles": {"4D530065": {
        "golden": {"save": "<save_id>", "status": "golden" | "proposed",
                   "how": "seed" | "promote" | "first-run" | "propose" | "import",
                   "by": "<who>", "utc": ..., "route": ..., "note": ...},
        "history": [<every golden it replaced, newest last>],
        "latest": {"save": ..., "utc": ..., "run": ..., "device": ...}}}}

  - A title run's disk is COMPOSED from the goldens and nothing else: every
    title's golden, minus the run's own title when its route is `first-run`.
    `plan` rebuilds any disk that is not exactly that, pristine: a disk a run
    wrote to is harvested, then rebuilt, never booted again.
  - A harvest goes to `latest`, never to `golden`. Only `promote` replaces a
    golden (the old one goes to `history`; no save is ever removed). The one
    automatic golden: a `first-run` run that reached `mark profile-saved` on
    a title with no golden (`first-run-saved`, called by the dispatcher).
  - `proposed` goldens were picked by `propose-all` (the most recent verified
    harvest) or `seed`; they load exactly like a golden and wait for a person
    to confirm (`promote` the same save) or replace them.

ROUTE STATE. Every route file declares `# state: returning|first-run|any`.
`resolve-route` (request.sh --route) picks `<base>.returning` when the title
has a golden and `<base>.first-run` when it has none, and REFUSES a route
whose declared state the composed disk cannot match: `returning` with no
golden, or a route that declares nothing. `first-run` always matches (the
disk is built without the title's save), and `any` claims not to care.
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
STATES = ("returning", "first-run", "any")


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
    # The `latest` slot only: a harvest never touches a golden (GOLDENS). A
    # composed disk carries every title's golden, so every harvest reads
    # them all back unchanged; `latest` records only what differs.
    g = golden(tid)
    if not g or g["save"] != m["save_id"]:
        note_latest(tid, m["save_id"], run, device)
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
    # What the shared disk held is what these titles' routes were written on:
    # propose it as the golden where a title has none, so the first composed
    # disk carries what the device carried.
    for t, s in sorted(got.items()):
        if not golden(t):
            set_golden(t, s, by=f"seed of {device} hdd.img (run {run})", how="seed",
                       status="proposed")
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


def plan(device, device_bytes, device_sha, cap=CAP, ceiling=CEILING, title_id=None, state="any"):
    """What the dispatcher does to DEVICE's titles disk before a title run.

        seed      no titles disk yet: harvest hdd.img into the store first
        harvest   the device's disk holds writes no harvest has read
        preserve  ... and harvesting them failed: pull the whole disk to
                  $TITLESTATE_DIR/unharvested/ (`preserved`), then rebuild
        build     compose the goldens (compose()), build and push
        refuse    the run's state cannot be composed (compose()): fail it
        keep      boot the disk that is there: exactly the composed goldens,
                  untouched since it was pushed

    DEVICE_BYTES < 0 means the file is not on the device. Never `build` over
    writes that were not harvested or preserved. CEILING is kept for callers;
    `preserve` replaced the keep-over-a-failed-harvest it bounded: a kept
    disk is one a run already wrote to, and booting it is the void
    (GOLDENS)."""
    st = load(device)
    img = st.get("image")
    if not img:
        if not st.get("seeded"):
            return {"action": "seed", "reason": f"{device} has no titles disk and its hdd.img was never harvested"}
        return {"action": "build", "reason": f"{device} has no titles disk yet"}
    if device_bytes >= 0 and device_sha != img.get("device_sha256"):
        lp = img.get("last_pull") or {}
        if lp.get("sha256") == device_sha and lp.get("errors"):
            return {"action": "preserve", "alert": True,
                    "reason": f"harvest of this disk failed for {', '.join(sorted(lp['errors']))} "
                              f"(run {lp.get('run')}); keeping the whole disk on the host, then rebuilding"}
        return {"action": "harvest", "reason": "the device's disk changed since its last harvest"}
    try:
        want, _info = compose(device, title_id, state)
    except NoGolden as e:
        return {"action": "refuse", "reason": str(e)}
    if device_bytes < 0:
        return {"action": "build", "reason": "the titles disk is not on the device"}
    if device_sha != img.get("sha256"):
        return {"action": "build",
                "reason": "the disk carries a run's writes since it was pushed; every run starts from the goldens"}
    built = img.get("built_from") or {}
    if want != built:
        diff = sorted(t for t in set(want) | set(built) if want.get(t) != built.get(t))
        return {"action": "build", "reason": f"the composed goldens differ from the disk's for {', '.join(diff)}"}
    if device_bytes > cap:
        return {"action": "build", "reason": f"the disk grew to {device_bytes} B > cap {cap} B"}
    return {"action": "keep", "reason": "the disk is the composed goldens, untouched since its push"}


def preserved(device, sha, path):
    """A disk whose harvest failed was pulled whole to PATH: nothing on it is
    lost by rebuilding, so plan() may move on."""
    with Registry(device) as st:
        img = st.get("image") or {}
        img.setdefault("preserved", []).append({"utc": now(), "sha256": sha, "path": os.path.abspath(path)})
        img["device_sha256"] = sha
        st["image"] = img
    return img


def rebuild(device, keep=5, title_id=None, state="any"):
    """Build DEVICE's titles disk from the composed goldens into images/,
    verify every save on it, and name it by content. Keeps the newest KEEP
    per device."""
    d = os.path.join(root(), "images")
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{device}.building.qcow2")
    built, info = compose(device, title_id, state)
    dirs = []
    for t, s in sorted(built.items()):
        sd = store_dir(t, s)
        if not os.path.isdir(sd):
            raise SystemExit(f"titlestate: no save {t}/{s} in the store")
        dirs.append(sd)
    saves.build(tmp, dirs)
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
    return {"path": out, "sha256": sha, "built_from": built, "composed": info}


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


# ----------------------------------------------------------------- goldens --

class NoGolden(Exception):
    """A run's state needs a profile the goldens cannot supply."""


class Goldens:
    """golden.json, read and written under an exclusive lock, replaced
    atomically, as Registry does for a device file."""

    def __init__(self):
        self.path = os.path.join(root(), "golden.json")

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.lock = open(self.path + ".lock", "w")
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        self.state = load_goldens()
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


def load_goldens():
    try:
        with open(os.path.join(root(), "golden.json")) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"titles": {}}


def disk_tid(tid):
    """The TitleID a title's saves are filed under on the disk (its XBE's)
    for a targets.toml key. The two differ where targets.toml uses the
    compat CSV's canonical id: Dead or Alive 3 is 4D53002D there and
    54430001 on the disk. Without this a first-run disk would keep the save
    it was meant to drop. golden.json `aliases`, written by `alias`."""
    if not tid:
        return tid
    return load_goldens().get("aliases", {}).get(tid, tid)


def set_alias(tid, disk):
    with Goldens() as gl:
        gl.setdefault("aliases", {})[tid] = disk
    return {tid: disk}


def title_meta_name(tid):
    """TitleMeta.xbx's TitleName from the newest stored save of TID."""
    for s in store_saves(tid):
        u = os.path.join(store_dir(tid, s), "UDATA", tid)
        for f in os.listdir(u) if os.path.isdir(u) else []:
            if f.lower() == "titlemeta.xbx":
                txt = open(os.path.join(u, f), "rb").read().decode("utf-16-le", "replace")
                for line in txt.splitlines():
                    line = line.strip().lstrip("\ufeff")
                    if line.startswith("TitleName="):
                        return line.split("=", 1)[1].strip()
    return None


def suggest_aliases():
    """targets.toml titles with no save under their own id, and the stored
    TitleIDs whose TitleMeta name matches theirs: [(tid, disk_tid, names)]."""
    def norm(s):
        return "".join(c for c in (s or "").lower() if c.isalnum())
    sd = os.path.join(root(), "saves")
    stored = {t: norm(title_meta_name(t)) for t in (os.listdir(sd) if os.path.isdir(sd) else [])
              if not t.startswith(".")}
    out = []
    for tid, t in sorted(targets().items()):
        if tid in stored:
            continue
        n = norm(t.get("name"))
        for st, sn in sorted(stored.items()):
            if sn and n and (sn[:10] in n or n[:10] in sn):
                out.append((tid, st, f"{t.get('name')} ~ {title_meta_name(st)}"))
    return out


def golden(tid):
    return (load_goldens()["titles"].get(disk_tid(tid)) or {}).get("golden")


def verify_store_save(tid, save):
    """Problems with a stored save: its dir, its save.json, and every file's
    sha256 against save.json. [] is a save that can be built onto a disk."""
    d = store_dir(tid, save)
    try:
        with open(os.path.join(d, "save.json")) as fh:
            m = json.load(fh)
    except (OSError, ValueError) as e:
        return [f"{tid}/{save}: no readable save.json ({e})"]
    bad = []
    if m.get("save_id") not in (None, save):
        bad.append(f"{tid}/{save}: save.json names {m.get('save_id')}")
    for e in m.get("entries", []):
        if e.get("dir"):
            continue
        p = os.path.join(d, *e["path"].split("/"))
        try:
            if sha256_file(p) != e.get("sha256"):
                bad.append(f"{e['path']}: sha256 differs")
        except OSError:
            bad.append(f"{e['path']}: missing")
    return bad


def set_golden(tid, save, by, how, status="golden", route=None, note=None, replace=False):
    """Make SAVE the golden of TID. A golden is never replaced unless REPLACE
    (`promote`); the one it replaces goes to `history`. Returns the record."""
    if status not in ("golden", "proposed"):
        raise SystemExit(f"titlestate: golden status {status!r}")
    tid = disk_tid(tid)
    bad = verify_store_save(tid, save)
    if bad:
        raise SystemExit(f"titlestate: {tid}/{save} does not verify in the store: {bad[:3]}")
    with Goldens() as gl:
        rec = gl["titles"].setdefault(tid, {})
        old = rec.get("golden")
        if old and not replace:
            raise SystemExit(f"titlestate: {tid} already has a golden ({old['save']}, {old['status']}); "
                             f"only `promote` replaces it")
        new = {"save": save, "status": status, "how": how, "by": by, "utc": now()}
        if route:
            new["route"] = route
        if note:
            new["note"] = note
        if old:
            rec.setdefault("history", []).append(old)
        rec["golden"] = new
        return new


def promote(tid, by, save=None, latest=False, note=None):
    """The only way a golden changes: SAVE (or the title's `latest`) becomes
    it, status golden. Promoting a proposed golden's own save confirms it."""
    if latest:
        save = ((load_goldens()["titles"].get(disk_tid(tid)) or {}).get("latest") or {}).get("save")
        if not save:
            raise SystemExit(f"titlestate: {tid} has no `latest` save to promote")
    if not save:
        raise SystemExit("titlestate: promote needs --save or --latest")
    return set_golden(tid, save, by=by, how="promote", note=note, replace=True)


def note_latest(tid, save, run, device):
    with Goldens() as gl:
        gl["titles"].setdefault(tid, {})["latest"] = {"save": save, "utc": now(), "run": run,
                                                       "device": device}


def first_run_saved(tid, save, run, route=None):
    """A first-run that reached `mark profile-saved` made SAVE: the golden,
    when the title has none. Never over an existing golden."""
    if golden(tid):
        return {"title_id": tid, "golden": golden(tid), "changed": False,
                "reason": "the title already has a golden; `promote` to replace it"}
    return {"title_id": tid, "changed": True,
            "golden": set_golden(tid, save, by=f"run {run}", how="first-run", route=route)}


def latest_harvest(tid):
    """[(utc, save)] newest first: every device's harvest of TID, then the
    `latest` slot, then the store's own order (save.json mtime)."""
    seen = []
    for d in DEVICES:
        r = load(d)["titles"].get(tid) or {}
        if r.get("save"):
            seen.append((r.get("harvested_utc") or r.get("since_utc") or "", r["save"]))
    lt = (load_goldens()["titles"].get(tid) or {}).get("latest")
    if lt:
        seen.append((lt.get("utc") or "", lt["save"]))
    seen.sort(reverse=True)
    out = []
    for _, s in seen:
        if s not in out:
            out.append(s)
    for s in store_saves(tid):
        if s not in out:
            out.append(s)
    return out


def save_dirs(tid, save):
    """The save directories (E:\\UDATA\\<TID>\\<12 hex>) a stored save carries.
    [] is title data and settings only: no profile to load."""
    try:
        with open(os.path.join(store_dir(tid, save), "save.json")) as fh:
            m = json.load(fh)
    except (OSError, ValueError):
        return []
    pre = f"UDATA/{tid}/".upper()
    return sorted({e["path"][len(pre):].split("/")[0] for e in m.get("entries", [])
                   if e["path"].upper().startswith(pre) and "/" in e["path"][len(pre):]})


def propose_all(by, refresh=False):
    """For every title in the store with no golden: the newest harvest that
    verifies AND carries a save directory, else the newest that verifies, as
    a `proposed` golden. A harvest of title data alone is not a profile:
    Castlevania's newest (53f0a40fe626) has none, while 20235e93867b holds
    the slot-1 save its returning route continues from. REFRESH re-picks
    titles whose golden is still `proposed` (never a confirmed one).
    Returns [(tid, save, note)]."""
    out = []
    sd = os.path.join(root(), "saves")
    for tid in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
        if tid.startswith("."):
            continue
        g = golden(tid)
        if g and not (refresh and g["status"] == "proposed"):
            continue
        ok = [s for s in latest_harvest(tid) if not verify_store_save(tid, s)]
        pick = next((s for s in ok if save_dirs(tid, s)), ok[0] if ok else None)
        if not pick:
            out.append((tid, None, "no save verifies"))
            continue
        if g and g["save"] == pick:
            continue
        set_golden(tid, pick, by=by, how="propose", status="proposed", replace=bool(g),
                   note="the newest verified harvest " + ("with a save directory" if save_dirs(tid, pick)
                                                         else "(title data only: no save directory)")
                        + "; confirm with `promote` or replace")
        out.append((tid, pick, "re-proposed" if g else "proposed"))
    return out


def import_save(src):
    """A save dir as saves.py writes one (save.json + UDATA/TDATA), e.g. from
    an hdd-reset backup, copied into the store under its own id after every
    file verifies. Never overwrites: an id already stored is the same save."""
    with open(os.path.join(src, "save.json")) as fh:
        m = json.load(fh)
    tid, sid = tid_norm(m["title_id"]), m["save_id"]
    if saves.save_id(m) != sid:
        raise SystemExit(f"titlestate: {src}: save.json's entries do not hash to {sid}")
    dest = store_dir(tid, sid)
    if not os.path.isdir(dest):
        tmp = os.path.join(root(), "saves", tid, f".import.{os.getpid()}")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(src, tmp)
        os.replace(tmp, dest)
    bad = verify_store_save(tid, sid)
    if bad:
        raise SystemExit(f"titlestate: imported {tid}/{sid} does not verify: {bad[:3]}")
    return tid, sid


def compose(device, title_id=None, state="any"):
    """What a title run's disk carries: every title's golden that DEVICE has
    not rejected, except TITLE_ID's when STATE is `first-run`. Raises
    NoGolden when STATE is `returning` and TITLE_ID has no usable golden.
    Returns (built_from, info) -- info is what the result's hdd.json records."""
    if state not in STATES:
        raise SystemExit(f"titlestate: state {state!r}: one of {', '.join(STATES)}")
    rej = load(device).get("rejected", {})
    want = {}
    for t, rec in load_goldens()["titles"].items():
        g = rec.get("golden")
        if g and g["save"] not in rej.get(t, []):
            want[t] = g["save"]
    dt = disk_tid(title_id)
    info = {"title_id": title_id, "disk_title_id": dt, "state": state, "save": None, "loaded": "none",
            "golden_status": None, "goldens": len(want)}
    if not title_id:
        info["loaded"] = "all goldens (title not identified)"
        return want, info
    g = golden(title_id)
    if state == "first-run":
        want.pop(dt, None)
    elif state == "returning" and dt in want and not save_dirs(dt, want[dt]):
        raise NoGolden(f"{title_id}'s golden {want[dt]} is title data only, no save directory; a "
                       f"returning route would meet no profile. {SETTINGS_ONLY_FIX}")
    elif state == "returning" and dt not in want:
        if g:
            raise NoGolden(f"{title_id}'s golden {g['save']} was rejected on {device}; a returning "
                           f"route would meet no profile")
        raise NoGolden(f"{title_id} has no golden profile; a returning route would meet no profile "
                       f"(run its first-run route, or `titlestate.py promote` a save)")
    if dt in want:
        info.update(save=want[dt], loaded="golden", golden_status=g["status"])
    return want, info


# ------------------------------------------------------------ route state --

# A refusal names its way forward (Star Wars Ep. III, 10-03: a route
# confirmed on its settings-only golden, headed `returning`, was refused and
# dropped from the queue as a decision for someone else).
SETTINGS_ONLY_FIX = ("If the route was confirmed on this golden as it is, head it `# state: any` (that loads the "
                     "golden unchanged); if it needs a save, `promote` one that has a save directory.")


def tid_for_iso(name):
    """TitleID for an ISO file name: targets.toml's `iso` entries, else an
    8-hex prefix (`4541000D-007_Agent...iso`). None when neither."""
    base = os.path.basename(name or "")
    for tid, t in targets().items():
        if base in (t.get("iso") or {}).values():
            return tid
    head = base.split("-")[0].split("_")[0].upper()
    if len(head) == 8 and all(c in "0123456789ABCDEF" for c in head):
        return head
    return None


def route_state(path):
    """The `# state:` a route file declares, or None. Any line of the header
    (the comments before the first step) may carry it."""
    with open(path) as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if not s.startswith("#"):
                break
            body = s.lstrip("#").strip()
            if body.lower().startswith("state:"):
                v = body.split(":", 1)[1].split()[0].strip() if body.split(":", 1)[1].split() else ""
                return v if v in STATES else f"invalid:{v}"
    return None


def resolve_route(name, title_id=None, device=None, routes_dir=None):
    """Which route file a request plays, the state it declares, and whether
    the disk compose() makes for it can match. NAME is a route file's base
    (`gta-sa`, `castlevania-cod.returning`) or a variant family's base
    (`castlevania-cod`): the family resolves to `.returning` when the title
    has a golden and `.first-run` when it has none.

    Returns {"path", "route_name", "state", "title_id", "golden", "refuse"};
    `refuse` is a one-line reason, or None."""
    rd = routes_dir or os.path.join(HERE, "routes")
    out = {"path": None, "route_name": name, "state": None, "title_id": title_id,
           "golden": None, "refuse": None}
    g = golden(title_id) if title_id else None
    if g and device and g["save"] in load(device).get("rejected", {}).get(disk_tid(title_id), []):
        g = None
    out["golden"] = g["save"] if g else None
    single = os.path.join(rd, f"{name}.route")
    if os.path.exists(single):
        out["path"] = single
    else:
        fam = {v: os.path.join(rd, f"{name}.{v}.route") for v in ("returning", "first-run")}
        if not any(os.path.exists(p) for p in fam.values()):
            out["refuse"] = f"no route '{name}' ({single})"
            return out
        # A golden of title data alone is no profile: such a title takes the
        # first-run route (Black's and GoldenEye's harvests, 10-02).
        prof = bool(g and save_dirs(disk_tid(title_id), g["save"]))
        v = "returning" if prof else "first-run"
        if not title_id:
            out["refuse"] = (f"'{name}' has first-run/returning variants and the title is not identified; "
                             f"name the variant (--route {name}.first-run)")
            return out
        if not os.path.exists(fam[v]):
            out["refuse"] = (f"{title_id} {'has a golden profile' if prof else 'has no golden profile'}, so it needs "
                             f"{name}.{v}.route, which does not exist")
            return out
        out["path"], out["route_name"] = fam[v], f"{name}.{v}"
    st = route_state(out["path"])
    out["state"] = st
    if st is None:
        out["refuse"] = (f"{os.path.basename(out['path'])} declares no `# state: returning|first-run|any`; "
                         f"a route that silently assumes a profile is the void this refuses")
    elif st.startswith("invalid:"):
        out["refuse"] = f"{os.path.basename(out['path'])}: `# state: {st[8:]}` is not one of {', '.join(STATES)}"
    elif st == "returning":
        if not title_id:
            out["refuse"] = (f"{os.path.basename(out['path'])} assumes a profile and the title is not "
                             f"identified (no targets.toml iso entry), so no golden can be loaded")
        elif not g:
            why = "was rejected on " + device if golden(title_id) else "does not exist"
            out["refuse"] = (f"{os.path.basename(out['path'])} assumes a profile, and {title_id}'s golden "
                             f"{why}: the disk would carry none")
        elif not save_dirs(disk_tid(title_id), g["save"]):
            out["refuse"] = (f"{os.path.basename(out['path'])} assumes a profile, and {title_id}'s golden "
                             f"{g['save']} is title data only, no save directory. {SETTINGS_ONLY_FIX}")
    return out


# ------------------------------------------------- held sessions (no dispatcher) --
#
# nav.py, pathfind.py, a lane's capture script and the owner's playtest boot
# the titles disk through these, so a held session starts from the same
# composed goldens a dispatched run does. The device steps are the
# dispatcher's (titles_disk_prepare): force-stop, plan rounds, push through
# <path>.new with the sha256 read back, MODE 660 before the rename (the
# #622 crash: docs/testing/dispatcher.sh "THE DISK MUST BE MODE 660"), the
# hddPath pref written and read back, and the SAME marker file
# ($DISPATCH_DIR/.hdd_pref.<device>) holding hdd.img, so a session that never
# calls `release` is put back by the dispatcher's restore_hdd_pref at its
# next request, and the disk's writes are harvested by its next plan().

SERIALS = {"nova": "ee317437", "thor": "bdc158a5"}
PKG = os.environ.get("PKG", "com.jreinach.hakux.debug")


def x1box():
    return f"/storage/emulated/0/Android/data/{PKG}/files/x1box"


def dispatch_dir():
    return os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")


class Adb:
    def __init__(self, device, serial=None):
        self.device = device
        self.serial = serial or os.environ.get("SERIAL") or SERIALS[device]

    def run(self, args, timeout=60, data=None):
        import subprocess
        r = subprocess.run(["adb", "-s", self.serial] + args, input=data, capture_output=True,
                           timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace").replace("\r", "")

    def sh(self, cmd, timeout=60, data=None):
        return self.run(["shell", cmd], timeout, data)[1]

    def sha(self, path):
        out = self.sh(f"sha256sum '{path}' 2>/dev/null || true", timeout=300).split()
        return out[0] if out and len(out[0]) == 64 else ""

    def nbytes(self, path):
        out = self.sh(f"stat -c %s '{path}' 2>/dev/null || echo -1").strip().splitlines()
        return int(out[0]) if out and out[0].lstrip("-").isdigit() else -1

    def mode(self, path):
        return self.sh(f"stat -c %a '{path}' 2>/dev/null").strip()

    def pull(self, src, dst, want):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        for _ in range(3):
            self.run(["pull", src, dst], timeout=600)
            if os.path.exists(dst) and sha256_file(dst) == want:
                return True
        if os.path.exists(dst):
            os.remove(dst)
        return False

    def make_660(self, path):
        if self.mode(path) != "660":
            self.sh(f"chmod 660 '{path}'")
        return self.mode(path) == "660"

    def push(self, src, dst):
        want = sha256_file(src)
        self.run(["push", src, dst + ".new"], timeout=600)
        if self.sha(dst + ".new") != want:
            raise SystemExit(f"titlestate: push {dst}: the device's copy does not match")
        if not self.make_660(dst + ".new"):
            raise SystemExit(f"titlestate: {dst}.new is not mode 660 after chmod; the app could not open it")
        self.sh(f"mv -f '{dst}.new' '{dst}'")
        if self.sha(dst) != want or self.mode(dst) != "660":
            raise SystemExit(f"titlestate: {dst} is not the pushed image, mode 660, after the rename")

    def prefs(self):
        return self.sh(f"run-as {PKG} cat shared_prefs/x1box_prefs.xml")

    def set_hdd(self, want):
        """hddPath := WANT, every other byte kept; read back. Returns the
        value it replaced."""
        import re
        s = self.prefs()
        if "</map>" not in s:
            raise SystemExit("titlestate: cannot read x1box_prefs.xml")
        m = re.search(r'<string name="hddPath">(.*?)</string>', s, re.S)
        was = m.group(1) if m else ""
        esc = want.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if m:
            s = s[:m.start(1)] + esc + s[m.end(1):]
        else:
            s = s.replace("</map>", f'    <string name="hddPath">{esc}</string>\n</map>')
        self.sh(f"run-as {PKG} sh -c 'cat > shared_prefs/x1box_prefs.xml'", data=s.encode())
        m2 = re.search(r'<string name="hddPath">(.*?)</string>', self.prefs(), re.S)
        if not m2 or m2.group(1) != esc:
            raise SystemExit(f"titlestate: wrote hddPath={want} but read back {m2.group(1) if m2 else None!r}")
        return was


def marker(device):
    return os.path.join(dispatch_dir(), f".hdd_pref.{device}")


def prepare(device, title_id=None, state="any", run=None, adb=None, log=print):
    """A held session's titles disk: the dispatcher's plan rounds, then
    hddPath -> titles.qcow2 with the marker written first. Returns the
    hdd.json-shaped record. Raises SystemExit (with the reason) on refuse."""
    adb = adb or Adb(device)
    run = run or f"held-{device}-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    x = x1box()
    dpath = f"{x}/titles.qcow2"
    adb.sh(f"am force-stop {PKG}")
    plans, action = [], None
    for _ in range(5):
        n = adb.nbytes(dpath)
        sha = adb.sha(dpath) if n >= 0 else ""
        p = plan(device, n, sha, title_id=title_id, state=state)
        plans.append(p)
        action = p["action"]
        log(f"titlestate: titles disk: {action} ({p['reason']})")
        if action == "keep":
            break
        if action == "refuse":
            raise SystemExit(f"titlestate: refusing: {p['reason']}")
        pull = os.path.join(root(), "pull", f"{device}-held.qcow2")
        if action == "seed":
            hs = adb.sha(f"{x}/hdd.img")
            if not hs or not adb.pull(f"{x}/hdd.img", pull, hs):
                raise SystemExit("titlestate: cannot pull hdd.img to seed")
            seed(device, pull, run)
            os.remove(pull)
        elif action == "harvest":
            if not adb.pull(dpath, pull, sha):
                raise SystemExit("titlestate: pull for harvest failed")
            after_run(device, pull, run + ":before", sha)
            os.remove(pull)
        elif action == "preserve":
            keep = os.path.join(root(), "unharvested", f"{device}-{sha[:12]}.qcow2")
            if not adb.pull(dpath, keep, sha):
                raise SystemExit("titlestate: pull to preserve failed")
            preserved(device, sha, keep)
        elif action == "build":
            b = rebuild(device, title_id=title_id, state=state)
            adb.push(b["path"], dpath)
            pushed(device, b["path"], dpath, b["built_from"])
    if action != "keep":
        raise SystemExit(f"titlestate: no stable plan after {len(plans)} rounds")
    mode0 = adb.mode(dpath)
    if not adb.make_660(dpath):
        raise SystemExit(f"titlestate: cannot make {dpath} mode 660")
    mk = marker(device)
    if not os.path.exists(mk):
        was = re_hdd(adb.prefs())
        if was == dpath:
            was = f"{x}/hdd.img"
        with open(mk, "w") as fh:
            fh.write(was)
    adb.set_hdd(dpath)
    _, info = compose(device, title_id, state)
    rec = dict(info, path=dpath, sha256_at_start=sha, bytes_at_start=n, plans=plans,
               mode_found=mode0 or None, mode="660", split="on", split_from="held", run=run)
    log(f"titlestate: hddPath -> {dpath}: {title_id or '-'} {state}, loaded {info['loaded']}"
        f"{' ' + info['save'] if info['save'] else ''}")
    return rec


def re_hdd(prefs):
    import re
    m = re.search(r'<string name="hddPath">(.*?)</string>', prefs, re.S)
    return m.group(1) if m else ""


def release(device, run=None, adb=None, log=print):
    """End of a held session: force-stop, harvest whatever the session wrote
    to the titles disk (to `latest`), and put hddPath back from the marker."""
    adb = adb or Adb(device)
    run = run or f"held-{device}-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    dpath = f"{x1box()}/titles.qcow2"
    adb.sh(f"am force-stop {PKG}")
    out = {"harvested": None}
    n = adb.nbytes(dpath)
    sha = adb.sha(dpath) if n >= 0 else ""
    if plan(device, n, sha)["action"] == "harvest":
        pull = os.path.join(root(), "pull", f"{device}-held.qcow2")
        if adb.pull(dpath, pull, sha):
            out["harvested"] = after_run(device, pull, run, sha)
            os.remove(pull)
        else:
            out["harvested"] = {"error": "pull failed; the next plan() harvests it"}
    mk = marker(device)
    if os.path.exists(mk):
        orig = open(mk).read().strip()
        if orig.endswith("/titles.qcow2"):
            orig = f"{x1box()}/hdd.img"
        adb.set_hdd(orig)
        os.remove(mk)
        out["hddPath"] = orig
    log(f"titlestate: released {device}: {json.dumps(out, sort_keys=True)[:300]}")
    return out


def take_hdd(device, tid, run=None, adb=None, log=print):
    """After hand play on hdd.img: pull it, harvest TID into the store as its
    `latest`, and say how to promote it. hdd.img is read, never written."""
    adb = adb or Adb(device)
    run = run or f"hand-{device}-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    src = f"{x1box()}/hdd.img"
    adb.sh(f"am force-stop {PKG}")
    sha = adb.sha(src)
    pull = os.path.join(root(), "pull", f"{device}-hdd-hand.img")
    if not sha or not adb.pull(src, pull, sha):
        raise SystemExit("titlestate: cannot pull hdd.img")
    try:
        s = harvest(device, tid, pull, run)
    finally:
        os.remove(pull)
    g = golden(tid)
    log(f"titlestate: {tid}: harvested {s} as latest; golden is "
        f"{g['save'] + ' (' + g['status'] + ')' if g else 'none'}. To make it the golden:\n"
        f"  titlestate.py promote --title-id {tid} --save {s} --by '<who>'")
    return s


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
    s.add_argument("--title-id"); s.add_argument("--state", default="any", choices=STATES)
    s = sub.add_parser("preserved")
    for f in ("--device", "--sha", "--path"):
        s.add_argument(f, required=True)
    s = sub.add_parser("rebuild"); s.add_argument("--device", required=True)
    s.add_argument("--title-id"); s.add_argument("--state", default="any", choices=STATES)
    s = sub.add_parser("choose"); s.add_argument("--title-id", required=True); s.add_argument("--devices")
    s = sub.add_parser("route"); s.add_argument("--title-id", required=True)
    s.add_argument("--variant", required=True, choices=VARIANTS)
    s = sub.add_parser("golden"); s.add_argument("--title-id"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("promote"); s.add_argument("--title-id", required=True)
    s.add_argument("--save"); s.add_argument("--latest", action="store_true")
    s.add_argument("--by", required=True); s.add_argument("--note")
    s = sub.add_parser("propose-all"); s.add_argument("--by", required=True)
    s.add_argument("--refresh", action="store_true", help="re-pick titles whose golden is still proposed")
    s = sub.add_parser("import-save"); s.add_argument("--dir", required=True)
    s = sub.add_parser("first-run-saved")
    for f in ("--title-id", "--save", "--run"):
        s.add_argument(f, required=True)
    s.add_argument("--route")
    s = sub.add_parser("compose"); s.add_argument("--device", required=True)
    s.add_argument("--title-id"); s.add_argument("--state", default="any", choices=STATES)
    s = sub.add_parser("resolve-route"); s.add_argument("--route", required=True)
    s.add_argument("--title-id"); s.add_argument("--iso"); s.add_argument("--device")
    s = sub.add_parser("tid-for-iso"); s.add_argument("name")
    s = sub.add_parser("alias"); s.add_argument("--title-id"); s.add_argument("--disk-tid")
    s.add_argument("--suggest", action="store_true")
    s = sub.add_parser("prepare"); s.add_argument("--device", required=True, choices=DEVICES)
    s.add_argument("--title-id"); s.add_argument("--iso")
    s.add_argument("--state", default="any", choices=STATES); s.add_argument("--run")
    s.add_argument("--hdd-img", action="store_true",
                   help="hand play on hdd.img: touch nothing, say so")
    s = sub.add_parser("release"); s.add_argument("--device", required=True, choices=DEVICES)
    s.add_argument("--run")
    s = sub.add_parser("take-hdd"); s.add_argument("--device", required=True, choices=DEVICES)
    s.add_argument("--title-id", required=True)
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
        print(json.dumps(plan(a.device, a.device_bytes, a.device_sha, a.cap, a.ceiling,
                              tid_norm(a.title_id) if a.title_id else None, a.state),
                         sort_keys=True))
    elif a.cmd == "preserved":
        preserved(a.device, a.sha, a.path)
    elif a.cmd == "rebuild":
        print(json.dumps(rebuild(a.device, title_id=tid_norm(a.title_id) if a.title_id else None,
                                 state=a.state), sort_keys=True))
    elif a.cmd == "choose":
        devs = a.devices.split(",") if a.devices else None
        print(json.dumps(choose(tid_norm(a.title_id), devs), indent=1, sort_keys=True))
    elif a.cmd == "route":
        print(route_path(tid_norm(a.title_id), a.variant))
    elif a.cmd == "golden":
        gl = load_goldens()["titles"]
        if a.title_id:
            gl = {tid_norm(a.title_id): gl.get(tid_norm(a.title_id), {})}
        if a.json:
            print(json.dumps(gl, indent=1, sort_keys=True))
            return 0
        names = targets()
        for t, rec in sorted(gl.items()):
            g, lt = rec.get("golden") or {}, rec.get("latest") or {}
            print(f"{t} {names.get(t, {}).get('name', '?')[:30]:30} "
                  f"{g.get('status', 'NONE'):8} {g.get('save', '-'):12} {g.get('how', '-'):9} "
                  f"by {g.get('by', '-')[:40]:40} latest {lt.get('save', '-')}")
    elif a.cmd == "promote":
        print(json.dumps(promote(tid_norm(a.title_id), a.by, a.save, a.latest, a.note), sort_keys=True))
    elif a.cmd == "propose-all":
        for t, s, why in propose_all(a.by, a.refresh):
            print(f"{t} {s or '-'} {why}")
    elif a.cmd == "import-save":
        print("%s %s" % import_save(a.dir))
    elif a.cmd == "first-run-saved":
        print(json.dumps(first_run_saved(tid_norm(a.title_id), a.save, a.run, a.route), sort_keys=True))
    elif a.cmd == "compose":
        try:
            want, info = compose(a.device, tid_norm(a.title_id) if a.title_id else None, a.state)
        except NoGolden as e:
            print(json.dumps({"refuse": str(e)}))
            return 3
        print(json.dumps(dict(info, built_from=want), sort_keys=True))
    elif a.cmd == "resolve-route":
        tid = tid_norm(a.title_id) if a.title_id else (tid_for_iso(a.iso) if a.iso else None)
        r = resolve_route(a.route, tid, a.device)
        print(json.dumps(r, sort_keys=True))
        return 3 if r["refuse"] else 0
    elif a.cmd == "tid-for-iso":
        print(tid_for_iso(a.name) or "")
    elif a.cmd == "alias":
        if a.suggest:
            for t, d, why in suggest_aliases():
                print(f"{t} {d} {why}")
        elif a.title_id and a.disk_tid:
            print(json.dumps(set_alias(tid_norm(a.title_id), tid_norm(a.disk_tid))))
        else:
            print(json.dumps(load_goldens().get("aliases", {}), indent=1, sort_keys=True))
    elif a.cmd == "prepare":
        if a.hdd_img:
            print(f"titlestate: {a.device}: hand play on hdd.img; nothing prepared. Afterwards, to keep "
                  f"the save: titlestate.py take-hdd --device {a.device} --title-id <T>")
            return 0
        tid = tid_norm(a.title_id) if a.title_id else (tid_for_iso(a.iso) if a.iso else None)
        if not tid:
            raise SystemExit("titlestate: prepare needs --title-id, an --iso targets.toml knows, or --hdd-img")
        print(json.dumps(prepare(a.device, tid, a.state, a.run, log=lambda m: print(m, file=sys.stderr)),
                         sort_keys=True))
    elif a.cmd == "release":
        print(json.dumps(release(a.device, a.run, log=lambda m: print(m, file=sys.stderr)), sort_keys=True))
    elif a.cmd == "take-hdd":
        take_hdd(a.device, tid_norm(a.title_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
