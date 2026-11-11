"""Python E4M3 GEMM: Fraction decode and product, then integer ulp accumulation.

Independent of the C++ model (no shared ulp-9 tables; C++ uses significand shifts).
"""
from fractions import Fraction

CANON_NAN = 0x7FC00000
ULP = Fraction(1, 1 << 18)


def decode_e4m3(code):
    """('nan', 0) | ('zero', sign) | ('num', Fraction signed). sign is 0 or 1."""
    c = int(code) & 0xFF
    s, e, m = (c >> 7) & 1, (c >> 3) & 15, c & 7
    if e == 15 and m == 7:
        return ("nan", 0)
    if e == 0 and m == 0:
        return ("zero", s)
    if e == 0:
        mag = Fraction(m, 8) * (Fraction(2) ** -6)
    else:
        mag = (1 + Fraction(m, 8)) * (Fraction(2) ** (e - 7))
    return ("num", -mag if s else mag)


def product_e4m3(ca, cb):
    """('nan',) | ('zero', sign) | ('num', Fraction)."""
    ka, va = decode_e4m3(ca)
    kb, vb = decode_e4m3(cb)
    if ka == "nan" or kb == "nan":
        return ("nan", 0)
    sa = va if ka == "zero" else (1 if va < 0 else 0)
    sb = vb if kb == "zero" else (1 if vb < 0 else 0)
    if ka == "zero" or kb == "zero":
        return ("zero", sa ^ sb)
    return ("num", va * vb)


def _rne_bits(n, all_neg0, tie="rne"):
    """n is signed integer, value = n * 2^{-18}. tie: rne | up."""
    if n == 0:
        return 0x80000000 if all_neg0 else 0
    sign = 1 if n < 0 else 0
    m = abs(int(n))
    e2 = m.bit_length() - 1
    bexp = (e2 - 18) + 127
    if e2 <= 23:
        sig24 = m << (23 - e2)
        return (sign << 31) | (bexp << 23) | (sig24 & 0x7FFFFF)
    shift = e2 - 23
    sig24 = m >> shift
    rest = m & ((1 << shift) - 1)
    round_bit = (rest >> (shift - 1)) & 1
    sticky = (rest & ((1 << (shift - 1)) - 1)) != 0
    bump = False
    if tie == "up":
        bump = bool(round_bit)
    else:
        bump = bool(round_bit) and (sticky or (sig24 & 1))
    if bump:
        sig24 += 1
        if sig24 == (1 << 24):
            sig24 = 1 << 23
            bexp += 1
    return (sign << 31) | (bexp << 23) | (sig24 & 0x7FFFFF)


def gemm_e4m3(A, B, R, C, K, tie="rne"):
    """A,B: lists of E4M3 codes 0..255. Returns R×C list of FP32 bit-patterns as int."""
    if R < 1 or C < 1 or K < 1:
        raise ValueError("R, C, K must be >= 1")
    out = []
    for i in range(R):
        row = []
        for j in range(C):
            acc = Fraction(0)
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
                    acc += p[1]
            if poison:
                row.append(CANON_NAN)
                continue
            q = acc / ULP
            if q.denominator != 1:
                raise ValueError("sum is not a 2^-18 multiple")
            n = q.numerator
            all_neg0 = n == 0 and n_neg0 == n_prod
            row.append(_rne_bits(n, all_neg0, tie=tie))
        out.append(row)
    return out
