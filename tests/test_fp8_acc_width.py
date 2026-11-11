"""40-bit acc wrap disagrees with the spec 43-bit acc."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model", "python"))
from ref_fp8 import ULP, _rne_bits, product_e4m3  # noqa: E402


def wrap_signed(n, bits):
    mod = 1 << bits
    y = int(n) % mod
    if y >= (1 << (bits - 1)):
        y -= mod
    return y


def gemm_wrap(A, B, R, C, K, bits):
    out = []
    for i in range(R):
        row = []
        for j in range(C):
            acc = 0
            poison = False
            n_prod = 0
            n_neg0 = 0
            for k in range(K):
                p = product_e4m3(A[i][k], B[k][j])
                n_prod += 1
                if p[0] == "nan":
                    poison = True
                    break
                if p[0] == "zero":
                    if p[1]:
                        n_neg0 += 1
                else:
                    acc += int(p[1] / ULP)
                    acc = wrap_signed(acc, bits)
            if poison:
                row.append(0x7FC00000)
                continue
            all_neg0 = acc == 0 and n_neg0 == n_prod
            row.append(_rne_bits(acc, all_neg0))
        out.append(row)
    return out


# K=11 of 448²: 43-bit value vs signed-40 wrap (values, not ulps).
PRED_43_VAL = 2207744
PRED_40_VAL = -1986560


def test_k11_max_40bit_disagrees():
    A = [[0x7E] * 11]
    B = [[0x7E] for _ in range(11)]
    c43 = gemm_wrap(A, B, 1, 1, 11, 43)[0][0]
    c40 = gemm_wrap(A, B, 1, 1, 11, 40)[0][0]
    n43 = wrap_signed(11 * 196 * (1 << 28), 43)
    n40 = wrap_signed(11 * 196 * (1 << 28), 40)
    assert n43 == PRED_43_VAL << 18, n43
    assert n40 == PRED_40_VAL << 18, n40
    assert c43 != c40
    assert c43 == _rne_bits(n43, False)
    assert c40 == _rne_bits(n40, False)


def test_k1_max_fits_40bit():
    A = [[0x7E]]
    B = [[0x7E]]
    assert gemm_wrap(A, B, 1, 1, 1, 43) == gemm_wrap(A, B, 1, 1, 1, 40)
