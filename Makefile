.PHONY: all data train engine optimise test test-core test-api test-frontend dev-api dev-frontend build up down clean app

PYTHON ?= python
PYTEST ?= pytest
STREAMLIT ?= streamlit
NPM ?= npm
DOCKER_COMPOSE ?= docker compose

all: data train engine optimise test

data:
	$(PYTHON) -m src.data.build_data_layer

train:
	$(PYTHON) -m src.models.train_impact_model

engine:
	$(PYTHON) -m src.engine.run_simulation

optimise:
	$(PYTHON) -m src.optimise

test-core:
	$(PYTEST) tests/test_core.py -v

test-api:
	$(PYTEST) tests_api/ -v

test-frontend:
	cd frontend && $(NPM) test

test: test-core test-api test-frontend

dev-api:
	$(PYTHON) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && $(NPM) run dev

app:
	$(STREAMLIT) run app.py

build:
	$(DOCKER_COMPOSE) build

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

clean:
	rm -rf __pycache__ src/__pycache__ tests/__pycache__ api/__pycache__ tests_api/__pycache__ .pytest_cache data/interim/* data/processed/* models/*.joblib frontend/dist frontend/node_modules/.vite
