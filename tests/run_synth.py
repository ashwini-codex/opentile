#!/usr/bin/env python3
"""Yosys cell counts for tile_top at 4x4 and 8x8."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports", "O9")
os.makedirs(REPORTS, exist_ok=True)


def yosys_script(R, C):
    return """
read_verilog -sv rtl/pe.sv rtl/array.sv rtl/tile_top.sv
chparam -set R %d -set C %d tile_top
hierarchy -top tile_top
synth -top tile_top
stat
stat -width
""" % (
        R,
        C,
    )


def parse_stat(txt):
    """Parse Yosys `stat -width` flattened 'design hierarchy' cell total."""
    cells = None
    types = {}
    collecting = False
    for line in txt.splitlines():
        m = re.match(r"\s+(\d+)\s+cells\s*$", line)
        if m:
            cells = int(m.group(1))
            types = {}
            collecting = True
            continue
        if collecting:
            tm = re.match(r"\s+(\d+)\s+(\S+)\s*$", line)
            if tm and tm.group(2).startswith("$_"):
                types[tm.group(2)] = int(tm.group(1))
                continue
            if tm and tm.group(2) == "submodules":
                collecting = False
                continue
            if line.startswith("===") or line.startswith("Warnings"):
                collecting = False
    dff = sum(v for k, v in types.items() if "DFF" in k.upper() or "FF" in k)
    return cells, dff, types


def run_one(R, C):
    logp = os.path.join(REPORTS, "synth-%dx%d.log" % (R, C))
    script = yosys_script(R, C)
    with open(logp, "w") as log:
        log.write(open(os.path.join(REPORTS, "versions.txt")).read())
        log.write("\n# yosys -p chparam R=%d C=%d; synth -top tile_top; stat\n" % (R, C))
        log.flush()
        p = subprocess.run(
            ["yosys", "-p", script],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    txt = open(logp, encoding="utf-8", errors="replace").read()
    cells, dff, types = parse_stat(txt)
    print("synth %dx%d cells=%s dff=%s rc=%s log=%s" % (R, C, cells, dff, p.returncode, logp))
    if p.returncode != 0 or cells is None:
        return None
    return dict(R=R, C=C, cells=cells, dff=dff, types=types, log=logp)


def main():
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            ["bash", "-lc", "date -u; yosys -V | head -1; verilator --version"],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    a = run_one(4, 4)
    b = run_one(8, 8)
    summary = os.path.join(REPORTS, "synth.log")
    with open(summary, "w") as f:
        f.write(open(ver).read() + "\n")
        if not a or not b:
            f.write("SYNTH FAIL\n")
            print("SYNTH FAIL")
            return 1
        ratio = b["cells"] / a["cells"]
        dff_ratio = (b["dff"] / a["dff"]) if a["dff"] else float("nan")
        f.write("4x4 cells=%d dff=%d\n" % (a["cells"], a["dff"]))
        f.write("8x8 cells=%d dff=%d\n" % (b["cells"], b["dff"]))
        f.write("ratio_cells=%.4f\n" % ratio)
        f.write("ratio_dff=%.4f\n" % dff_ratio)
        f.write("SYNTH OK\n")
        print("ratio_cells=%.4f ratio_dff=%.4f" % (ratio, dff_ratio))
        print("SYNTH OK")
    # Per-type dumps for the report
    for st, name in ((a, "4x4"), (b, "8x8")):
        with open(os.path.join(REPORTS, "cells-%s.txt" % name), "w") as f:
            f.write("cells=%d dff=%d\n" % (st["cells"], st["dff"]))
            for k in sorted(st["types"], key=lambda x: (-st["types"][x], x)):
                f.write("%s %d\n" % (k, st["types"][k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
