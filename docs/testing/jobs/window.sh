#!/usr/bin/env bash
#
# The account's usage windows, in one place. SOURCED, never executed.
#
#   . "$JOBS/window.sh"
#   window_limit_hit  <run.json>   0 if that run stopped on the account's window
#   window_note_limit <who> <log>  record the hit (and the reset time, if the
#                                  run told us one) in $WORK/window/limits.tsv
#   window_check                   sets WINDOW_DEFER / WHY / UNTIL / FACTS
#
# WHY ONE FILE. Two jobs already needed the detection (run-claude-job.sh had
# it inline; lane.sh had nothing, so every lane that met a closed window read
# as a lane that failed at its work -- it burned an attempt, and the fourth
# attempt escalates the model). Two more need the reserve (board.sh decides,
# status.sh reports). A regex copied into four files is a regex that means
# four things by the end of the week.
#
# WHAT CAN BE OBSERVED FROM HERE, AND WHAT CANNOT (docs/ORCHESTRATION-DESIGN.md
# §9.1). There is NO API here for "how much of the account's five-hour or
# weekly window is left". Nothing in this file knows it. What it has is:
#
#   - the runs this fleet itself started: logs/<job>/index.tsv, one line per
#     run with turns, seconds and the run's own total_cost_usd;
#   - the moments a session was actually refused: a run whose JSON says the
#     usage limit was reached, which is the ONLY first-hand evidence that the
#     account's window closed, and which sometimes carries the reset time.
#
# So the controls here are evidence-driven and they FAIL OPEN. An unknown
# window must not stop the fleet: a missing signal that halts dispatch is an
# outage with a tidy explanation. Every path that cannot compute an answer
# leaves WINDOW_DEFER=0.

# $WORK/limits.env is the host's dial for every number below; sourcing it
# twice (most callers already have) is harmless.
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
[ -f "$WORK/limits.env" ] && . "$WORK/limits.env"

# ---------------------------------------------------------------- detection
#
# WHY THIS IS NOT THE ONE-LINE GREP IT REPLACES. The old test was
#
#     grep -qiE '"is_error": *true.*(rate.?limit|usage limit)' "$log"
#
# over the whole file. `claude -p --output-format json` writes one long line,
# `is_error` precedes `result` in it, and a run's RESULT IS PROSE THE MODEL
# WROTE. Measured on the host: cloud-remediate-128's result says "a bound for
# the pathological run rather than a rate limit for the normal one" -- and
# `error_max_turns` sets is_error too, so a capped run that happened to
# mention a rate limit in its summary would have been reported as a closed
# window, exited 75, and grown the unit's RestartSec. A lane briefed on THIS
# defect writes that phrase into its own summary by construction.
#
# So the JSON is parsed and the decision is made on fields, not on the prose:
# terminal_reason / subtype / api_error_status, or a result that BEGINS with
# the CLI's own words. The raw-text fallback runs only when there is no
# parsable JSON at all -- a session killed before it wrote one -- because
# that is the one case where the fields cannot be consulted.
#
# WHAT IT COULD NOT BE TESTED AGAINST. No run on this host has ever hit the
# limit (85 logs to 2026-09-19: 72 success, 14 error_max_turns, 5 unparsable,
# zero limit fields), so the exact shape the CLI emits is unconfirmed. That is
# why several fields are accepted rather than one: a miss leaves today's
# behaviour (the run reads as a failure), and there is no shape in the
# measured corpus that this reports as a limit.
window_limit_probe() {   # <log> -> "<0|1> <reset epoch or 0>"
    [ -n "${1:-}" ] && [ -s "$1" ] || { echo "0 0"; return 0; }
    python3 - "$1" <<'PY' 2>/dev/null || echo "0 0"
import json, re, sys

raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
LIMIT = re.compile(r"(usage|rate)[ _-]?limit", re.I)
PHRASE = re.compile(r"Claude (AI )?usage limit reached", re.I)

d = {}
s = raw.find("{")
if s >= 0:
    try:
        d = json.loads(raw[s:raw.rfind("}") + 1])
    except Exception:
        d = {}

res = str(d.get("result") or "")
hit = bool(
    LIMIT.search(str(d.get("terminal_reason") or ""))
    or LIMIT.search(str(d.get("subtype") or ""))
    or LIMIT.search(str(d.get("api_error_status") or ""))
    or PHRASE.match(res.lstrip())
    or re.match(r"\s*(rate[ _-]?limit|usage limit)", res, re.I)
    # No parsable JSON: the session died before writing its result, so the
    # CLI's own message on stderr is all there is.
    or (not d and PHRASE.search(raw))
)
# "Claude AI usage limit reached|<epoch>" -- when the CLI names the reset, that
# is an OBSERVED time, not the five-hour upper bound guessed at below.
reset = 0
m = re.search(r"usage limit reached\|(\d{9,})", raw, re.I)
if m:
    reset = int(m.group(1))
print("%d %d" % (1 if hit else 0, reset))
PY
}

window_limit_hit() {   # <log>
    local p; p="$(window_limit_probe "${1:-}")"
    WINDOW_RESET="${p##* }"
    [ "${p%% *}" = "1" ]
}

