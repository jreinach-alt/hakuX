#!/usr/bin/env python3
"""fpsdiag.py -- capture, analyze, gaps: one diagnostic tool for the GTA III /
Blinx 2 / Fable fps misses (#433).

    fpsdiag.py capture --serial <s> --title <name> --seconds <n> --out <dir>
    fpsdiag.py analyze <dir-or-file> [--title <name>] [--bars targets.toml]
    fpsdiag.py gaps [dir-or-file]

This tool reads. It never writes a pref, sets an env switch, kills a
process, or sends input -- `capture` only attaches to an already-running
session (`adb logcat`, `adb shell cat <sysfs node>`, `dumpsys`), the same
restriction the brief and `docs/lanes/fpsdiag1018/CAPTURE.md` describe for a
human running it. No gameplay is navigated by this file.

Local only: no API key, no model call, no model download. Every number
`analyze`/`gaps` prints traces to a source line in the capture it was given;
see `docs/lanes/fpsdiag1018/FINDINGS.md` for the candidate list and the
measurements this file's checks are built from.

WINDOWS, CLASSES, AND THE "NEVER ONE WINDOW" RULE
    A window is one `hakuX-pace` 60-flip line if present, else the capture's
    fixed 1 s slices. `fps_for(window)` prefers the pace window's own `ms=`
    span (the window's real duration -- `hakuX-perf gfps=` is a trailing
    ~1 s rate, not the window's rate; see FINDINGS.md "Known" methodology
    note and memory `gfps-is-last-second-not-window`). A window classifies
    dip/good against `bar = target_fps * fps_tolerance` from `targets.toml`
    (fpsdiag1018 FINDINGS.md 1.1-1.3). Every per-candidate verdict needs
    >= MIN_WINDOWS of EACH class or it reports "not measured: insufficient
    windows", never a verdict from one window or one run (brief step 4).

NON-GAMEPLAY WINDOWS
    A window containing a boot/pipeline-warmup marker (`init: pipelines`,
    `Shader module warm-up`), a save-state load (`[savestate] op=load`), or
    zero flip advance (frozen/black) is refused -- excluded from both
    classes, counted separately, never scored.

MISSING COUNTERS
    If a candidate's required tag never appears anywhere in the capture,
    the candidate is "not measured: <tag> absent from this capture" --
    never "refuted". Some tags are perflog-build-only (`hakuX-phase`,
    `hakuX-cpu`, `xemu-vsync`, `xemu-pace`, `hakuX-rpbrk`) and are
    genuinely absent from plain release-build captures; see `gaps`.
"""
import argparse
import bisect
import json
import os
import re
import statistics
import sys
import time

MIN_WINDOWS = 3  # per class, or a candidate cannot report a verdict (never one window)

# --------------------------------------------------------------------------
# logcat parsing
# --------------------------------------------------------------------------

LOGCAT_LINE = re.compile(
    r'^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d\d\d)\s+(\d+)\s+\d+\s+(\w)\s+([^:]+):\s?(.*)$'
)


def parse_line(line):
    """Return (t_seconds_in_day, pid, tag, msg) or None. t is monotonic within one day."""
    m = LOGCAT_LINE.match(line)
    if not m:
        return None
    _, _, hh, mm, ss, pid, _level, tag, msg = m.groups()
    t = int(hh) * 3600 + int(mm) * 60 + float(ss)
    return t, pid, tag.strip(), msg


def num(rx, s, d=None):
    m = re.search(rx, s)
    return float(m.group(1)) if m else d


def iter_logcat_files(path):
    """Yield (filename, line) for every text file under path that looks like a
    logcat (threadtime format). Accepts a single file or a directory (scanned
    recursively); non-logcat files (screenshots, arm.log's own route/park
    lines) are skipped by trying to parse their first matching line."""
    if os.path.isfile(path):
        candidates = [path]
    else:
        candidates = []
        for root, _dirs, files in os.walk(path):
            for f in files:
                if f.endswith(('.txt', '.log')):
                    candidates.append(os.path.join(root, f))
    for fp in candidates:
        try:
            with open(fp, errors='replace') as fh:
                for line in fh:
                    yield fp, line
        except OSError:
            continue


