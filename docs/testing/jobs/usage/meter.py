#!/usr/bin/env python3
"""
meter.py -- week-to-date dollar-equivalent spend by actor, estimated against
the account's weekly usage window.

    meter.py                 # one tick: scan, update $WORK/usage/state.json
                              # and usage/summary.txt, print the summary line
    meter.py calibrate PCT   # add a calibration point: "the account reads
                              # PCT% right now" (from claude.ai)

MODEL-FREE and INCREMENTAL. This runs as a lane briefing's "no device" cousin
-- a systemd timer every 30 min (units/hakux-usage-meter.{service,timer}),
not a Claude session. Every transcript file this has already read is
recorded in state["offsets"] by (size, mtime); a run that finds a file
unchanged never opens it, and a file that only grew is seek()ed to the
remembered byte and reads just the new tail. The one unavoidable full read
is the very first tick ever, or a transcript this host has never seen
before -- not "every run", which is the thing the brief asked this file not
to do.

WHAT THIS CANNOT SEE, AND WHY THE CALIBRATION EXISTS. There is no API here
for "what percent of the account's weekly window is used" -- same absence
jobs/window.sh's big comment documents for the five-hour and weekly windows.
What this file CAN compute is a dollar-equivalent spend figure from Claude
Code's own transcripts (session jsonl files under ~/.claude/projects), priced
by fitting a per-model rate against the few headless runs that log a real
total_cost_usd (jobs/summarise_run.py's index entries). That figure is a
LOWER BOUND on the account's real usage: it cannot see the owner's own
claude.ai (web) use, and it only scans transcripts that look like hakuX work
(see RELEVANT below) -- a deliberate narrowing, not an oversight, because the
calibration below is what reconciles "this fleet's dollar spend" against
"the account's percent reading", and that reconciliation already absorbs
everything this file cannot observe directly.

THE CALIBRATION. Two readings the owner took from claude.ai are seeded as
CAL_SEED below (2026-10-02 10:10 PDT decision). Each is turned into an
implied weekly $ capacity by computing this file's own spend-since-that-
reading's-week-start at the moment of the reading, then dividing by the
percent: capacity = spend_at_reading / (percent/100). The two seeds disagree
(see NOTES.md for the measured gap) because the owner's own non-harness
usage is a different fraction of the account's week each time; the ESTIMATE
below is from the most recent calibration point, not an average of all of
them, because recency is the only information this file has about which
fraction is current. `calibrate PCT` appends a new point computed the same
way and does not touch the two seeds.

THE WEEK ANCHOR mirrors jobs/window.sh's (Thursday 21:00 America/Los_Angeles,
the same owner decision): duplicated rather than imported, because the two
files have no runtime dependency on each other and sharing a module would
create one across directories neither lane owns outright. Kept honest by
selftest.d/89-usage-mode.sh, which sources window.sh and asserts the two
compute the identical week start for several fixed instants -- the same
cross-check jobs/localtime.sh and localtime.py use for the display zone.

THE FIT (#433, meterfit1010). fit_prices() above prices a modelUsage token
against that SAME run's modelUsage cost -- so a billed model call that never
makes it into a transcript (it happens; see NOTES.md) is invisible to both
sides of that ratio, and the 14-day window it averages over lags a week
whose price mix is still moving. fit_prices_transcripts() instead prices
each run's own TRANSCRIPT token sum (transcript_eq) against that run's own
costUSD: the missing calls now show up as a gap between the two totals, not
a wash, and a short trailing window (SHORT_WINDOW_HOURS) tracks this week
instead of the last two. combined_price_map() is what scan_transcripts()
actually prices events with: fit_prices_transcripts()'s number for a model
when it has enough recent data (SHORT_MIN_RUNS, SHORT_MIN_COST) or any data
at all within the fit window, else fit_prices()'s -- so a model the
transcript fit never saw keeps today's behaviour exactly. See
selftest.d/88-usage-meterfit.sh and docs/lanes/meterfit1010/NOTES.md.
"""
import glob
import json
import os
import re
import sys
import time
import collections
import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:                                   # pragma: no cover
    ZoneInfo = None

WORK = os.environ.get("HAKUX_WORK", os.path.expanduser("~/hakux-work"))
PROJECTS_DIR = os.environ.get("HAKUX_CLAUDE_PROJECTS", os.path.expanduser("~/.claude/projects"))
STATE_PATH = os.path.join(WORK, "usage", "state.json")
SUMMARY_PATH = os.path.join(WORK, "usage", "summary.txt")

