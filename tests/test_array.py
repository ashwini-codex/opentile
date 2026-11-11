"""cocotb tests for rtl/array.sv. SUITE selects the check; models generate all expected values."""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from array_cycle import ArrayModel, write_trace  # noqa: E402
from ref import gemm_int8  # noqa: E402
from trace_compare import compare  # noqa: E402

R = int(os.environ.get("PARAM_R") or "4")
C = int(os.environ.get("PARAM_C") or "4")
SUITE = os.environ.get("SUITE") or "traces"
SEED = int(os.environ.get("SEED") or "1")
K_MAX = int(os.environ.get("K_MAX") or "64")
REPORTS = os.path.join(ROOT, "reports", "O7")
TRACE_GOT = os.environ.get("TRACE_GOT") or os.path.join(REPORTS, "dut.trace")
TRACE_WANT = os.environ.get("TRACE_WANT") or os.path.join(REPORTS, "model.trace")


def to_signed(val, bits):
    v = int(val)
    if v >= (1 << (bits - 1)):
        v -= 1 << bits
    return v


def pack_vec(elems, width):
    v = 0
    for i, x in enumerate(elems):
        v |= (int(x) & ((1 << width) - 1)) << (width * i)
    return v


def unpack_acc(val, R, C):
    out = []
    iv = int(val)
    for n in range(R * C):
        w = (iv >> (32 * n)) & 0xFFFFFFFF
        out.append(to_signed(w, 32))
    return out


async def tick(dut):
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.clr.value = 1
    dut.en.value = 0
    if hasattr(dut, "valid"):
        dut.valid.value = 1
    dut.a_vec.value = 0
    dut.b_vec.value = 0
    await tick(dut)
    await tick(dut)


def drive(dut, a_vec, b_vec):
    dut.a_vec.value = pack_vec(a_vec, 8)
    dut.b_vec.value = pack_vec(b_vec, 8)


async def run_array(dut, A, B, R, C, K, stall_pattern=None):
    """Drive the same schedule as ArrayModel.run. Returns (final_matrix, acc_flats per en-cycle)."""
    m = ArrayModel(R, C)
    expect_final, expect_tr = m.run(A, B, K, stall_pattern=stall_pattern)
    schedule = []
    for k in range(K):
        schedule.append(([A[i][k] for i in range(R)], [B[k][j] for j in range(C)]))
    z_a, z_b = [0] * R, [0] * C
    for _ in range(R + C - 2):
        schedule.append((z_a, z_b))
    if stall_pattern is None:
        stall_pattern = [False] * len(schedule)
    dut.clr.value = 1
    dut.en.value = 0
    drive(dut, z_a, z_b)
    await tick(dut)
    dut.clr.value = 0
    idx = 0
    held_a, held_b = z_a, z_b
    got_flats = []
    for stall in stall_pattern:
        if stall:
            dut.en.value = 0
            if hasattr(dut, "valid"):
                dut.valid.value = 1
            drive(dut, held_a, held_b)
            await tick(dut)
        else:
            a_vec, b_vec = schedule[idx]
            idx += 1
            held_a, held_b = a_vec, b_vec
            dut.en.value = 1
            if hasattr(dut, "valid"):
                dut.valid.value = 1
            drive(dut, a_vec, b_vec)
            await tick(dut)
            got_flats.append(unpack_acc(dut.acc_o.value, R, C))
    dut.en.value = 0
    await tick(dut)
    final_flat = unpack_acc(dut.acc_o.value, R, C)
    final = [final_flat[i * C : (i + 1) * C] for i in range(R)]
    return final, got_flats, expect_final, [rec["acc"] for rec in expect_tr if not rec["stalled"]]


def last_change(flats):
    last = -1
    prev = None
    for t, acc in enumerate(flats):
        if prev is None or acc != prev:
            last = t
        prev = acc
    return last


def rand_ab(rng, R, C, K, force_last=True):
    A = [[rng.randint(-128, 127) for _ in range(K)] for _ in range(R)]
    B = [[rng.randint(-128, 127) for _ in range(C)] for _ in range(K)]
    if force_last:
        A[R - 1][K - 1] = 1
        B[K - 1][C - 1] = 1
    return A, B


