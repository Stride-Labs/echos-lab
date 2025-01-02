VERSION=$(shell grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

GCR_REPO=gcr.io/stride-nodes/echos
IMAGE_NAME=$(GCR_REPO)/echos-lab:$(VERSION)
LATEST_IMAGE_NAME=$(GCR_REPO)/echos-lab:latest

DOCKER := $(shell which docker)

###################################################
##            Setup and Formatting               ##
###################################################

install:
	@echo "Installing package and dependencies..."
	@pip install -e .[dev]
	@pip uninstall uvloop -y

lint:
	@echo "Running linting checks..."
	@flake8 --max-line-length 120 --exclude .ipynb_checkpoints echos_lab tests

type-check:
	@echo "Running type checks..."
	@mypy --install-types --non-interactive echos_lab tests --ignore-missing-imports

format:
	@echo "Formatting code..."
	@black --skip-string-normalization --line-length 120 echos_lab
	@echo "Sorting imports..."
	@isort --profile=black echos_lab tests

tidy: lint type-check format

clean:
	@echo "Cleaning up..."
	@rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .coverage
	@find . -type d -name "__pycache__" -exec rm -rf {} +

###################################################
##                  Testing                      ##
###################################################

test:
	@echo "Running tests..."
	@pytest . -vv -m "not integration" $(TEST)


###################################################
##                 Local Testing                 ##
###################################################

start-db:
	@echo "Starting postgres..."
	@docker compose up -d postgres
	@sleep 5  # Wait for postgres to be ready
	@echo "Initializing tables..."
	@echos db init

docker-up:
	@echo "Starting services..."
	@docker compose up --build -d

docker-down:
	@echo "Stopping services..."
	@docker compose down -v

docker-logs:
	@docker compose logs -f

docker-psql:
	@docker compose exec postgres psql -U user -d echos

docker-clean:
	@echo "Cleaning up Docker environment..."
	@docker compose down -v

integration-test:
	@echo "Running integration tests..."
	@docker compose up -d postgres
	@sleep 5  # Wait for postgres to be ready
	@pytest -v -m integration tests/integration/test_db_migration.py
	@docker compose down


###################################################
##                 Deployment                    ##
###################################################

check-clean-main:
	@current_branch=$$(git rev-parse --abbrev-ref HEAD); \
	if [ "$$current_branch" != "main" ]; then \
		echo "Error: You must be on the 'main' branch to run this command."; \
		exit 1; \
	fi; \
	if ! git diff --quiet; then \
		echo "Error: You have uncommitted changes. Commit or stash them before proceeding."; \
		exit 1; \
	fi; \
	if ! git diff --cached --quiet; then \
		echo "Error: You have staged changes. Commit or stash them before proceeding."; \
		exit 1; \
	fi

upload: check-clean-main docker-build docker-push docker-push-latest

docker-build:
	@echo "Building docker image: $(IMAGE_NAME)"
	@$(DOCKER) buildx build --platform linux/amd64 --tag $(IMAGE_NAME) .

docker-push:
	@echo "Pushing image to GCR"
	@$(DOCKER) push $(IMAGE_NAME)

docker-push-latest:
	@echo "Tagging image as latest: $(LATEST_IMAGE_NAME)"
	@$(DOCKER) tag $(IMAGE_NAME) $(LATEST_IMAGE_NAME)
	@echo "Pushing image to GCR: $(LATEST_IMAGE_NAME)"
	@$(DOCKER) push $(LATEST_IMAGE_NAME)

upload-dev:
	@if [ -z "$(TAG)" ]; then \
		echo "Error: Missing argument for upload-dev. Usage: make upload-dev TAG=<tag>, e.g. make upload-dev TAG=vito"; \
		exit 1; \
	fi; \
	VERSION=dev-$(TAG); \
	IMAGE_NAME=$(GCR_REPO)/echos-lab:$$VERSION; \
	echo "Building docker image: $$IMAGE_NAME"; \
	$(DOCKER) buildx build --platform linux/amd64 --tag $$IMAGE_NAME .; \
	echo "Pushing image to GCR"; \
	$(DOCKER) push $$IMAGE_NAME
