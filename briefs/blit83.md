# lane.blit83 -- #83, ANALYSIS ONLY

Base: 55bc6c6c2beed87350cf1c02f67403afddc2acef (origin/master).
Files: NONE. files = [] is deliberate. hw/xbox/nv2a/pgraph/vk/blit.c is
lane.blitsafe's and stays there -- four issues in that file cluster are
already one lane's, and a fifth agent inside perform_blit() is exactly the
collision territory.toml exists to prevent. READ IT, do not edit it. If the
answer needs an edit, come back and ask for the file; you will get it.

THE FACT: eight ImgBlt_Overlap_* captures each differ from the golden by
EXACTLY 1 px, and in every case OURS IS ONE LOW. They are on the SRCCOPY
path, not BLEND_AND. It is not a magnitude spread -- a fixed sign at a fixed
magnitude across eight captures is a mechanism, and reading can identify it.

GOAL: say WHICH one-low mechanism it is, with the line that does it. Candidate
shapes to separate, and add any you find: an inclusive/exclusive bound on a
copy extent; a rounding or truncation in a coordinate; an off-by-one in an
overlap-direction memmove. SRCCOPY is a memmove of width_bytes with no beta
and no divide, so the BLEND_AND arithmetic cannot be it -- which is the whole
reason this issue was filed separately from #38 and #84.

THE TIME-CRITICAL PART, and do it FIRST: these eight are the MUST-NOT-MOVE
CONTROL on #84's BLEND_AND arm, and #84 is in fold right now. #83's own
blocker_falsifier says so: "if 'the blend fix cannot reach these' were false,
the eight would move when the BLEND_AND divide lands". The claim that the
divide cannot reach the SRCCOPY path is currently held by CONSTRUCTION -- by
reading -- and not by measurement. Trace the folded BLEND_AND change against
the SRCCOPY path and state, in writing on #83, whether the control is sound.
If it is not, the arm's control leg is void and the board needs to know before
the arm is judged, not after.

FALSIFIER: name the world in which your mechanism is wrong. If your candidate
predicts one low, it must also predict WHY these eight and not the other
Image blit captures -- the eight are a subset, and a mechanism that would hit
all of them is refuted by the ones that read clean.

DONE WHEN: a comment on #83 naming the mechanism and its line, or naming what
reading cannot settle and what would; plus the explicit control verdict for
#84's arm. No commits to hw/. No device, no arm, no build required.
