.PHONY: up down restart clean-data prune logs status

# Path to the main compose file
COMPOSE_FILE := infrastructure/docker-compose.yml

# 🚀 Start everything in the background
up:
	docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "Checking for dangling images to save space..."
	docker image prune -f

# 🛑 Stop services but keep your data
down:
	docker compose -f $(COMPOSE_FILE) down --remove-orphans

# 🔄 Rebuild and Restart (Useful when you change backend code)
restart:
	docker compose -f $(COMPOSE_FILE) up -d --build --force-recreate
	docker image prune -f

# 🧹 THE SPACE SAVER: Stops everything and WIPES all databases
# Note: These paths now target your new /data directory structure
clean-data:
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans
	@echo "Wiping local data directories..."
	rm -rf ./data/pg_data/*
	rm -rf ./data/qdrant_data/*
	@echo "Data wiped. System lean."

# ☢️ Nuclear Cleanup (The "Emergency" Disk Space command)
prune:
	docker system prune -a --volumes -f

# 📋 View logs for the backend and worker
logs:
	docker compose -f $(COMPOSE_FILE) logs -f backend worker

# 📊 Check service health
status:
	docker compose -f $(COMPOSE_FILE) ps

	.PHONY: up down restart clean-data prune logs status

# 📝 Help command to show available options
help:
	@echo "Nexus Monorepo Control Center:"
	@echo "  make up         - Build and start services"
	@echo "  make down       - Stop services"
	@echo "  make restart    - Force rebuild and restart"
	@echo "  make clean-data - Stop services and DELETE all DB/Vector data"
	@echo "  make prune      - Deep clean Docker (Recover Disk Space)"
	@echo "  make status     - View running services"