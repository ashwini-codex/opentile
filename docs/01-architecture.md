# OpenTile — architecture  **[N] for everything marked [N]**

## Parameters [N]
| Parameter | Default | Legal range | Meaning |
|---|---|---|---|
| `R` | 4 | 1..16 | rows of PEs = rows of A and C |
| `C` | 4 | 1..16 | columns of PEs = columns of B and C |
| `K_MAX` | 64 | 1..4096 | largest runtime K; sizes the scratchpad |
| `FMT` | `"INT8"` | `"INT8"` or `"E4M3"` | operand format. Default keeps 1.0 INT8 behaviour |
Runtime input `cfg_k_i` selects K in 1..`K_MAX`. Data width is fixed: 8-bit operands, 32-bit result port (INT8: wrap32; E4M3: IEEE binary32 bits). E4M3 internal acc is 43-bit fixed-point (LSB=2⁻¹⁸).

## Sizing (defaults) [N]
For `R=4`, `C=4`, `K_MAX=64`:
- A scratchpad: `R·K_MAX` = 256 bytes = **2048 bits**
- B scratchpad: `K_MAX·C` = 256 bytes = **2048 bits**
- Total scratchpad = **4096 bits**
- PE count = `R·C` = **16**
An 8×8 instance (`R=C=8`, same `K_MAX`) has **64 PEs** and scratchpad `8·64 + 64·8` = 1024 bytes = 8192 bits.
Bound check: `K_MAX · 16384 = 64 · 16384 = 1,048,576 < 2³¹ = 2,147,483,648`. The same inequality holds at the legal-parameter ceiling `K_MAX=4096` (67,108,864 < 2³¹).

## Layers
| Layer | Artifact |
|---|---|
| L0 contract | this file, `02-numerics-spec.md`, `03-interface-spec.md` |
| L1 functional model | `model/python/ref.py`, `model/cpp/ref.cpp`, vector file |
| L2 cycle model | `model/python/array_cycle.py`, trace files |
| L3 test environment | `tests/` cocotb testbench + stand-in DUTs |
| L4 processing element | `rtl/pe.sv` |
| L5 array | `rtl/array.sv` (skew front-end + R×C PEs) |
| L6 interface/control | `rtl/tile_top.sv` |

## Dataflow [N]: output-stationary
PE(i,j) keeps one running sum for C[i][j]. The array is fed **unskewed vectors**: at feed cycle k (k = 0..K-1) it receives column k of A (`a_vec[i] = A[i][k]`) and row k of B (`b_vec[j] = B[k][j]`). Inside `array.sv`, row i is delayed by i cycles and column j by j cycles (skew registers); each PE passes its A input right and its B input down through one register. Hence the pair (A[i][k], B[k][j]) meets at PE(i,j) in **array cycle t = i + j + k** (t counted from the first feed cycle, t = 0).
- The last product lands at PE(R−1,C−1) in cycle K+R+C−3, so the **compute phase lasts exactly `K+R+C−2` cycles** [N]. Final accumulators are stable from the clock edge that ends cycle K+R+C−3.
- Feed inputs outside k∈[0,K) are zero (the controller supplies zeros, so the array may simply run `en` for the whole compute phase).
- Useful fraction of PE cycles = K/(K+R+C−2).

Golden example (hand-checked and simulated): `docs/golden/2x2-k3.md`.

## PE behaviour [N] (`rtl/pe.sv`)
Ports: `clk`, `clr`, `en`, `valid`, `a_in[7:0]` signed, `b_in[7:0]` signed, `a_out[7:0]`, `b_out[7:0]`, `valid_o`, `acc[31:0]` signed. Parameter `FMT` default `"INT8"`.
On each rising edge, in priority order:
1. `clr` → datapath zeros (`acc`/`acc_fx`/`poison`/`all_neg0`/`seen`), `a_out ← 0`, `b_out ← 0`, `valid_o ← 0`.
2. else `en` → `a_out ← a_in`, `b_out ← b_in`, `valid_o ← valid`, and a MAC as below.
3. else everything holds (global freeze).
If `clr` and `en` are both 1, `clr` wins. After `clr`, `acc`, `a_out` and `b_out` are 0 (these are the port reset values; the PE has no `rst_n`).
Latency of the pass-through: exactly one cycle. `acc` is visible the cycle after the update edge (`FMT=INT8`: registered wrap32; `FMT=E4M3`: combinational RNE of the registered 43-bit sum).

