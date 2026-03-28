.PHONY: backend frontend test install

# Backend
install:
	cd apps/backend && pip install -r requirements.txt

backend:
	cd apps/backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
frontend:
	cd apps/frontend && npm run dev

# Tests
test:
	cd apps/backend && python -m pytest app/tests/ -v

# Run both
dev:
	@echo "Run 'make backend' and 'make frontend' in separate terminals"
