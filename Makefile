.PHONY: all build clean test analyze fmt coverage cov-html help
BUILD ?= build
CONFIG ?= Debug

all: build

help:
	@echo "Targets: build test analyze fmt coverage clean"

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
	@echo "Formatting..."
	@find powerscope/include powerscope/src powerscope/tests \
	    -type f \( -name "*.c" -o -name "*.h" \) -print0 \
	    | xargs -0 -r clang-format -i

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
