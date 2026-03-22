#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/telegram-ai-character"
CURRENT_DIR="${APP_ROOT}/current"
DEPLOY_DIR="${APP_ROOT}/deploy"
COMPOSE_FILE="${DEPLOY_DIR}/app.compose.yaml"
ARCHIVE_PATH="/tmp/telegram-ai-character-latest-lite.tar.gz"

if [[ ! -f "${ARCHIVE_PATH}" ]]; then
  echo "archive not found: ${ARCHIVE_PATH}" >&2
  exit 1
fi

if [[ ! -d "${CURRENT_DIR}" ]]; then
  echo "current dir not found: ${CURRENT_DIR}" >&2
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

BACKUP_DIR="${APP_ROOT}/current.bak.relationship.$(date +%Y%m%d%H%M%S)"
cp -a "${CURRENT_DIR}" "${BACKUP_DIR}"

tar -xzf "${ARCHIVE_PATH}" -C "${CURRENT_DIR}" --no-same-owner

cd "${DEPLOY_DIR}"
docker compose -f "${COMPOSE_FILE}" up -d --build api bot
docker compose -f "${COMPOSE_FILE}" ps api bot
