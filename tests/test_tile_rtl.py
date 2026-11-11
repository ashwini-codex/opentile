"""Extra RTL tests for tile_top. Does not modify the stand-in testbench."""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from axi_monitor import AxiMonitor  # noqa: E402
from ref import gemm_int8  # noqa: E402
from tb import reset, run_txn, to_signed  # noqa: E402

R = int(os.environ.get("PARAM_R", "2"))
C = int(os.environ.get("PARAM_C", "2"))
K_MAX = int(os.environ.get("K_MAX", "64"))
SEED = int(os.environ.get("SEED", "1"))
SUITE = os.environ.get("SUITE") or "extra"
REPORTS = os.path.join(ROOT, "reports", "O8")
CFILE = os.environ.get("CFILE") or ""


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)


def ones(rr, cc, kk):
    A = [[1] * kk for _ in range(rr)]
    B = [[1] * cc for _ in range(kk)]
    return A, B


async def count_latency(dut, A, B, rr, cc, kk):
    """Inclusive cycles from start-accept edge through done_o, no back-pressure."""
    a_beats = [A[i][k] for i in range(rr) for k in range(kk)]
    b_beats = [B[k][j] for k in range(kk) for j in range(cc)]
    a_i = b_i = 0
    dut.cfg_k_i.value = kk
    dut.start_i.value = 1
    dut.m_axis_c_tready.value = 1
    cycles = 0

    def drive_ab():
        if a_i < len(a_beats):
            dut.s_axis_a_tdata.value = a_beats[a_i] & 0xFF
            dut.s_axis_a_tlast.value = int(a_i == len(a_beats) - 1)
            dut.s_axis_a_tvalid.value = 1
        else:
            dut.s_axis_a_tvalid.value = 0
            dut.s_axis_a_tlast.value = 0
        if b_i < len(b_beats):
            dut.s_axis_b_tdata.value = b_beats[b_i] & 0xFF
            dut.s_axis_b_tlast.value = int(b_i == len(b_beats) - 1)
            dut.s_axis_b_tvalid.value = 1
        else:
            dut.s_axis_b_tvalid.value = 0
            dut.s_axis_b_tlast.value = 0

    drive_ab()
    await Timer(1, units="ns")
    while True:
        cycles += 1
        av = int(dut.s_axis_a_tvalid.value)
        ar = int(dut.s_axis_a_tready.value)
        bv = int(dut.s_axis_b_tvalid.value)
        br = int(dut.s_axis_b_tready.value)
        await RisingEdge(dut.clk)
        if av and ar and a_i < len(a_beats):
            a_i += 1
        if bv and br and b_i < len(b_beats):
            b_i += 1
        if int(dut.done_o.value):
            dut.start_i.value = 0
            return cycles
        if cycles == 1:
            dut.start_i.value = 0
        drive_ab()
        await Timer(1, units="ns")
        if cycles > 100000:
            raise AssertionError("latency timeout")


