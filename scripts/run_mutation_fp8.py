#!/usr/bin/env python3
"""Apply E4M3-only edits; fast PE fp8_mut + 2×2 array −0."""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from mutations_fp8 import MUTANTS  # noqa: E402

REPORTS = os.path.join(ROOT, "reports", "O15")
PE = os.path.join(ROOT, "tests", "pe")
ARRAY = os.path.join(ROOT, "tests", "array")
os.makedirs(REPORTS, exist_ok=True)


def tests_ok(xml_path):
    if not os.path.isfile(xml_path):
        return False
    txt = open(xml_path, encoding="utf-8").read()
    if "<failure" in txt or "<error" in txt:
        return False
    return "<testcase" in txt


def apply_mut(src_root, rel, old, new):
    path = os.path.join(src_root, rel)
    txt = open(path, encoding="utf-8").read()
    if old not in txt:
        return "missing"
    if txt.count(old) != 1:
        return "not-unique:%d" % txt.count(old)
    open(path, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    return "ok"


def fast_ok(rtl_root, work):
    rtl = os.path.join(rtl_root, "rtl")
    pe_sv = os.path.join(rtl, "pe.sv")
    arr_sv = os.path.join(rtl, "array.sv")
    runs = [
        (
            "pe",
            PE,
            dict(
                DUT=pe_sv,
                PARAM_FMT="E4M3",
                SUITE="fp8_mut",
                SEED="1",
                SIM_BUILD=os.path.join(work, "pe"),
                WAVES="0",
            ),
        ),
        (
            "neg0",
            ARRAY,
            dict(
                DUT=arr_sv,
                PE=pe_sv,
                MODULE="test_array_fp8",
                PARAM_R="2",
                PARAM_C="2",
                PARAM_FMT="E4M3",
                SUITE="neg0",
                SEED="1",
                SIM_BUILD=os.path.join(work, "neg0"),
                WAVES="0",
            ),
        ),
    ]
    for name, cwd, extra in runs:
        e = os.environ.copy()
        e.update(extra)
        e.setdefault("SIM", "verilator")
        e["COCOTB_RESULTS_FILE"] = os.path.join(work, name + ".xml")
        e["PYTHONPATH"] = (
            os.path.join(ROOT, "tests")
            + os.pathsep
            + os.path.join(ROOT, "model", "python")
            + os.pathsep
            + os.path.join(ROOT, "scripts")
        )
        logp = os.path.join(work, name + ".log")
        with open(logp, "w") as log:
            p = subprocess.run(
                ["make", "-C", cwd], env=e, cwd=cwd, stdout=log, stderr=subprocess.STDOUT
            )
        if p.returncode != 0 or not tests_ok(e["COCOTB_RESULTS_FILE"]):
            return False, name
    return True, "all"


def main():
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            ["bash", "-lc", "date -u; verilator --version"],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    out = os.path.join(REPORTS, "mutation.log")
    results = []
    with open(out, "w") as summary:
        summary.write(open(ver).read() + "\n")
        summary.write("mutants=%d\n" % len(MUTANTS))
        for mid, rel, old, new, why in MUTANTS:
            td = tempfile.mkdtemp(prefix="mut_" + mid + "_")
            try:
                shutil.copytree(os.path.join(ROOT, "rtl"), os.path.join(td, "rtl"))
                st = apply_mut(td, rel, old, new)
                if st != "ok":
                    line = "%s APPLY_%s %s\n" % (mid, st, why)
                    summary.write(line)
                    print(line.strip())
                    results.append((mid, "apply-fail", why, st))
                    continue
                work = os.path.join(td, "work")
                os.makedirs(work)
                survived, where = fast_ok(td, work)
                status = "SURVIVED" if survived else ("KILLED:%s" % where)
                line = "%s %s %s\n" % (mid, status, why)
                summary.write(line)
                print(line.strip())
                results.append((mid, "survived" if survived else "killed", why, where))
            finally:
                shutil.rmtree(td, ignore_errors=True)
    killed = sum(1 for r in results if r[1] == "killed")
    survived = [r for r in results if r[1] == "survived"]
    apply_fail = [r for r in results if r[1] == "apply-fail"]
    n = len(results)
    with open(out, "a") as summary:
        summary.write(
            "killed=%d survived=%d apply_fail=%d n=%d\n"
            % (killed, len(survived), len(apply_fail), n)
        )
        if n:
            summary.write("score=%.4f\n" % (killed / float(n)))
        summary.write("MUTATION-FP8 OK\n" if not apply_fail else "MUTATION-FP8 APPLY FAIL\n")
    with open(os.path.join(REPORTS, "mutation-results.txt"), "w") as f:
        for r in results:
            f.write("%s %s %s %s\n" % r)
    print("killed", killed, "survived", len(survived), "apply_fail", len(apply_fail))
    return 0 if not apply_fail else 1


if __name__ == "__main__":
    sys.exit(main())
