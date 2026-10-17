#!/usr/bin/env bash
# scripts/run-android-emulator.sh — build a debug APK, boot an Android emulator,
# and launch the app against the local backend.
#
# Usage:
#   ./scripts/run-android-emulator.sh [avd-name]
#
# Environment:
#   API_URL   Backend URL baked in as the first-launch default.
#             Default: https://localhost:8089 (forwarded to the Mac via `adb reverse`,
#             so the hostname matches the self-signed cert in certs/).
#   SKIP_WEB  Set to 1 to skip rebuilding the frontend bundle.
#   EMULATOR_GPU
#             GPU renderer passed via `-gpu`. Default: swiftshader_indirect (software).
#             `-gpu host` renders fine guest-side but presents a black window on
#             macOS 26 + emulator 37.1.11 (gfxstream host presentation broken),
#             so software rendering is the stable default for now.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
API_URL="${API_URL:-https://localhost:8089}"
BACKEND_PORT="${BACKEND_PORT:-8089}"
APP_ID="com.hobbyland.pricecompare"

export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-${HOME}/Library/Android/sdk}}"
[[ -d "${ANDROID_HOME}" ]] || { echo "ERROR: Android SDK not found at ${ANDROID_HOME}" >&2; exit 1; }
ADB="${ANDROID_HOME}/platform-tools/adb"
EMULATOR="${ANDROID_HOME}/emulator/emulator"

AVD="${1:-$("${EMULATOR}" -list-avds | head -1)}"
[[ -n "${AVD}" ]] || { echo "ERROR: no AVD found. Create one in Android Studio > Device Manager." >&2; exit 1; }

if [[ "${SKIP_WEB:-0}" != "1" ]]; then
  echo "==> Building frontend (API: ${API_URL})"
  VITE_API_BASE_URL="${API_URL}" pnpm --filter frontend exec tsc -p tsconfig.json
  VITE_API_BASE_URL="${API_URL}" pnpm --filter frontend exec vite build
  pnpm --filter mobile exec cap sync android
fi

DEV_CERT_DIR="mobile/android/app/src/debug/res/raw"
mkdir -p "${DEV_CERT_DIR}"
if [[ -f certs/server.pem ]]; then
  # Refresh the committed debug trust anchor (public cert only).
  cp certs/server.pem "${DEV_CERT_DIR}/dev_server_cert.pem"
else
  echo "WARN: certs/server.pem missing — run scripts/generate-cert.sh; HTTPS to the backend will fail." >&2
fi

echo "==> Building debug APK"
(cd mobile/android && ./gradlew assembleDebug --build-cache --parallel -q)
APK="${ROOT_DIR}/mobile/android/app/build/outputs/apk/debug/app-debug.apk"

if ! "${ADB}" devices | grep -q "emulator-.*device$"; then
  echo "==> Booting emulator: ${AVD}"
  nohup "${EMULATOR}" -avd "${AVD}" -gpu "${EMULATOR_GPU:-swiftshader_indirect}" -netdelay none -netspeed full >/tmp/android-emulator.log 2>&1 &
fi

echo "==> Waiting for emulator to finish booting"
"${ADB}" wait-for-device
until [[ "$("${ADB}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; do sleep 2; done

echo "==> Forwarding emulator localhost:${BACKEND_PORT} -> Mac localhost:${BACKEND_PORT}"
"${ADB}" reverse "tcp:${BACKEND_PORT}" "tcp:${BACKEND_PORT}"

echo "==> Installing and launching ${APP_ID}"
"${ADB}" install -r "${APK}" >/dev/null
"${ADB}" shell am force-stop "${APP_ID}"
"${ADB}" shell monkey -p "${APP_ID}" -c android.intent.category.LAUNCHER 1 >/dev/null

echo "==> Running. Inspect the WebView at chrome://inspect in desktop Chrome."
echo "    Logs: ${ADB} logcat | grep -i -E 'Capacitor|chromium'"
