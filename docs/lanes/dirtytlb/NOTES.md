# lane.dirtytlb (#548)

Who calls `tlb_reset_dirty` off the vCPU thread, per flip, and what each
caller costs. Work in progress; the sections below fill in as runs land.
