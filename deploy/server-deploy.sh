#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/deploy/eam}"
BRANCH="${BRANCH:-main}"
PROJECT_NAME="${PROJECT_NAME:-eam}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

cd "$APP_DIR"

if [ ! -d .git ]; then
  echo "$APP_DIR is not a git checkout. Run deploy/bootstrap-server.sh first." >&2
  exit 1
fi

git fetch --prune origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

if [ ! -f .env ]; then
  echo "Missing $APP_DIR/.env; refusing to deploy without production secrets." >&2
  exit 1
fi

docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" config --quiet
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build --remove-orphans
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps
