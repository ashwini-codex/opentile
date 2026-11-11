#!/usr/bin/env python3
"""Size regression: tile testbench vs real tile_top at SIZES (default 2 4 8)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
REPORTS = os.path.join(ROOT, "reports", "O9")
os.makedirs(REPORTS, exist_ok=True)

RTL = os.path.join(ROOT, "rtl")
GOOD = " ".join(
    [os.path.join(RTL, "tile_top.sv"), os.path.join(RTL, "array.sv"), os.path.join(RTL, "pe.sv")]
)
MAKE = ["make", "-C", TESTS]


def tests_ok(xml_path):
    if not os.path.isfile(xml_path):
        return False
    txt = open(xml_path, encoding="utf-8").read()
    if "<failure" in txt or "<error" in txt:
        return False
    return "<testcase" in txt


def sources(dut_sv):
    return " ".join([dut_sv, os.path.join(RTL, "array.sv"), os.path.join(RTL, "pe.sv")])


def run(label, env, log_name, expect_pass):
    e = os.environ.copy()
    e.update(env)
    e["PYTHONPATH"] = TESTS + os.pathsep + os.path.join(ROOT, "model", "python") + (
        os.pathsep + e["PYTHONPATH"] if e.get("PYTHONPATH") else ""
    )
    e.setdefault("COCOTB_LOG_LEVEL", "INFO")
    e.setdefault("SIM", "verilator")
    xmlp = os.path.join(REPORTS, log_name.replace(".log", ".xml"))
    e["COCOTB_RESULTS_FILE"] = xmlp
    logp = os.path.join(REPORTS, log_name)
    print("RUN", label, "expect", "PASS" if expect_pass else "FAIL")
    with open(logp, "w") as log:
        log.write("label=%s expect_pass=%s\n" % (label, expect_pass))
        log.flush()
        p = subprocess.run(MAKE, env=e, cwd=TESTS, stdout=log, stderr=subprocess.STDOUT)
    ok = (p.returncode == 0) and tests_ok(xmlp)
    line = "  -> %s make_rc %s log %s" % ("PASS" if ok else "FAIL", p.returncode, logp)
    print(line)
    with open(os.path.join(REPORTS, "sizes.log"), "a") as f:
        f.write("RUN %s expect %s\n%s\n" % (label, "PASS" if expect_pass else "FAIL", line))
    if expect_pass and not ok:
        print("ERROR: %s should have passed" % label)
        return 1
    if (not expect_pass) and ok:
        print("ERROR: %s should have failed" % label)
        return 1
    return 0


def rtl(suite, R, C, extra=None):
    env = dict(
        DUT=os.path.join(RTL, "tile_top.sv"),
        VERILOG_SOURCES=GOOD,
        MODULE="test_tile" if suite != "latency" else "test_tile_rtl",
        PARAM_R=str(R),
        PARAM_C=str(C),
        K_MAX="64",
        SUITE=suite,
        BP="always",
        SEED="1",
        SIM_BUILD="sim_build/sz_%s_%dx%d" % (suite, R, C),
    )
    if extra:
        env.update(extra)
    return env


def main():
    sizes = [int(x) for x in (os.environ.get("SIZES") or "2 4 8").split()]
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            [
                "bash",
                "-lc",
                "date -u; verilator --version; python3 -c 'import cocotb; print(\"cocotb\", cocotb.__version__)'",
            ],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    with open(os.path.join(REPORTS, "sizes.log"), "w") as f:
        f.write(open(ver).read() + "\n")
        f.write("SIZES=%s\n" % sizes)
    rc = 0
    for n in sizes:
        rc |= run(
            "rtl random %dx%d" % (n, n),
            rtl("random", n, n),
            "size-%d-random.log" % n,
            True,
        )
        rc |= run(
            "rtl latency %dx%d" % (n, n),
            rtl("latency", n, n, extra={"MODULE": "test_tile_rtl", "SUITE": "latency"}),
            "size-%d-latency.log" % n,
            True,
        )
    early = os.path.join(RTL, "variants", "tile_early_read.sv")
    rc |= run(
        "early_read 8x8 caught",
        dict(
            DUT=early,
            VERILOG_SOURCES=sources(early),
            MODULE="test_tile",
            PARAM_R="8",
            PARAM_C="8",
            K_MAX="64",
            SUITE="random",
            BP="always",
            SEED="1",
            SIM_BUILD="sim_build/sz_early_8x8",
        ),
        "size-8-early-caught.log",
        False,
    )
    with open(os.path.join(REPORTS, "sizes.log"), "a") as f:
        f.write("exit_rc=%d\n" % rc)
        f.write("SIZES OK\n" if rc == 0 else "SIZES FAIL\n")
    if rc == 0:
        print("SIZES OK")
    return rc


if __name__ == "__main__":
    sys.exit(main())