async def run_a_done_b_slow(dut, A, B, rr, cc, kk):
    """Finish A first, hold extra A valid, require tready=0 until B completes."""
    a_beats = [A[i][k] for i in range(rr) for k in range(kk)]
    b_beats = [B[k][j] for k in range(kk) for j in range(cc)]
    expect = gemm_int8(A, B, rr, cc, kk)
    a_i = b_i = 0
    extra = 0
    got = []
    dut.cfg_k_i.value = kk
    dut.start_i.value = 1
    dut.m_axis_c_tready.value = 1

    def drive():
        if a_i < len(a_beats):
            dut.s_axis_a_tdata.value = a_beats[a_i] & 0xFF
            dut.s_axis_a_tlast.value = int(a_i == len(a_beats) - 1)
            dut.s_axis_a_tvalid.value = 1
        else:
            dut.s_axis_a_tdata.value = 0x7F
            dut.s_axis_a_tlast.value = 0
            dut.s_axis_a_tvalid.value = 1
        if (a_i >= len(a_beats)) and (extra >= 4) and (b_i < len(b_beats)):
            dut.s_axis_b_tdata.value = b_beats[b_i] & 0xFF
            dut.s_axis_b_tlast.value = int(b_i == len(b_beats) - 1)
            dut.s_axis_b_tvalid.value = 1
        else:
            dut.s_axis_b_tvalid.value = 0
            dut.s_axis_b_tlast.value = 0

    drive()
    await Timer(1, units="ns")
    cycles = 0
    saw_a_tready_low = False
    while True:
        cycles += 1
        av = int(dut.s_axis_a_tvalid.value)
        ar = int(dut.s_axis_a_tready.value)
        bv = int(dut.s_axis_b_tvalid.value)
        br = int(dut.s_axis_b_tready.value)
        cv = int(dut.m_axis_c_tvalid.value)
        cr = int(dut.m_axis_c_tready.value)
        if a_i >= len(a_beats) and b_i < len(b_beats):
            if ar != 0:
                raise AssertionError("A tready still 1 after A beats done")
            saw_a_tready_low = True
            extra += 1
        await RisingEdge(dut.clk)
        if cycles == 1:
            dut.start_i.value = 0
        if av and ar and a_i < len(a_beats):
            a_i += 1
        if bv and br and b_i < len(b_beats):
            b_i += 1
        if cv and cr:
            got.append(to_signed(dut.m_axis_c_tdata.value, 32))
        if int(dut.done_o.value):
            break
        drive()
        await Timer(1, units="ns")
        if cycles > 100000:
            raise AssertionError("load_hold timeout")
    if not saw_a_tready_low:
        raise AssertionError("never observed A tready=0 after A done")
    flat = [expect[i][j] for i in range(rr) for j in range(cc)]
    if got != flat:
        raise AssertionError("load_hold C mismatch got %s want %s" % (got, flat))


async def pulse_reset(dut, cycles=2):
    dut.rst_n.value = 0
    dut.start_i.value = 0
    dut.s_axis_a_tvalid.value = 0
    dut.s_axis_b_tvalid.value = 0
    dut.m_axis_c_tready.value = 1
    for _ in range(cycles):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert int(dut.busy_o.value) == 0
    assert int(dut.done_o.value) == 0
    assert int(dut.err_code_o.value) == 0
    assert int(dut.s_axis_a_tready.value) == 0
    assert int(dut.s_axis_b_tready.value) == 0
    assert int(dut.m_axis_c_tvalid.value) == 0


async def wait_state_then_reset(dut, after_start, A, B, rr, cc, kk):
    a_beats = [A[i][k] for i in range(rr) for k in range(kk)]
    b_beats = [B[k][j] for k in range(kk) for j in range(cc)]
    a_i = b_i = 0
    dut.cfg_k_i.value = kk
    dut.start_i.value = 1
    dut.m_axis_c_tready.value = 1

    def drive_ab():
        if a_i < len(a_beats):
            dut.s_axis_a_tdata.value = a_beats[a_i] & 0xFF
            dut.s_axis_a_tlast.value = int(a_i == len(a_beats) - 1)
            dut.s_axis_a_tvalid.value = 1
        else:
            dut.s_axis_a_tvalid.value = 0
        if b_i < len(b_beats):
            dut.s_axis_b_tdata.value = b_beats[b_i] & 0xFF
            dut.s_axis_b_tlast.value = int(b_i == len(b_beats) - 1)
            dut.s_axis_b_tvalid.value = 1
        else:
            dut.s_axis_b_tvalid.value = 0

    drive_ab()
    await Timer(1, units="ns")
    for n in range(after_start):
        av = int(dut.s_axis_a_tvalid.value)
        ar = int(dut.s_axis_a_tready.value)
        bv = int(dut.s_axis_b_tvalid.value)
        br = int(dut.s_axis_b_tready.value)
        await RisingEdge(dut.clk)
        if n == 0:
            dut.start_i.value = 0
        if av and ar and a_i < len(a_beats):
            a_i += 1
        if bv and br and b_i < len(b_beats):
            b_i += 1
        drive_ab()
        await Timer(1, units="ns")
    await pulse_reset(dut)


