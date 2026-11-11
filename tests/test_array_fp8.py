"""cocotb E4M3 tests for rtl/array.sv (PARAM_FMT=E4M3)."""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from array_cycle import write_trace  # noqa: E402
from array_cycle_fp8 import ArrayModelE4M3  # noqa: E402
from ref_fp8 import CANON_NAN, gemm_e4m3  # noqa: E402
from trace_compare import compare  # noqa: E402

R = int(os.environ.get("PARAM_R") or "2")
C = int(os.environ.get("PARAM_C") or "2")
SUITE = os.environ.get("SUITE") or "fp8"
SEED = int(os.environ.get("SEED") or "1")
REPORTS = os.path.join(ROOT, "reports", "O14")
TRACE_GOT = os.environ.get("TRACE_GOT") or os.path.join(REPORTS, "e4m3.dut.trace")
TRACE_WANT = os.environ.get("TRACE_WANT") or os.path.join(REPORTS, "e4m3.model.trace")


def pack_vec(elems, width):
    v = 0
    for i, x in enumerate(elems):
        v |= (int(x) & ((1 << width) - 1)) << (width * i)
    return v


def unpack_u32(val, R, C):
    out = []
    iv = int(val)
    for n in range(R * C):
        out.append((iv >> (32 * n)) & 0xFFFFFFFF)
    return out


async def tick(dut):
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.clr.value = 1
    dut.en.value = 0
    dut.valid.value = 0
    dut.a_vec.value = 0
    dut.b_vec.value = 0
    await tick(dut)
    await tick(dut)


def drive(dut, a_vec, b_vec):
    dut.a_vec.value = pack_vec(a_vec, 8)
    dut.b_vec.value = pack_vec(b_vec, 8)


async def run_array_fp8(dut, A, B, R, C, K, stall_pattern=None):
    m = ArrayModelE4M3(R, C)
    expect_final, expect_tr = m.run(A, B, K, stall_pattern=stall_pattern)
    schedule = []
    for k in range(K):
        schedule.append(([A[i][k] for i in range(R)], [B[k][j] for j in range(C)], 1))
    z_a, z_b = [0] * R, [0] * C
    for _ in range(R + C - 2):
        schedule.append((z_a, z_b, 0))
    if stall_pattern is None:
        stall_pattern = [False] * len(schedule)
    dut.clr.value = 1
    dut.en.value = 0
    dut.valid.value = 0
    drive(dut, z_a, z_b)
    await tick(dut)
    dut.clr.value = 0
    idx = 0
    held_a, held_b, held_v = z_a, z_b, 0
    got_flats = []
    for stall in stall_pattern:
        if stall:
            dut.en.value = 0
            dut.valid.value = held_v
            drive(dut, held_a, held_b)
            await tick(dut)
        else:
            a_vec, b_vec, v = schedule[idx]
            idx += 1
            held_a, held_b, held_v = a_vec, b_vec, v
            dut.en.value = 1
            dut.valid.value = v
            drive(dut, a_vec, b_vec)
            await tick(dut)
            got_flats.append(unpack_u32(dut.acc_o.value, R, C))
    dut.en.value = 0
    await tick(dut)
    final_flat = unpack_u32(dut.acc_o.value, R, C)
    final = [final_flat[i * C : (i + 1) * C] for i in range(R)]
    return final, got_flats, expect_final, [rec["acc"] for rec in expect_tr if not rec["stalled"]]


def rand_ab(rng, R, C, K):
    A = [[rng.randrange(256) for _ in range(K)] for _ in range(R)]
    B = [[rng.randrange(256) for _ in range(C)] for _ in range(K)]
    return A, B


@cocotb.test()
async def test_suite(dut):
    await start_clock(dut)
    os.makedirs(REPORTS, exist_ok=True)
    rng = random.Random(SEED)

    if SUITE in ("fp8", "model"):
        for n in range(40):
            K = rng.randint(1, 8)
            A, B = rand_ab(rng, R, C, K)
            final, got, expect_final, expect_flats = await run_array_fp8(dut, A, B, R, C, K)
            want = gemm_e4m3(A, B, R, C, K)
            if final != want or final != expect_final or got != expect_flats:
                raise AssertionError(
                    "fp8 n=%d K=%d got %s want %s model %s"
                    % (n, K, [[hex(x) for x in r] for r in final],
                       [[hex(x) for x in r] for r in want],
                       [[hex(x) for x in r] for r in expect_final])
                )

    elif SUITE == "trace":
        A = [[0x38, 0x38, 0x38], [0x38, 0x38, 0x38]]
        B = [[0x38, 0x38], [0x38, 0x38], [0x38, 0x38]]
        final, got, _, expect_flats = await run_array_fp8(dut, A, B, 2, 2, 3)
        write_trace(TRACE_GOT, 2, 2, 3, got)
        write_trace(TRACE_WANT, 2, 2, 3, expect_flats)
        errs = compare(TRACE_GOT, TRACE_WANT)
        want = gemm_e4m3(A, B, 2, 2, 3)
        if errs or final != want:
            raise AssertionError("e4m3 trace %s final %s want %s" % (errs, final, want))

    elif SUITE == "nan":
        A = [[0x38, 0x7F], [0x00, 0x38]]
        B = [[0x38, 0x38], [0x38, 0x01]]
        final, _, _, _ = await run_array_fp8(dut, A, B, 2, 2, 2)
        want = gemm_e4m3(A, B, 2, 2, 2)
        if final != want:
            raise AssertionError("nan array %s vs %s" % (final, want))
        if final[0][0] != CANON_NAN:
            raise AssertionError("C00 should be NaN got %08x" % final[0][0])

    elif SUITE == "neg0":
        # All K products −0 at every PE: +0 × −1, twice.
        A = [[0x00, 0x00], [0x00, 0x00]]
        B = [[0xB8, 0xB8], [0xB8, 0xB8]]
        final, _, _, _ = await run_array_fp8(dut, A, B, 2, 2, 2)
        want = gemm_e4m3(A, B, 2, 2, 2)
        if final != want:
            raise AssertionError("neg0 %s vs %s" % (final, want))
        if any(x != 0x80000000 for row in final for x in row):
            raise AssertionError("expected all −0, got %s" % final)

    else:
        raise AssertionError("unknown SUITE " + SUITE)
