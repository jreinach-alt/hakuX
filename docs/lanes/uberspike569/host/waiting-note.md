[lane.uberspike569] waiting: on the Nova, for the six device requests that the 16:23-16:29 PDT wipe took. They are queued a third time, now that #624 is on master (`dfa30e5780`). The refs and predictions have not changed. The soaks are hard-pinned to the Nova.

| arm | ref | id |
|---|---|---|
| E A (already ran) | 23543417aa | `1790724542-uberspike569-1360739` |
| E H | 6bec23c3f4 | `1790730667-uberspike569-2559646` |
| DOA A / B / H | 23543417aa / 752b4f0f7b / 6bec23c3f4 | `1790730667-uberspike569-2559714`, `1790730668-uberspike569-2559794`, `1790730669-uberspike569-2559870` |
| Kabuki A / B2 | 8b15159b2f / d0152f9c44 | `1790730670-uberspike569-2559946`, `1790730670-uberspike569-2560023` |

This resolves when all seven have result dirs under `dispatch/results/`. Both devices are on the owner's top-up hold for now. Judging plan: `docs/lanes/uberspike569/BUILD.md` section 10.