WEEK_ANCHOR_DAY = "Thu"
WEEK_ANCHOR_HOUR = 21
WEEK_ANCHOR_TZ = "America/Los_Angeles"
KEEP_DAYS = 8            # events trimmed to this trailing window; > 7 so a
                          # tick right after the reset still has last week's
                          # tail for the burn-rate windows, never for % math

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# The owner's two claude.ai readings (2026-10-02 10:10 PDT decision). Each is
# (ISO instant with its own UTC offset, percent). Never edited by `calibrate`;
# new points are appended under state["calibration"] instead.
CAL_SEED = [
    ("2026-09-30T22:40:00-07:00", 92.0),
    ("2026-10-02T10:10:00-07:00", 16.0),
]


def _zone(tzname):
    if ZoneInfo is None:
        return datetime.timezone.utc
    try:
        return ZoneInfo(tzname)
    except Exception:
        return datetime.timezone.utc


def week_bounds(now_epoch, anchor_day=WEEK_ANCHOR_DAY, anchor_hour=WEEK_ANCHOR_HOUR,
                 tzname=WEEK_ANCHOR_TZ):
    """-> (start_epoch, end_epoch) of the week containing now_epoch, anchored
    on the most recent <anchor_day> <anchor_hour>:00 in <tzname> at or before
    now. Mirrors jobs/window.sh's window_check; see module docstring."""
    zone = _zone(tzname)
    anchor = DAYS.index(anchor_day[:3].title())
    now_local = datetime.datetime.fromtimestamp(now_epoch, zone)
    d = now_local.replace(hour=anchor_hour, minute=0, second=0, microsecond=0)
    start_local = d - datetime.timedelta(days=(d.weekday() - anchor) % 7)
    if start_local > now_local:
        start_local -= datetime.timedelta(days=7)
    start = int(start_local.timestamp())
    return start, start + 7 * 86400


def iso_to_epoch(s):
    try:
        return datetime.datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0


# ----------------------------------------------------------------- pricing
def fit_prices(work_dir, max_age_days=14):
    """Per-model $ per input-equivalent-token, fit from the headless run
    index's own total_cost_usd -- the only ground truth available. Reads
    only files under max_age_days (stat is cheap; the content read is small:
    one short JSON object per run)."""
    num = collections.Counter()
    den = collections.Counter()
    cutoff = time.time() - max_age_days * 86400
    for f in glob.glob(os.path.join(work_dir, "logs", "**", "*.json"), recursive=True):
        try:
            if os.path.getmtime(f) < cutoff:
                continue
            r = json.load(open(f))
        except Exception:
            continue
        if not isinstance(r, dict):
            continue
        for m, u in (r.get("modelUsage") or {}).items():
            eq = (u.get("inputTokens", 0) + 1.25 * u.get("cacheCreationInputTokens", 0)
                  + 0.1 * u.get("cacheReadInputTokens", 0) + 5 * u.get("outputTokens", 0))
            if eq and u.get("costUSD"):
                num[m] += u["costUSD"]
                den[m] += eq
    return {m: num[m] / den[m] for m in num if den[m]}


def price_for(price_map, model):
    if not model:
        return None
    for k, v in price_map.items():
        if model in k or k in model:
            return v
    base = re.sub(r"-\d{8}$", "", model)
    for k, v in price_map.items():
        if base and base in k:
            return v
    return None


# ------------------------------------------------------- transcript pricing
SHORT_WINDOW_HOURS = 72   # chosen from the 10-10 audit (NOTES.md): long
                          # enough to hold >= SHORT_MIN_RUNS for every model
                          # that runs daily, short enough to track a week
                          # whose price mix is still moving
SHORT_MIN_RUNS = 5
SHORT_MIN_COST = 5.0      # either floor failing drops a model to the 14-day
                          # window below, same as fit_prices()'s max_age_days


def _norm_model(model):
    """Collapse the billing-only suffixes a modelUsage key can carry (the
    1M-context tag, a dated snapshot) that the transcript's own
    message.model never does -- "claude-opus-5[1m]" bills separately from
    "claude-opus-5" but is the same model logged the same way in the
    transcript."""
    m = re.sub(r"\[1m\]$", "", model)
    m = re.sub(r"-\d{8}$", "", m)
    return m


