"""Cycle-accurate array model vs GEMM, golden trace, stalls, no-skew fail."""
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
from array_cycle import ArrayModel, parse_trace, write_trace  # noqa: E402
from ref import gemm_int8  # noqa: E402

GOLDEN_A = [[1, 2, 3], [4, 5, 6]]
GOLDEN_B = [[1, 0], [0, 1], [1, 1]]
GOLDEN_TRACE = [
    [1, 0, 0, 0],
    [1, 0, 4, 0],
    [4, 2, 4, 0],
    [4, 5, 10, 5],
    [4, 5, 10, 11],
]


def last_change(traces):
    last = -1
    prev = None
    for rec in traces:
        if rec["stalled"]:
            continue
        if prev is None or rec["acc"] != prev:
            last = rec["t"]
        prev = rec["acc"]
    return last


def test_golden_2x2_k3_cycle_for_cycle():
    m = ArrayModel(2, 2)
    final, traces = m.run(GOLDEN_A, GOLDEN_B, 3)
    assert [rec["acc"] for rec in traces] == GOLDEN_TRACE
    assert final == [[4, 5], [10, 11]]
    assert last_change(traces) == 3 + 2 + 2 - 3
    assert len(traces) == 3 + 2 + 2 - 2
    path = os.path.join(ROOT, "reports", "O4", "golden-2x2-k3.trace")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_trace(path, 2, 2, 3, [rec["acc"] for rec in traces])
    header, rows = parse_trace(path)
    assert header == "# opentile-trace R=2 C=2 K=3"
    assert [acc for _, acc in rows] == GOLDEN_TRACE


def test_4x4_k4_length_10():
    rng = random.Random(4)
    R = C = K = 4
    A = [[rng.randint(-8, 8) for _ in range(K)] for _ in range(R)]
    B = [[rng.randint(-8, 8) for _ in range(C)] for _ in range(K)]
    A[R - 1][K - 1] = 1
    B[K - 1][C - 1] = 1
    m = ArrayModel(R, C)
    final, traces = m.run(A, B, K)
    assert len(traces) == 10
    assert last_change(traces) == 9
    assert final == gemm_int8(A, B, R, C, K)


def test_final_equals_gemm_10000():
    rng = random.Random(40)
    for n in range(10000):
        R = rng.randint(1, 8)
        C = rng.randint(1, 8)
        K = rng.randint(1, 16)
        A = [[rng.randint(-128, 127) for _ in range(K)] for _ in range(R)]
        B = [[rng.randint(-128, 127) for _ in range(C)] for _ in range(K)]
        final, traces = ArrayModel(R, C).run(A, B, K)
        assert final == gemm_int8(A, B, R, C, K), (R, C, K, n)


def test_last_change_exhaustive():
    rng = random.Random(1)
    for R in range(1, 9):
        for C in range(1, 9):
            for K in range(1, 17):
                A = [[rng.randint(1, 5) for _ in range(K)] for _ in range(R)]
                B = [[rng.randint(1, 5) for _ in range(C)] for _ in range(K)]
                A[R - 1][K - 1] = 1
                B[K - 1][C - 1] = 1
                _, traces = ArrayModel(R, C).run(A, B, K)
                assert last_change(traces) == K + R + C - 3, (R, C, K)


def test_stall_insensitivity():
    rng = random.Random(9)
    for n in range(200):
        R = rng.randint(1, 4)
        C = rng.randint(1, 4)
        K = rng.randint(1, 8)
        A = [[rng.randint(-20, 20) for _ in range(K)] for _ in range(R)]
        B = [[rng.randint(-20, 20) for _ in range(C)] for _ in range(K)]
        T = K + R + C - 2
        base_final, base_tr = ArrayModel(R, C).run(A, B, K)
        pattern = []
        for _ in range(T):
            for _s in range(rng.randint(0, 3)):
                pattern.append(True)
            pattern.append(False)
        stalled_final, stalled_tr = ArrayModel(R, C).run(A, B, K, stall_pattern=pattern)
        assert stalled_final == base_final
        live = [rec["acc"] for rec in stalled_tr if not rec["stalled"]]
        assert live == [rec["acc"] for rec in base_tr]


def test_no_skew_caught():
    m = ArrayModel(2, 2, skew=False)
    final, traces = m.run(GOLDEN_A, GOLDEN_B, 3)
    accs = [rec["acc"] for rec in traces]
    assert accs != GOLDEN_TRACE
    assert final != [[4, 5], [10, 11]] or accs != GOLDEN_TRACE


def test_o1_3x3_trace_written():
    A = [[1, 0, 2], [3, 1, 0], [0, 2, 1]]
    B = [[1, 0, 1], [0, 1, 0], [1, 0, 1]]
    m = ArrayModel(3, 3)
    final, traces = m.run(A, B, 3)
    assert final == [[3, 0, 3], [3, 1, 3], [1, 2, 1]]
    path = os.path.join(ROOT, "reports", "O4", "o1-3x3.trace")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_trace(path, 3, 3, 3, [rec["acc"] for rec in traces])
    expect = [
        [1, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 3, 0, 0, 0, 0, 0],
        [3, 0, 1, 3, 0, 0, 0, 0, 0],
        [3, 0, 1, 3, 1, 3, 0, 0, 0],
        [3, 0, 3, 3, 1, 3, 1, 2, 0],
        [3, 0, 3, 3, 1, 3, 1, 2, 0],
        [3, 0, 3, 3, 1, 3, 1, 2, 1],
    ]
    assert [rec["acc"] for rec in traces] == expect
