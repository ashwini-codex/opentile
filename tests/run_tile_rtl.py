#!/usr/bin/env python3
"""Extra RTL tests + tile testbench against real tile_top. Stand-in runs stay in run_sim.py."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
REPORTS = os.path.join(ROOT, "reports", "O8")
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
    line = "  -> %s make_rc %s xml %s log %s" % (
        "PASS" if ok else "FAIL",
        p.returncode,
        xmlp,
        logp,
    )
    print(line)
    with open(os.path.join(REPORTS, "tile-rtl.log"), "a") as f:
        f.write("RUN %s expect %s\n%s\n" % (label, "PASS" if expect_pass else "FAIL", line))
    if expect_pass and not ok:
        print("ERROR: %s should have passed" % label)
        return 1
    if (not expect_pass) and ok:
        print("ERROR: %s should have failed" % label)
        return 1
    return 0


def rtl_env(module, suite, R, C, extra=None):
    env = dict(
        DUT=os.path.join(RTL, "tile_top.sv"),
        VERILOG_SOURCES=GOOD,
        MODULE=module,
        PARAM_R=str(R),
        PARAM_C=str(C),
        K_MAX="64",
        SUITE=suite,
        BP="always",
        SEED="1",
        SIM_BUILD="sim_build/rtl_%s_%dx%d" % (suite, R, C),
    )
    if extra:
        env.update(extra)
    return env


def main():
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
    with open(os.path.join(REPORTS, "tile-rtl.log"), "w") as f:
        f.write(open(ver).read() + "\n")
    rc = 0

    # Unmodified tile testbench vs real DUT
    for R, C in ((2, 2), (2, 3), (3, 3), (1, 1), (3, 2), (4, 1)):
        rc |= run(
            "rtl directed %dx%d" % (R, C),
            rtl_env("test_tile", "directed", R, C),
            "rtl-directed-%dx%d.log" % (R, C),
            True,
        )
    rc |= run(
        "rtl random 2x2",
        rtl_env("test_tile", "random", 2, 2),
        "rtl-random.log",
        True,
    )
    for bp in ("always", "random", "long", "every_other"):
        rc |= run(
            "rtl bp " + bp,
            rtl_env("test_tile", "bp", 2, 2, extra={"BP": bp, "SIM_BUILD": "sim_build/rtl_bp_2x2"}),
            "rtl-bp-%s.log" % bp,
            True,
        )
    rc |= run(
        "rtl err",
        rtl_env("test_tile", "err", 2, 2),
        "rtl-err.log",
        True,
    )

    # Extra RTL suites
    rc |= run(
        "latency 4x4 K=4",
        rtl_env("test_tile_rtl", "latency", 4, 4),
        "rtl-latency-4x4.log",
        True,
    )
    rc |= run(
        "reset mid",
        rtl_env("test_tile_rtl", "reset_mid", 2, 2),
        "rtl-reset-mid.log",
        True,
    )
    rc |= run(
        "tlast flags",
        rtl_env("test_tile_rtl", "tlast", 2, 2),
        "rtl-tlast.log",
        True,
    )
    rc |= run(
        "K_MAX",
        rtl_env("test_tile_rtl", "kmax", 2, 2),
        "rtl-kmax.log",
        True,
    )
    rc |= run(
        "axi monitor",
        rtl_env("test_tile_rtl", "monitor", 2, 2),
        "rtl-monitor.log",
        True,
    )

    xfiles = []
    for seed in (1, 2, 3):
        cfile = os.path.join(REPORTS, "xinit-%d.c.txt" % seed)
        rc |= run(
            "xinit seed %d" % seed,
            rtl_env(
                "test_tile_rtl",
                "xinit",
                2,
                2,
                extra={
                    "XSEED": str(seed * 17 + 3),
                    "CFILE": cfile,
                    "SIM_BUILD": "sim_build/rtl_xinit_%d" % seed,
                },
            ),
            "rtl-xinit-%d.log" % seed,
            True,
        )
        if os.path.isfile(cfile):
            xfiles.append(open(cfile).read())
    if len(set(xfiles)) != 1 or not xfiles:
        print("ERROR: x-initial C results differ or missing")
        rc |= 1

    noready = os.path.join(RTL, "variants", "tile_store_noready.sv")
    early = os.path.join(RTL, "variants", "tile_early_read.sv")
    rc |= run(
        "store_noready caught",
        dict(
            DUT=noready,
            VERILOG_SOURCES=sources(noready),
            MODULE="test_tile",
            PARAM_R="2",
            PARAM_C="2",
            K_MAX="64",
            SUITE="catch",
            BP="stall3",
            SEED="1",
            SIM_BUILD="sim_build/rtl_noready",
        ),
        "rtl-noready-caught.log",
        False,
    )
    rc |= run(
        "early_read caught",
        dict(
            DUT=early,
            VERILOG_SOURCES=sources(early),
            MODULE="test_tile",
            PARAM_R="2",
            PARAM_C="2",
            K_MAX="64",
            SUITE="catch",
            BP="always",
            SEED="1",
            SIM_BUILD="sim_build/rtl_early",
        ),
        "rtl-early-caught.log",
        False,
    )

    with open(os.path.join(REPORTS, "tile-rtl.log"), "a") as f:
        f.write("exit_rc=%d\n" % rc)
        f.write("TILE-RTL OK\n" if rc == 0 else "TILE-RTL FAIL\n")
    if rc == 0:
        print("TILE-RTL OK")
    return rc


if __name__ == "__main__":
    sys.exit(main())
