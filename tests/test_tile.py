"""cocotb tests for tile_top stand-ins. SUITE=directed|random|bp|err|catch."""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from gen_vectors import directed, load_vector_file, write_file  # noqa: E402
from tb import COV, reset, run_txn  # noqa: E402

R = int(os.environ.get("PARAM_R", "2"))
C = int(os.environ.get("PARAM_C", "2"))
K_MAX = int(os.environ.get("K_MAX", "64"))
SEED = int(os.environ.get("SEED", "1"))
SUITE = os.environ.get("SUITE", "directed")
BP = os.environ.get("BP", "always")
VEC = os.environ.get("VECTORS") or os.path.join(ROOT, "model", "vectors", "directed.vec")
REPORTS = os.path.join(ROOT, "reports", "O5")


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)


@cocotb.test()
async def test_suite(dut):
    await start_clock(dut)
    if SUITE == "directed":
        write_file(VEC, directed())
        recs = [r for r in load_vector_file(VEC) if r["R"] == R and r["C"] == C]
        assert recs, "no directed records for %dx%d" % (R, C)
        for r in recs:
            await run_txn(
                dut, r["A"], r["B"], R, C, r["K"], bp=BP, seed=SEED, name=r["name"]
            )
            await RisingEdge(dut.clk)
    elif SUITE == "random":
        rng = random.Random(SEED)
        for n in range(1000):
            K = rng.randint(1, 8)
            A = [[rng.randint(-128, 127) for _ in range(K)] for _ in range(R)]
            B = [[rng.randint(-128, 127) for _ in range(C)] for _ in range(K)]
            await run_txn(dut, A, B, R, C, K, bp=BP, seed=SEED + n, name="rand_%d" % n)
    elif SUITE == "bp":
        A = [[1, 2], [3, 4]]
        B = [[5, 6], [7, 8]]
        await run_txn(dut, A, B, 2, 2, 2, bp=BP, seed=SEED, name="bp_" + BP)
    elif SUITE == "err":
        dut.cfg_k_i.value = 0
        dut.start_i.value = 1
        await RisingEdge(dut.clk)
        dut.start_i.value = 0
        await Timer(20, units="ns")
        assert int(dut.busy_o.value) == 0
        assert int(dut.err_code_o.value) & 1
        assert int(dut.s_axis_a_tready.value) == 0
        dut.cfg_k_i.value = K_MAX + 1
        dut.start_i.value = 1
        await RisingEdge(dut.clk)
        dut.start_i.value = 0
        await RisingEdge(dut.clk)
        assert int(dut.err_code_o.value) & 1
        assert int(dut.busy_o.value) == 0
        COV.record([[0]], [[0]], 0, K_MAX, "always", R, C, int(dut.err_code_o.value))
        A = [[1, 2], [3, 4]]
        B = [[5, 6], [7, 8]]
        await run_txn(
            dut, A, B, 2, 2, 2, bp="always", seed=1, name="busy_probe", start_busy_probe=True
        )
        # Spec: err_code_o is cleared on an accepted start (after K_RANGE above).
        assert int(dut.err_code_o.value) == 0, "err_code_o not cleared on accepted start"
    elif SUITE == "catch":
        A = [[-1, 2], [3, -4]]
        B = [[5, -6], [7, 8]]
        await run_txn(dut, A, B, 2, 2, 2, bp=BP, seed=SEED, name="catch")
    else:
        raise AssertionError("unknown SUITE " + SUITE)
    os.makedirs(REPORTS, exist_ok=True)
    COV.dump(os.path.join(REPORTS, "coverage_%s_%dx%d_%s.txt" % (SUITE, R, C, BP)))
