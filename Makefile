.PHONY: install seed api web test lint build up down reset
install:
	python -m pip install -r backend/requirements.txt
	cd frontend && npm ci
seed:
	cd backend && python -m scripts.seed_demo
api:
	cd backend && uvicorn app.main:app --reload
web:
	cd frontend && npm run dev
test:
	cd backend && pytest -q
lint:
	cd backend && ruff check app tests scripts
	cd frontend && npm run lint
build:
	cd frontend && npm run build
up:
	docker compose up -d --build
down:
	docker compose down
reset:
	docker compose down -v && docker compose build --no-cache && docker compose up -d
