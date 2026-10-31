# Revizo monorepo — convenience glue only.
# The Python server (server/) and React app (web/) are independent packages;
# this Makefile just orchestrates the two. Neither depends on the other at build time.

SERVER_DIR := server
WEB_DIR := web
PORT := 8000

.PHONY: install install-server install-web dev build serve test-server clean

install: install-server install-web

install-server:
	cd $(SERVER_DIR) && uv sync

install-web:
	cd $(WEB_DIR) && npm install

## Build the React app and copy it into server/static (served by FastAPI).
build:
	cd $(WEB_DIR) && npm run build
	rm -rf $(SERVER_DIR)/static
	mkdir -p $(SERVER_DIR)/static
	cp -r $(WEB_DIR)/dist/. $(SERVER_DIR)/static/

## Run both: FastAPI on :8000 (--reload) and Vite dev on :5173 (proxies /api to :8000).
dev:
	@cd $(SERVER_DIR) && uv run uvicorn main:app --port $(PORT) --reload & \
	SERVER_PID=$$! ; \
	cd $(WEB_DIR) && npm run dev ; \
	kill $$SERVER_PID 2>/dev/null || true

## Production-style: serve the built SPA + API from FastAPI alone (run `make build` first).
serve: build
	cd $(SERVER_DIR) && uv run uvicorn main:app --port $(PORT)

test-server:
	cd $(SERVER_DIR) && uv run pytest -q

clean:
	rm -rf $(WEB_DIR)/dist $(SERVER_DIR)/static
