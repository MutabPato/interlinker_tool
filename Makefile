USE_SUDO ?= 1
DOCKER := docker
ifeq ($(USE_SUDO),1)
DOCKER := sudo docker
endif

IMAGE_NAME ?= interlinker
IMAGE_TAG ?= latest
FULL_IMAGE_NAME := $(IMAGE_NAME):$(IMAGE_TAG)
CONTAINER_NAME ?= interlinker_app
ENV_FILE ?= $(if $(wildcard .env),.env,.env.example)
HOST_PORT ?= 8000
CONTAINER_PORT ?= 8000

.PHONY: help build up down logs shell migrate

help:
	@echo "Available targets:"
	@echo "  make build        Build the Docker image ($(FULL_IMAGE_NAME))"
	@echo "  make up           Build (if needed) and run the container in detached mode"
	@echo "  make down         Stop the running container"
	@echo "  make logs         Follow logs from the running container"
	@echo "  make shell        Open an interactive shell inside the container"
	@echo "  make migrate      Run Django migrations inside the container"
	@echo "  set USE_SUDO=0 to disable automatic sudo (default USE_SUDO=1)"
	@echo "  defaults to .env if present, otherwise falls back to .env.example"

build:
	$(DOCKER) build -t $(FULL_IMAGE_NAME) .

	$(DOCKER) rm -f $(CONTAINER_NAME) >/dev/null 2>&1 || true
	$(DOCKER) run \
		--rm \
		-d \
		--name $(CONTAINER_NAME) \
		--env-file $(ENV_FILE) \
		-p $(HOST_PORT):$(CONTAINER_PORT) \
		$(FULL_IMAGE_NAME)
	@echo "App running at http://127.0.0.1:$(HOST_PORT)/"

# Stops the container if it's running.
down:
	$(DOCKER) stop $(CONTAINER_NAME)

logs:
	$(DOCKER) logs -f $(CONTAINER_NAME)

shell:
	$(DOCKER) exec -it $(CONTAINER_NAME) /bin/sh

migrate:
	$(DOCKER) exec -it $(CONTAINER_NAME) python manage.py migrate --noinput
