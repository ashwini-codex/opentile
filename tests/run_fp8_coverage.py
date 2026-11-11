#!/usr/bin/env python3
"""E4M3 functional bins. K=1 pass must miss cancel; full pass hits all 7."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PE = os.path.join(ROOT, "tests", "pe")
REPORTS = os.path.join(ROOT, "reports", "O15")
os.makedirs(REPORTS, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fp8_bins import REQUIRED  # noqa: E402


def tests_ok(xml_path):
    if not os.path.isfile(xml_path):
        return False
    txt = open(xml_path, encoding="utf-8").read()
    if "<failure" in txt or "<error" in txt:
        return False
    return "<testcase" in txt


def load_hits(path):
    hits = set()
    if not os.path.isfile(path):
        return hits
    for line in open(path, encoding="utf-8"):
        parts = line.split()
        if len(parts) == 2 and parts[1] == "HIT":
            hits.add(parts[0])
    return hits


def main():
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            ["bash", "-lc", "date -u; verilator --version"],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    env = os.environ.copy()
    env.update(
        SIM="verilator",
        DUT=os.path.join(ROOT, "rtl", "pe.sv"),
        PARAM_FMT="E4M3",
        SUITE="fp8_cov",
        SEED="1",
        SIM_BUILD="sim_build/pe_e4m3_cov",
        WAVES="0",
        COCOTB_RESULTS_FILE=os.path.join(REPORTS, "fp8-cov.xml"),
    )
    logp = os.path.join(REPORTS, "fp8-cov.log")
    with open(logp, "w") as log:
        log.write(open(ver).read() + "\n")
        p = subprocess.run(
            ["make", "-C", PE], env=env, cwd=PE, stdout=log, stderr=subprocess.STDOUT
        )
    k1 = load_hits(os.path.join(REPORTS, "bins-k1.txt"))
    full = load_hits(os.path.join(REPORTS, "functional-fp8.txt"))
    miss_k1 = [b for b in REQUIRED if b not in k1]
    miss_full = [b for b in REQUIRED if b not in full]
    ok = (p.returncode == 0) and tests_ok(env["COCOTB_RESULTS_FILE"])
    gap = "fp8_cancel" in miss_k1 and "fp8_cancel" not in miss_full
    rc = 0
    if not ok:
        rc |= 1
    if miss_full:
        rc |= 1
    if not gap:
        rc |= 1
    with open(os.path.join(REPORTS, "coverage.log"), "w") as f:
        f.write(open(ver).read() + "\n")
        f.write("k1_hits=%s miss=%s\n" % (sorted(k1), miss_k1))
        f.write("full_hits=%s miss=%s\n" % (sorted(full), miss_full))
        f.write("cancel_gap_from_k1=%s\n" % gap)
        f.write("FP8-COVERAGE OK\n" if rc == 0 else "FP8-COVERAGE FAIL\n")
    print("FP8-COVERAGE", "OK" if rc == 0 else "FAIL", "k1_miss", miss_k1, "full_miss", miss_full)
    return rc


if __name__ == "__main__":
    sys.exit(main())
