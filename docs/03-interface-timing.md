# Interface timing — 2×2, K=2 (drawn before `tile_top.sv`)

No back-pressure. Both streams offer a beat every LOAD cycle. Inclusive count from the start-accept edge through `done_o`.

Example operands (values on the wires; any legal INT8 pair has the same control timing):
A = `[[1, 2], [3, 4]]`, B = `[[5, 6], [7, 8]]`.
A beats (row-major): 1, 2, 3, 4 + TLAST on the last.
B beats: 5, 6, 7, 8 + TLAST on the last.
C beats: 19, 22, 43, 50 + TLAST on the last.

Formula: `1 + max(R·K, K·C) + (K+R+C−2) + 1 + R·C + 1`
= `1 + max(4,4) + 4 + 1 + 4 + 1` = **15** cycles (t = 0 .. 14).

| t | state next | busy | done | a_rdy | b_rdy | a xfer | b xfer | c_valid | c xfer | array clr/en | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | IDLE→LOAD | 0 | 0 | 0 | 0 | — | — | 0 | — | clr=1 en=0 | `start_i` accepted, K latched |
| 1 | LOAD | 1 | 0 | 1 | 1 | A0=1 | B0=5 | 0 | — | clr=1 en=0 | first LOAD; both streams offer |
| 2 | LOAD | 1 | 0 | 1 | 1 | A1=2 | B1=6 | 0 | — | clr=1 | |
| 3 | LOAD | 1 | 0 | 1 | 1 | A2=3 | B2=7 | 0 | — | clr=1 | |
| 4 | LOAD→COMPUTE | 1 | 0 | 1 | 1 | A3=4 L | B3=8 L | 0 | — | clr=1 | last A/B beats; next is COMPUTE |
| 5 | COMPUTE t=0 | 1 | 0 | 0 | 0 | — | — | 0 | — | clr=0 en=1 | feed A[:,0], B[0,:] |
| 6 | COMPUTE t=1 | 1 | 0 | 0 | 0 | — | — | 0 | — | en=1 | feed A[:,1], B[1,:] |
| 7 | COMPUTE t=2 | 1 | 0 | 0 | 0 | — | — | 0 | — | en=1 | zeros (t≥K) |
| 8 | COMPUTE t=3 →DRAIN | 1 | 0 | 0 | 0 | — | — | 0 | — | en=1 | last compute; last product lands |
| 9 | DRAIN→STORE | 1 | 0 | 0 | 0 | — | — | 0 | — | clr=0 en=0 | acc stable |
| 10 | STORE n=0 | 1 | 0 | 0 | 0 | — | — | 1 | 19 | en=0 | |
| 11 | STORE n=1 | 1 | 0 | 0 | 0 | — | — | 1 | 22 | en=0 | |
| 12 | STORE n=2 | 1 | 0 | 0 | 0 | — | — | 1 | 43 | en=0 | |
| 13 | STORE n=3 →IDLE | 1 | 0 | 0 | 0 | — | — | 1 L | 50 | en=0 | last C accepted this edge |
| 14 | IDLE | 0 | 1 | 0 | 0 | — | — | 0 | — | clr=1 en=0 | `done_o` pulse; `busy_o=0` |

`L` = TLAST. `a_rdy`/`b_rdy` are `tready`. A transfer is `tvalid && tready` on that edge.

Wave (same 15 cycles; `C` is `m_axis_c`):

```
clk     ⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬⌐¬
        0  1  2  3  4  5  6  7  8  9  10 11 12 13 14
start   ‾‾¬_________________________________________
state   IDL LOAD------------ COMPUTE-------- DRN STORE------------ IDL
busy    ___‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾___
done    _____________________________________________‾‾¬
a_ready ___‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾___________________________
b_ready ___‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾___________________________
c_valid _______________________________‾‾‾‾‾‾‾‾‾‾‾‾‾‾___
c_last  _________________________________________‾‾‾___
arr.clr ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾___________________________‾‾
arr.en  ___________________‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾___________
```

## 4×4, K=4 (no back-pressure) — predicted before sim
`1 + max(16,16) + (4+4+4−2) + 1 + 16 + 1 = 1+16+10+1+16+1 = **45**`.

Per state (inclusive of the start edge as IDLE, exclusive of overlapping exits):
| State | Cycles | Role |
|---|---|---|
| IDLE (start accept) | 1 | sample `start_i`/`cfg_k_i` |
| LOAD | 16 | `max(R·K, K·C)` |
| COMPUTE | 10 | `K+R+C−2` |
| DRAIN | 1 | `en=0`, acc hold |
| STORE | 16 | `R·C` C beats |
| IDLE (`done_o`) | 1 | pulse |
| **Total** | **45** | start edge through done |
