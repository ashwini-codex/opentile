# Decisions (newest first)

Format: `YYYY-MM-DD | decision | reason | Supersedes: <none or earlier line>`

2026-11-11 | E4M3 mutation campaign is `scripts/mutations_fp8.py` (12 edits), separate from the INT8 list of 32 | Campaign covers only the new E4M3 logic | Supersedes: none
2026-11-10 | PE/array `FMT` is a 32-bit `"INT8"`/`"E4M3"` parameter; `acc[31:0]` width unchanged (E4M3 payload is IEEE bits) | Spec C is FP32 bits; INT8 tests keep the same port | Supersedes: none
2026-11-10 | E4M3 PE MACs only on `en && valid`; `valid` is the unskewed real-k strobe, delayed with A | COMPUTE padding is `0x00×0x00` (+0) and must not participate in the K-product −0 rule | Supersedes: none
2026-11-10 | tile_top drives array `valid` from existing `feed` (`t_q < K` in COMPUTE) | Same pin INT8 already used to zero the vectors after k=K; INT8 MAC of those zeros was identity | Supersedes: none
2026-11-10 | Leave `docs/07-synthesis-report.md` at the 28421/85900 freeze; live `make synth` after the `valid` pin is 28462/85971 | Extra `valid`/`valid_o` flops; 1.0 numbers stay the freeze in that report | Supersedes: none
2026-11-10 | Vector format v2 adds optional `FMT INT8|E4M3`; v1 files stay valid as INT8 | Adding a field requires a version bump | Supersedes: freeze-as-v1 wording that assumed no field change
2026-11-10 | Decode-only library oracle is `ml_dtypes==0.5.1` `float8_e4m3fn` | Used for decode only, not accumulation | Supersedes: none
2026-11-10 | E4M3 products accumulate in a 43-bit two's-complement fixed-point register (LSB=2⁻¹⁸); one FP32 RNE at the end | 64·448²·2¹⁸ = 49·2³⁶ fits in 43 signed bits | Supersedes: none
2026-11-10 | Exact-zero E4M3 sum is FP32 −0 iff every one of the K products is −0; else +0 | Matches IEEE x+(−x)=+0 for nonzero cancellation | Supersedes: none
2026-11-10 | Any NaN operand in a C element's K pairs → canonical FP32 qNaN `0x7FC00000` | Both E4M3 NaN codes (`0x7F`,`0xFF`) collapse | Supersedes: none
2026-11-10 | E4M3 1.1 C stream is IEEE binary32 (not packed E4M3) | One rounding to FP32 is the spec result | Supersedes: none
2026-11-09 | 1.0 synthesis evidence remains Yosys cell counts; no timing number invented | OpenLane still absent (`make versions`) | Supersedes: none
2026-11-09 | Mutation is `make mutation`, not inside `make verify` | 32 Verilator rebuilds ~6 min; keep the default CI path short | Supersedes: none
2026-11-09 | Mutation campaign is `scripts/mutations.py` (32 named edits), not MCY | `mcy` is on PATH but the required evidence is classified one-line edits | Supersedes: none
2026-11-09 | Verilator `--coverage` is `VL_COVERAGE`, not cocotb `COVERAGE` | cocotb Makefile.sim treats `COVERAGE=1` as Python coverage.py | Supersedes: none
2026-11-09 | Fast mutation subset includes 2×2 latency and A `tready=0` after A-done | Round-1 survivors M17/M32 were test gaps against [N] COMPUTE length and LOAD tready | Supersedes: none
2026-11-09 | 8×8 is a parameterised instance; RTL default stays R=C=4 | Spec [N] default is 4; scale by `chparam`/`-GR` | Supersedes: none
2026-11-09 | Tile formal is BMC depth 20 + cover, not k-induction | Beat-count auxiliaries are not inductive (`DONE (UNKNOWN)` on prove); BMC holds the same asserts | Supersedes: none
2026-11-09 | Scratchpad vector feed is generate-loop `assign`, not `always_comb` integer for-loops | Yosys 0.70 infers latches on the loop indices | Supersedes: none
2026-11-09 | Uninit-state seeds are `--x-initial unique` plus runtime `+verilator+seed+N` | Verilator 5.053 rejects `--x-initial-seed` | Supersedes: none
2026-11-09 | PE INT32 wrap is a dedicated 131072-cycle (−128)×(−128) run, not inside the length-≤200 random suite | 200×16384 = 3.28e6 ≪ 2³¹; wrap needs 131072 products | Supersedes: none
2026-11-09 | Formal PE uses wrapper `pe_formal` (not `bind`) | Yosys 0.70 `read -formal` reports `syntax error, unexpected TOK_ID` on `bind` | Supersedes: none
2026-11-09 | `make lint` treats any `%Warning`/`%Error` in the Verilator log as failure; no blanket `-Werror` | Verilator 5.053 rejects `-Werror` (`Invalid option`; wants `-Werror-<msg>`) | Supersedes: none
2026-11-09 | Vector format v1 frozen in `docs/04-vector-format.md`; later change needs a version bump | Field set is the published contract | Supersedes: earlier "frozen as model-v1" wording
2026-11-09 | `make sim` verdict uses `results.xml` `<failure>`, not the Verilator process exit code | cocotb 1.9.2 Makefile.verilator cannot propagate test-fail status (`$finish` → 0) | Supersedes: none
2026-11-08 | Cycle traces omit `en=0` stall cycles; t counts only compute edges | Compact acc history; stall tests compare the filtered sequence | Supersedes: none
2026-11-08 | Reference models accept K ≥ 1 with no hard cap so a wrap test can use K=131072 (all −128 → C=−2³¹) | Spec forbids overflow for K≤131071; still requires a real INT32 wrap case | Supersedes: none
2026-11-08 | `start_i` is level-sampled in IDLE, not edge-detected; holding it through `done_o` starts another transaction | "Pulse" was ambiguous; this is the simpler FSM | Supersedes: none
2026-11-08 | Rejected (bad-K) start sets `err_code_o[0]` and leaves bits 1–2 unchanged; does not clear sticky TLAST flags | Start is not accepted, so the "cleared on accepted start" rule does not apply | Supersedes: none
2026-11-08 | `busy_o=0` in the same IDLE cycle as `done_o=1` | IDLE defines `busy_o=0`; matches "until the cycle done_o pulses" as exclusive of that cycle | Supersedes: none
2026-11-08 | While `m_axis_c_tvalid=0`, C `tdata`/`tlast` are unspecified | AXI-Stream payload is meaningless without valid; avoids over-constraining reset | Supersedes: none
2026-11-08 | Packed `a_vec`/`b_vec`/`acc_o` bit order: element 0 in the LSB slice | Two engineers could flatten either endianness | Supersedes: none
2026-11-08 | `clr=1` only in IDLE and LOAD; `clr=0` in COMPUTE, DRAIN, STORE | Spec named IDLE+LOAD; the other states were implicit | Supersedes: none
2026-11-08 | Synthesis evidence is Yosys cell counts only; no OpenLane/timing flow | `make versions`: openlane not found, flow.tcl not found | Supersedes: none
2026-11-08 | Pin cocotb==1.9.2 via Ubuntu pip and put /usr/local/bin before OSS CAD Suite on PATH | Suite 2026-10-14 ships cocotb-config 2.1.0.dev0 which would shadow the pin | Supersedes: none
2026-11-08 | Toolchain is Docker image opentile:dev (ubuntu:24.04 + OSS CAD Suite 2026-10-14, sha256-pinned tarballs) | Reproducible CAD tools without a host native install | Supersedes: none
2026-11-08 | Output-stationary dataflow, skew inside array.sv, unskewed vector feed | Fixes summation order; simplest controller | Supersedes: none
2026-11-08 | INT32 wrapping accumulator; raw INT32 output; no requantisation in 1.0 | Matches the exact INT32 sum; K_MAX makes overflow impossible | Supersedes: none
2026-11-08 | No array stall during COMPUTE; back-pressure only in LOAD and STORE; `en` freezes all PE state | Results are read after compute, nothing streams out during compute | Supersedes: earlier draft "global stall on output not ready"
2026-11-08 | K_MAX=64, R=C=4 default; sideband ports instead of AXI-Lite registers | Keeps 1.0 small and fully specified | Supersedes: none
2026-11-08 | Synchronous active-low reset for control, datapath cleared by `clr` | One reset style, no X dependence on state before clr | Supersedes: none
2026-11-08 | TLAST violations set sticky error flags; transaction continues on beat counts | Deterministic behaviour with no hang states | Supersedes: none
2026-11-08 | Uninitialised-state check uses Verilator --x-initial unique with several seeds (results must be identical) instead of X-propagation | Verilator is two-state | Supersedes: none
