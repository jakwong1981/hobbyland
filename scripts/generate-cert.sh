#!/usr/bin/env bash
# scripts/generate-cert.sh — create a self-signed TLS certificate for local HTTPS
#
# Usage:
#   scripts/generate-cert.sh            # writes certs/server.pem + certs/server-key.pem
#   CERT_DIR=/elsewhere scripts/generate-cert.sh
#
# Idempotent: existing certificates are kept; delete them to regenerate. The cert
# is valid for localhost / 127.0.0.1 and is for development use only — browsers
# will warn until it is trusted.
set -euo pipefail

cd "$(dirname "$0")/.."

CERT_DIR="${CERT_DIR:-certs}"
CERT_FILE="${CERT_DIR}/server.pem"
KEY_FILE="${CERT_DIR}/server-key.pem"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "==> Certificate already exists at ${CERT_DIR}/ — skipping (delete to regenerate)"
  exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "!! openssl not found — install it (e.g. brew install openssl), then re-run" >&2
  exit 1
fi

mkdir -p "$CERT_DIR"

# 825 days is the maximum validity Apple platforms accept for self-signed certs.
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -days 825 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$KEY_FILE"

echo "==> Self-signed certificate written to ${CERT_DIR}/ (CN=localhost, SAN: localhost, 127.0.0.1)"
