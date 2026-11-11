# OpenTile — overview

**Goal.** A parameterised, open-source INT8 matrix-multiply tile in SystemVerilog: C = A × B with signed 8-bit inputs and 32-bit accumulation, on an R×C output-stationary systolic array, fed and drained over AXI-Stream, with a verification story a reader can reproduce with one command.

**Release 1.0** = INT8 tile (`rtl/tile_top.sv`). **Release 1.1** = adds FP8 E4M3 on the PE and array (`FMT="E4M3"`).

**Non-goals.** Training, sparsity, formats below 8 bits, multi-tile scheduling, chip fabrication, a full UVM environment, any performance claim beyond what the synthesis report shows, AXI-Lite/register-bus, requantisation of outputs.

**What "done" means** — all of:
1. `make verify` passes from a fresh clone inside the pinned container and in CI.
2. Two independent reference implementations agree; vector format is frozen in `docs/04-vector-format.md`.
3. Coverage, formal, mutation and synthesis reports exist with their honest limits written down (`docs/08-what-these-numbers-do-not-show.md`).

Glossary: `docs/GLOSSARY.md`. Decisions: `docs/DECISIONS.md`.
