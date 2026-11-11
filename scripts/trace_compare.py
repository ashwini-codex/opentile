#!/usr/bin/env python3
"""Compare two opentile-trace files. Exit 0 iff headers and all acc rows match."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
from array_cycle import parse_trace  # noqa: E402


def compare(path_a, path_b):
    ha, ra = parse_trace(path_a)
    hb, rb = parse_trace(path_b)
    errs = []
    if ha != hb:
        errs.append("header mismatch: %r vs %r" % (ha, hb))
    if len(ra) != len(rb):
        errs.append("length %d vs %d" % (len(ra), len(rb)))
    n = min(len(ra), len(rb))
    for i in range(n):
        t1, a1 = ra[i]
        t2, a2 = rb[i]
        if t1 != t2 or a1 != a2:
            errs.append("first differ at file index %d: t=%s acc=%s vs t=%s acc=%s" % (i, t1, a1, t2, a2))
            break
    return errs


def main():
    if len(sys.argv) != 3:
        print("usage: trace_compare.py <got.trace> <want.trace>", file=sys.stderr)
        return 2
    errs = compare(sys.argv[1], sys.argv[2])
    if errs:
        print("TRACE MISMATCH")
        for e in errs:
            print(" ", e)
        return 1
    print("TRACE MATCH")
    return 0


if __name__ == "__main__":
    sys.exit(main())
