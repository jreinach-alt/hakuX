# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# usage/meter.py's transcript fit (#433, meterfit1010): fit_prices_transcripts,
# collect_fit_samples, transcript_eq, combined_price_map, migrate_events,
# reprice_events, reprice_calibration_capacity. See the module docstring's
# "THE FIT" and docs/lanes/meterfit1010/NOTES.md for why.
# NO LIVE TRANSCRIPTS: every ~/.claude/projects file this fragment reads is
# one it wrote itself, under its own HAKUX_WORK/HAKUX_CLAUDE_PROJECTS, the
# same isolation 89-usage-mode.sh uses for the same reason.
#
# Depends on no other fragment.

echo "== meter.py: the transcript fit (#433)"
UF="$T/usagemeterfit"; rm -rf "$UF"
mkdir -p "$UF/work/logs/lane" "$UF/projects/-home-justin-hakux-work-wt-meterfix"
UF_SAVED_WORK_SET=${HAKUX_WORK+1}; UF_SAVED_WORK=${HAKUX_WORK-}
UF_SAVED_PROJECTS_SET=${HAKUX_CLAUDE_PROJECTS+1}; UF_SAVED_PROJECTS=${HAKUX_CLAUDE_PROJECTS-}
export HAKUX_WORK="$UF/work" HAKUX_CLAUDE_PROJECTS="$UF/projects"
UF_NOW_ISO='2026-10-10T18:00:00Z'
UF_NOW=$(date -u -d "$UF_NOW_ISO" +%s)

# Three cases, one shared fixture tree, built once in Python (mirrors
# 89-usage-mode.sh's fixture style): a run log under work/logs/lane/*.json
# (session_id + modelUsage, exactly what collect_fit_samples() reads) and,
# for the two cases that have one, a transcript under projects/<proj>/<sid>.jsonl.
#
#   claude-opus-5-5   (case 1, "ratio"):    1 run, $1.00 for 1000 modelUsage
#       eq-tokens, but its OWN transcript only logged 900 -- some of the
#       billed call's tokens never made it into the transcript (see the
#       module docstring's two-cause finding). fit_prices() (today) prices
#       it at $1/1000; fit_prices_transcripts() must price it at $1/900,
#       higher by exactly the 1000/900 ratio.
#   claude-fable-5-1  (case 2, "fallback"): 1 run 1h ago ($1, eq 100) plus
#       1 run 5 days ago ($9, eq 1800). The recent run alone is below both
#       SHORT_MIN_RUNS and SHORT_MIN_COST, so the fit must fall back to the
#       full 14-day window (both runs: $10 / 1900 eq) -- not the thin
#       recent-only number ($1/100) and not the older run alone ($9/1800).
#   claude-haiku-4-5-20251001 (case 3, "no transcript"): 1 run, session_id
#       with NO transcript file anywhere. collect_fit_samples() must skip it
#       entirely, so combined_price_map() keeps fit_prices()'s modelUsage-based
#       number for this model -- "a model with no fit at all keeps today's
#       behaviour" (the brief's words).
python3 - "$UF/work/logs/lane" "$UF/projects/-home-justin-hakux-work-wt-meterfix" "$UF_NOW" <<'PY'
import datetime, json, os, sys, time

logs_dir, proj_dir, now = sys.argv[1], sys.argv[2], int(sys.argv[3])

def write_run(name, session_id, model, cost, mu_eq_tokens, age_s):
    path = os.path.join(logs_dir, name + ".json")
    with open(path, "w") as fh:
        json.dump({"session_id": session_id, "modelUsage": {
            model: {"inputTokens": mu_eq_tokens, "cacheCreationInputTokens": 0,
                    "cacheReadInputTokens": 0, "outputTokens": 0, "costUSD": cost}}}, fh)
    mtime = now - age_s
    os.utime(path, (mtime, mtime))

