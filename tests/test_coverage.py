"""Coverage suite: FSM, TLAST, K_MAX, sizes, acc bands. Tile testbench via run_txn."""
import os
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from ref import gemm_int8  # noqa: E402
from tb import COV, reset, run_txn, to_signed  # noqa: E402
from test_tile_rtl import run_tlast  # noqa: E402

R = int(os.environ.get("PARAM_R", "2"))
C = int(os.environ.get("PARAM_C", "2"))
K_MAX = int(os.environ.get("K_MAX", "64"))
REPORTS = os.path.join(ROOT, "reports", "O10")

ST = {0: "IDLE", 1: "LOAD", 2: "COMPUTE", 3: "DRAIN", 4: "STORE"}


class FsmCover:
    def __init__(self):
        self.states = set()
        self.trans = set()

    async def run(self, dut):
        prev = None
        await Timer(1, units="ns")
        while True:
            try:
                s = int(dut.state.value)
            except Exception:
                s = None
            if s is not None and s in ST:
                self.states.add("fsm_" + ST[s])
                if prev is not None and prev in ST and s != prev:
                    self.trans.add("fsm_%s_%s" % (ST[prev], ST[s]))
                prev = s
            await RisingEdge(dut.clk)
            await Timer(1, units="ns")


@cocotb.test()
async def test_coverage(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    fsm = FsmCover()
    cocotb.start_soon(fsm.run(dut))

    A0 = [[0, 0], [0, 0]]
    B0 = [[0, 0], [0, 0]]
    await run_txn(dut, A0, B0, 2, 2, 2, bp="always", seed=1, name="cov_zero")

    A1 = [[1, -1], [-1, 1]]
    B1 = [[1, 1], [1, -1]]
    await run_txn(dut, A1, B1, 2, 2, 2, bp="always", seed=1, name="cov_pm1")

    Ae = [[-128, 127], [127, -128]]
    Be = [[-128, 127], [127, -128]]
    await run_txn(dut, Ae, Be, 2, 2, 2, bp="always", seed=1, name="cov_ext")

    await run_txn(dut, [[9], [-4]], [[2, 8]], 2, 2, 1, bp="always", seed=1, name="cov_k1")
    await run_txn(
        dut, [[20, 0], [0, 20]], [[20, 0], [0, 20]], 2, 2, 2, bp="always", seed=1, name="cov_med"
    )
    await run_txn(
        dut,
        [[1] * K_MAX, [2] * K_MAX],
        [[1] * 2 for _ in range(K_MAX)],
        2,
        2,
        K_MAX,
        bp="always",
        seed=1,
        name="cov_kmax",
    )
    await run_txn(dut, [[1, 2, 3], [4, 5, 6]], [[1, 0], [0, 1], [1, 1]], 2, 2, 3, bp="random", seed=3, name="cov_ktyp")
    await run_txn(dut, A1, B1, 2, 2, 2, bp="long", seed=4, name="cov_bplong")
    await run_txn(dut, A1, B1, 2, 2, 2, bp="every_other", seed=5, name="cov_bpeo")
    await run_txn(dut, A1, B1, 2, 2, 2, bp="stall3", seed=6, name="cov_bpstall")

    dut.cfg_k_i.value = 0
    dut.start_i.value = 1
    await RisingEdge(dut.clk)
    dut.start_i.value = 0
    await Timer(1, units="ns")
    COV.record([[0]], [[0]], 0, K_MAX, "always", R, C, int(dut.err_code_o.value))

    await run_tlast(dut, A1, B1, 2, 2, 2, a_bad=True, b_bad=False)
    COV.record(A1, B1, 2, K_MAX, "always", 2, 2, int(dut.err_code_o.value))
    await RisingEdge(dut.clk)
    await run_tlast(dut, A1, B1, 2, 2, 2, a_bad=False, b_bad=True)
    COV.record(A1, B1, 2, K_MAX, "always", 2, 2, int(dut.err_code_o.value))

    # Ten directed hand vectors. Logged after the run.
    hand = [
        ("h1_all_m128_x1", [[-128, -128], [-128, -128]], [[1, 1], [1, 1]], 2, "always"),
        ("h2_all_127_xm128", [[127, 127], [127, 127]], [[-128, -128], [-128, -128]], 2, "always"),
        ("h3_corner", [[7, 0], [0, 0]], [[9, 0], [0, 0]], 2, "always"),
        ("h4_k5_ones", [[1] * 5, [1] * 5], [[1, 1] for _ in range(5)], 5, "always"),
        ("h5_alt01", [[0, 1], [1, 0]], [[0, 1], [1, 0]], 2, "every_other"),
        ("h6_id_like", [[1, 0], [0, 1]], [[10, 20], [30, 40]], 2, "always"),
        ("h7_all_m1", [[-1, -1], [-1, -1]], [[-1, -1], [-1, -1]], 2, "random"),
        ("h8_k63", [[1] * 63, [-1] * 63], [[1, -1] for _ in range(63)], 63, "always"),
        ("h9_ext_stall3", [[-128, 0], [0, 127]], [[1, -1], [-1, 1]], 2, "stall3"),
        ("h10_rows_pm3", [[3, 3], [-3, -3]], [[1, 0], [0, 1]], 2, "long"),
    ]
    hand_lines = []
    for name, A, B, K, bp in hand:
        await run_txn(dut, A, B, 2, 2, K, bp=bp, seed=11, name=name)
        exp = gemm_int8(A, B, 2, 2, K)
        hand_lines.append("%s K=%d bp=%s C=%s PASS" % (name, K, bp, exp))
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "hand-vectors.log"), "w") as hf:
        hf.write("hand vectors %d (all matched gemm_int8)\n" % len(hand_lines))
        for ln in hand_lines:
            hf.write(ln + "\n")

    COV.bins.update(fsm.states)
    COV.bins.update(fsm.trans)
    os.makedirs(REPORTS, exist_ok=True)
    COV.dump(os.path.join(REPORTS, "functional-2x2.txt"))
