# Makefile for Power Scope project (native + firmware builds)
# Uses CMake as the build system generator.
# Usage on Unix-like systems (Linux, macOS, WSL, CI). On Windows, use scripts/env.ps1.

.PHONY: all help \
        build test analyze coverage clean \
        fmt fmt-check \
        fw-build fw-flash fw-debug fw-clean

# --------------------
# Common config
# --------------------
GENERATOR ?= Ninja
EXPORT_COMPILE_COMMANDS ?= ON

# --------------------
# Native build (library + unit tests)
# --------------------
BUILD  ?= build
CONFIG ?= Debug

# --------------------
# Firmware build (cross compile)
# --------------------
FW_BUILD  ?= build-fw
FW_CONFIG ?= Release
FW_DEBUG  ?= OFF
TOOLCHAIN ?= cmake/arm-none-eabi-toolchain.cmake

# Firmware selection (multi-target)
PS_TARGET    ?= stm32l432_nucleo
PS_TRANSPORT ?= UART

# Derived firmware build dir (matches Windows flow)
FW_OUT := $(FW_BUILD)/$(PS_TARGET)/$(PS_TRANSPORT)/$(FW_CONFIG)

all: build

help:
	@echo ""
	@echo "Power Scope - Make targets"
	@echo ""
	@echo "Native build (library + tests):"
	@echo "  build            Configure + build core library and unit test binaries"
	@echo "  test             Run unit tests via ctest"
	@echo "  analyze          Configure + build with ENABLE_ANALYSIS=ON"
	@echo "  coverage         Build + run tests with coverage and generate report (requires gcovr)"
	@echo "  clean            Remove native build + coverage outputs"
	@echo ""
	@echo "Formatting targets:"
	@echo "  fmt              Format powerscope sources (clang-format)"
	@echo "  fmt-check        Verify formatting (clang-format --dry-run)"
	@echo ""
	@echo "Firmware (cross compile) targets:"
	@echo "  fw-build         Configure + build firmware"
	@echo "  fw-flash         Flash firmware (requires OpenOCD and target-defined 'flash')"
	@echo "  fw-debug         Start debug server (requires OpenOCD and target-defined 'debug-server')"
	@echo "  fw-clean         Remove current firmware build outputs ($(FW_OUT))"
	@echo ""
	@echo "Common variables:"
	@echo "  GENERATOR        CMake generator (default: $(GENERATOR))"
	@echo "  EXPORT_COMPILE_COMMANDS  ON/OFF (default: $(EXPORT_COMPILE_COMMANDS))"
	@echo ""
	@echo "Native build variables:"
	@echo "  BUILD            Build dir (default: $(BUILD))"
	@echo "  CONFIG           Debug/Release (default: $(CONFIG))"
	@echo ""
	@echo "Firmware variables:"
	@echo "  FW_BUILD         Firmware build root (default: $(FW_BUILD))"
	@echo "  FW_CONFIG        Debug/Release (default: $(FW_CONFIG))"
	@echo "  FW_DEBUG         ON/OFF (default: $(FW_DEBUG))"
	@echo "  PS_TARGET        Target folder under ./firmware (default: $(PS_TARGET))"
	@echo "  PS_TRANSPORT     UART or USB_CDC (default: $(PS_TRANSPORT))"
	@echo "  TOOLCHAIN        CMake toolchain file (default: $(TOOLCHAIN))"
	@echo "  FW_OUT           Derived output dir (current: $(FW_OUT))"
	@echo ""
	@echo "Examples:"
	@echo "  make fw-build PS_TARGET=stm32l432_nucleo PS_TRANSPORT=USB_CDC"
	@echo "  make fw-build FW_CONFIG=Debug FW_DEBUG=ON"
	@echo ""

# --------------------
# Native build targets
# --------------------
build:
	@cmake -S . -B $(BUILD) -G "$(GENERATOR)" \
	  -DCMAKE_BUILD_TYPE=$(CONFIG) \
	  -DCMAKE_EXPORT_COMPILE_COMMANDS=$(EXPORT_COMPILE_COMMANDS)
	@cmake --build $(BUILD) -j

test: build
	@ctest --test-dir $(BUILD) --output-on-failure

analyze:
	@rm -rf $(BUILD)
	@cmake -S . -B $(BUILD) -G "$(GENERATOR)" \
	  -DCMAKE_BUILD_TYPE=$(CONFIG) \
	  -DENABLE_ANALYSIS=ON \
	  -DCMAKE_EXPORT_COMPILE_COMMANDS=$(EXPORT_COMPILE_COMMANDS)
	@cmake --build $(BUILD) -j

clean:
	@rm -rf $(BUILD) coverage coverage.info

# --------------------
# Formatting
# --------------------
fmt:
	@echo "Formatting powerscope files..."
	@find powerscope/include powerscope/src \
	    -type f \( -name "*.c" -o -name "*.h" \) -print0 \
	    | xargs -0 -r -n1 sh -c 'echo "Formatting $$0"; clang-format -i "$$0"'
	@echo "Formatting complete."

fmt-check:
	@echo "Checking formatting for powerscope files..."
	@set -e; \
	FAIL=0; \
	find powerscope/include powerscope/src -type f \( -name "*.c" -o -name "*.h" \) -print0 \
	    | xargs -0 -n1 sh -c ' \
	        FILE="$$0"; \
	        echo "Checking $$FILE"; \
	        clang-format --dry-run --Werror "$$FILE" || FAIL=1'; \
	if [ $$FAIL -eq 1 ]; then \
	    echo "Some files are not formatted correctly. Run '\''make fmt'\'' to fix."; \
	    exit 1; \
	else \
	    echo "All files are correctly formatted!"; \
	fi

# --------------------
# Coverage report
# --------------------
coverage:
	@rm -rf coverage
	@mkdir -p coverage
	@cmake -S . -B $(BUILD) -G "$(GENERATOR)" \
	  -DCMAKE_BUILD_TYPE=$(CONFIG) \
	  -DENABLE_COVERAGE=ON \
	  -DCMAKE_EXPORT_COMPILE_COMMANDS=$(EXPORT_COMPILE_COMMANDS)
	@cmake --build $(BUILD) -j
	@ctest --test-dir $(BUILD) --output-on-failure
	@gcovr --root . \
	  --filter 'powerscope/(src|include)/' \
	  --exclude 'powerscope/tests/.*|firmware/.*|third_party/.*' \
	  --xml -o coverage/coverage.xml \
	  --html=coverage/index.html \
	  --html-details \
	  --print-summary
	@echo "Coverage report: coverage/index.html"

# --------------------
# Firmware build targets (cross compile; tests disabled)
# --------------------
fw-build:
	@cmake -S . -B "$(FW_OUT)" -G "$(GENERATOR)" \
	  --toolchain "$(TOOLCHAIN)" \
	  -DCMAKE_BUILD_TYPE=$(FW_CONFIG) \
	  -DBUILD_FIRMWARE=ON \
	  -DPS_TARGET=$(PS_TARGET) \
	  -DPS_TRANSPORT=$(PS_TRANSPORT) \
	  -DBUILD_TESTING=OFF \
	  -DFW_DEBUG=$(FW_DEBUG) \
	  -DCMAKE_EXPORT_COMPILE_COMMANDS=$(EXPORT_COMPILE_COMMANDS)
	@cmake --build "$(FW_OUT)" -j

fw-debug: fw-build
	@cmake --build "$(FW_OUT)" --target debug-server

fw-flash: fw-build
	@cmake --build "$(FW_OUT)" --target flash

fw-clean:
	@rm -rf "$(FW_OUT)"