# --------------------------------------------------------------------------
# streams: which logcat lines carry which measurement, and how to read them
#
# Keyed by a detector (substring test on the raw line) checked in order,
# first match wins -- same style as vcpuwait433/decompose.py, extended to
# every tag this lane's capture formats were read from (see NOTES.md
# section 1.2's list of source files read for the exact print formats).
# --------------------------------------------------------------------------

def parse_gfps(msg):
    r = {'gfps': num(r'gfps=(\d+)', msg)}
    g = re.search(r'G:([\d.]+)\(([\d.]+)-([\d.]+)\)', msg)
    if g:
        r['G'], r['G_min'], r['G_max'] = (float(x) for x in g.groups())
    r['Df'] = num(r'Df:(\d+)', msg)
    r['Ri'] = num(r'Ri:([\d.]+)', msg)
    r['Tq'] = num(r'Tq:(\d+)', msg)
    r['S'] = num(r' S:([\d.]+)', msg)
    r['J'] = num(r' J:([\d.]+)', msg)
    return r


def parse_pace(msg):
    r = {'f': num(r'f=(\d+)', msg), 'max': num(r'max=([\d.]+)', msg), 'ms': num(r'ms=([\d.]+)', msg)}
    return r


def parse_phase(msg):
    r = {}
    fin = re.search(r'Fin:([\d.]+)\(Sub:([\d.]+) Fen:([\d.]+)\)', msg)
    if fin:
        r['Fin'], r['Sub'], r['Fen'] = (float(x) for x in fin.groups())
    r['Surf'] = num(r'^Surf:([\d.]+)', msg)
    tot = num(r'Tot:([\d.]+)', msg)
    if tot is not None:
        r['Tot'] = tot
    gpu = re.search(r'GPU:([\d.]+)\(R:([\d.]+) X:([\d.]+)', msg)
    if gpu:
        r['GPU'], r['GPU_R'], r['GPU_X'] = (float(x) for x in gpu.groups())
    r['Draw'] = num(r'Draw:([\d.]+)', msg)
    idle = re.search(r'Idle:([\d.]+)\(Fr:([\d.]+) St:([\d.]+)\)', msg)
    if idle:
        r['Idle'] = float(idle.group(1))
    return r


def parse_drawrec(msg):
    r = {
        'f': num(r' f=(\d+)', msg), 'dirty': num(r'dirty=(\d+)', msg),
        'redo': num(r'redo=(\d+)', msg), 'redoKB': num(r'redoKB=(\d+)', msg),
        'runs': num(r'runs=(\d+)', msg), 'pages': num(r'pages=(\d+)', msg),
        'shc': num(r'shc=(\d+)', msg),
    }
    w = re.search(r'walks=(\d+)\+(\d+)', msg)
    if w:
        r['walk_flip'], r['walk_budget'] = (float(x) for x in w.groups())
    return r


def parse_rdc(msg):
    r = {
        'f': num(r' f=(\d+)', msg), 'dt': num(r' dt=(\d+)', msg),
        'tcpu': num(r'tcpu=([\d.]+)', msg), 'rdous': num(r'rdous=(\d+)', msg),
    }
    vtx = re.search(r'vtx=(\d+)/(\d+)/(\d+)/(\d+)', msg)
    tex = re.search(r'tex=(\d+)/(\d+)/(\d+)/(\d+)', msg)
    if vtx:
        r['vtx_us'] = float(vtx.group(2))
    if tex:
        r['tex_us'] = float(tex.group(2))
    return r


def parse_idlehalt(msg):
    span = num(r'span_us=(\d+)', msg)
    r = {'w': num(r' w=(\d+)', msg), 'span_us': span,
         'run_us': num(r'run_us=(\d+)', msg), 'rq_us': num(r'rq_us=(\d+)', msg)}
    return r


def parse_rr425w(msg):
    return {'w': num(r' w=(\d+)', msg), 'idle_us': num(r'idle_us=(\d+)', msg),
            'busy_us': num(r'busy_us=(\d+)', msg)}


def parse_tlb68(msg):
    return {'w': num(r' w=(\d+)', msg), 'dt': num(r' dt=(\d+)', msg), 'cpu': num(r'cpu=(\d+)', msg)}


def parse_lock474(msg):
    return {'dt_ms': num(r'dt_ms=(\d+)', msg),
            'rd_wait_ms': num(r'rd_wait_ms=([\d.]+)', msg),
            'wr_wait_ms': num(r'wr_wait_ms=([\d.]+)', msg)}


