# OpenTile — numerics specification  (INT8 1.0; FP8 E4M3 1.1)

## INT8 [N]
- Operands: signed 8-bit two's complement, range −128..127.
- Product: exact signed 16-bit (largest magnitude (−128)×(−128) = 16384).
- Accumulation: 32-bit two's complement, **wraps on overflow**. Within the supported K range wrapping cannot occur: |sum| ≤ K × 16384 ≤ 64 × 16384 = 1,048,576 ≪ 2³¹. (Overflow is impossible for K ≤ 131071; the models and the PE unit test still implement and test the wrap, because the PE is also exercised outside the tile's supported K.)
- Result: `C[i][j] = wrap32( Σ_{k<K} A[i][k]·B[k][j] )`, output as raw signed INT32. **No saturation, no requantisation, no rounding** in 1.0. `wrap32` is reduction modulo 2³² into two's-complement INT32: `((x + 2³¹) mod 2³²) − 2³¹`.
- Summation order is irrelevant for INT8 (integer addition is associative, including under wrap) — a test must show this.
- Supported K: 1..`K_MAX`. K = 0 and K > `K_MAX` are errors (see interface spec). The *model* functions accept any K ≥ 1 up to 131071.

## Decisions fixed here (also logged in DECISIONS.md)
1. Output-stationary dataflow.
2. INT32 wrapping accumulator.
3. 1.0 outputs raw INT32.
4. No global stall of the array during compute: output back-pressure is applied only in LOAD (via `tready`) and STORE (via `tvalid/tready`) because results are read after compute ends. The array still has an `en` that freezes all state; it is used to test stall-insensitivity and is asserted only during COMPUTE by the top. *(Supersedes an earlier draft "global stall on output not ready"; reason: outputs are not streamed during compute.)*
5. K_MAX = 64 default.
6. Synchronous active-low reset `rst_n` for control; datapath cleared by `clr`.

## Open items
None for INT8. None for E4M3.

## FP8 E4M3 [N] (1.1)
Applies when the format parameter is E4M3. INT8 rules above are unchanged.

### Encoding
8-bit container, same AXI-Stream `tdata` width as INT8. Bit 7 = sign `S`, bits [6:3] = exponent `E` (unsigned, bias **7**), bits [2:0] = mantissa `M`. No infinities.

| Class | Condition | Value |
|---|---|---|
| Signed zero | `E=0`, `M=0` | `(-1)^S · 0` |
| Subnormal | `E=0`, `M≠0` | `(-1)^S · 2^{-6} · (M/8)` = `(-1)^S · M · 2^{-9}` |
| Normal | `1 ≤ E ≤ 15` and not NaN | `(-1)^S · 2^{E-7} · (1 + M/8)` |
| NaN | `E=15` and `M=7` | NaN (two codes: `0x7F` and `0xFF`) |

Largest finite: `S=0`, `E=15`, `M=6` → `2^8 · 1.75` = **448**. Smallest positive subnormal = **2⁻⁹**. Smallest positive normal = **2⁻⁶**. `1.0` is `E=7`, `M=0` (`0x38`).

### Product
If either operand is NaN, the product is NaN (sign of NaN is ignored). Otherwise the product is exact: magnitude = |A|·|B|, sign = `S_A XOR S_B` (IEEE XOR, including zeros). So `(+0)·(−x)` is `−0` for finite nonzero `x`.

### Accumulation (exact fixed-point)
All **finite** products for one `C[i][j]` are summed in a **43-bit two's-complement** register whose LSB has weight **2⁻¹⁸**.

Derivation (`K_MAX=64`): smallest finite |A| and |B| are 2⁻⁹, so min |product| = 2⁻¹⁸ → 18 fraction bits. Max |product| = 448² = 200704. Max |sum| = 64·200704 = 12,845,056. In ulps of 2⁻¹⁸: `64 · 448² · 2¹⁸ = 49 · 2³⁶`. A 43-bit two's-complement integer holds ±2⁴², and 49·2³⁶ < 2⁴², so **43 bits** is the smallest width that holds every legal sum (including sign).

Why this removes order dependence: the running sum is integer addition of those ulps. Integer addition is associative (including wrap, which cannot occur for K ≤ 64). There is **no rounding of partial sums**.

If **any** of the K products is NaN, `C[i][j]` is the canonical NaN below and the numeric sum is not used.

### One rounding to FP32
After the K-sum, convert the 43-bit fixed-point value to IEEE 754 **binary32** with **round-to-nearest, ties to even** (IEEE 754-2008 `roundTiesToEven`). That is the **only** rounding in the E4M3 path. Legal |sums| are integer multiples of 2⁻¹⁸ in [0, 12,845,056], so they are finite FP32 (no overflow to Inf; nonzero values are FP32 normals).

Canonical NaN output: FP32 quiet NaN with payload 0, positive sign: bits `0x7FC00000`. Both operand NaN codes produce this same result.

### Signed zero of an exact-zero sum
Product signs follow XOR as above. If the exact sum is zero:
- output FP32 **−0** iff **every** of the K products is −0;
- otherwise output FP32 **+0** (includes all-+0, mixed +0/−0, and cancellation of nonzero terms).

### What this does *not* model
Running sums in a narrower float (FP16/FP32/TF32 accumulators with rounding every MAC), stochastic rounding, E5M2, saturation to 448, and any kernel other than GEMM. Those would re-introduce order dependence; this design's exact acc does not.

### Output
`C[i][j]` is that FP32 value (raw 32-bit IEEE bits on the C stream in 1.1). No requantisation back to E4M3 in 1.1.
