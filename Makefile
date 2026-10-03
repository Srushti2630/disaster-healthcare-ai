.PHONY: data train engine optimise test app all clean

PYTHON = ./.venv/bin/python
PYTEST = ./.venv/bin/pytest
STREAMLIT = ./.venv/bin/streamlit

all: data train engine optimise test

data:
	$(PYTHON) -m src.data.build_data_layer

train:
	$(PYTHON) -m src.models.train_impact_model

engine:
	$(PYTHON) -m src.engine.run_simulation

optimise:
	$(PYTHON) -m src.optimise

test:
	$(PYTEST) -v

app:
	$(STREAMLIT) run app.py

clean:
	rm -rf __pycache__ src/__pycache__ tests/__pycache__ .pytest_cache data/interim/* data/processed/* models/*.joblib
