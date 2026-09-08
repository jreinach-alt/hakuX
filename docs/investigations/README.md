# Investigations

Long-form records of individual bugs chased in depth. Each is a snapshot of what
was tried and what was ruled out, kept so the same ground is not covered twice.

These are **not** the issue tracker. Open work lives in
[GitHub issues](https://github.com/jreinach-alt/hakuX/issues); these documents
are the reasoning behind it.

| document | subject | status |
|---|---|---|
| [`freeze-analysis.md`](freeze-analysis.md) | Location-specific freeze: guest parks in a kernel halt loop, no PGRAPH interrupt pending, works on desktop xemu. Thirteen hypotheses eliminated. | **open** — roadmap item 5 |
| [`gl-texture-artifacts.md`](gl-texture-artifacts.md) | Misplaced geometry and stretched textures on the GLES renderer after the x1_box port. | fixes applied (`427055fba3`); needs re-confirmation |