def parse_uber569(msg):
    return {'mode': num(r'mode=(\d+)', msg), 'cold': num(r'cold=(\d+)', msg),
            'lib_ms': num(r'lib_ms=([\d.]+)', msg), 'queued': num(r'queued=(\d+)', msg)}


def parse_rpbrk(msg):
    m = re.search(r'RP:(\d+)\(fin(\d+) fb(\d+) qry(\d+) clr(\d+) nd(\d+) srf(\d+)\)', msg)
    if not m:
        return {}
    keys = ('RP', 'fin', 'fb', 'qry', 'clr', 'nd', 'srf')
    return dict(zip(keys, (float(x) for x in m.groups())))


# (stream, detector(msg)->bool, parser(msg)->dict). Order matters: bracketed
# tags are checked before the bare 'gfps='/'hakuX-pace' substrings because a
# line can contain both a tag-column hint and a bracket (xemu-surf's
# "[surf413] xemu-surf ..." for one), and the bracket is the one that is
# never shared by another stream.
STREAMS = [
    ('rpbrk', lambda m: m.startswith('RP:'), parse_rpbrk),
    ('drawrec', lambda m: '[drawrec]' in m, parse_drawrec),
    ('rdc', lambda m: '[rdc]' in m, parse_rdc),
    ('idlehalt', lambda m: '[idlehalt]' in m, parse_idlehalt),
    ('rr425w', lambda m: '[rr425w]' in m, parse_rr425w),
    ('tlb68', lambda m: '[tlb68]' in m, parse_tlb68),
    ('lock474', lambda m: '[lock474]' in m, parse_lock474),
    ('uber569', lambda m: '[uber569]' in m, parse_uber569),
    ('gpl569', lambda m: '[gpl569]' in m, lambda m: {'links': num(r'links=(\d+)', m), 'cold': num(r'cold=(\d+)', m)}),
    ('savestate', lambda m: '[savestate]' in m, lambda m: {'op': (re.search(r'op=(\w+)', m) or [None, None])[1]}),
    ('gfps', lambda m: 'gfps=' in m, parse_gfps),
    ('pace', lambda m: m.startswith('f=') and 'max=' in m, parse_pace),
    ('phase', lambda m: m.startswith('Surf:') or ('Fin:' in m and 'Idle:' in m and 'Tot:' in m), parse_phase),
    ('vulkan', lambda m: m.startswith('GPU:') and 'Driver:' in m, lambda m: {'line': m}),
    ('boot_marker', lambda m: 'init: pipelines' in m or 'Shader module warm-up' in m, lambda m: {}),
    ('gc', lambda m: m.startswith('GC_') or 'Background concurrent copying GC' in m, lambda m: {}),
]


def classify(tag, msg):
    for name, detect, parser in STREAMS:
        try:
            if detect(msg):
                return name, parser(msg)
        except Exception:
            continue
    return None, None


# --------------------------------------------------------------------------
# capture loading: parse every line of every file into per-stream rows with
# a (file, t) key; t is seconds-in-day, fine for one capture (never spans
# midnight in anything this lane has read).
# --------------------------------------------------------------------------

class Capture:
    def __init__(self, path, pid=None):
        self.path = path
        self.pid = pid
        self.rows = {name: [] for name, _d, _p in STREAMS}  # name -> [(t, fields)]
        self.files_read = set()
        self.pids_seen = set()
        self._load()

    def _load(self):
        for fp, line in iter_logcat_files(self.path):
            parsed = parse_line(line)
            if not parsed:
                continue
            t, pid, tag, msg = parsed
            self.pids_seen.add(pid)
            if self.pid and pid != str(self.pid):
                continue
            name, fields = classify(tag, msg)
            if name is None:
                continue
            self.files_read.add(fp)
            self.rows[name].append((t, fields))
        for name in self.rows:
            self.rows[name].sort(key=lambda r: r[0])

    def has(self, stream):
        return len(self.rows.get(stream, [])) > 0

    def near(self, stream, t, tol=3.0):
        """Fields of the row in `stream` nearest at-or-before t, within tol seconds."""
        rs = self.rows.get(stream, [])
        ts = [r[0] for r in rs]
        i = bisect.bisect_right(ts, t) - 1
        if i < 0 or t - ts[i] > tol:
            return None
        return rs[i][1]

    def between(self, stream, t0, t1):
        rs = self.rows.get(stream, [])
        ts = [r[0] for r in rs]
        lo = bisect.bisect_left(ts, t0)
        hi = bisect.bisect_right(ts, t1)
        return [r[1] for r in rs[lo:hi]]