@cocotb.test()
async def test_suite(dut):
    await start_clock(dut)
    os.makedirs(REPORTS, exist_ok=True)
    rng = random.Random(SEED)

    if SUITE == "traces":
        for n in range(200):
            K = rng.randint(1, 8)
            A, B = rand_ab(rng, R, C, K)
            final, got, expect_final, expect_flats = await run_array(dut, A, B, R, C, K)
            write_trace(TRACE_GOT, R, C, K, got)
            write_trace(TRACE_WANT, R, C, K, expect_flats)
            errs = compare(TRACE_GOT, TRACE_WANT)
            if errs or final != expect_final:
                raise AssertionError("traces n=%d K=%d %s final %s vs %s" % (n, K, errs, final, expect_final))

    elif SUITE == "random":
        for n in range(1000):
            K = rng.randint(1, 8)
            A, B = rand_ab(rng, R, C, K, force_last=False)
            final, got, _, _ = await run_array(dut, A, B, R, C, K)
            want = gemm_int8(A, B, R, C, K)
            if final != want:
                raise AssertionError("random n=%d K=%d got %s want %s" % (n, K, final, want))

    elif SUITE == "shapes":
        for K in (1, K_MAX):
            A, B = rand_ab(rng, R, C, K)
            final, got, expect_final, expect_flats = await run_array(dut, A, B, R, C, K)
            want = gemm_int8(A, B, R, C, K)
            if final != want or final != expect_final or got != expect_flats:
                raise AssertionError("shape %dx%d K=%d mismatch" % (R, C, K))
            if last_change(got) != K + R + C - 3:
                raise AssertionError(
                    "last_change %d want %d for %dx%d K=%d" % (last_change(got), K + R + C - 3, R, C, K)
                )

    elif SUITE == "stall":
        K = 4
        A, B = rand_ab(rng, R, C, K)
        nfeed = K + R + C - 2
        pat = []
        feeds = 0
        while feeds < nfeed:
            if rng.random() < 0.25 and feeds > 0:
                pat.append(True)
            else:
                pat.append(False)
                feeds += 1
        final, got, expect_final, expect_flats = await run_array(dut, A, B, R, C, K, stall_pattern=pat)
        want = gemm_int8(A, B, R, C, K)
        if final != want or got != expect_flats:
            raise AssertionError("stall mismatch")

    elif SUITE == "formula":
        K = 2
        A, B = rand_ab(rng, R, C, K)
        final, got, _, _ = await run_array(dut, A, B, R, C, K)
        if last_change(got) != K + R + C - 3:
            raise AssertionError("formula last_change %d want %d" % (last_change(got), K + R + C - 3))
        if len(got) != K + R + C - 2:
            raise AssertionError("formula length %d" % len(got))
        if final != gemm_int8(A, B, R, C, K):
            raise AssertionError("formula gemm")

    elif SUITE == "wavefront":
        K = 4
        A = [[1] * K for _ in range(R)]
        B = [[1] * C for _ in range(K)]
        final, got, _, expect_flats = await run_array(dut, A, B, R, C, K)
        if got != expect_flats:
            raise AssertionError("wavefront traces")
        lines = ["4x4 K=4 all-ones: PEs with acc delta this cycle"]
        prev = [0] * (R * C)
        for t, acc in enumerate(got):
            grid = []
            for i in range(R):
                row = []
                for j in range(C):
                    n = i * C + j
                    row.append("1" if acc[n] != prev[n] else ".")
                grid.append(" ".join(row))
            if t in (0, 4, 9):
                lines.append("t=%d" % t)
                lines.extend(grid)
                lines.append("")
            prev = acc
        with open(os.path.join(REPORTS, "wavefront.txt"), "w") as f:
            f.write("\n".join(lines) + "\n")
        if last_change(got) != 9:
            raise AssertionError("wavefront last_change %d" % last_change(got))
        if got[0][0] == 0:
            raise AssertionError("first update missing at t=0")

    elif SUITE == "catch":
        K = 3
        A = [[1, 2, 3], [4, 5, 6]]
        B = [[1, 0], [0, 1], [1, 1]]
        final, got, expect_final, expect_flats = await run_array(dut, A, B, 2, 2, K)
        write_trace(TRACE_GOT, 2, 2, K, got)
        write_trace(TRACE_WANT, 2, 2, K, expect_flats)
        errs = compare(TRACE_GOT, TRACE_WANT)
        if not errs:
            raise AssertionError("broken skew should mismatch traces")
        with open(os.path.join(REPORTS, "nonskew-caught.txt"), "w") as f:
            f.write("\n".join(errs) + "\n")

    elif SUITE == "golden":
        A = [[1, 2, 3], [4, 5, 6]]
        B = [[1, 0], [0, 1], [1, 1]]
        final, got, _, expect_flats = await run_array(dut, A, B, 2, 2, 3)
        write_trace(os.path.join(REPORTS, "golden-2x2-k3.dut.trace"), 2, 2, 3, got)
        write_trace(os.path.join(REPORTS, "golden-2x2-k3.model.trace"), 2, 2, 3, expect_flats)
        errs = compare(
            os.path.join(REPORTS, "golden-2x2-k3.dut.trace"),
            os.path.join(REPORTS, "golden-2x2-k3.model.trace"),
        )
        if errs or final != [[4, 5], [10, 11]]:
            raise AssertionError("golden %s %s" % (errs, final))

    else:
        raise AssertionError("unknown SUITE " + SUITE)