async def run_tlast(dut, A, B, rr, cc, kk, a_bad=False, b_bad=False):
    expect = gemm_int8(A, B, rr, cc, kk)
    a_beats = [A[i][k] for i in range(rr) for k in range(kk)]
    b_beats = [B[k][j] for k in range(kk) for j in range(cc)]
    got = []
    lasts = []
    a_i = b_i = 0
    dut.cfg_k_i.value = kk
    dut.start_i.value = 1
    dut.m_axis_c_tready.value = 1

    def tlast_a(i):
        if a_bad:
            return int(i == 0)
        return int(i == len(a_beats) - 1)

    def tlast_b(i):
        if b_bad:
            return int(i == 0)
        return int(i == len(b_beats) - 1)

    def drive_ab():
        if a_i < len(a_beats):
            dut.s_axis_a_tdata.value = a_beats[a_i] & 0xFF
            dut.s_axis_a_tlast.value = tlast_a(a_i)
            dut.s_axis_a_tvalid.value = 1
        else:
            dut.s_axis_a_tvalid.value = 0
            dut.s_axis_a_tlast.value = 0
        if b_i < len(b_beats):
            dut.s_axis_b_tdata.value = b_beats[b_i] & 0xFF
            dut.s_axis_b_tlast.value = tlast_b(b_i)
            dut.s_axis_b_tvalid.value = 1
        else:
            dut.s_axis_b_tvalid.value = 0
            dut.s_axis_b_tlast.value = 0

    drive_ab()
    await Timer(1, units="ns")
    timeout = 0
    while True:
        timeout += 1
        if timeout > 200000:
            raise AssertionError("tlast txn timeout")
        av = int(dut.s_axis_a_tvalid.value)
        ar = int(dut.s_axis_a_tready.value)
        bv = int(dut.s_axis_b_tvalid.value)
        br = int(dut.s_axis_b_tready.value)
        cv = int(dut.m_axis_c_tvalid.value)
        cr = int(dut.m_axis_c_tready.value)
        if cv and cr:
            got.append(to_signed(dut.m_axis_c_tdata.value, 32))
            lasts.append(int(dut.m_axis_c_tlast.value))
        await RisingEdge(dut.clk)
        if timeout == 1:
            dut.start_i.value = 0
        if av and ar and a_i < len(a_beats):
            a_i += 1
        if bv and br and b_i < len(b_beats):
            b_i += 1
        if int(dut.done_o.value):
            break
        drive_ab()
        await Timer(1, units="ns")
    flat = [expect[i][j] for i in range(rr) for j in range(cc)]
    assert got == flat, "tlast txn C mismatch got %s want %s" % (got, flat)
    err = int(dut.err_code_o.value)
    if a_bad:
        assert err & 2, "A_TLAST not set"
    if b_bad:
        assert err & 4, "B_TLAST not set"
    return err


