#!/usr/bin/env bash
# Batch 10 of lane.verdict433 (#433): the two flagged titles the 2026-09-30
# 20:50 PDT addendum made candidates, on master b1cea467c6 (the Forza decay fix
# e816bc35dd, #583, and the P3 shader pre-build b1cea467c6, #569), Nova, the
# defaults, 1200 s of gameplay (confirmation_s = 1200 for both in targets.toml).
#
# Kabuki runs twice on the same ref. The dispatcher clears the shader caches
# whenever the apk differs from the device's previous run (dispatcher.sh,
# clear_shader_caches_on_apk_change), and P3 removes the fight's create burst
# only on a launch that has the title's recorded pipelines. The first launch is
# the warm-up that records them; the second is the confirmation. All three
# requests use one ref, so Forza between them does not clear anything. The
# confirmation's result.json "shader_cache" says whether it ran kept or cleared.
#
# Forza runs the survey route (as lane.forzadecay414's runs did): it has no
# `mark gameplay`, so it is judged from `mark play` with --reviewed-gameplay
# after its route-frames are looked at.
set -u
R=docs/testing/request.sh
REF=${REF:-b1cea467c6}
KABUKI='43560001-Kabuki_Warriors.xiso.iso'
FORZA='4D53006E-Forza_Motorsport.xiso.iso'

env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
    --title "$KABUKI" --route kabuki-warriors --seconds 420 \
    --env PERF_REGIMEN=default --issue 433 \
    --no-expect "warm-up launch that records Kabuki's pipelines for the confirmation after it, not an A/B arm" \
    --purpose "#433 batch 10: Kabuki Warriors warm-up launch (records pipelines for P3's pre-build), kabuki-warriors route, nova, defaults; the confirmation follows on the same ref"

env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
    --title "$KABUKI" --route kabuki-warriors --seconds 1480 \
    --env PERF_REGIMEN=default --issue 433 \
    --no-expect "Playable confirmation soak (1200 s, flagged title), not an A/B arm" \
    --purpose "#433 Playable confirmation (batch 10): Kabuki Warriors on master b1cea467c6 (P3 pre-build), second launch on this apk, kabuki-warriors route, nova, defaults, 1200 s after the mark"

env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
    --title "$FORZA" --route survey --seconds 1480 \
    --env PERF_REGIMEN=default --issue 433 \
    --no-expect "Playable confirmation soak (1200 s, flagged title), not an A/B arm" \
    --purpose "#433 Playable confirmation (batch 10): Forza Motorsport on master b1cea467c6 (#583 decay fix), survey route, nova, defaults, 1200 s after mark play, judged with --reviewed-gameplay"