def write_transcript(session_id, model, input_tokens, age_s):
    path = os.path.join(proj_dir, session_id + ".jsonl")
    ts = datetime.datetime.fromtimestamp(now - age_s, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w") as fh:
        fh.write(json.dumps({"type": "assistant", "timestamp": ts,
                              "message": {"id": "msg-" + session_id, "model": model,
                                          "usage": {"input_tokens": input_tokens,
                                                    "cache_creation_input_tokens": 0,
                                                    "cache_read_input_tokens": 0,
                                                    "output_tokens": 0}}}) + "\n")

# case 1: ratio
write_run("opus1", "sid-opus1", "claude-opus-5-5", 1.0, 1000, 3600)
write_transcript("sid-opus1", "claude-opus-5-5", 900, 3600)

# case 2: fallback -- one recent run (inside the 72h short window), one 5
# days old (inside the 14-day window, outside the short one)
write_run("fable-recent", "sid-fable1", "claude-fable-5-1", 1.0, 100, 3600)
write_transcript("sid-fable1", "claude-fable-5-1", 100, 3600)
write_run("fable-older", "sid-fable2", "claude-fable-5-1", 9.0, 1800, 5 * 86400)
write_transcript("sid-fable2", "claude-fable-5-1", 1800, 5 * 86400)

# case 3: no transcript at all for this session_id
write_run("haiku-missing", "sid-haiku-missing-xyz", "claude-haiku-4-5-20251001", 2.0, 2000, 3600)
PY

check "the fixture transcripts and run logs landed where collect_fit_samples() reads them" \
    test -f "$UF/work/logs/lane/opus1.json" -a -f "$UF/projects/-home-justin-hakux-work-wt-meterfix/sid-opus1.jsonl"

check "case 1 (ratio): fit_prices_transcripts prices the opus run at cost/transcript_eq, higher than fit_prices()'s cost/modelUsage_eq by exactly the 1000/900 ratio" \
    python3 -c "
import sys
sys.path.insert(0, '$HERE/usage')
import meter

work, projects, now = '$UF/work', '$UF/projects', float($UF_NOW)
old_fit = meter.fit_prices(work)
samples = meter.collect_fit_samples(work, projects, now=now)
new_fit = meter.fit_prices_transcripts(samples, now)
old_opus = old_fit['claude-opus-5-5']
new_opus = new_fit['claude-opus-5-5']
assert abs(old_opus - 1.0/1000) < 1e-9, ('old fit should be \$1/1000 eq-tokens', old_opus)
assert abs(new_opus - 1.0/900) < 1e-9, ('new fit should be \$1/900 transcript eq-tokens', new_opus)
ratio = new_opus / old_opus
assert abs(ratio - 1000.0/900.0) < 1e-6, ('price must be higher by exactly the modelUsage/transcript ratio', ratio)
"

check "case 1's MUTANT -- re-point fit_prices_transcripts at modelUsage tokens instead of transcript tokens, and the ratio check above fails (it collapses to 1.0, same as today's fit)" \
    python3 -c "
import sys, json
sys.path.insert(0, '$HERE/usage')
import meter

work, projects, now = '$UF/work', '$UF/projects', float($UF_NOW)
# The mutant: feed fit_prices_transcripts the run's modelUsage eq (1000) in
# place of its transcript eq (900) for every sample -- i.e. undo the #433
# fix and go back to pricing a modelUsage token against itself.
samples = meter.collect_fit_samples(work, projects, now=now)
mutant_samples = []
for mtime, model, cost, eq in samples:
    if model == 'claude-opus-5-5':
        eq = 1000.0        # the run's modelUsage eq, not its transcript eq (900)
    mutant_samples.append((mtime, model, cost, eq))
mutant_fit = meter.fit_prices_transcripts(mutant_samples, now)
old_fit = meter.fit_prices(work)
ratio = mutant_fit['claude-opus-5-5'] / old_fit['claude-opus-5-5']
assert abs(ratio - 1.0) < 1e-9, ('mutant must reproduce the OLD ratio (1.0, no fix): if this fails the mutant is not exercising the bug', ratio)
"

check "case 2 (fallback): the recent run alone is below SHORT_MIN_RUNS/SHORT_MIN_COST, so fable falls back to the full 14-day window (\$10/1900 eq), not the thin recent-only (\$1/100) or older-only (\$9/1800) numbers" \
    python3 -c "
import sys
sys.path.insert(0, '$HERE/usage')
import meter

work, projects, now = '$UF/work', '$UF/projects', float($UF_NOW)
samples = meter.collect_fit_samples(work, projects, now=now)
fit = meter.fit_prices_transcripts(samples, now)
fable = fit['claude-fable-5-1']
want = 10.0 / 1900.0
assert abs(fable - want) < 1e-9, ('must be the combined 14-day fit', fable, want)
assert abs(fable - 1.0/100.0) > 1e-6, ('must NOT be the thin recent-only window', fable)
assert abs(fable - 9.0/1800.0) > 1e-6, ('must NOT be the older run alone', fable)
"

check "case 3 (no transcript): collect_fit_samples skips the haiku run entirely (no transcript file for its session_id)" \
    python3 -c "
import sys
sys.path.insert(0, '$HERE/usage')
import meter

samples = meter.collect_fit_samples('$UF/work', '$UF/projects', now=float($UF_NOW))
assert not any(model == 'claude-haiku-4-5-20251001' for _, model, _, _ in samples), samples
"

check "case 3: combined_price_map keeps fit_prices()'s modelUsage-based number for a model the transcript fit never saw (today's behaviour)" \
    python3 -c "
import sys
sys.path.insert(0, '$HERE/usage')
import meter

work, projects, now = '$UF/work', '$UF/projects', float($UF_NOW)
old_fit = meter.fit_prices(work)
merged = meter.combined_price_map(work, projects, now)
assert abs(merged['claude-haiku-4-5-20251001'] - old_fit['claude-haiku-4-5-20251001']) < 1e-12, \
    ('a model with no transcript-fit data must keep fit_prices()\'s own number unchanged', merged, old_fit)
assert abs(merged['claude-haiku-4-5-20251001'] - 2.0/2000) < 1e-9, merged
"

# Falsifier for the 10-19 time bomb: case 2 above already proves the fix
# against TODAY's real gap (UF_NOW is a fixed calendar date, and the real
# gap to wall-clock only grows) -- this proves it against a gap deliberately
# pushed far past the 14-day edge, so the check does not itself start
# failing again once the real gap grows past 14 days too.
UH="$T/usagemeterfit-faredge"; rm -rf "$UH"
mkdir -p "$UH/work/logs/lane" "$UH/projects/-home-justin-hakux-work-wt-meterfix"
export HAKUX_WORK="$UH/work" HAKUX_CLAUDE_PROJECTS="$UH/projects"
UH_NOW=$(( $(date +%s) - 30 * 86400 ))

python3 - "$UH/work/logs/lane" "$UH/projects/-home-justin-hakux-work-wt-meterfix" "$UH_NOW" <<'PY'
import datetime, json, os, sys

logs_dir, proj_dir, now = sys.argv[1], sys.argv[2], int(sys.argv[3])

def write_run(name, session_id, model, cost, mu_eq_tokens, age_s):
    path = os.path.join(logs_dir, name + ".json")
    with open(path, "w") as fh:
        json.dump({"session_id": session_id, "modelUsage": {
            model: {"inputTokens": mu_eq_tokens, "cacheCreationInputTokens": 0,
                    "cacheReadInputTokens": 0, "outputTokens": 0, "costUSD": cost}}}, fh)
    mtime = now - age_s
    os.utime(path, (mtime, mtime))

def write_transcript(session_id, model, input_tokens, age_s):
    path = os.path.join(proj_dir, session_id + ".jsonl")
    ts = datetime.datetime.fromtimestamp(now - age_s, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w") as fh:
        fh.write(json.dumps({"type": "assistant", "timestamp": ts,
                              "message": {"id": "msg-" + session_id, "model": model,
                                          "usage": {"input_tokens": input_tokens,
                                                    "cache_creation_input_tokens": 0,
                                                    "cache_read_input_tokens": 0,
                                                    "output_tokens": 0}}}) + "\n")

# Same shape as case 2 (fallback): one run 1h old, one 5 days old, both ages
# measured from UH_NOW -- which is itself pinned 30 real days in the past.
write_run("faredge-recent", "sid-faredge1", "claude-fable-5-1", 1.0, 100, 3600)
write_transcript("sid-faredge1", "claude-fable-5-1", 100, 3600)
write_run("faredge-older", "sid-faredge2", "claude-fable-5-1", 9.0, 1800, 5 * 86400)
write_transcript("sid-faredge2", "claude-fable-5-1", 1800, 5 * 86400)
PY

check "falsifier: a fixture clock pinned 30 real days in the past still gets the combined 14-day fit, because the cutoff is measured from the fixture's own now= and not wall-clock" \
    python3 -c "
import sys
sys.path.insert(0, '$HERE/usage')
import meter

work, projects, now = '$UH/work', '$UH/projects', float($UH_NOW)
samples = meter.collect_fit_samples(work, projects, now=now)
fit = meter.fit_prices_transcripts(samples, now)
fable = fit['claude-fable-5-1']
want = 10.0 / 1900.0
assert abs(fable - want) < 1e-9, ('must be the combined 14-day fit even 30 real days later', fable, want)
"

check "falsifier's MUTANT -- reinstate collect_fit_samples's pre-#433 cutoff (always wall-clock, the now= argument silently ignored) and the far-past fixture's model drops out of the fit entirely" \
    python3 -c "
import sys, glob, json, os, time
sys.path.insert(0, '$HERE/usage')
import meter

work, projects, now = '$UH/work', '$UH/projects', float($UH_NOW)

def broken_collect_fit_samples(work_dir, projects_dir, max_age_days=14):
    cutoff = time.time() - max_age_days * 86400   # the pre-#433 bug: now= ignored
    samples = []
    for f in glob.glob(os.path.join(work_dir, 'logs', '**', '*.json'), recursive=True):
        try:
            mtime = os.path.getmtime(f)
            if mtime < cutoff:
                continue
            r = json.load(open(f))
        except Exception:
            continue
        if not isinstance(r, dict):
            continue
        mu = r.get('modelUsage') or {}
        sid = r.get('session_id')
        if not mu or not sid:
            continue
        eq_by_model = meter.transcript_eq(projects_dir, sid)
        if eq_by_model is None:
            continue
        for model, u in mu.items():
            cost = u.get('costUSD')
            eq = meter._eq_for_billing_model(eq_by_model, model)
            if cost and eq:
                samples.append((mtime, model, cost, eq))
    return samples

samples = broken_collect_fit_samples(work, projects)
fit = meter.fit_prices_transcripts(samples, now)
assert 'claude-fable-5-1' not in fit, \
    ('mutant must drop the far-past fixture model entirely: if this fails the mutant is not exercising the 10-19 bug', fit)
"

export HAKUX_WORK="$UF/work" HAKUX_CLAUDE_PROJECTS="$UF/projects"

echo "== meter.py: old-format state migrates on the first tick; the latest calibration recomputes, its percent/utc do not"
UG="$T/usagemeterfit-migrate"; rm -rf "$UG"
mkdir -p "$UG/work/logs/lane" "$UG/projects/-home-justin-hakux-work-wt-meterfix" "$UG/work/usage"
export HAKUX_WORK="$UG/work" HAKUX_CLAUDE_PROJECTS="$UG/projects"
UG_NOW_ISO='2026-10-10T18:00:00Z'
UG_NOW=$(date -u -d "$UG_NOW_ISO" +%s)

python3 - "$UG" "$UG_NOW" <<'PY'
import datetime, json, os, sys

root, now = sys.argv[1], int(sys.argv[2])
logs_dir = os.path.join(root, "work", "logs", "lane")
proj_dir = os.path.join(root, "projects", "-home-justin-hakux-work-wt-meterfix")
sid = "sid-mig-opus"

run_path = os.path.join(logs_dir, "mig-opus.json")
with open(run_path, "w") as fh:
    json.dump({"session_id": sid, "modelUsage": {"claude-opus-5-5": {
        "inputTokens": 1000, "cacheCreationInputTokens": 0, "cacheReadInputTokens": 0,
        "outputTokens": 0, "costUSD": 1.0}}}, fh)
mtime = now - 3600
os.utime(run_path, (mtime, mtime))

ts_path = os.path.join(proj_dir, sid + ".jsonl")
ts = datetime.datetime.fromtimestamp(now - 3600, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(ts_path, "w") as fh:
    fh.write(json.dumps({"type": "assistant", "timestamp": ts,
                          "message": {"id": "msg-mig-opus", "model": "claude-opus-5-5",
                                      "usage": {"input_tokens": 900, "cache_creation_input_tokens": 0,
                                                "cache_read_input_tokens": 0, "output_tokens": 0}}}) + "\n")
st = os.stat(ts_path)

# Pre-#433 state: an event with "cost" only (no model/eq), and the offset
# already pointing past this exact transcript -- as if a prior, pre-fit
# tick had already scanned it in full. migrate_events() must clear BOTH
# (the event and the offset) so this tick re-reads the file and rebuilds
# the event with model+eq, not just leave the stale cost-only event there.
state = {
    "offsets": {ts_path: {"size": st.st_size, "mtime": st.st_mtime, "actor": "lane:meterfix"}},
    "events": [{"ts": now - 300, "actor": "lane:meterfix", "cost": 7.0, "id": "legacy-1"}],
    "calibration": [
        {"utc": "2026-09-30T22:40:00-07:00", "percent": 92.0, "spend_at_time": 0.0, "capacity": 1.0},
        {"utc": "2026-10-02T10:10:00-07:00", "percent": 16.0, "spend_at_time": 0.0, "capacity": 1.0},
        {"utc": "2026-10-10T18:00:00+00:00", "percent": 20.0, "spend_at_time": 0.0, "capacity": 999.0},
    ],
}
with open(os.path.join(root, "work", "usage", "state.json"), "w") as fh:
    json.dump(state, fh)
PY

HAKUX_NOW="$UG_NOW" python3 "$HERE/usage/meter.py" >/dev/null

check "migration: every event now carries model and eq" \
    python3 -c "
import json
s = json.load(open('$UG/work/usage/state.json'))
events = s['events']
assert events, 'migration must not drop every event'
assert all('model' in e and 'eq' in e for e in events), events
"
check "migration: the stale legacy cost-only event (\$7.00) is gone, replaced by the rescanned transcript event" \
    python3 -c "
import json
s = json.load(open('$UG/work/usage/state.json'))
assert not any(e.get('id') == 'legacy-1' for e in s['events']), s['events']
assert any(e.get('id') == 'msg-mig-opus' for e in s['events']), s['events']
"
check "migration: the latest calibration point's percent and utc are the owner's reading, untouched" \
    python3 -c "
import json
s = json.load(open('$UG/work/usage/state.json'))
latest = s['calibration'][-1]
assert latest['percent'] == 20.0, latest
assert latest['utc'] == '2026-10-10T18:00:00+00:00', latest
"
check "migration: the latest calibration point's capacity is recomputed (no longer the 999.0 placeholder) from the re-priced, rescanned events" \
    python3 -c "
import json
s = json.load(open('$UG/work/usage/state.json'))
latest = s['calibration'][-1]
assert latest['capacity'] != 999.0, latest
assert latest['capacity'] is not None and latest['capacity'] > 0, latest
"
check "migration: the two seeded calibration points are untouched (older points are left as they are)" \
    python3 -c "
import json
s = json.load(open('$UG/work/usage/state.json'))
seed1, seed2 = s['calibration'][0], s['calibration'][1]
assert seed1 == {'utc': '2026-09-30T22:40:00-07:00', 'percent': 92.0, 'spend_at_time': 0.0, 'capacity': 1.0}, seed1
assert seed2 == {'utc': '2026-10-02T10:10:00-07:00', 'percent': 16.0, 'spend_at_time': 0.0, 'capacity': 1.0}, seed2
"
check "migration: a second tick (now fully migrated) is a no-op on the event list -- migrate_events only fires once" \
    bash -c '
        cp "$1/work/usage/state.json" "$1/state-after-1.json"
        HAKUX_NOW="$2" python3 "$3/usage/meter.py" >/dev/null
        python3 -c "
import json
a = json.load(open(\"$1/state-after-1.json\"))[\"events\"]
b = json.load(open(\"$1/work/usage/state.json\"))[\"events\"]
assert a == b, (a, b)
"
    ' _ "$UG" "$UG_NOW" "$HERE"

unset UF UF_NOW UF_NOW_ISO UG UG_NOW UG_NOW_ISO
if [ -n "$UF_SAVED_WORK_SET" ]; then export HAKUX_WORK="$UF_SAVED_WORK"; else unset HAKUX_WORK; fi
if [ -n "$UF_SAVED_PROJECTS_SET" ]; then export HAKUX_CLAUDE_PROJECTS="$UF_SAVED_PROJECTS"; else unset HAKUX_CLAUDE_PROJECTS; fi
unset UF_SAVED_WORK_SET UF_SAVED_WORK UF_SAVED_PROJECTS_SET UF_SAVED_PROJECTS
check "HAKUX_WORK is restored to the harness's own value after this fragment" \
    [ "${HAKUX_WORK-}" = "$T/work" ]
