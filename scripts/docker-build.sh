#!/usr/bin/env bash
# scripts/docker-build.sh — build the hobbyland-app Docker image
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE_NAME="${IMAGE_NAME:-hobbyland-app}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"

echo "==> Building ${IMAGE_NAME}:latest (tag ${IMAGE_TAG})"
docker build -t "${IMAGE_NAME}:latest" -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "==> Done. Images:"
docker images "${IMAGE_NAME}" --format '  {{.Repository}}:{{.Tag}}  ({{.Size}})'
