# What these numbers do not show

This file is the honest limit of the coverage, formal, mutation, and synthesis evidence. 100% of the *defined* bins is not a proof of correctness.

## Functional coverage
Hitting every bin in `scripts/required_bins.txt` means those *classes of stimulus* occurred and the scoreboard did not fail. It does not mean:
- every INT8 pair was applied at every PE (65536² is not the tile suite);
- every legal (R,C,K) was run (R,C ≤ 16, K ≤ 64 is a large space; we sample 2/4/8 and directed shapes);
- packing bugs that only appear at untested shapes cannot exist.

## Line / toggle coverage
Verilator coverage is a two-state, clocked count of statements/toggles in this testbench. Unreachable `default` FSM encodings, reset-abandoned STORE, and Yosys-only generate corners may sit at 0%. 100% line coverage of `pe.sv` still misses a wrong *spec*.

## Formal
PE properties are BMC depth 20 **and** k-induction. Tile properties are BMC depth 20 plus covers; k-induction was not used (aux beat counters). Depth 20 means: no counterexample of length ≤ 20 after a reset. It does not bound longer bugs (e.g. a K=64 LOAD). Covers show the asserts are not vacuous on those traces, not that every path was proved.

## Mutation
32 hand-written edits in `scripts/mutations.py` are a **sample**, not the set of all faults. Measured score **27/32 = 0.8438**; five survivors are equivalent (M08/M23/M24/M28/M29). See `docs/mutation.md`. Equivalent mutants say nothing about quality. A killed mutant says *this* fast 2×2 subset can fail, not that `make verify` would catch every cousin of that fault.

## Synthesis cell counts
Yosys `synth` generic cells, not a placed-and-routed chip. No timing, area in µm², or power.

## Out of scope (also in the README)
Multiple outstanding transactions, interrupts, AXI-Lite, run-time R/C change, mid-txn K change. FP8 E4M3 is 1.1 at the PE/array (`FMT`); `tile_top` C stream is still INT32 wrap (`docs/03-interface-spec.md`).

## FP8 bins
Seven operand/result classes. Hitting them does not mean every E4M3 pair at every K, or that a 40-bit acc would have been caught by K=1 exhaustive (it would not: 448² fits in 40 bits). The 40-bit gap is a dedicated K=11 test, not a bin.
