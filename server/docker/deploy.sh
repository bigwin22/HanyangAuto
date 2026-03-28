#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-${SCRIPT_DIR}/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

required_commands=(docker)
for command in "${required_commands[@]}"; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Missing required command: ${command}" >&2
    exit 1
  fi
done

if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "docker compose or docker-compose is required" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Missing compose file: ${COMPOSE_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

required_env_vars=(
  GHCR_OWNER
  GHCR_USERNAME
  GHCR_TOKEN
  CONTAINER_NAME
  DOMAIN
  APP_DATA_DIR
  APP_LOGS_DIR
  DB_ENCRYPTION_KEY_B64
  SESSION_SECRET_B64
  ADMIN_INITIAL_PASSWORD
  INTERNAL_API_TOKEN
)

for env_var in "${required_env_vars[@]}"; do
  if [[ -z "${!env_var:-}" ]]; then
    echo "Missing required environment variable: ${env_var}" >&2
    exit 1
  fi
done

mkdir -p "${APP_DATA_DIR}" "${APP_LOGS_DIR}"

echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin

export IMAGE_TAG
export PROJECT_ROOT

"${DOCKER_COMPOSE[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" pull
"${DOCKER_COMPOSE[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d
"${DOCKER_COMPOSE[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps

docker image prune -f >/dev/null 2>&1 || true
