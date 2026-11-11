# Mutation report

Campaign: `scripts/mutations.py` (32 unique one-occurrence edits) via `make mutation`.
A second campaign covers E4M3-only logic: `scripts/mutations_fp8.py` (12 edits), all killed.

INT8 fast subset (2×2): directed, err (including err-clear), tlast, then `mut_extra` (latency 15 + A `tready=0` after A done).

INT8 result: **killed 27 / survived 5 / apply_fail 0 / n=32 / score=0.8438**.
Non-equivalent mutants: **27/27 killed**. E4M3: **12/12 killed**.

## INT8 survivors (equivalent)

| ID | Edit | Why equivalent |
|---|---|---|
| M08 | PE `a_out <= 8'sd1` on clr | Tile C unchanged: COMPUTE already feeds `R+C−2` zeros, so the poisoned west-east link is sampled only while the east PE's B has not arrived (`b_in=0`). PE `SUITE=control` would see `a_out!=0`; that is outside this tile fast subset. |
| M23 | `arr_en` also in DRAIN | COMPUTE already flushed zeros through the array; DRAIN MAC is `0*0`. One DRAIN cycle, latency unchanged. |
| M24 | no `clr` in LOAD | Every txn enters LOAD from IDLE (or reset), where `clr=1` already zeros acc. Legal FSM never LOAD without a prior IDLE/reset clr. |
| M28 | reset `k_q` 1→0 | Accepted start always latches `cfg_k_i` before LOAD indexes the scratchpad. IDLE `tready=0`. |
| M29 | `unique case` `default: state<=state` | `state` is a 5-value enum; default is unreachable. |

## Test gaps closed

| ID | Why it first survived | Test added |
|---|---|---|
| M17 | Extra COMPUTE cycle of zeros; scoreboard checks C, not length | `SUITE=mut_extra` latency `1+max(R·K,K·C)+(K+R+C−2)+1+R·C+1` (2×2 K=2 → 15) |
| M32 | TB drops A `tvalid` after the last beat, so extra `tready` never fired | `run_a_done_b_slow`: keep A valid after TLAST while B is delayed; assert A `tready=0` |

E4M3 F01 (NaN from A only) first survived because every NaN vector had NaN on A; a B-side NaN `(0x01, 0x7F)` kills it. F07 (40-bit acc) is killed by K=11 of 448².
