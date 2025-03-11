.PHONY: all lint format test help start_mcp test_integration

# Default target executed when no arguments are given to make.
all: help

######################
# TESTING AND COVERAGE
######################

# Define a variable for the test file path.
TEST_FILE ?= tests/unit_tests

test:
	uv run pytest --disable-socket --allow-unix-socket $(TEST_FILE)

test_watch:
	uv run ptw . -- $(TEST_FILE)

.PHONY: test_integration

test_integration:
	uv run uvicorn tests.integration.mcp_server:app --host localhost --port 8133 --reload & \
	pid=$$!; \
	trap "kill -9 $$pid" EXIT; \
	while [ "$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8133/health)" != "200" ]; do \
	  sleep 0.2; \
	done; \
	MCP_SSE_URL="http://localhost:8133/mcp/sse" uv run pytest tests/integration

start_mcp:
	# start mcp server for integration tsets
	uv run uvicorn tests.integration.mcp_server:app --host localhost --port 8133 --reload


run_integration_test:
	uv run pytest tests/integration


######################
# LINTING AND FORMATTING
######################

# Define a variable for Python and notebook files.
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --relative=. --name-only --diff-filter=d master | grep -E '\.py$$|\.ipynb$$')

lint lint_diff:
	[ "$(PYTHON_FILES)" = "" ] ||	uv run ruff format $(PYTHON_FILES) --diff
	[ "$(PYTHON_FILES)" = "" ] ||	uv run ruff check $(PYTHON_FILES) --diff
	# [ "$(PYTHON_FILES)" = "" ] || uv run mypy $(PYTHON_FILES)

format format_diff:
	[ "$(PYTHON_FILES)" = "" ] || uv run ruff format $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || uv run ruff check --fix $(PYTHON_FILES)


generate_examples:
	uv run langgraph-gen examples/agentic_rag/spec.yml --language python
	uv run langgraph-gen examples/agentic_rag/spec.yml --language typescript
	uv run langgraph-gen examples/rag/spec.yml --language python
	uv run langgraph-gen examples/rag/spec.yml --language typescript
	

######################
# HELP
######################

help:
	@echo '===================='
	@echo '-- LINTING --'
	@echo 'format                       - run code formatters'
	@echo 'lint                         - run linters'
	@echo 'spell_check                 	- run codespell on the project'
	@echo 'spell_fix                		- run codespell on the project and fix the errors'
	@echo '-- TESTS --'
	@echo 'coverage                     - run unit tests and generate coverage report'
	@echo 'test                         - run unit tests'
	@echo 'test TEST_FILE=<test_file>   - run all tests in file'
	@echo '-- DOCUMENTATION tasks are from the top-level Makefile --'

