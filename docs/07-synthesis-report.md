# Synthesis report (1.0 freeze)

Timing / PPA flow: **not available**. No OpenLane, OpenROAD, or vendor timing tools in the image (`make versions` prints `openlane: not found`). OpenTile 1.0 reports **Yosys cell counts only** — not a clock period, not placed area, not power.

Tool: Yosys `0.70+16 (git sha1 3bb533450)`. Default RTL parameters stay **R=C=4**; 8×8 is `chparam`. Reproduce with `make synth`.

## tile_top 4×4 and 8×8

Yosys script per size: `read_verilog -sv rtl/pe.sv rtl/array.sv rtl/tile_top.sv; chparam -set R <n> -set C <n> tile_top; hierarchy -top tile_top; synth -top tile_top; stat; stat -width`

Scratchpad maps to FFs (`$_DFFE_PP_`: 4096 at 4×4 = 4096 scratchpad bits; 8192 at 8×8). PE flops are `$_SDFFE_PP0P_`.

### Totals (flattened `design hierarchy` inclusive cell count)

| Instance | Cells | DFF (all *DFF*) |
|---|---:|---:|
| 4×4 | **28421** | **5053** |
| 8×8 | **85900** | **11805** |
| 8×8 / 4×4 | **3.0224** | **2.3362** |

### Cell types

| Type | 4×4 | 8×8 |
|---|---:|---:|
| `$_NAND_` | 7655 | 27217 |
| `$_DFFE_PP_` | 4096 | 8192 |
| `$_AND_` | 4092 | 12261 |
| `$_XOR_` | 3636 | 13958 |
| `$_MUX_` | 3331 | 6534 |
| `$_XNOR_` | 1638 | 6095 |
| `$_ORNOT_` | 1148 | 3216 |
| `$_OR_` | 948 | 2554 |
| `$_SDFFE_PP0P_` | 864 | 3520 |
| `$_ANDNOT_` | 480 | 1525 |
| `$_NOR_` | 323 | 556 |
| `$_NOT_` | 117 | 179 |
| `$_SDFFE_PN0P_` | 85 | 85 |
| `$_SDFF_PN0_` | 7 | 7 |
| `$_SDFFE_PN1P_` | 1 | 1 |
| **Total** | **28421** | **85900** |

### Prediction gap

Predicted total-cell ratio **3.6** (PE×4, skew×4.67, scratchpad×2). Measured **3.02**. DFF ratio predicted **2.4**, measured **2.34** (scratchpad FFs dominate and only double). Combo grew ~3.2× rather than 4× (`$_MUX_` 3331→6534 is ~2×; controller muxing does not quadruple). That pulls the cell ratio below the PE-count factor of 4.

PE-only Yosys (`make pe-test`): 902 cells with the `valid_o` pin (1.0 freeze without that pin was 901 / 48 `$_SDFFE_PP0P_`). E4M3 PE is 2049 cells / 63 DFF (ratio 2.272 vs INT8).

Live `make synth` after the array `valid` pin is 28462 / 85971; the table above is the 1.0 freeze.

## What limits size and speed (no STA)

- **Size:** `R` and `C` legal 1..16; default 4, demonstrated 8. Scratchpad maps to FFs (`$_DFFE_PP_` = `(R+C)·K_MAX·8` bits). 8×8 already 8192 those FFs; 16×16 at `K_MAX=64` would be 16384 scratchpad bits plus 256 PEs.
- **Speed (cycles, not ns):** COMPUTE is `K+R+C−2` with no array stall; STORE is `R·C` serial AXI-Stream beats. For square N with K=N the inclusive latency is `2N²+3N+1` (15 / 45 / 153). Measured: 2×2 K=2 = 15, 4×4 K=4 = 45, 8×8 K=2 = 99 (`make sim SIZES="2 4 8"`).
- **4×4 vs 8×8:** PE count ×4; scratchpad FFs ×2; measured cells ×3.02 (combo did not quadruple; see prediction gap above).
