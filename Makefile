.PHONY: up down restart clean-data reset-db clean-frontend prune logs status help

# Path to the main compose file
COMPOSE_FILE := infrastructure/docker-compose.yml
PROJECT_NAME := nexus

# 🚀 Start everything in the background
up:
	docker compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE) up -d --build
	@echo "Checking for dangling images to save space..."
	docker image prune -f

# 🛑 Stop services but keep your data
down:
	docker compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE) down --remove-orphans

# 🔄 Rebuild and Restart (Useful when you change backend code)
restart:
	docker compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE) up -d --build --force-recreate
	docker image prune -f

# 🧹 THE SPACE SAVER: Stops everything and WIPES all databases
clean-data:
	docker compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE) down -v --remove-orphans
	@echo "Wiping local data directories..."
	rm -rf ./data/pg_data/*
	rm -rf ./data/qdrant_data/*
	@echo "Data wiped. System lean."

# 🎯 CLEAN VECTOR DB: Wipes specific Qdrant collections while services are running
clean-vector-db:
	@echo "Wiping Qdrant collections via API..."
	curl -s -X DELETE http://localhost:6333/collections/semantic_cache > /dev/null
	curl -s -X DELETE http://localhost:6333/collections/documents > /dev/null
	@echo "✅ Database collections reset successfully. They will be recreated on the next request."

# 🎯 RESET VECTOR DB: Wipes DATA but keeps the collections intact
reset-vector-db:
	@echo "Clearing all points from collections..."
	@curl -s -X POST http://localhost:6333/collections/semantic_cache/points/delete \
		-H "Content-Type: application/json" \
		-d '{"filter": {}}' > /dev/null
	@curl -s -X POST http://localhost:6333/collections/documents/points/delete \
		-H "Content-Type: application/json" \
		-d '{"filter": {}}' > /dev/null
	@echo "✅ Points cleared. Collections are still alive."


reset-semantic-cache:
	@echo "Clearing semantic cache collection..."
	@curl -s -X POST http://localhost:6333/collections/semantic_cache/points/delete \
		-H "Content-Type: application/json" \
		-d '{"filter": {}}' > /dev/null
	@echo "✅ Semantic cache cleared"

# 🧼 CLEAN FRONTEND: Wipes the Next.js cache
clean-frontend:
	@echo "Wiping Next.js cache..."
	rm -rf ./apps/frontend/.next
	@echo "✅ Frontend cache cleared."

# ☢️ Nuclear Cleanup (The "Emergency" Disk Space command)
prune:
	docker system prune -a --volumes -f

# 📋 View logs for the backend and worker
logs:
	docker compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE) logs -f backend worker

# 📊 Check service health
status:
	docker compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE) ps

# 📝 Help command to show available options
help:
	@echo "Nexus Monorepo Control Center:"
	@echo "  make up             			- Build and start services"
	@echo "  make down           			- Stop services"
	@echo "  make restart        			- Force rebuild and restart"
	@echo "  make reset-vector-db   		- Delete Qdrant collections without stopping containers"
	@echo "  make reset-semantic-cache   	- Delete semantic cache collection without stopping containers"
	@echo "  make clean-frontend 			- Wipe the Next.js .next cache"
	@echo "  make clean-data     			- Stop services and DELETE all DB/Vector data"
	@echo "  make prune          			- Deep clean Docker (Recover Disk Space)"
	@echo "  make status         			- View running services"