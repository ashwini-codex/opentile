#!/usr/bin/env python3
"""Functional bins + Verilator line/toggle + formal cover copy."""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
REPORTS = os.path.join(ROOT, "reports", "O10")
os.makedirs(REPORTS, exist_ok=True)
RTL = os.path.join(ROOT, "rtl")
GOOD = " ".join([os.path.join(RTL, "tile_top.sv"), os.path.join(RTL, "array.sv"), os.path.join(RTL, "pe.sv")])


def tests_ok(xml_path):
    if not os.path.isfile(xml_path):
        return False
    txt = open(xml_path, encoding="utf-8").read()
    if "<failure" in txt or "<error" in txt:
        return False
    return "<testcase" in txt


def run_make(env, log_name):
    e = os.environ.copy()
    e.update(env)
    e["PYTHONPATH"] = TESTS + os.pathsep + os.path.join(ROOT, "model", "python")
    e.setdefault("SIM", "verilator")
    xmlp = os.path.join(REPORTS, log_name.replace(".log", ".xml"))
    e["COCOTB_RESULTS_FILE"] = xmlp
    logp = os.path.join(REPORTS, log_name)
    with open(logp, "w") as log:
        p = subprocess.run(["make", "-C", TESTS], env=e, cwd=TESTS, stdout=log, stderr=subprocess.STDOUT)
    ok = (p.returncode == 0) and tests_ok(xmlp)
    print("coverage run", log_name, "PASS" if ok else "FAIL")
    return ok, logp


def load_bins(path):
    bins = set()
    if not os.path.isfile(path):
        return bins
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("coverage"):
            continue
        bins.add(line)
    return bins


def main():
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            [
                "bash",
                "-lc",
                "date -u; verilator --version; sby --version 2>/dev/null | head -1; "
                "python3 -c 'import cocotb; print(\"cocotb\", cocotb.__version__)'",
            ],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    rc = 0
    ok, _ = run_make(
        dict(
            DUT=os.path.join(RTL, "tile_top.sv"),
            VERILOG_SOURCES=GOOD,
            MODULE="test_coverage",
            PARAM_R="2",
            PARAM_C="2",
            K_MAX="64",
            SUITE="cov",
            BP="always",
            SEED="1",
            VL_COVERAGE="1",
            SIM_BUILD="sim_build/cov_2x2",
        ),
        "cov-2x2.log",
    )
    if not ok:
        rc |= 1
    bins = set()
    bins |= load_bins(os.path.join(REPORTS, "functional-2x2.txt"))
    for p in glob.glob(os.path.join(ROOT, "reports", "O5", "coverage_*.txt")):
        bins |= load_bins(p)
    required = [
        ln.strip()
        for ln in open(os.path.join(ROOT, "scripts", "required_bins.txt"), encoding="utf-8")
        if ln.strip() and not ln.startswith("#")
    ]
    missing = [b for b in required if b not in bins]
    with open(os.path.join(REPORTS, "functional-union.txt"), "w") as f:
        f.write("bins %d required %d missing %d\n" % (len(bins), len(required), len(missing)))
        for b in sorted(bins):
            f.write(b + "\n")
        if missing:
            f.write("--- missing ---\n")
            for b in missing:
                f.write(b + "\n")
            rc |= 1
    # Verilator writes coverage.dat in the make CWD (tests/), not SIM_BUILD.
    cov_dat = []
    for pat in (
        os.path.join(TESTS, "coverage.dat"),
        os.path.join(TESTS, "sim_build", "cov_2x2", "coverage.dat"),
    ):
        if os.path.isfile(pat):
            cov_dat.append(pat)
    cov_dat += glob.glob(os.path.join(TESTS, "sim_build", "**", "coverage.dat"), recursive=True)
    cov_dat = sorted(set(cov_dat))
    vlog = os.path.join(REPORTS, "verilator-coverage.log")
    with open(vlog, "w") as f:
        f.write(open(ver).read() + "\n")
        if not cov_dat:
            f.write("NO_COVERAGE_DAT\n")
            found = glob.glob(os.path.join(TESTS, "sim_build/cov_2x2/**/*"), recursive=True)
            f.write("sim_build files %d\n" % len(found))
            for p in found[:40]:
                f.write(p + "\n")
            rc |= 1
        else:
            saved = os.path.join(REPORTS, "coverage.dat")
            shutil.copy(cov_dat[0], saved)
            anno = os.path.join(REPORTS, "anno")
            os.makedirs(anno, exist_ok=True)
            cmd = ["verilator_coverage", "--annotate", anno] + cov_dat
            f.write("CMD %s\n" % " ".join(cmd))
            p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
            if p.returncode != 0:
                rc |= 1
    # Formal cover copy
    for src, dst in (
        (os.path.join(ROOT, "reports", "O6", "formal.log"), os.path.join(REPORTS, "formal-pe.log")),
        (os.path.join(ROOT, "reports", "O8", "formal.log"), os.path.join(REPORTS, "formal-tile.log")),
    ):
        if os.path.isfile(src):
            shutil.copy(src, dst)
    with open(os.path.join(REPORTS, "coverage.log"), "w") as f:
        f.write(open(ver).read() + "\n")
        f.write("missing_bins=%d\n" % len(missing))
        f.write("COVERAGE OK\n" if rc == 0 else "COVERAGE FAIL\n")
    print("COVERAGE", "OK" if rc == 0 else "FAIL", "missing", missing)
    return rc


if __name__ == "__main__":
    sys.exit(main())