def transcript_eq(projects_dir, session_id):
    """-> {model: eq} summing ONE run's own transcript -- its main session
    jsonl plus any subagents/*.jsonl beside it -- or None if no transcript
    file exists at all for this session_id (the run is skipped by every
    caller, on both sides of the fit; see module docstring). Dedups by
    assistant message id: the FIRST line holding a given id counts, the same
    rule scan_transcripts applies tick over tick, applied here in one pass
    over however many lines this one run wrote."""
    paths = (glob.glob(os.path.join(projects_dir, "*", session_id + ".jsonl"))
              + glob.glob(os.path.join(projects_dir, "*", session_id, "subagents", "*.jsonl")))
    if not paths:
        return None
    seen = set()
    eq = collections.Counter()
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") != "assistant":
                continue
            m = e.get("message") or {}
            mid = m.get("id")
            if mid:
                if mid in seen:
                    continue
                seen.add(mid)
            model = m.get("model")
            if not model:
                continue
            u = m.get("usage") or {}
            eq[model] += (u.get("input_tokens", 0) + 1.25 * u.get("cache_creation_input_tokens", 0)
                          + 0.1 * u.get("cache_read_input_tokens", 0) + 5 * u.get("output_tokens", 0))
    return eq


def _eq_for_billing_model(eq_by_model, model):
    """-> transcript eq attributed to one modelUsage billing key, matching
    through _norm_model since the transcript never carries that key's
    billing-only suffixes."""
    if model in eq_by_model:
        return eq_by_model[model]
    base = _norm_model(model)
    total = 0.0
    for k, v in eq_by_model.items():
        if _norm_model(k) == base:
            total += v
    return total


def collect_fit_samples(work_dir, projects_dir, max_age_days=14):
    """-> [(mtime, model, costUSD, transcript_eq), ...], one tuple per
    billed model entry of every headless run under work_dir/logs whose run
    log carries a session_id AND a transcript (transcript_eq() found at
    least one file). A run missing either contributes nothing -- same
    silence on both sides of the ratio fit_prices_transcripts() fits, which
    is why a run with no transcript cannot skew it."""
    cutoff = time.time() - max_age_days * 86400
    samples = []
    for f in glob.glob(os.path.join(work_dir, "logs", "**", "*.json"), recursive=True):
        try:
            mtime = os.path.getmtime(f)
            if mtime < cutoff:
                continue
            r = json.load(open(f))
        except Exception:
            continue
        if not isinstance(r, dict):
            continue
        mu = r.get("modelUsage") or {}
        sid = r.get("session_id")
        if not mu or not sid:
            continue
        eq_by_model = transcript_eq(projects_dir, sid)
        if eq_by_model is None:
            continue
        for model, u in mu.items():
            cost = u.get("costUSD")
            eq = _eq_for_billing_model(eq_by_model, model)
            if cost and eq:
                samples.append((mtime, model, cost, eq))
    return samples


def fit_prices_transcripts(samples, now, short_hours=SHORT_WINDOW_HOURS,
                            min_runs=SHORT_MIN_RUNS, min_cost=SHORT_MIN_COST):
    """Per-model $/eq-token, fit against each run's own TRANSCRIPT token sum
    instead of its modelUsage token count (see collect_fit_samples and the
    module docstring's "THE FIT"). Prefers the trailing short_hours window;
    falls back per model to the full `samples` window when short_hours holds
    fewer than min_runs runs or less than min_cost dollars for that model --
    e.g. a model this fleet barely used this week. A model absent from
    `samples` entirely is simply absent from the returned map."""
    short_floor = now - short_hours * 3600
    num_s = collections.Counter(); den_s = collections.Counter()
    n_s = collections.Counter(); cost_s = collections.Counter()
    num_l = collections.Counter(); den_l = collections.Counter()
    for mtime, model, cost, eq in samples:
        num_l[model] += cost
        den_l[model] += eq
        if mtime >= short_floor:
            num_s[model] += cost
            den_s[model] += eq
            n_s[model] += 1
            cost_s[model] += cost
    prices = {}
    for model in den_l:
        if n_s.get(model, 0) >= min_runs and cost_s.get(model, 0) >= min_cost:
            prices[model] = num_s[model] / den_s[model]
        elif den_l[model]:
            prices[model] = num_l[model] / den_l[model]
    return prices


def combined_price_map(work_dir, projects_dir, now, max_age_days=14):
    """The price map scan_transcripts() actually uses: fit_prices_transcripts()'s
    number for a model it has data for, else fit_prices()'s -- "a model with
    no fit at all keeps today's behaviour" (the brief's words)."""
    base = fit_prices(work_dir, max_age_days=max_age_days)
    samples = collect_fit_samples(work_dir, projects_dir, max_age_days=max_age_days)
    merged = dict(base)
    merged.update(fit_prices_transcripts(samples, now))
    return merged