# The fleet's only first-hand record of the account's window closing. One
# tab-separated line per hit: when, which session, the reset time if the run
# named one, and the log. window_check reads it; status.sh shows it.
window_note_limit() {   # <who> <log>
    local who="${1:-?}" log="${2:-}" reset="${WINDOW_RESET:-0}" riso="-"
    mkdir -p "$WORK/window" 2>/dev/null || return 0
    [ "${reset:-0}" -gt 0 ] 2>/dev/null && riso="$(date -u -d "@$reset" +%FT%TZ 2>/dev/null || echo -)"
    printf '%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$who" "$riso" "$(basename "${log:-}")" \
        >> "$WORK/window/limits.tsv"
}

# ------------------------------------------------------------------ the reserve
#
# Two rules, both keyed on evidence this fleet produced itself.
#
# 1. COOLDOWN AFTER A MEASURED HIT. A session was refused, so the window is
#    closed. If the run named its reset, we wait for it -- that is a value.
#    If it did not, five hours is an UPPER BOUND on the reset and not its
#    value: waiting the bound would idle up to five hours of open window. So
#    the wait is a re-probe interval (WINDOW_COOLDOWN_MIN, default 30), after
#    which the fleet tries again and either succeeds or records a fresh hit.
#
# 2. THE WEEKLY RESERVE (§9.1: "lanes and audits do not start in the last
#    fifth of the weekly window"). Time alone cannot be the rule: a calendar
#    that stops dispatch every Friday would be a throttle, and §9.1's own
#    sentence says the board "checks the day AND the run index". So both, and
#    the second must be evidence:
#
#      the week is >= 80% elapsed      (WEEK_RESERVE, and the anchor below)
#      AND the run index says the budget is nearly spent
#           -- WEEK_SPEND_BUDGET is declared and 80% of it is gone, or
#           -- this fleet has been refused WEEK_LIMIT_HITS times SINCE THE
#              RESERVE BEGAN, which needs nothing declared at all.
#
#    An undeclared budget with no hits therefore never defers. That is the
#    intended failure mode: expanding is the default.
#
# THE WEEK'S START IS A DECLARATION, NOT A MEASUREMENT. The account's weekly
# window resets on its own anchor, which is not visible from this host, and a
# wrong anchor makes the reserve either permanent or useless. WEEK_ANCHOR (a
# three-letter day, default Mon) and WEEK_ANCHOR_HOUR (UTC, default 0) are in
# $WORK/limits.env, the status page prints the start it used, and the rule is
# built so that being wrong by a day or two costs at most a shifted reserve
# window rather than a stopped fleet.
window_check() {
    WINDOW_DEFER=0; WINDOW_WHY=""; WINDOW_UNTIL=""; WINDOW_FACTS=""; WINDOW_ZONE=0
    local out
    out=$(
        HAKUX_WORK="$WORK" \
        HAKUX_NOW="${HAKUX_NOW:-}" \
        WINDOW_COOLDOWN_MIN="${WINDOW_COOLDOWN_MIN:-30}" \
        WEEK_ANCHOR="${WEEK_ANCHOR:-Mon}" \
        WEEK_ANCHOR_HOUR="${WEEK_ANCHOR_HOUR:-0}" \
        WEEK_RESERVE="${WEEK_RESERVE:-0.2}" \
        WEEK_SPEND_BUDGET="${WEEK_SPEND_BUDGET:-}" \
        WEEK_LIMIT_HITS="${WEEK_LIMIT_HITS:-2}" \
        python3 - <<'PY' 2>/dev/null
import datetime, glob, os, sys

W = os.environ["HAKUX_WORK"]
def num(name, dflt):
    try:
        return float(os.environ.get(name) or dflt)
    except ValueError:
        return float(dflt)

now = int(num("HAKUX_NOW", 0)) or int(datetime.datetime.now(datetime.timezone.utc).timestamp())
UTC = datetime.timezone.utc
def iso(t):
    return datetime.datetime.fromtimestamp(int(t), UTC).strftime("%Y-%m-%dT%H:%MZ")
def epoch(s):
    for f in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%MZ"):
        try:
            return int(datetime.datetime.strptime(s, f).replace(tzinfo=UTC).timestamp())
        except ValueError:
            pass
    return 0

# ---- the week this control is reasoning about
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
try:
    anchor = DAYS.index(os.environ.get("WEEK_ANCHOR", "Mon")[:3].title())
except ValueError:
    anchor = 0
d = datetime.datetime.fromtimestamp(now, UTC).replace(
    hour=int(num("WEEK_ANCHOR_HOUR", 0)), minute=0, second=0, microsecond=0)
start = int((d - datetime.timedelta(days=(d.weekday() - anchor) % 7)).timestamp())
if start > now:
    start -= 7 * 86400
week_end = start + 7 * 86400
elapsed = (now - start) / (7.0 * 86400)

# ---- what this fleet spent since then, from the run index summarise_run.py
# writes. Rows written before the model column existed have eight fields and
# their cost is one column to the left; status.sh shifts them the same way.
spend, runs = 0.0, 0
for f in glob.glob(os.path.join(W, "logs", "*", "index.tsv")):
    try:
        rows = open(f, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        continue
    for line in rows:
        p = line.split("\t")
        if len(p) < 8 or epoch(p[0]) < start:
            continue
        runs += 1
        try:
            spend += float(p[4] if len(p) == 8 else p[5])
        except (ValueError, IndexError):
            pass

# ---- and the times it was actually refused
#
# A refusal is first-hand evidence that A window closed -- but NOTHING HERE CAN
# TELL WHICH. The five-hour window and the weekly one are refused with the same
# message, so counting Tuesday's refusals as evidence that Sunday's weekly
# budget is gone would be reading a bound as a value. Refusals INSIDE the
# reserve's own stretch of the week need no such inference: whichever window
# they belong to, dispatching more sessions into it is waste. So the weekly
# arm counts those, and the week's total is reported but never armed on.
hits, zone_hits, last_hit, last_reset = [], [], 0, 0
try:
    for line in open(os.path.join(W, "window", "limits.tsv"),
                     encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("\t")
        t = epoch(p[0]) if p else 0
        if not t:
            continue
        if t >= start:
            hits.append(t)
        if t >= last_hit:
            last_hit, last_reset = t, (epoch(p[2]) if len(p) > 2 else 0)
except OSError:
    pass

budget = num("WEEK_SPEND_BUDGET", 0)
reserve = num("WEEK_RESERVE", 0.2)
arm_hits = int(num("WEEK_LIMIT_HITS", 2))
cool = int(num("WINDOW_COOLDOWN_MIN", 30)) * 60
zone_start = start + int((1 - reserve) * 7 * 86400)
zone_hits = [t for t in hits if t >= zone_start]

facts = ("week from %s (%d%% elapsed, reserve from %s), %d run(s), spend %.1f of %s, "
         "%d usage-limit hit(s) this week (%d in the reserve)" %
         (iso(start), round(elapsed * 100), iso(zone_start), runs, spend,
          ("%.0f" % budget) if budget > 0 else "no declared budget",
          len(hits), len(zone_hits)))

defer, until, why, zone = 0, "", "", int(elapsed >= 1 - reserve)
if last_hit:
    if last_reset > now:
        defer, until = 1, iso(last_reset)
        why = ("a session was refused at %s and the run named its reset" % iso(last_hit))
    elif now - last_hit < cool:
        defer, until = 1, iso(last_hit + cool)
        why = ("a session was refused at %s; five hours is the upper bound on the "
               "reset and not its value, so this re-probes in %d min"
               % (iso(last_hit), cool // 60))
if not defer and zone:
    over = budget > 0 and spend >= budget * (1 - reserve)
    armed = over or len(zone_hits) >= arm_hits
    if not armed:
        # IN THE RESERVE ZONE AND NOT ARMED. Saying nothing here would make an
        # inert control indistinguishable from a working one -- the fleet would
        # sail through every Sunday reporting nothing, and the first sign that
        # §9.1's reserve never armed would be a window exhausted on a Thursday.
        facts += ("; the weekly reserve is NOT armed: %s, and this fleet has been "
                  "refused %d time(s) since the reserve began (%d arms it)" %
                  ("%.1f of a declared %.0f is spent" % (spend, budget) if budget > 0
                   else "there is no declared WEEK_SPEND_BUDGET in $WORK/limits.env",
                   len(zone_hits), arm_hits))
    if armed:
        defer, until = 1, iso(week_end)
        why = ("the last %d%% of the weekly window is the owner's reserve, and %s"
               % (round(reserve * 100),
                  ("the run index says %.1f of a declared %.0f is spent" % (spend, budget))
                  if over else
                  ("this fleet has been refused %d time(s) since the reserve began at %s"
                   % (len(zone_hits), iso(zone_start)))))
# Four LINES, not four tab-separated fields: tab is an IFS whitespace
# character, so `read` collapses a run of them and an empty `until` silently
# shifts every later field left -- which put the facts in WINDOW_UNTIL and
# read as a deferral with no reason.
print("\n".join((str(defer), until, why, facts, str(zone))))
PY
    ) || return 0
    [ -n "$out" ] || return 0
    { IFS= read -r WINDOW_DEFER
      IFS= read -r WINDOW_UNTIL
      IFS= read -r WINDOW_WHY
      IFS= read -r WINDOW_FACTS
      IFS= read -r WINDOW_ZONE; } <<< "$out"
    WINDOW_DEFER="${WINDOW_DEFER:-0}"; WINDOW_ZONE="${WINDOW_ZONE:-0}"
    return 0
}

# The one sentence every caller prints, so the fleet never goes quiet without
# saying why. A deferral is NOT a failure: it carries no FAIL, so no gate
# reads it as breakage and wakes a model tick to investigate it.
window_defer_line() {   # <what is being deferred>
    echo "DEFERRING ${1:-dispatch}: $WINDOW_WHY. Resumes $WINDOW_UNTIL. This is a budget decision, not a failure -- folds, arms, labels, sessions already running and this status page all continue, and no lane attempt is counted. ($WINDOW_FACTS)"
}
