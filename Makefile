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

.PHONY: help build up down logs shell clean status whoami reset-password

## Show this help message
help:
	@echo "$(BLUE)Pulse News - Local Deployment Commands$(RESET)"
	@echo ""
	@echo "$(GREEN)Available targets:$(RESET)"
	@echo "  $(YELLOW)make build$(RESET)    - Build the Docker image"
	@echo "  $(YELLOW)make up$(RESET)       - Start the service (builds if needed)"
	@echo "  $(YELLOW)make down$(RESET)     - Stop and remove the container"
	@echo "  $(YELLOW)make restart$(RESET)  - Restart the service"
	@echo "  $(YELLOW)make logs$(RESET)           - Follow container logs"
	@echo "  $(YELLOW)make shell$(RESET)          - Open a shell inside the running container"
	@echo "  $(YELLOW)make status$(RESET)         - Check container status"
	@echo "  $(YELLOW)make whoami$(RESET)         - Show bootstrap state and operator emails"
	@echo "  $(YELLOW)make reset-password$(RESET) - Reset/create an operator password (EMAIL=...)"
	@echo "  $(YELLOW)make clean$(RESET)          - Remove container, image, and volumes"
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
	PULSE_NEWS_PORT=$(PORT) docker compose up -d --build
	@echo ""
	@echo "$(GREEN)Pulse News is starting up!$(RESET)"
	@echo "$(BLUE)Access URLs:$(RESET)"
	@echo "  Local:     http://localhost:$(PORT)"
	@echo "  Network:   http://$(shell hostname -I | awk '{print $$1}' 2>/dev/null || echo 'YOUR_IP'):$(PORT)"
	@echo ""
	@echo "$(YELLOW)Note: It may take 10-20 seconds for the service to be ready.$(RESET)"
	@echo "$(YELLOW)Run 'make logs' to monitor startup progress.$(RESET)"
	@echo ""
	@echo "$(GREEN)Operator account:$(RESET)"
	@echo "  - First-time launch: open the URL above and create the initial operator on the bootstrap screen."
	@echo "  - Already bootstrapped: run '$(YELLOW)make whoami$(RESET)' to see operator emails."
	@echo "  - Forgot the password:  run '$(YELLOW)make reset-password EMAIL=you@example.com$(RESET)'."

## Stop the service
down:
	@echo "$(BLUE)Stopping Pulse News...$(RESET)"
	docker compose down
	@echo "$(GREEN)Service stopped.$(RESET)"

## Restart the service
restart: down up

## View container logs
logs:
	@echo "$(BLUE)Following logs (Ctrl+C to exit)...$(RESET)"
	docker compose logs -f

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

## Show bootstrap state and operator emails (no passwords)
whoami:
	@docker exec $(CONTAINER_NAME) python -c "\
from app.database import get_session_maker; \
from app.models import User, SystemSettings; \
s=get_session_maker()(); \
settings=s.get(SystemSettings,1); \
users=s.query(User).order_by(User.id).all(); \
print('Bootstrap:', 'complete' if settings and settings.initialized else 'pending (open the URL to create the first operator)'); \
print('Operators:'); \
[print(f'  - {u.email}  (created {u.created_at:%Y-%m-%d})') for u in users] if users else print('  (none yet)')" 2>/dev/null || \
	  echo "$(RED)Container not running. Start it with 'make up'.$(RESET)"

## Reset or create an operator password.  Usage: make reset-password EMAIL=you@example.com [PASSWORD=newpass]
reset-password:
	@if [ -z "$(EMAIL)" ]; then \
	  echo "$(RED)EMAIL is required.$(RESET)"; \
	  echo "Usage: make reset-password EMAIL=you@example.com [PASSWORD=new-password]"; \
	  exit 1; \
	fi
	@if [ -n "$(PASSWORD)" ]; then \
	  NEW_PW='$(PASSWORD)'; \
	else \
	  printf "New password for %s (min 8 chars, hidden): " "$(EMAIL)"; \
	  stty -echo; read NEW_PW; stty echo; echo; \
	fi; \
	if [ -z "$$NEW_PW" ] || [ $${#NEW_PW} -lt 8 ]; then \
	  echo "$(RED)Password must be at least 8 characters.$(RESET)"; exit 1; \
	fi; \
	docker exec -e RP_EMAIL='$(EMAIL)' -e RP_PASSWORD="$$NEW_PW" $(CONTAINER_NAME) python /app/backend/scripts/reset_password.py \
	  || { echo "$(RED)Reset failed. Is the container running? Try 'make up'.$(RESET)"; exit 1; }

## Clean up everything
clean:
	@echo "$(RED)Removing container, image, and volumes...$(RESET)"
	docker compose down -v
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
