"""E4M3 functional bins. Classification only; DUT checks live elsewhere."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model", "python"))
from ref_fp8 import product_e4m3  # noqa: E402

REQUIRED = [
    "fp8_zero",
    "fp8_subnormal",
    "fp8_normal",
    "fp8_max",
    "fp8_nan",
    "fp8_mixed_signs",
    "fp8_cancel",
]


def class_of(code):
    c = int(code) & 0xFF
    e, m = (c >> 3) & 15, c & 7
    if e == 15 and m == 7:
        return "nan"
    if e == 0 and m == 0:
        return "zero"
    if e == 0:
        return "subnormal"
    if e == 15 and m == 6:
        return "max"
    return "normal"


def record_pairs(bins, pairs, result_bits):
    """pairs: list of (a,b) E4M3 codes for one C element. result_bits: FP32 bits."""
    bins = set(bins)
    kinds = []
    n_nonzero = 0
    for a, b in pairs:
        ca, cb = class_of(a), class_of(b)
        for k in (ca, cb):
            if k == "zero":
                bins.add("fp8_zero")
            elif k == "subnormal":
                bins.add("fp8_subnormal")
            elif k == "normal":
                bins.add("fp8_normal")
            elif k == "max":
                bins.add("fp8_max")
            elif k == "nan":
                bins.add("fp8_nan")
        kinds.append((ca, cb))
        p = product_e4m3(a, b)
        if p[0] == "num":
            n_nonzero += 1
            if p[1] < 0:
                bins.add("fp8_mixed_signs")
        elif p[0] == "zero" and p[1]:
            bins.add("fp8_mixed_signs")
    if (
        len(pairs) >= 2
        and (int(result_bits) & 0xFFFFFFFF) == 0
        and n_nonzero >= 2
    ):
        bins.add("fp8_cancel")
    return bins


def dump(path, bins, extra=None):
    lines = ["coverage fp8"]
    if extra:
        lines.append(extra)
    for b in REQUIRED:
        lines.append("%s %s" % (b, "HIT" if b in bins else "MISS"))
    for b in sorted(bins):
        if b not in REQUIRED:
            lines.append(b)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
