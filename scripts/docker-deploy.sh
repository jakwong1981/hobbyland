#!/usr/bin/env bash
# scripts/docker-deploy.sh — build (optional), force-recreate the container, health-check, and optionally import CSVs
#
# Usage:
#   scripts/docker-deploy.sh                  # recreate the container from hobbyland-app:latest
#   scripts/docker-deploy.sh --build          # rebuild the image first
#   scripts/docker-deploy.sh --import         # recreate, then import CSVs into the container
#   scripts/docker-deploy.sh --build --import # both
#
# The Docker daemon is started when it is not answering (Docker Desktop / OrbStack
# on macOS, the docker service on Linux). Any container already holding the service
# is removed and recreated from scratch, so a stale container can never keep serving
# an old image or keep the published port bound. `docker compose down` is safe here:
# the database is a bind mount on ./data, not a named volume.
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-8089}"
SERVICE="app"
APP_URL="https://localhost:${PORT}"
DAEMON_WAIT_S="${DAEMON_WAIT_S:-90}"
HEALTH_WAIT_S="${HEALTH_WAIT_S:-30}"
BUILD=0
IMPORT=0

for arg in "$@"; do
  case "$arg" in
    --build)  BUILD=1 ;;
    --import) IMPORT=1 ;;
    *) echo "Unknown option: $arg (usage: $0 [--build] [--import])" >&2; exit 2 ;;
  esac
done

# compose derives the project name from the directory, and the container from
# <project>-<service>-<index>; reproduce it so a leftover container from an older
# project label can still be found and removed by name.
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$PWD" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')}"
CONTAINER_NAME="${PROJECT_NAME}-${SERVICE}-1"

docker_daemon_up() {
  docker info >/dev/null 2>&1
}

launch_desktop_docker() {
  local app
  for app in Docker OrbStack; do
    if [ -d "/Applications/${app}.app" ]; then
      echo "==> Launching ${app}"
      open -a "$app"
      return 0
    fi
  done
  return 1
}

wait_for_daemon() {
  local i
  for i in $(seq 1 "$DAEMON_WAIT_S"); do
    if docker_daemon_up; then
      echo "==> Docker daemon ready after ${i}s"
      return 0
    fi
    sleep 1
  done
  echo "!! Docker daemon did not become ready in ${DAEMON_WAIT_S}s" >&2
  exit 1
}

ensure_docker_daemon() {
  if docker_daemon_up; then
    echo "==> Docker daemon is running"
    return 0
  fi

  echo "==> Docker daemon is not responding — starting it"
  case "$(uname)" in
    Darwin)
      launch_desktop_docker || {
        echo "!! Install/launch Docker Desktop or OrbStack manually, then re-run" >&2
        exit 1
      }
      ;;
    *)
      if command -v systemctl >/dev/null 2>&1; then
        systemctl start docker 2>/dev/null || sudo systemctl start docker
      else
        echo "!! No known way to start Docker on this platform — start it manually, then re-run" >&2
        exit 1
      fi
      ;;
  esac
  wait_for_daemon
}

remove_existing_container() {
  echo "==> Tearing down any existing stack (project '${PROJECT_NAME}')"
  docker compose down --remove-orphans --timeout 10 >/dev/null 2>&1 || true

  if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "==> Removing leftover container ${CONTAINER_NAME}"
    docker rm -f "$CONTAINER_NAME" >/dev/null
  fi
}

wait_until_healthy() {
  local i
  echo "==> Waiting for ${APP_URL} to become healthy"
  for i in $(seq 1 "$HEALTH_WAIT_S"); do
    # -k: the container serves a self-signed certificate at this phase
    if curl -kfsS "${APP_URL}/api/imports" > /dev/null 2>&1; then
      echo "==> Healthy after ${i}s"
      return 0
    fi
    sleep 1
  done
  echo "!! Service did not become healthy in ${HEALTH_WAIT_S}s; recent logs:" >&2
  docker compose ps >&2
  docker compose logs --tail 30 >&2
  exit 1
}

ensure_docker_daemon

if [ "$BUILD" -eq 1 ]; then
  "$(dirname "$0")/docker-build.sh"
fi

# Resolve before `up` so the read-only /csvs bind mount is correct on the first
# create; re-running `up` afterwards would only recreate the container again.
if [ "$IMPORT" -eq 1 ]; then
  CSV_DIR="${CSV_DIR:-$HOME/github/python_program}"
  if [ ! -d "$CSV_DIR" ]; then
    echo "!! CSV_DIR not found: $CSV_DIR" >&2
    exit 1
  fi
  export CSV_DIR
fi

# The stack serves HTTPS using a self-signed certificate mounted from ./certs.
if [ ! -f certs/server.pem ] || [ ! -f certs/server-key.pem ]; then
  echo "==> No TLS certificate found in ./certs — generating a self-signed one"
  "$(dirname "$0")/generate-cert.sh"
fi

remove_existing_container

echo "==> Starting stack (docker compose up -d --force-recreate)"
docker compose up -d --force-recreate --remove-orphans

wait_until_healthy

if [ "$IMPORT" -eq 1 ]; then
  echo "==> Importing CSVs from ${CSV_DIR} (mounted read-only at /csvs)"
  docker compose exec -T "$SERVICE" node backend/dist/cli/import.js --dir /csvs
fi

echo "==> Deployed: ${APP_URL}"
if [ -f .env ] && grep -q '^DOMAIN=' .env; then
  echo "==> Public URL: https://$(sed -n 's/^DOMAIN=//p' .env) (via Caddy, Let's Encrypt)"
fi
docker compose ps