# ------------------------------------------------------------- actor rules
def relevant(proj):
    return "hakux-work" in proj or proj.endswith("-hakuX") or proj == "-home-justin-hakuX"


def classify_dir(proj):
    """-> actor string, or 'NEEDS_MESSAGE' for a bare orchestrator-repo
    session (hostops tick vs. lane.local driving by hand -- only the first
    user message tells those apart), or None if irrelevant."""
    if not relevant(proj):
        return None
    if proj.endswith("-board-wt"):
        return "board"
    m = re.search(r"-wt-(.+)$", proj)
    if m:
        name = m.group(1)
        return "cloud" if name.startswith("cloud-") else "lane:" + name
    if proj.endswith("-hakuX"):
        return "NEEDS_MESSAGE"
    return "other"


def first_user_text(path, limit_bytes=65536):
    """The first non-empty user message, truncated. Used ONLY to tell a
    hostops tick (starts 'FOCUS --' or 'OVERRIDE (') from lane.local typing
    by hand -- never printed, never stored beyond this one classification."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(limit_bytes)
    except OSError:
        return ""
    for line in head.splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") != "user":
            continue
        c = (e.get("message") or {}).get("content")
        s = c if isinstance(c, str) else " ".join(
            x.get("text", "") for x in (c or []) if isinstance(x, dict))
        s = s.strip()
        if s:
            return s[:16]
    return ""


def resolve_message_actor(path):
    head = first_user_text(path)
    if head.startswith("FOCUS") or head.startswith("OVERRIDE"):
        return "hostops"
    return "interactive"


# -------------------------------------------------------------------- state
def load_state():
    try:
        with open(STATE_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {"offsets": {}, "events": [], "calibration": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh)
    os.replace(tmp, STATE_PATH)


# -------------------------------------------------------------------- scan
def scan_transcripts(state, projects_dir, price_map):
    """Update state["offsets"] and append new state["events"]. The very
    first time a file is seen its whole content is read (there is no offset
    to resume from); every run after that reads only the bytes appended
    since the last tick. On a brand new host this means the FIRST tick ever
    reads this fleet's whole history once -- which is also what makes the
    two seeded calibration points (ensure_calibration, called right after
    this, before trim_events) computable from state["events"] without a
    second pass over the same files."""
    offsets = state.setdefault("offsets", {})
    events = state.setdefault("events", [])
    seen_ids = set(e.get("id") for e in events if e.get("id"))
    for path in glob.glob(os.path.join(projects_dir, "**", "*.jsonl"), recursive=True):
        proj = path[len(projects_dir):].lstrip("/").split("/", 1)[0]
        cat = classify_dir(proj)
        if cat is None:
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        rec = offsets.get(path, {})
        start_byte = rec.get("size", 0) if rec.get("mtime") == st.st_mtime else 0
        if start_byte > st.st_size:
            start_byte = 0           # file rotated/truncated: re-read it whole
        if start_byte >= st.st_size and rec.get("mtime") == st.st_mtime:
            continue                 # unchanged since last tick: not opened at all
        actor = rec.get("actor") if cat == "NEEDS_MESSAGE" else cat
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                fh.seek(start_byte)
                chunk = fh.read()
        except OSError:
            continue
        if actor is None and cat == "NEEDS_MESSAGE":
            actor = resolve_message_actor(path)
        last_nl = chunk.rfind("\n")
        if last_nl < 0:
            offsets[path] = {"size": start_byte, "mtime": st.st_mtime, "actor": actor}
            continue
        for line in chunk[:last_nl].splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") != "assistant":
                continue
            m = e.get("message") or {}
            mid = m.get("id")
            if mid and mid in seen_ids:
                continue
            ts = e.get("timestamp")
            try:
                tt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
            u = m.get("usage") or {}
            model = m.get("model")
            eq = (u.get("input_tokens", 0) + 1.25 * u.get("cache_creation_input_tokens", 0)
                  + 0.1 * u.get("cache_read_input_tokens", 0) + 5 * u.get("output_tokens", 0))
            price = price_for(price_map, model)
            if price is None or not eq:
                continue
            if mid:
                seen_ids.add(mid)
            events.append({"ts": tt, "actor": actor, "cost": price * eq, "id": mid,
                           "model": model, "eq": eq})
        offsets[path] = {"size": start_byte + last_nl + 1, "mtime": st.st_mtime, "actor": actor}
    return state


def trim_events(state, now, keep_days=KEEP_DAYS):
    floor = now - keep_days * 86400
    state["events"] = [e for e in state["events"] if e["ts"] >= floor]


def reprice_events(events, price_map):
    """Recompute "cost" in place for every event that carries "model" and
    "eq" (#433: re-pricing without a re-read). An event still in the
    pre-#433 format -- cost only, from before this fit existed -- is left
    exactly as it is; migrate_events() is what clears those out of the
    KEEP_DAYS window so the next scan_transcripts() rebuilds them WITH the
    two fields, which is the only thing that makes them re-priceable."""
    for e in events:
        model, eq = e.get("model"), e.get("eq")
        if model is None or eq is None:
            continue
        price = price_for(price_map, model)
        if price is not None:
            e["cost"] = price * eq


def migrate_events(state, now, keep_days=KEEP_DAYS):
    """One-time upgrade from the pre-#433 state format to the current one.
    A no-op once every event already carries "model" and "eq" (the normal
    case, every tick after the first). Otherwise: drop every event inside
    the keep window -- after trim_events this is ALL of them, so in
    practice this clears the whole list -- and clear the byte offset of
    every transcript file touched inside that window, so the very next
    scan_transcripts() call re-reads those files from byte 0 and rebuilds
    the same events with the two new fields. This is the "re-read the
    transcripts for the KEEP_DAYS window once" the brief asks for: bounded
    to files that could hold something inside the window, not a full-fleet
    re-read."""
    events = state.get("events", [])
    if events and all(("model" in e and "eq" in e) for e in events):
        return
    floor = now - keep_days * 86400
    state["events"] = [e for e in events if e.get("ts", 0) < floor]
    offsets = state.get("offsets", {})
    for path, rec in list(offsets.items()):
        if rec.get("mtime", 0) >= floor:
            del offsets[path]


# --------------------------------------------------------------- reporting
def spend_in(events, start, end=None):
    total = collections.Counter()
    for e in events:
        if e["ts"] < start or (end is not None and e["ts"] >= end):
            continue
        total[e["actor"]] += e["cost"]
    return total


def ensure_calibration(state):
    """Seed the two calibration points, once, from state["events"]. Must run
    AFTER scan_transcripts and BEFORE trim_events: on a brand new host the
    first-ever scan reads this fleet's whole history with no time floor
    (see scan_transcripts), so everything either seed point needs is already
    in state["events"] -- a second pass over the files would read the same
    bytes again for no reason. `have` makes this a no-op on every later
    tick, so the ordering only matters once."""
    have = {c["utc"] for c in state.get("calibration", [])}
    for utc_str, pct in CAL_SEED:
        if utc_str in have:
            continue
        reading_epoch = iso_to_epoch(utc_str)
        if not reading_epoch:
            continue
        wk_start, _ = week_bounds(reading_epoch)
        spend = sum(e["cost"] for e in state["events"] if wk_start <= e["ts"] <= reading_epoch)
        capacity = spend / (pct / 100.0) if pct else None
        state.setdefault("calibration", []).append({
            "utc": utc_str, "percent": pct, "spend_at_time": round(spend, 2),
            "capacity": round(capacity, 2) if capacity else None,
        })


def calibrate(state, percent, now):
    wk_start, _ = week_bounds(now)
    spend = sum(e["cost"] for e in state["events"] if e["ts"] >= wk_start)
    capacity = spend / (percent / 100.0) if percent else None
    state.setdefault("calibration", []).append({
        "utc": datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
                   .strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "percent": percent, "spend_at_time": round(spend, 2),
        "capacity": round(capacity, 2) if capacity else None,
    })


def reprice_calibration_capacity(state):
    """Recompute the LATEST calibration point's capacity from the
    just-repriced events (#433: the Low trigger reads this number, and a
    short fit window can move it every tick as runs roll in and out of the
    window). utc and percent are the owner's reading and are never touched.
    Every OLDER point is left exactly as it is -- it was an owner reading
    already baked in at the time it was taken, not something this tick's
    price belongs to."""
    cal = state.get("calibration") or []
    if not cal:
        return
    latest = cal[-1]
    pct = latest.get("percent")
    reading_epoch = iso_to_epoch(latest.get("utc", ""))
    if not pct or not reading_epoch:
        return
    wk_start, _ = week_bounds(reading_epoch)
    spend = sum(e["cost"] for e in state["events"] if wk_start <= e["ts"] <= reading_epoch)
    latest["spend_at_time"] = round(spend, 2)
    if spend:
        latest["capacity"] = round(spend / (pct / 100.0), 2)


def build_report(state, now):
    wk_start, wk_end = week_bounds(now)
    spend_week = spend_in(state["events"], wk_start)
    spend_1h = spend_in(state["events"], now - 3600)
    spend_6h = spend_in(state["events"], now - 6 * 3600)
    spend_24h = spend_in(state["events"], now - 24 * 3600)
    total_week = sum(spend_week.values())
    rate_1h = sum(spend_1h.values())              # $/h: a 1h window IS an hourly rate
    rate_6h = sum(spend_6h.values()) / 6.0        # $/h: averaged over the window,
    rate_24h = sum(spend_24h.values()) / 24.0     # not the window's raw total -- all
                                                    # three must be the same UNIT or
                                                    # "burn rate over the last 1h, 6h,
                                                    # 24h" would print one figure N
                                                    # times the others for a flat burn.
                                                    # KEEP_DAYS=8 keeps a full 24h of
                                                    # events on hand at every tick, even
                                                    # the first one right after a reset.
    cal = state.get("calibration") or []
    capacity = None
    for c in cal:                                 # most recent point wins; see docstring
        if c.get("capacity"):
            capacity = c["capacity"]
    estimated_pct = (total_week / capacity * 100.0) if capacity else None
    hours_left = max(0.0, (wk_end - now) / 3600.0)
    projected_pct = None
    if capacity and estimated_pct is not None:
        # Project from the 24h rate, not the 6h rate: a day/night cycle, so a
        # single busy evening (bursty lanes, an interactive session) does not
        # get extrapolated over the quiet overnight hours still to come. A
        # 24h window still catches a real sustained ramp, just not a 3-6h
        # spike -- see 89-usage-mode.sh's "burst after quiet" case.
        projected_pct = estimated_pct + (rate_24h * hours_left / capacity * 100.0)
    top3 = sorted(spend_week.items(), key=lambda kv: -kv[1])[:3]
    return {
        "generated_utc": datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week_start_epoch": wk_start, "week_end_epoch": wk_end,
        "spend_by_actor": dict(spend_week), "spend_since_reset": round(total_week, 2),
        "rate_1h": round(rate_1h, 2), "rate_6h": round(rate_6h, 2),
        "rate_24h": round(rate_24h, 2),
        "capacity_dollars_per_week": capacity,
        "estimated_percent": round(estimated_pct, 1) if estimated_pct is not None else None,
        "projected_percent_at_reset": round(projected_pct, 1) if projected_pct is not None else None,
        "top3": top3, "calibration": cal,
    }


def summary_line(report, mode="unknown"):
    pct = report["estimated_percent"]
    proj = report["projected_percent_at_reset"]
    top3 = ", ".join("%s $%.0f" % (a, c) for a, c in report["top3"]) or "none"
    return ("mode=%s estimated_week=%s%% spend_since_reset=$%.0f top3=[%s] "
            "rate_24h=$%.1f/h projected_at_reset=%s%%" % (
                mode, ("%.0f" % pct) if pct is not None else "?",
                report["spend_since_reset"], top3, report["rate_24h"],
                ("%.0f" % proj) if proj is not None else "?"))


def current_mode():
    path = os.path.join(WORK, "usage", "mode")
    try:
        for line in open(path):
            if line.startswith("mode="):
                return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return "unknown"


def main(argv):
    now = float(os.environ.get("HAKUX_NOW", "") or time.time())
    state = load_state()
    migrate_events(state, now)
    price_map = combined_price_map(WORK, PROJECTS_DIR, now)
    scan_transcripts(state, PROJECTS_DIR, price_map)
    reprice_events(state["events"], price_map)
    ensure_calibration(state)
    trim_events(state, now)

    if len(argv) >= 2 and argv[1] == "calibrate":
        if len(argv) < 3:
            print("usage: meter.py calibrate PERCENT", file=sys.stderr)
            return 2
        calibrate(state, float(argv[2]), now)

    reprice_calibration_capacity(state)
    report = build_report(state, now)
    state["last_report"] = report
    save_state(state)

    line = summary_line(report, current_mode())
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    tmp = SUMMARY_PATH + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(line + "\n")
    os.replace(tmp, SUMMARY_PATH)
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
