# lane.glerr86 -- #86: gl/shaders.c drains every pending GL error silently at shader load on Android

Base: origin/master (fetch it; your worktree is already on it).
Files: hw/xbox/nv2a/pgraph/gl/shaders.c (yours). Nothing else without a grant.
Issue: read `gh issue view 86 --comments` first. No device is needed to
write the fix; the device only shows what the drain has been hiding.

Goal: stop the Android arm from swallowing GL errors at shader load. Errors
that were pending before the load must be reported once with their site
(a `[glerr]` logcat line naming the enum and the shader), not discarded, and
the shipping GL path must be able to surface a GL error again. Do not change
what the shader loader compiles; change only what it does with glGetError.

Falsifier: this change moves no pixels. Register an inertness prediction
(must_not_move over the suites you can name from gl/ captures, e.g.
Texture_render_target/* and Blend_tests/*) with ab_compare.py --register,
committed after your code commits. The new evidence is the logcat: say in
NOTES.md what a device run's `grep '\[glerr\]'` should and should not show.

Done when: the fix is pushed on lane/glerr86 with the prediction committed,
the PR body follows roles/lane.md's template, and the PR is marked ready.