# --------------------------------------------------------------------------
# windows
# --------------------------------------------------------------------------

class Window:
    def __init__(self, t0, t1, fps, source):
        self.t0, self.t1, self.fps, self.source = t0, t1, fps, source
        self.fields = {}       # stream -> list of field dicts seen in [t0, t1]
        self.gameplay = True
        self.refuse_reason = None


def build_windows(cap):
    """Flip-counted windows from hakuX-pace (preferred: pace's own ms= is the
    window's real duration, not gfps='s trailing ~1s rate -- FINDINGS.md
    Known methodology note), else fixed 1 s slices over the gfps timeline."""
    windows = []
    if cap.has('pace'):
        prev_t = None
        for t, fields in cap.rows['pace']:
            ms = fields.get('ms')
            if ms is None:
                prev_t = t
                continue
            t0 = prev_t if prev_t is not None else t - ms / 1000.0
            fps = fields.get('f') and (60.0 / (ms / 1000.0) if ms else None)
            windows.append(Window(t0, t, fps, 'pace'))
            prev_t = t
    elif cap.has('gfps'):
        for t, fields in cap.rows['gfps']:
            windows.append(Window(t - 1.0, t, fields.get('gfps'), 'gfps-1s'))
    for w in windows:
        for stream in cap.rows:
            rows = cap.between(stream, w.t0, w.t1)
            if rows:
                w.fields[stream] = rows
    return windows


def mark_refused(windows, cap):
    """Exclude boot-warmup, save-state-load, and frozen (zero flip advance)
    windows from scoring -- never scored as gameplay, never silently dropped
    either (counted and reported)."""
    boot_t = [t for t, _ in cap.rows.get('boot_marker', [])]
    load_t = [t for t, f in cap.rows.get('savestate', []) if f.get('op') == 'load']
    for w in windows:
        if any(w.t0 - 2 <= t <= w.t1 + 2 for t in boot_t):
            w.gameplay, w.refuse_reason = False, 'boot/pipeline-warmup marker in window'
            continue
        if any(w.t0 <= t <= w.t1 for t in load_t):
            w.gameplay, w.refuse_reason = False, 'save-state load in window'
            continue
        pace_rows = w.fields.get('pace')
        if pace_rows:
            # between(t0, t1) is inclusive of t0, which is the *previous*
            # window's own terminal pace row -- so pace_rows can carry that
            # trailing non-zero row alongside this window's own. The window
            # is defined by its own row (the last one, at t1); that is the
            # one flip-advance event this window actually reports.
            own = pace_rows[-1]
            if (own.get('max') or 0) == 0 and (own.get('ms') or 0) == 0:
                w.gameplay, w.refuse_reason = False, 'zero flip advance (frozen/black)'


# --------------------------------------------------------------------------
# bars (targets.toml)
# --------------------------------------------------------------------------

def load_bar(title, targets_path):
    """Return (target_fps, fps_tolerance, bar) for a title name or id, falling
    back to [defaults] -- a title absent from targets.toml (Fable) is judged
    on defaults only, same as the title_verdict.py convention."""
    defaults = {'playable_fps': 30.0, 'fps_share_min': 0.90, 'fps_tolerance': 0.95}
    if not targets_path or not os.path.exists(targets_path):
        d = defaults
    else:
        import tomllib
        with open(targets_path, 'rb') as fh:
            doc = tomllib.load(fh)
        d = {**defaults, **doc.get('defaults', {})}
        for _tid, entry in doc.get('titles', {}).items():
            if title and (title == _tid or title.lower() in entry.get('name', '').lower()):
                d = {**d, **{k: v for k, v in entry.items() if k in ('target_fps', 'fps_tolerance')}}
                break
    target = d.get('target_fps', d['playable_fps'])
    tol = d.get('fps_tolerance', 0.95)
    return target, tol, target * tol


# --------------------------------------------------------------------------
# candidates: each is (key, title_scope, requires streams, check(windows))
# check returns (verdict, detail) where verdict in
#   'supported' | 'refuted' | 'not measured'
# --------------------------------------------------------------------------

