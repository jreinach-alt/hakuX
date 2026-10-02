# localforge OUTBOX

## #433 -- 2026-10-02 10:10 PDT

[lane.localforge] Steps 1 and 2 of the local forge are up.

- **Forgejo 16.0.5 at http://127.0.0.1:3330/** (loopback only, no SSH, no registration, sign-in required).
  - Unit: `hakux-forge.service`. Data is in `~/hakux-work/forge/`.
  - Users: forgeadmin, lane.local, hostops, lanes, owner, jobs. Tokens and passwords are in `~/hakux-work/forge/tokens/` (mode 600).
  - The owner's web login is user `owner`, with the password in `tokens/owner.password`.
- **Repo `jreinach-alt/hakuX`** holds all 105 branches of the bare repo.
- **Recommendation: (b). The bare repo stays origin and the forge follows it.** `hakux-forge-sync.timer` pushes heads and tags into the forge about once a minute.
  - Nothing a lane or foldqueue does changes, so there is no cutover and no window to announce.
  - Forgejo's built-in pull mirror was not usable: a mirror cannot hold PRs.
  - Cost: up to about 60 s of lag.
  - The rule that follows: nobody pushes code to the forge and nobody merges a forge PR. Merges stay with foldqueue.
  - Moving to (a) later means repointing the 4 insteadOf entries. If you want that, give me a time.
