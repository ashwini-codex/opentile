#!/usr/bin/env python3
"""E4M3 PE/array cocotb + Yosys cell counts. INT8 runners stay in run_pe/run_array."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PE = os.path.join(ROOT, "tests", "pe")
ARRAY = os.path.join(ROOT, "tests", "array")
REPORTS = os.path.join(ROOT, "reports", "O14")
os.makedirs(REPORTS, exist_ok=True)


def tests_ok(xml_path):
    if not os.path.isfile(xml_path):
        return False
    txt = open(xml_path, encoding="utf-8").read()
    if "<failure" in txt or "<error" in txt:
        return False
    return "<testcase" in txt


def run(label, cwd, env, log_name, expect_pass):
    e = os.environ.copy()
    e.update(env)
    e.setdefault("SIM", "verilator")
    xmlp = os.path.join(REPORTS, log_name.replace(".log", ".xml"))
    e["COCOTB_RESULTS_FILE"] = xmlp
    logp = os.path.join(REPORTS, log_name)
    print("RUN", label, "expect", "PASS" if expect_pass else "FAIL")
    with open(logp, "w") as log:
        log.write("label=%s expect_pass=%s\n" % (label, expect_pass))
        log.flush()
        p = subprocess.run(
            ["make", "-C", cwd], env=e, cwd=cwd, stdout=log, stderr=subprocess.STDOUT
        )
    ok = (p.returncode == 0) and tests_ok(xmlp)
    print("  ->", "PASS" if ok else "FAIL", "make_rc", p.returncode, "log", logp)
    if expect_pass and not ok:
        print("ERROR: %s should have passed" % label)
        return 1
    if (not expect_pass) and ok:
        print("ERROR: %s should have failed" % label)
        return 1
    return 0


def synth_pe(fmt, log_name):
    logp = os.path.join(REPORTS, log_name)
    if fmt == "E4M3":
        script = (
            "read_verilog -sv rtl/pe.sv\n"
            "chparam -set FMT 1161055539 pe\n"
            "hierarchy -top pe\n"
            "synth -top pe\n"
            "stat\n"
            "stat -width\n"
        )
    else:
        script = (
            "read_verilog -sv rtl/pe.sv\n"
            "hierarchy -top pe\n"
            "synth -top pe\n"
            "stat\n"
            "stat -width\n"
        )
    with open(logp, "w") as log:
        p = subprocess.run(
            ["yosys", "-p", script],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    txt = open(logp, encoding="utf-8", errors="replace").read()
    cells = None
    for line in txt.splitlines():
        m = re.match(r"\s+(\d+)\s+cells\s*$", line)
        if m:
            cells = int(m.group(1))
    print("synth FMT=%s cells=%s rc=%s log=%s" % (fmt, cells, p.returncode, logp))
    if p.returncode != 0 or cells is None:
        return None
    return cells


def main():
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            [
                "bash",
                "-lc",
                "date -u; verilator --version; yosys -V | head -1; "
                "python3 -c 'import cocotb; print(\"cocotb\", cocotb.__version__)'",
            ],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    summary = os.path.join(REPORTS, "fp8-rtl.log")
    with open(summary, "w") as f:
        f.write(open(ver).read() + "\n")
    rc = 0
    rc |= run(
        "e4m3 pe all",
        PE,
        dict(
            DUT=os.path.join(ROOT, "rtl", "pe.sv"),
            SUITE="all",
            PARAM_FMT="E4M3",
            SEED="1",
            SIM_BUILD="sim_build/pe_e4m3",
            WAVES="0",
        ),
        "pe-e4m3.log",
        True,
    )
    rc |= run(
        "e4m3 pe tie-up (must fail)",
        PE,
        dict(
            DUT=os.path.join(ROOT, "rtl", "pe.sv"),
            SUITE="fp8_tie",
            PARAM_FMT="E4M3",
            TIE_UP="1",
            SEED="1",
            SIM_BUILD="sim_build/pe_e4m3_tieup",
            WAVES="0",
        ),
        "tie-up-caught.log",
        False,
    )
    rc |= run(
        "e4m3 array 2x2 model",
        ARRAY,
        dict(
            DUT=os.path.join(ROOT, "rtl", "array.sv"),
            MODULE="test_array_fp8",
            PARAM_R="2",
            PARAM_C="2",
            PARAM_FMT="E4M3",
            SUITE="model",
            SEED="3",
            SIM_BUILD="sim_build/a2x2_e4m3",
            WAVES="0",
        ),
        "array-2x2-model.log",
        True,
    )
    rc |= run(
        "e4m3 array 4x4 model",
        ARRAY,
        dict(
            DUT=os.path.join(ROOT, "rtl", "array.sv"),
            MODULE="test_array_fp8",
            PARAM_R="4",
            PARAM_C="4",
            PARAM_FMT="E4M3",
            SUITE="model",
            SEED="4",
            SIM_BUILD="sim_build/a4x4_e4m3",
            WAVES="0",
        ),
        "array-4x4-model.log",
        True,
    )
    rc |= run(
        "e4m3 array 2x2 trace",
        ARRAY,
        dict(
            DUT=os.path.join(ROOT, "rtl", "array.sv"),
            MODULE="test_array_fp8",
            PARAM_R="2",
            PARAM_C="2",
            PARAM_FMT="E4M3",
            SUITE="trace",
            SEED="1",
            SIM_BUILD="sim_build/a2x2_e4m3",
            WAVES="0",
            TRACE_GOT=os.path.join(REPORTS, "e4m3-2x2-k3.dut.trace"),
            TRACE_WANT=os.path.join(REPORTS, "e4m3-2x2-k3.model.trace"),
        ),
        "array-trace.log",
        True,
    )
    rc |= run(
        "e4m3 array nan",
        ARRAY,
        dict(
            DUT=os.path.join(ROOT, "rtl", "array.sv"),
            MODULE="test_array_fp8",
            PARAM_R="2",
            PARAM_C="2",
            PARAM_FMT="E4M3",
            SUITE="nan",
            SEED="1",
            SIM_BUILD="sim_build/a2x2_e4m3",
            WAVES="0",
        ),
        "array-nan.log",
        True,
    )
    rc |= run(
        "e4m3 array neg0",
        ARRAY,
        dict(
            DUT=os.path.join(ROOT, "rtl", "array.sv"),
            MODULE="test_array_fp8",
            PARAM_R="2",
            PARAM_C="2",
            PARAM_FMT="E4M3",
            SUITE="neg0",
            SEED="1",
            SIM_BUILD="sim_build/a2x2_e4m3",
            WAVES="0",
        ),
        "array-neg0.log",
        True,
    )
    c_int8 = synth_pe("INT8", "pe-synth-int8.log")
    c_e4m3 = synth_pe("E4M3", "pe-synth-e4m3.log")
    with open(os.path.join(REPORTS, "cells.txt"), "w") as f:
        f.write("int8_pe_cells=%s\n" % c_int8)
        f.write("e4m3_pe_cells=%s\n" % c_e4m3)
        if c_int8 and c_e4m3:
            f.write("ratio=%.3f\n" % (c_e4m3 / float(c_int8)))
    if c_int8 is None or c_e4m3 is None:
        print("ERROR: PE synth cell parse failed")
        rc |= 1
    with open(summary, "a") as f:
        f.write("int8_pe_cells=%s e4m3_pe_cells=%s\n" % (c_int8, c_e4m3))
        f.write("exit_rc=%d\n" % rc)
        f.write("FP8-RTL OK\n" if rc == 0 else "FP8-RTL FAIL\n")
    if rc == 0:
        print("FP8-RTL OK")
    return rc


if __name__ == "__main__":
    sys.exit(main())