def _dip_good(windows, bar):
    scored = [w for w in windows if w.gameplay and w.fps is not None]
    dip = [w for w in scored if w.fps < bar]
    good = [w for w in scored if w.fps >= bar]
    return dip, good


def _need(dip, good):
    return len(dip) >= MIN_WINDOWS and len(good) >= MIN_WINDOWS


def _mean_field(windows, stream, key):
    vals = []
    for w in windows:
        for row in w.fields.get(stream, []):
            if row.get(key) is not None:
                vals.append(row[key])
    return statistics.mean(vals) if vals else None


def check_gpu_saturation(windows, bar):
    dip, good = _dip_good(windows, bar)
    if not _need(dip, good):
        return 'not measured', 'insufficient windows (need >=%d of each class)' % MIN_WINDOWS
    dip_gpu, good_gpu = _mean_field(dip, 'phase', 'GPU'), _mean_field(good, 'phase', 'GPU')
    dip_tot, good_tot = _mean_field(dip, 'phase', 'Tot'), _mean_field(good, 'phase', 'Tot')
    if None in (dip_gpu, good_gpu, dip_tot, good_tot) or not dip_tot or not good_tot:
        return 'not measured', 'hakuX-phase absent from this capture (perflog-only tag)'
    dip_busy, good_busy = 100 * dip_gpu / dip_tot, 100 * good_gpu / good_tot
    if dip_busy > 85 and dip_busy - good_busy > 15:
        return 'supported', 'GPU busy %.0f%% in dip windows vs %.0f%% in good (n=%d/%d)' % (dip_busy, good_busy, len(dip), len(good))
    return 'refuted', 'GPU busy %.0f%% in dip windows vs %.0f%% in good (n=%d/%d) -- not saturated' % (dip_busy, good_busy, len(dip), len(good))


def check_tlb_walk_cost(windows, bar):
    dip, good = _dip_good(windows, bar)
    if not _need(dip, good):
        return 'not measured', 'insufficient windows (need >=%d of each class)' % MIN_WINDOWS
    tcpu = _mean_field(dip, 'rdc', 'tcpu')
    vtx = _mean_field(dip, 'rdc', 'vtx_us')
    tex = _mean_field(dip, 'rdc', 'tex_us')
    if tcpu is None:
        return 'not measured', '[rdc] absent from this capture'
    walk_ms = ((vtx or 0) + (tex or 0)) / 1000.0
    share = 100 * walk_ms / tcpu if tcpu else None
    if share is None:
        return 'not measured', '[rdc] tcpu present but walk-time fields absent'
    if share > 20:
        return 'supported', 'TLB walk time is %.1f%% of render-thread CPU in dip windows (n=%d)' % (share, len(dip))
    return 'refuted', 'TLB walk time is %.1f%% of render-thread CPU in dip windows (n=%d) -- not the dominant cost' % (share, len(dip))


def check_rpbrk(windows, bar):
    return 'not measured', ('hakuX-rpbrk/RPBreaks races across threads once the deferred-finish '
                             'render thread is active (FINDINGS.md section 2 item 6); not citable '
                             'per-window in a dip/park regime -- fixing the racy emitter is itself '
                             'the first step (FINDINGS.md candidate 1)')


def check_fin_fen_swing(windows, bar):
    dip, good = _dip_good(windows, bar)
    if not _need(dip, good):
        return 'not measured', 'insufficient windows (need >=%d of each class)' % MIN_WINDOWS
    dip_fen, good_fen = _mean_field(dip, 'phase', 'Fen'), _mean_field(good, 'phase', 'Fen')
    if dip_fen is None or good_fen is None:
        return 'not measured', 'hakuX-phase absent from this capture (perflog-only tag)'
    if dip_fen - good_fen > 2.0:
        return 'supported', 'Fen (fence-wait) %.1fms dip vs %.1fms good (n=%d/%d)' % (dip_fen, good_fen, len(dip), len(good))
    return 'refuted', 'Fen (fence-wait) %.1fms dip vs %.1fms good (n=%d/%d) -- no swing' % (dip_fen, good_fen, len(dip), len(good))


