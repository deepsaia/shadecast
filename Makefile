.PHONY: sync lint test engine frontend frontend-test types

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

# The client. Node comes from .node-version (fnm use); pnpm from the packageManager field.
frontend:
	pnpm --dir frontend install --frozen-lockfile
	pnpm --dir frontend build

frontend-test:
	pnpm --dir frontend install --frozen-lockfile
	pnpm --dir frontend lint
	pnpm --dir frontend typecheck
	pnpm --dir frontend test

# The client's types come from the server's schema, so the contract is written once, in pydantic.
types:
	mkdir -p out
	uv run python -m shadecast.server.openapi > out/openapi.json
	pnpm --dir frontend types
