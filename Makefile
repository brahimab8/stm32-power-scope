.PHONY: all build clean test analyze fmt fmt-check coverage cov-html help
BUILD ?= build
CONFIG ?= Debug

all: build

help:
	@echo "Targets: build test analyze fmt fmt-check coverage clean"

build:
	@cmake -S . -B $(BUILD) -DCMAKE_BUILD_TYPE=$(CONFIG) -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
	@cmake --build $(BUILD) -j

clean:
	@rm -rf $(BUILD) coverage coverage.info

test: build
	@ctest --test-dir $(BUILD) --output-on-failure

analyze:
	@rm -rf $(BUILD)
	@cmake -S . -B $(BUILD) -DCMAKE_BUILD_TYPE=$(CONFIG) -DENABLE_ANALYSIS=ON
	@cmake --build $(BUILD) -j

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
	    echo "Some files are not formatted correctly. Run 'make fmt' to fix."; \
	    exit 1; \
	else \
	    echo "All files are correctly formatted!"; \
	fi

# Coverage via gcovr
coverage:
	@rm -rf coverage
	@mkdir -p coverage
	@cmake -S . -B $(BUILD) -DCMAKE_BUILD_TYPE=$(CONFIG) -DENABLE_COVERAGE=ON
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