def check_fin_sub_swing(windows, bar):
    """Fin:(Sub:.. Fen:..) splits two different waits on the same calling
    thread (draw.c's finish_submit vs finish_fence phase timers, #433;
    docs/lanes/fpsdata1018/NOTES.md, mechanism account): Sub is the CURRENT
    finish's own wait -- on a non-render-thread caller, `qemu_event_wait`
    for the async render thread to submit+complete (draw.c ~5924-6017) --
    while Fen (check_fin_fen_swing, above) is the NEXT frame slot's
    already-in-flight fence wait during frame rotation (draw.c ~6097-6107).
    A title whose Fin swing is Sub, not Fen, is not queue-depth-bound the
    way GTA III is; it is waiting on the render thread itself to service a
    non-deferred finish."""
    dip, good = _dip_good(windows, bar)
    if not _need(dip, good):
        return 'not measured', 'insufficient windows (need >=%d of each class)' % MIN_WINDOWS
    dip_sub, good_sub = _mean_field(dip, 'phase', 'Sub'), _mean_field(good, 'phase', 'Sub')
    if dip_sub is None or good_sub is None:
        return 'not measured', 'hakuX-phase absent from this capture (perflog-only tag)'
    if dip_sub - good_sub > 2.0:
        return 'supported', 'Sub (finish-submit wait) %.1fms dip vs %.1fms good (n=%d/%d)' % (dip_sub, good_sub, len(dip), len(good))
    return 'refuted', 'Sub (finish-submit wait) %.1fms dip vs %.1fms good (n=%d/%d) -- no swing' % (dip_sub, good_sub, len(dip), len(good))


def check_surf_download_wait(windows, bar):
    """Surf (hakuX-phase's surface_update_ms, pgraph/vk/surface.c:6134/6292)
    swinging with no matching Fin/Fen/Sub swing points at
    download_surface_complete_deferred_at (surface.c:2105), called from
    pgraph_vk_surface_update's deferred-download retirement
    (surface.c:6210-6227) -- its own `dfF` (df_flush_ms) sub-field in the
    xemu-surf `Srf:` line (nv2a_profile_get_surf_timing_str, profile.c:1135)
    accounts for most of Surf in every dip window checked while making this
    candidate (#433; docs/lanes/fpsdata1018/NOTES.md, mechanism account),
    not upload/create/bind. This check reads only the coarse Surf field;
    `Srf:`'s dfF/dfR split is not parsed here (not needed for a verdict)."""
    dip, good = _dip_good(windows, bar)
    if not _need(dip, good):
        return 'not measured', 'insufficient windows (need >=%d of each class)' % MIN_WINDOWS
    dip_surf, good_surf = _mean_field(dip, 'phase', 'Surf'), _mean_field(good, 'phase', 'Surf')
    if dip_surf is None or good_surf is None:
        return 'not measured', 'hakuX-phase absent from this capture, or Surf field never printed (perflog-only tag)'
    if dip_surf - good_surf > 2.0:
        return 'supported', 'Surf (surface update) %.1fms dip vs %.1fms good (n=%d/%d)' % (dip_surf, good_surf, len(dip), len(good))
    return 'refuted', 'Surf (surface update) %.1fms dip vs %.1fms good (n=%d/%d) -- no swing' % (dip_surf, good_surf, len(dip), len(good))


def check_redo_shc_volume(windows, bar):
    dip, good = _dip_good(windows, bar)
    if not _need(dip, good):
        return 'not measured', 'insufficient windows (need >=%d of each class)' % MIN_WINDOWS
    dip_shc, good_shc = _mean_field(dip, 'drawrec', 'shc'), _mean_field(good, 'drawrec', 'shc')
    if dip_shc is None or good_shc is None:
        return 'not measured', '[drawrec] absent from this capture'
    note = ('redo/shc volume %.0f dip vs %.0f good (n=%d/%d) correlates, but no build times the '
            'copy/full-shader-bind path directly -- this candidate stays "not measured" for '
            'causation until that timer exists (FINDINGS.md candidate 3)' % (dip_shc, good_shc, len(dip), len(good)))
    return 'not measured', note


def check_art_gc(windows, bar):
    dip, good = _dip_good(windows, bar)
    if not _need(dip, good):
        return 'not measured', 'insufficient windows (need >=%d of each class)' % MIN_WINDOWS
    hit = sum(1 for w in dip if w.fields.get('gc'))
    if hit:
        return 'supported', '%d of %d dip windows contain an ART GC log line' % (hit, len(dip))
    total_gc = sum(len(w.fields.get('gc', [])) for w in windows)
    if total_gc == 0:
        return 'refuted', 'zero ART GC log lines in this capture (n=%d dip windows checked)' % len(dip)
    return 'refuted', 'ART GC lines present elsewhere in the capture but not inside any of %d dip windows' % len(dip)


