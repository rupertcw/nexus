.PHONY: up down restart clean-data prune logs status

# 🚀 Start everything in the background
up:
	docker compose up -d --build
	@echo "Checking for dangling images to save space..."
	docker image prune -f

# 🛑 Stop services but keep your data (pg_data, qdrant_data)
down:
	docker compose down --remove-orphans

# 🔄 Rebuild and Restart (Useful when you change backend code)
restart:
	docker compose up -d --build --force-recreate
	docker image prune -f

# 🧹 THE SPACE SAVER: Stops everything and WIPES all databases
# This targets the specific folders in your compose file
clean-data:
	docker compose down -v --remove-orphans
	@echo "Wiping local data directories..."
	rm -rf ./pg_data/*
	rm -rf ./qdrant_data/*
	rm -rf ./data/*
	@echo "Data wiped. System lean."

# ☢️ Nuclear Cleanup (The "Emergency" Disk Space command)
prune:
	docker system prune -a --volumes -f

# 📋 View logs for the backend and worker (the most important ones)
logs:
	docker compose logs -f backend worker

# 📊 Check service health
status:
	docker compose ps