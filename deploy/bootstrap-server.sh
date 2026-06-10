#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/deploy/eam}"
REPO_URL="${REPO_URL:-https://github.com/zbbzbb123/eam.git}"
BRANCH="${BRANCH:-main}"

backup_dir=""

if [ -d "$APP_DIR/.git" ]; then
  echo "$APP_DIR is already a git checkout."
elif [ -e "$APP_DIR" ]; then
  backup_dir="${APP_DIR}.pre-github-$(date +%Y%m%d-%H%M%S)"
  mv "$APP_DIR" "$backup_dir"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

if [ -n "$backup_dir" ] && [ -f "$backup_dir/.env" ] && [ ! -f "$APP_DIR/.env" ]; then
  cp "$backup_dir/.env" "$APP_DIR/.env"
fi

cd "$APP_DIR"
bash deploy/server-deploy.sh