def _needs_capture_samples(name):
    def check(windows, bar):
        return 'not measured', ('requires a live system snapshot (%s) that only `fpsdiag.py capture` '
                                 'produces; this capture has no such samples -- see `gaps`' % name)
    return check


CANDIDATES = [
    ('gpu_saturation', 'GTA III, SA, Blinx 2 (not in FINDINGS.md\'s ranked could-be list; a Known/Not check)', check_gpu_saturation),
    ('tlb_walk_cost', 'Fable, Blinx 2, GTA III pilot (Known/Not check)', check_tlb_walk_cost),
    ('c1_rpbrk_nondraw_breaks', 'GTA III', check_rpbrk),
    ('c2_fin_fen_queue_depth', 'GTA III', check_fin_fen_swing),
    ('c2b_fin_sub_renderthread_wait', 'RalliSport 2, Fable', check_fin_sub_swing),
    ('c3_redo_shc_copy_bind_cost', 'Fable, Blinx 2', check_redo_shc_volume),
    ('c9_surf_download_wait', 'Blinx 2', check_surf_download_wait),
    ('c4_competing_process_cpu', 'GTA III, Blinx 2, Fable', _needs_capture_samples('dumpsys cpuinfo / /proc/*/stat')),
    ('c5_memory_page_cache_pressure', 'GTA III, Blinx 2, Fable', _needs_capture_samples('/proc/meminfo samples')),
    ('c6_thread_core_migration', 'GTA III, Blinx 2, Fable', _needs_capture_samples('/proc/<pid>/task/*/stat processor field')),
    ('c7_art_gc_pause', 'GTA III, Blinx 2, Fable', check_art_gc),
    ('c8_surfaceflinger_backpressure', 'GTA III, Blinx 2, Fable', _needs_capture_samples('dumpsys SurfaceFlinger')),
]


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def cmd_analyze(args):
    cap = Capture(args.path, pid=args.pid)
    if not cap.files_read:
        print('VOID: no logcat-format lines found under %r' % args.path)
        if cap.pids_seen:
            print('   pids seen in this capture: %s' % ', '.join(sorted(cap.pids_seen)))
        return 1
    windows = build_windows(cap)
    if not windows:
        print('VOID: no hakuX-pace or hakuX-perf gfps= lines found -- cannot build a single window')
        return 1
    mark_refused(windows, cap)
    target, tol, bar = load_bar(args.title, args.bars)
    scored = [w for w in windows if w.gameplay]
    refused = [w for w in windows if not w.gameplay]
    dip, good = _dip_good(windows, bar)
    print('== %s' % args.path)
    print('   files read: %d' % len(cap.files_read))
    print('   bar = %.1f fps (target %.1f x tolerance %.2f)' % (bar, target, tol))
    print('   windows: %d total, %d scored, %d refused (not gameplay)' % (len(windows), len(scored), len(refused)))
    for w in refused[:5]:
        print('     refused %.1f-%.1f: %s' % (w.t0, w.t1, w.refuse_reason))
    print('   dip (< bar): %d windows, good (>= bar): %d windows' % (len(dip), len(good)))
    print()
    print('   candidate                         title scope                                    verdict        detail')
    for key, scope, check in CANDIDATES:
        verdict, detail = check(windows, bar)
        print('   %-33s %-45s %-14s %s' % (key, scope[:45], verdict, detail))
    return 0


def cmd_gaps(args):
    cap = Capture(args.path, pid=args.pid) if args.path else None
    print('fpsdiag.py gaps -- counters named in FINDINGS.md section 3 the current build/capture does not produce')
    print()
    for key, scope, check in CANDIDATES:
        if cap is None:
            print('%-33s needs: see FINDINGS.md section 3 instrument column' % key)
            continue
        windows = build_windows(cap)
        mark_refused(windows, cap)
        _target, _tol, bar = load_bar(args.title, args.bars)
        verdict, detail = check(windows, bar)
        if verdict == 'not measured':
            print('%-33s GAP: %s' % (key, detail))
    return 0


