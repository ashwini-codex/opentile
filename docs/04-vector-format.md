# Vector file format v1 / v2 [N]

Text, UTF-8, newline-separated. Used by `model/python/gen_vectors.py`, both reference models, and the testbenches. **v1** is frozen. **v2** adds an optional `FMT` line. v1 files remain valid (implicit `FMT INT8`). Logged in `docs/DECISIONS.md`.

## File
- First non-blank line **must** be exactly `# opentile-vectors v1` or `# opentile-vectors v2`.
- A `#` starts a comment to end of line, except that first magic line.
- Blank lines are ignored.
- One or more records follow. Records do not nest.

## Record grammar
```
TEST <name>
FMT INT8|E4M3          # optional; default INT8. Required to be present or omitted consistently; v1 files omit it.
R <r> C <c> K <k>
A <r*k hex-bytes>
B <k*c hex-bytes>
C <r*c hex-words>
END
```

- `<name>` matches `[A-Za-z0-9_]+` (ASCII only).
- `<r>`, `<c>`, `<k>` are decimal integers, `r,c ∈ [1,16]`, `k ≥ 1`. Generator directed cases use `k ≤ 64` except wrap-stress files.
- Tokens on `R`/`C`/`K` may appear on one line in that order.
- Hex is lowercase or uppercase. No `0x` prefix.

## Integer encoding (`FMT INT8`, default)
- **A, B bytes:** each token is exactly two hex digits. It is the two's-complement bit pattern of a signed INT8. `00`=0, `7f`=127, `80`=−128, `ff`=−1. Row-major: A beat `n` is `A[n // K][n % K]`; B beat `n` is `B[n // C][n % C]`.
- **C words:** each token is exactly eight hex digits. Two's-complement INT32. `00000000`=0, `00000023`=35, `fff00000`=−1048576, `80000000`=−2147483648. Row-major: beat `n` is `C[n // C][n % C]` (here the second `C` is the column count).

## E4M3 encoding (`FMT E4M3`)
- **A, B bytes:** two hex digits, the raw E4M3 code (`00`=+0, `38`=1.0, `7e`=448, `7f`/`ff`=NaN, `80`=−0).
- **C words:** eight hex digits, IEEE 754 binary32 bit pattern of the GEMM result (`3f800000`=1.0, `7fc00000`=canonical qNaN, `80000000`=−0).

## Example
```
# opentile-vectors v1
TEST demo_1x1
R 1 C 1 K 1
A 05
B 07
C 00000023
END
```
This is A=`[[5]]`, B=`[[7]]`, C=`[[35]]`.

## Rejecting malformed records
A loader **must** reject the file (non-zero exit / exception) if any of:
1. Missing or wrong magic line.
2. `TEST` name does not match `[A-Za-z0-9_]+`.
3. Duplicate name in one file.
4. `R`/`C`/`K` missing, non-integer, or out of range (`R,C` not in 1..16, `K < 1`).
5. `A`/`B`/`C` token count ≠ `R*K` / `K*C` / `R*C`.
6. A/B token not exactly 2 hex digits, or C token not exactly 8 hex digits.
7. Record missing `END`, or tokens after `END` before the next `TEST`.
8. Unexpected keyword.

Comments inside a record (`# ...`) are allowed and ignored.

## Generator
`python3 model/python/gen_vectors.py -o <path>` writes the INT8 directed set as **v1**. Re-run is deterministic (fixed seeds in names `rand_<seed>`). E4M3 records are v2 with `FMT E4M3`.
