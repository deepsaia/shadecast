.PHONY: sync lint test engine

sync:
	uv sync

lint:
	uv run ruff format
	uv run ruff check --fix
	uv run pyrefly check

test: lint
	uv run pytest tests/ -q

engine:
	uv venv --python 3.12 .venv-engine
	uv pip install --python .venv-engine solweig-gpu numba "gdal==$$(gdal-config --version)"