def cmd_capture(args):
    """Attach to an already-running session and record one host-side capture.
    Never launches, never sends input -- every sub-step below is a read.
    Not run by this lane (never touches a device); written for the owner
    (CAPTURE.md) or a lane holding a device, per request.sh/ab_run.sh."""
    import subprocess

    def adb(*cmd, timeout=10):
        return subprocess.run(['adb', '-s', args.serial] + list(cmd),
                               capture_output=True, text=True, timeout=timeout).stdout

    os.makedirs(args.out, exist_ok=True)
    samples_dir = os.path.join(args.out, 'samples')
    os.makedirs(samples_dir, exist_ok=True)

    # 1. Driver identity: dump the FULL ring buffer first (not just new
    # lines) so a one-time startup line already scrolled past is still
    # caught, before following live output for `seconds`. If still absent,
    # this is recorded plainly -- it is not proof of the stock driver
    # (FINDINGS.md 1.1 methodology note); it is proof nothing conclusive
    # was observed, and the manifest says exactly that.
    ring = adb('logcat', '-d', '-v', 'threadtime')
    gpu_line = next((l for l in ring.splitlines() if 'Driver: PurpleVK' in l or ('GPU:' in l and 'Driver:' in l)), None)

    with open(os.path.join(args.out, 'logcat.txt'), 'w') as fh:
        fh.write(ring)
        proc = subprocess.Popen(['adb', '-s', args.serial, 'logcat', '-v', 'threadtime'],
                                 stdout=fh, stderr=subprocess.DEVNULL)
        try:
            period = 1.0
            elapsed = 0.0
            with open(os.path.join(samples_dir, 'periodic.ndjson'), 'w') as sfh:
                while elapsed < args.seconds:
                    sample = {
                        't': elapsed,
                        'thermal': adb('shell', 'for z in /sys/class/thermal/thermal_zone*/temp; do cat "$z"; done'),
                        'battery_temp': adb('shell', 'cat /sys/class/power_supply/battery/temp'),
                        'meminfo': adb('shell', 'cat /proc/meminfo'),
                        'wakefulness': adb('shell', 'dumpsys power | grep mWakefulness'),
                        'cpu_online': adb('shell', 'cat /sys/devices/system/cpu/online'),
                        'top': adb('shell', 'top -b -n 1 -o %CPU | head -15'),
                    }
                    if args.pid:
                        sample['task_stat'] = adb('shell', 'cat /proc/%s/task/*/stat 2>/dev/null' % args.pid)
                    sfh.write(json.dumps(sample) + '\n')
                    sfh.flush()
                    time.sleep(period)
                    elapsed += period
        finally:
            proc.terminate()

    manifest = {
        'serial': args.serial, 'title': args.title, 'seconds': args.seconds,
        'gpu_driver_line': gpu_line or 'not observed (ring buffer did not contain a startup driver line; '
                                        'this is NOT evidence of a non-PurpleVK driver on an attach capture -- '
                                        'confirm separately, e.g. a fresh app launch, before trusting this field)',
        'captured_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(os.path.join(args.out, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=2)
    print('wrote %s' % args.out)
    if gpu_line is None:
        print('WARNING: no GPU driver line observed in the ring buffer -- see manifest.json "gpu_driver_line"')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    pa = sub.add_parser('analyze', help='cut a capture into windows and report candidate verdicts')
    pa.add_argument('path')
    pa.add_argument('--title')
    pa.add_argument('--pid', help='restrict to one logcat pid, for a multi-title capture file')
    pa.add_argument('--bars', default=os.path.join(os.path.dirname(__file__), '..', '..', 'titles', 'targets.toml'))
    pa.set_defaults(func=cmd_analyze)

    pg = sub.add_parser('gaps', help='list missing counters for the could-be candidates')
    pg.add_argument('path', nargs='?')
    pg.add_argument('--title')
    pg.add_argument('--pid')
    pg.add_argument('--bars', default=os.path.join(os.path.dirname(__file__), '..', '..', 'titles', 'targets.toml'))
    pg.set_defaults(func=cmd_gaps)

    pc = sub.add_parser('capture', help='attach to a running session and record one host-side capture')
    pc.add_argument('--serial', required=True)
    pc.add_argument('--title', required=True)
    pc.add_argument('--seconds', type=int, required=True)
    pc.add_argument('--out', required=True)
    pc.add_argument('--pid')
    pc.add_argument('--attach', action='store_true', default=True)
    pc.set_defaults(func=cmd_capture)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
