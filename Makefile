# Interface for humans and CI. Host targets wrap the pinned Docker image unless IN_IMAGE=1.
SHELL := /bin/bash
IMAGE ?= opentile:dev
DOCKER ?= docker
SIZES ?= 2 4 8
IN_IMAGE ?=
RUN_IN_IMAGE = $(DOCKER) run --rm -v "$(CURDIR)":/work -w /work $(IMAGE)

.PHONY: docker-image versions smoke smoke-broken synth-probe verify \
        lint model-test pe-test array-test sim formal coverage mutation synth clean

docker-image:
	$(DOCKER) build -t $(IMAGE) -f Dockerfile .

ifeq ($(IN_IMAGE),)

versions smoke smoke-broken synth-probe verify model-test sim lint pe-test formal array-test synth coverage mutation: docker-image
	$(RUN_IN_IMAGE) make $@ IN_IMAGE=1 SIZES="$(SIZES)"

else

versions:
	@echo "=== tool versions ==="
	@date -u +"date_utc=%Y-%m-%dT%H:%M:%SZ"
	@echo "PATH=$$PATH"
	@which python3 verilator yosys sby z3 g++ cocotb-config
	@/usr/bin/python3 --version
	@verilator --version
	@yosys -V | head -1
	@sby --version 2>/dev/null || sby -h 2>&1 | head -2
	@z3 --version
	@/usr/bin/python3 -c "import cocotb,pytest; print('cocotb', cocotb.__version__); print('pytest', pytest.__version__)"
	@g++ --version | head -1
	@echo -n "openlane: "; command -v openlane || echo "not found"
	@echo -n "flow.tcl: "; command -v flow.tcl || echo "not found"

smoke:
	$(MAKE) -C tests/smoke MODULE=test_reg1
	yosys -s tests/smoke/synth.ys
	cd tests/smoke && sby -f reg1.sby

smoke-broken:
	-$(MAKE) -C tests/smoke MODULE=test_reg1_broken
	test -f tests/smoke/results.xml
	grep -q '<failure' tests/smoke/results.xml

synth-probe:
	yosys -s tests/smoke/probe.ys

model-test:
	$(MAKE) -C model/cpp clean all
	python3 model/python/gen_vectors.py -o model/vectors/directed.vec
	python3 -m pytest tests/test_models.py tests/test_cycle_model.py tests/test_fp8_models.py tests/test_fp8_acc_width.py -q --tb=short

sim:
	python3 tests/run_sim.py
	SIZES="$(SIZES)" python3 tests/run_sizes.py

lint:
	mkdir -p reports/O6 reports/O7 reports/O8
	verilator --lint-only -Wall --top-module tile_top --sv rtl/pe.sv rtl/array.sv rtl/tile_top.sv > reports/O8/lint.log 2>&1; \
	  st=$$?; cat reports/O8/lint.log; \
	  if [ $$st -ne 0 ] || grep -E '%(Warning|Error)' reports/O8/lint.log; then exit 1; fi
	cp reports/O8/lint.log reports/O7/lint.log
	cp reports/O8/lint.log reports/O6/lint.log

pe-test:
	python3 tests/run_pe.py
	python3 tests/run_fp8_rtl.py
	yosys -s tests/pe/synth.ys > reports/O6/pe-synth.log 2>&1
	cat reports/O6/pe-synth.log

formal:
	mkdir -p reports/O6 reports/O8
	cd formal && sby -f pe.sby > ../reports/O6/formal.log 2>&1 || (cat ../reports/O6/formal.log; exit 1)
	cat reports/O6/formal.log
	cd formal && sby -f tile_top.sby > ../reports/O8/formal.log 2>&1 || (cat ../reports/O8/formal.log; exit 1)
	cat reports/O8/formal.log
	cd formal && sby -f tile_store_noready.sby > ../reports/O8/formal-noready.log 2>&1; \
	  if grep -q 'DONE (PASS' ../reports/O8/formal-noready.log; then \
	    echo "ERROR: store_noready variant should fail formal"; cat ../reports/O8/formal-noready.log; exit 1; \
	  fi; \
	  if ! grep -q 'DONE (FAIL' ../reports/O8/formal-noready.log; then \
	    echo "ERROR: store_noready formal did not produce FAIL"; cat ../reports/O8/formal-noready.log; exit 1; \
	  fi
	cat reports/O8/formal-noready.log

array-test:
	python3 tests/run_array.py

synth:
	python3 tests/run_synth.py

coverage:
	python3 tests/run_coverage.py
	python3 tests/run_fp8_coverage.py

mutation:
	python3 scripts/run_mutation.py
	python3 scripts/run_mutation_fp8.py

verify: smoke lint model-test pe-test array-test sim formal synth coverage
	@echo "VERIFY COMPLETE"

endif

clean:
	rm -rf build sim_build __pycache__ results.xml \
	  tests/smoke/sim_build tests/smoke/results.xml tests/smoke/reg1 \
	  tests/sim_build tests/results.xml tests/pe/sim_build tests/pe/dump.vcd \
	  tests/array/sim_build tests/array/dump.vcd \
	  formal/pe formal/pe_bmc formal/pe_prove formal/pe_cover \
	  formal/tile_top formal/tile_top_bmc formal/tile_top_prove formal/tile_top_cover \
	  formal/tile_store_noready formal/tile_store_noready_bmc \
	  formal/tile_store_noready_prove formal/tile_store_noready_cover