@cocotb.test()
async def test_rtl(dut):
    mon = AxiMonitor()
    await start_clock(dut)
    cocotb.start_soon(mon.run(dut))
    os.makedirs(REPORTS, exist_ok=True)

    if SUITE == "latency":
        A, B = ones(R, C, 4 if R == 4 else 2)
        K = 4 if R == 4 else 2
        n = await count_latency(dut, A, B, R, C, K)
        want = 1 + max(R * K, K * C) + (K + R + C - 2) + 1 + R * C + 1
        path = os.path.join(REPORTS, "latency-%dx%d-k%d.txt" % (R, C, K))
        with open(path, "w") as f:
            f.write("cycles=%d want=%d\n" % (n, want))
        assert n == want, "latency %d want %d" % (n, want)
        await run_txn(dut, A, B, R, C, K, bp="always", seed=SEED, name="lat_check")

    elif SUITE == "reset_mid":
        A, B = ones(2, 2, 2)
        # 2x2 K=2: LOAD t=1..4, COMPUTE t=5..8, STORE t=10..13 (from timing diagram)
        await wait_state_then_reset(dut, 3, A, B, 2, 2, 2)  # LOAD
        await run_txn(dut, A, B, 2, 2, 2, bp="always", seed=1, name="after_rst_load")
        await wait_state_then_reset(dut, 7, A, B, 2, 2, 2)  # COMPUTE
        await run_txn(dut, A, B, 2, 2, 2, bp="always", seed=1, name="after_rst_compute")
        await wait_state_then_reset(dut, 12, A, B, 2, 2, 2)  # STORE
        await run_txn(dut, A, B, 2, 2, 2, bp="always", seed=1, name="after_rst_store")

    elif SUITE == "tlast":
        A, B = ones(2, 2, 2)
        await run_tlast(dut, A, B, 2, 2, 2, a_bad=True, b_bad=False)
        await RisingEdge(dut.clk)
        await run_tlast(dut, A, B, 2, 2, 2, a_bad=False, b_bad=True)

    elif SUITE == "kmax":
        rng = random.Random(SEED)
        K = K_MAX
        A = [[rng.randint(-128, 127) for _ in range(K)] for _ in range(R)]
        B = [[rng.randint(-128, 127) for _ in range(C)] for _ in range(K)]
        await run_txn(dut, A, B, R, C, K, bp="always", seed=SEED, name="kmax")
        dut.cfg_k_i.value = 0
        dut.start_i.value = 1
        await RisingEdge(dut.clk)
        dut.start_i.value = 0
        await Timer(1, units="ns")
        assert int(dut.busy_o.value) == 0
        assert int(dut.err_code_o.value) & 1
        dut.cfg_k_i.value = K_MAX + 1
        dut.start_i.value = 1
        await RisingEdge(dut.clk)
        dut.start_i.value = 0
        await Timer(1, units="ns")
        assert int(dut.busy_o.value) == 0
        assert int(dut.err_code_o.value) & 1

    elif SUITE == "catch":
        A = [[-1, 2], [3, -4]]
        B = [[5, -6], [7, 8]]
        bp = os.environ.get("BP") or "stall3"
        await run_txn(dut, A, B, 2, 2, 2, bp=bp, seed=SEED, name="catch")

    elif SUITE == "xinit":
        A, B = ones(2, 2, 2)
        await run_txn(dut, A, B, 2, 2, 2, bp="always", seed=1, name="xinit")
        if CFILE:
            expect = gemm_int8(A, B, 2, 2, 2)
            flat = [expect[i][j] for i in range(2) for j in range(2)]
            with open(CFILE, "w") as f:
                f.write(" ".join(str(x) for x in flat) + "\n")

    elif SUITE == "mut_extra":
        A, B = ones(R, C, 2)
        K = 2
        n = await count_latency(dut, A, B, R, C, K)
        want = 1 + max(R * K, K * C) + (K + R + C - 2) + 1 + R * C + 1
        assert n == want, "latency %d want %d" % (n, want)
        await RisingEdge(dut.clk)
        A2 = [[1, 2], [3, 4]]
        B2 = [[5, 6], [7, 8]]
        await run_a_done_b_slow(dut, A2, B2, 2, 2, 2)

    elif SUITE == "monitor":
        A = [[1, 2], [3, 4]]
        B = [[5, 6], [7, 8]]
        await run_txn(dut, A, B, 2, 2, 2, bp="long", seed=SEED, name="mon_long")
        await run_txn(dut, A, B, 2, 2, 2, bp="random", seed=SEED + 1, name="mon_rand")

    else:
        raise AssertionError("unknown SUITE " + SUITE)

    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    if not mon.ok():
        raise AssertionError("axi monitor: " + "; ".join(mon.violations))
    with open(os.path.join(REPORTS, "axi-monitor-%s.txt" % SUITE), "w") as f:
        f.write("violations=0 suite=%s\n" % SUITE)
