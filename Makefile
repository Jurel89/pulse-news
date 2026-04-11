# Pulse News - Local Deployment Makefile
# Usage: make [target]

# Configuration
PORT ?= 9876
IMAGE_NAME = pulse-news
CONTAINER_NAME = pulse-news

# Colors for output
BLUE = \033[36m
GREEN = \033[32m
YELLOW = \033[33m
RED = \033[31m
RESET = \033[0m

.PHONY: help build up down logs shell clean status

## Show this help message
help:
	@echo "$(BLUE)Pulse News - Local Deployment Commands$(RESET)"
	@echo ""
	@echo "$(GREEN)Available targets:$(RESET)"
	@echo "  $(YELLOW)make build$(RESET)    - Build the Docker image"
	@echo "  $(YELLOW)make up$(RESET)       - Start the service (builds if needed)"
	@echo "  $(YELLOW)make down$(RESET)     - Stop and remove the container"
	@echo "  $(YELLOW)make restart$(RESET)  - Restart the service"
	@echo "  $(YELLOW)make logs$(RESET)     - Follow container logs"
	@echo "  $(YELLOW)make shell$(RESET)    - Open a shell inside the running container"
	@echo "  $(YELLOW)make status$(RESET)   - Check container status"
	@echo "  $(YELLOW)make clean$(RESET)    - Remove container, image, and volumes"
	@echo ""
	@echo "$(BLUE)Configuration:$(RESET)"
	@echo "  PORT=$(PORT) (set via PORT=xxxx or in .env file)"
	@echo "  Default: 9876"
	@echo ""
	@echo "$(GREEN)Quick start:$(RESET)"
	@echo "  1. Copy .env.example to .env and fill in your values"
	@echo "  2. Run: make up"
	@echo "  3. Access at: http://$(shell hostname -I | awk '{print $$1}'):$(PORT)"

## Build the Docker image
build:
	@echo "$(BLUE)Building Pulse News Docker image...$(RESET)"
	docker build -t $(IMAGE_NAME):latest .
	@echo "$(GREEN)Build complete!$(RESET)"

## Start the service
up:
	@echo "$(BLUE)Starting Pulse News on port $(PORT)...$(RESET)"
	@echo "$(YELLOW)Make sure you've configured your .env file!$(RESET)"
	PULSE_NEWS_PORT=$(PORT) docker-compose up -d --build
	@echo ""
	@echo "$(GREEN)Pulse News is starting up!$(RESET)"
	@echo "$(BLUE)Access URLs:$(RESET)"
	@echo "  Local:     http://localhost:$(PORT)"
	@echo "  Network:   http://$(shell hostname -I | awk '{print $$1}' 2>/dev/null || echo 'YOUR_IP'):$(PORT)"
	@echo ""
	@echo "$(YELLOW)Note: It may take 10-20 seconds for the service to be ready.$(RESET)"
	@echo "$(YELLOW)Run 'make logs' to monitor startup progress.$(RESET)"

## Stop the service
down:
	@echo "$(BLUE)Stopping Pulse News...$(RESET)"
	docker-compose down
	@echo "$(GREEN)Service stopped.$(RESET)"

## Restart the service
restart: down up

## View container logs
logs:
	@echo "$(BLUE)Following logs (Ctrl+C to exit)...$(RESET)"
	docker-compose logs -f

## Open a shell in the container
shell:
	@echo "$(BLUE)Opening shell in Pulse News container...$(RESET)"
	docker exec -it $(CONTAINER_NAME) /bin/bash

## Check container status
status:
	@echo "$(BLUE)Container Status:$(RESET)"
	@docker ps --filter "name=$(CONTAINER_NAME)" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "$(BLUE)Health Check:$(RESET)"
	@docker inspect --format='{{.State.Health.Status}}' $(CONTAINER_NAME) 2>/dev/null || echo "Not running"

## Clean up everything
clean:
	@echo "$(RED)Removing container, image, and volumes...$(RESET)"
	docker-compose down -v
	docker rmi $(IMAGE_NAME):latest 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(RESET)"

## Quick setup - copy env file if it doesn't exist
setup:
	@if [ ! -f .env ]; then \
		echo "$(BLUE)Creating .env from .env.example...$(RESET)"; \
		cp .env.example .env; \
		echo "$(YELLOW)Please edit .env and add your API keys before running 'make up'$(RESET)"; \
	else \
		echo "$(GREEN).env file already exists$(RESET)"; \
	fi