INT8 MAC (`FMT="INT8"`): `acc ← acc + a_in*b_in` (signed 16-bit product sign-extended, 32-bit two's-complement wrap). `valid` is ignored for the product (always MAC on `en`) so 1.0 tests keep their meaning; `valid` is still delayed with A.

E4M3 MAC (`FMT="E4M3"`): only when `en && valid`. Decode each 8-bit code; 4×4-bit significand multiply; add unbiased exponents (`E=0` → −9 else `E−10`); align `sig_prod << (exp_a+exp_b+18)` into the 43-bit acc. Sticky NaN → `acc` bits `0x7FC00000`. −0 iff every valid product was −0. Padding feeds (`valid=0`) shift A/B but do not count as K-products.

## Array [N] (`rtl/array.sv`)
Ports: `clk`, `clr`, `en`, `valid` (1 = this unskewed feed is a real k), `a_vec` (packed `R` signed 8-bit elements; element i in bits `[8*i+7:8*i]`), `b_vec` (packed `C` signed 8-bit elements; element j in bits `[8*j+7:8*j]`), `acc_o` (packed `R*C` signed 32-bit elements; index n=`i*C+j` in bits `[32*n+31:32*n]`). Parameter `FMT` is passed to every PE. `valid` is delayed with A (row i by i, then rightward through PEs) so it meets the operands at t=`i+j+k`. `clr` clears PEs *and* the skew registers. `en` low freezes PEs and skew registers; feed inputs are ignored while `en` is low (driver may hold them). No other reset: datapath state is defined by `clr`. The top drives `clr=1` in IDLE and throughout LOAD, and `clr=0` in COMPUTE, DRAIN and STORE. The top's existing `feed` (`t_q < K` in COMPUTE) is the array `valid` pin.

## Top-level controller [N] (`rtl/tile_top.sv`) states
`IDLE → LOAD → COMPUTE → DRAIN → STORE → IDLE`. Details, timing and the error behaviour are in `03-interface-spec.md`. Array `clr=1` in IDLE and LOAD; `en=1` only in COMPUTE.

## Measured cycle counts (informative)
Inclusive cycles from the accepted-start edge through `done_o`, no back-pressure, both streams offering every LOAD cycle. Formula (same as `docs/03-interface-spec.md`): `1 + max(R·K, K·C) + (K+R+C−2) + 1 + R·C + 1`.

| R×C | K | Formula | Measured | Log |
|---|---:|---:|---:|---|
| 2×2 | 2 | 15 | 15 | `make sim SIZES="2 4 8"` |
| 4×4 | 4 | 45 | 45 | `make sim SIZES="2 4 8"` |
| 8×8 | 2 | 99 | 99 | `make sim SIZES="2 4 8"` |
| 2×2 | 3 | 18 | golden compute 5; full-tile 18 is the formula (RTL latency suite uses K=2 when R≠4) | `docs/golden/2x2-k3.md` |

8×8 with K=8 would be 153 by the same formula; the size sweep measures 8×8 at K=2 (99 cycles).

## Scratchpad [N]
A memory `R*K_MAX` bytes (row-major A), B memory `K_MAX*C` bytes (row-major B). Combinational read during COMPUTE: feed cycle k reads A[0..R-1][k] and B[k][0..C-1]. For array cycles t ≥ K the top **drives `a_vec` and `b_vec` to 0**; it does not use scratchpad values at those k. Contents undefined after reset; a transaction never reads a location it did not write.

## Trace format [N]
Text, one file per run. Used by `model/python/array_cycle.py`, the array cocotb dumper, and `scripts/trace_compare.py`.

```
# opentile-trace R=<R> C=<C> K=<K>
<t> <acc_0> <acc_1> ... <acc_{R*C-1}>
```

- First line is the header comment exactly as above (`<R>` etc. are decimal integers).
- Then one line per **array cycle** t = 0, 1, … after the rising edge that ends that cycle (same convention as `docs/golden/2x2-k3.md`).
- Accumulators are signed decimal INT32, **row-major** index n = i·C+j (same packing as `acc_o`).
- Compute runs t = 0 .. K+R+C−3 inclusive (K+R+C−2 lines). Extra trailing lines, if present, must repeat the final acc (hold).
- Stall cycles (`en=0`) are **omitted** from this file (they do not advance t). The cycle model may record them separately.

Example (golden 2×2 K=3):

```
# opentile-trace R=2 C=2 K=3
0 1 0 0 0
1 1 0 4 0
2 4 2 4 0
3 4 5 10 5
4 4 5 10 11
```
