.PHONY: help test test-cov test-watch mypy lint format clean install dev-install run

# Colors for terminal output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

## help: Show this help message
help:
	@echo "${BLUE}Digital Being - Development Commands${NC}"
	@echo ""
	@echo "${GREEN}Available commands:${NC}"
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'

## install: Install production dependencies
install:
	@echo "${YELLOW}Installing production dependencies...${NC}"
	pip install -r requirements.txt
	@echo "${GREEN}✓ Production dependencies installed${NC}"

## dev-install: Install development dependencies
dev-install: install
	@echo "${YELLOW}Installing development dependencies...${NC}"
	pip install -r requirements-dev.txt
	@echo "${GREEN}✓ Development dependencies installed${NC}"

## test: Run all tests
test:
	@echo "${YELLOW}Running tests...${NC}"
	pytest -v
	@echo "${GREEN}✓ Tests completed${NC}"

## test-cov: Run tests with coverage report
test-cov:
	@echo "${YELLOW}Running tests with coverage...${NC}"
	pytest --cov=core --cov-report=term-missing --cov-report=html
	@echo "${GREEN}✓ Coverage report generated in htmlcov/${NC}"

## test-watch: Run tests in watch mode (requires pytest-watch)
test-watch:
	@echo "${YELLOW}Running tests in watch mode...${NC}"
	pytest-watch

## test-fast: Run tests without slow markers
test-fast:
	@echo "${YELLOW}Running fast tests only...${NC}"
	pytest -v -m "not slow"

## mypy: Run type checker
mypy:
	@echo "${YELLOW}Running type checker...${NC}"
	mypy core/
	@echo "${GREEN}✓ Type checking completed${NC}"

## lint: Run code linters
lint:
	@echo "${YELLOW}Running linters...${NC}"
	@echo "${BLUE}Running flake8...${NC}"
	-flake8 core/ --max-line-length=100 --ignore=E501,W503
	@echo "${BLUE}Running pylint...${NC}"
	-pylint core/ --disable=C0111,C0103,R0913,R0914,R0915
	@echo "${GREEN}✓ Linting completed${NC}"

## format: Auto-format code with black and isort
format:
	@echo "${YELLOW}Formatting code...${NC}"
	@echo "${BLUE}Running isort...${NC}"
	isort core/ tests/
	@echo "${BLUE}Running black...${NC}"
	black core/ tests/
	@echo "${GREEN}✓ Code formatted${NC}"

## check: Run all checks (tests + mypy + lint)
check: test mypy lint
	@echo "${GREEN}✓ All checks passed!${NC}"

## clean: Remove generated files and caches
clean:
	@echo "${YELLOW}Cleaning up...${NC}"
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf *.egg-info
	rm -rf dist
	rm -rf build
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "${GREEN}✓ Cleanup completed${NC}"

## run: Start Digital Being
run:
	@echo "${YELLOW}Starting Digital Being...${NC}"
	python main.py

## docs: Generate documentation
docs:
	@echo "${YELLOW}Generating documentation...${NC}"
	cd docs && make html
	@echo "${GREEN}✓ Documentation generated in docs/_build/html/${NC}"

## stats: Show project statistics
stats:
	@echo "${BLUE}Project Statistics:${NC}"
	@echo "Lines of code:"
	@find core -name '*.py' | xargs wc -l | tail -1
	@echo "\nNumber of tests:"
	@find tests -name 'test_*.py' | xargs grep -c "def test_" | awk -F: '{sum += $$2} END {print sum}'
	@echo "\nTest coverage:"
	@pytest --cov=core --cov-report=term | grep TOTAL
