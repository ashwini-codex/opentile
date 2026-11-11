# OpenTile — interface specification [N]

Top module `tile_top #(R=4, C=4, K_MAX=64)`. Single clock `clk`, rising edge. Reset `rst_n`: synchronous, active low.

## Ports
| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk`, `rst_n` | in | 1 | clock; synchronous active-low reset |
| `cfg_k_i` | in | 16 | K for the next transaction; sampled on the edge where `start_i` is accepted |
| `start_i` | in | 1 | level-sampled in IDLE (intended as a 1-cycle pulse); accepted only when state is IDLE |
| `busy_o` | out | 1 | 1 in LOAD, COMPUTE, DRAIN, STORE; 0 in IDLE (including the cycle `done_o` pulses) |
| `done_o` | out | 1 | one-cycle pulse in the first IDLE cycle after the last C beat is accepted |
| `err_o` | out | 1 | combinational `|err_code_o` (OR of the three flags) |
| `err_code_o` | out | 3 | sticky flags, reset value 0, cleared on each **accepted** start and on reset: bit0 `K_RANGE` (start with K = 0 or K > K_MAX; start is **not** accepted, no transaction), bit1 `A_TLAST` (A stream TLAST wrong), bit2 `B_TLAST` |
| `s_axis_a_tdata/tvalid/tready/tlast` | in/in/out/in | 8/1/1/1 | A operand stream; `tdata` is the two's-complement bit pattern of signed INT8 |
| `s_axis_b_tdata/tvalid/tready/tlast` | in/in/out/in | 8/1/1/1 | B operand stream; `tdata` as signed INT8 two's complement |
| `m_axis_c_tdata/tvalid/tready/tlast` | out/out/in/out | 32/1/1/1 | C result stream; `tdata` is signed INT32 two's complement |

No AXI-Lite or memory-mapped registers in 1.0: the "control and status registers" are the sideband ports above. (Logged as a decision.)

## Stream framing and packing [N]
- One element per beat. A: `R*K` beats, **row-major** (beat n = i*K + k). B: `K*C` beats, **row-major** (beat n = k*C + j). C: `R*C` beats, **row-major** (beat n = i*C + j), signed 32-bit.
- TLAST must be asserted exactly on the final beat of each stream and on no other beat. A violation sets `A_TLAST`/`B_TLAST` (sticky) but the transaction **continues**, counting beats, not trusting TLAST.
- The A and B streams are independent: either may be loaded first or concurrently.
- Standard AXI-Stream rules apply: a source must not drop TVALID or change TDATA/TLAST while TVALID=1 and TREADY=0; a transfer happens on a cycle with TVALID && TREADY.

## Controller [N]
| State | Behaviour |
|---|---|
| IDLE | `s_axis_*_tready=0`, `m_axis_c_tvalid=0`, `busy_o=0`, `done_o=0` except the one-cycle return pulse below. On `start_i=1` with 1 ≤ `cfg_k_i` ≤ K_MAX: latch K (sampled this edge; later `cfg_k_i` changes are ignored until the next accepted start), clear `err_code_o`, go LOAD next cycle. On `start_i=1` with K = 0 or K > K_MAX: set `err_code_o[0]` (`K_RANGE`), leave bits 1–2 unchanged, stay IDLE, `busy_o` stays 0. `start_i` in LOAD/COMPUTE/DRAIN/STORE is ignored and does not change `err_code_o`. If `start_i` is still 1 on the IDLE cycle that pulses `done_o` and K is in range, a new transaction is accepted immediately. |
| LOAD | `busy_o=1`. `s_axis_a_tready = (a_count < R*K)`, likewise B; accepted beats are written to the scratchpad. Beats offered while `tready=0` are not counted (AXI-Stream). When both counts are reached → COMPUTE (the next cycle). Back-pressure (`tready=0` while a count is still short) may last any number of cycles, including 1000; no timeout, no error. |
| COMPUTE | exactly `K+R+C-2` cycles, array `en=1`, `clr=0`. Feed cycle k (k=0..K-1) presents A[:,k] and B[k,:]; later cycles present zeros. |
| DRAIN | exactly 1 cycle, `en=0`, `clr=0`; results are stable. |
| STORE | `busy_o=1`. `m_axis_c_tvalid=1`, beat n carries `acc[n]`; advance on `tvalid && tready`; `tlast` on beat R*C−1. After the last beat is accepted: next cycle is IDLE with `done_o=1` for that cycle only. `tdata` and `tlast` are stable while `tvalid && !tready`. C-side back-pressure may last any number of cycles, including 1000; no timeout, no error. |

Minimum cycle count from the edge where start is accepted to the cycle `done_o` pulses, with no back-pressure and both streams offering a beat every cycle starting in the first LOAD cycle (**informative**):
`1 (start edge → LOAD) + max(R*K, K*C) (LOAD) + (K+R+C−2) (COMPUTE) + 1 (DRAIN) + R*C (STORE) + 1 (done pulse)`
This count is inclusive of the start cycle and the `done_o` cycle. For 4×4, K=4 it is **45**. For the golden 2×2, K=3 it is `1+max(6,6)+5+1+4+1 = 18`. COMPUTE length `K+R+C−2` is the same quantity as in `docs/01-architecture.md` and `docs/golden/2x2-k3.md` (5 cycles for 2×2 K=3).

Measured (same formula): 2×2 K=2 = **15**, 4×4 K=4 = **45**, 8×8 K=2 = **99** (`make sim SIZES="2 4 8"`).

## Reset behaviour [N]
Reset at any time returns to IDLE: `busy_o=0`, `done_o=0`, `err_code_o=0` (so `err_o=0`), `tvalid=0` on C, `tready=0` on A/B, all counters cleared. A C beat in flight is abandoned; scratchpad contents are not preserved. While `m_axis_c_tvalid=0` (including after reset), `m_axis_c_tdata` and `m_axis_c_tlast` are unspecified; a sink must ignore them. After reset deassertion the design accepts `start_i` in the next cycle.

## Timing diagram
A drawn timing diagram of one 2×2 K=2 transaction is in `docs/03-interface-timing.md`.

## Out of scope (must be repeated in the README)
Multiple outstanding transactions, interrupts, AXI-Lite, partial tiles (R or C changes at run time), K changing mid-transaction, any data format other than INT8 (until 1.1).
