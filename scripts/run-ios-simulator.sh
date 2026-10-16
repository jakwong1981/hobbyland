#!/usr/bin/env bash
# scripts/run-ios-simulator.sh — build a debug iOS Simulator .app, boot the
# iOS Simulator, trust certs/server.pem, and launch the app against the local backend.
#
# Usage:
#   ./scripts/run-ios-simulator.sh [simulator-name-or-udid]
#
# Environment:
#   API_URL        Backend URL baked in as the first-launch default.
#                  Default: https://localhost:8089 (if certs/server.pem exists)
#                  or http://localhost:8089
#   IOS_SIMULATOR  Simulator device name or UDID (can also be passed as $1).
#                  Default: first booted simulator or first available iPhone.
#   SKIP_WEB       Set to 1 to skip rebuilding the frontend bundle + cap sync.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
APP_ID="com.hobbyland.pricecompare"

if [[ -z "${API_URL:-}" ]]; then
  if [[ -f "${ROOT_DIR}/certs/server.pem" ]]; then
    API_URL="https://localhost:8089"
  else
    API_URL="http://localhost:8089"
  fi
fi

# Auto-discover Homebrew and user gem binaries (e.g. ~/.gem/ruby/*/bin/pod)
for bin_dir in /opt/homebrew/bin /usr/local/bin "${HOME}"/.gem/ruby/*/bin; do
  [[ -d "${bin_dir}" ]] && PATH="${bin_dir}:${PATH}"
done
export PATH

# Auto-configure DEVELOPER_DIR when xcode-select points to CommandLineTools instead of Xcode.app
if [[ "$(uname -s)" == "Darwin" ]] && ! xcodebuild -version >/dev/null 2>&1; then
  if [[ -d "/Applications/Xcode.app/Contents/Developer" ]]; then
    export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
  fi
fi

[[ "$(uname -s)" == "Darwin" ]] || {
  echo "ERROR: iOS Simulator requires macOS with Xcode installed." >&2
  exit 1
}
xcodebuild -version >/dev/null 2>&1 || {
  echo "ERROR: xcodebuild not functional. Install Xcode.app in /Applications/Xcode.app." >&2
  exit 1
}

if [[ "${SKIP_WEB:-0}" != "1" ]]; then
  command -v pod >/dev/null 2>&1 || {
    echo "ERROR: CocoaPods not found. Install with: brew install cocoapods" >&2
    exit 1
  }
  echo "==> Building frontend (API: ${API_URL})"
  VITE_API_BASE_URL="${API_URL}" pnpm --filter frontend exec tsc -p tsconfig.json
  VITE_API_BASE_URL="${API_URL}" pnpm --filter frontend exec vite build
  if [[ ! -d mobile/ios ]]; then
    pnpm --filter mobile exec cap add ios
  fi
  pnpm --filter mobile exec cap sync ios
fi

SIM_DERIVED="${ROOT_DIR}/mobile/ios/build/sim"
echo "==> Building Debug iOS Simulator app"
xcodebuild -workspace "${ROOT_DIR}/mobile/ios/App/App.xcworkspace" \
  -scheme App \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath "${SIM_DERIVED}" \
  COMPILER_INDEX_STORE_ENABLE=NO \
  -quiet \
  build

SIM_APP="${SIM_DERIVED}/Build/Products/Debug-iphonesimulator/App.app"
REQUESTED_SIM="${1:-${IOS_SIMULATOR:-}}"
SIM_UDID=""

if [[ -n "${REQUESTED_SIM}" ]]; then
  SIM_UDID="$(xcrun simctl list devices available | grep -F "${REQUESTED_SIM}" | grep -Eo '[0-9A-F]{8}-([0-9A-F]{4}-){3}[0-9A-F]{12}' | head -1 || true)"
fi
if [[ -z "${SIM_UDID}" ]]; then
  SIM_UDID="$(xcrun simctl list devices booted | grep -Eo '[0-9A-F]{8}-([0-9A-F]{4}-){3}[0-9A-F]{12}' | head -1 || true)"
fi
if [[ -z "${SIM_UDID}" ]]; then
  SIM_UDID="$(xcrun simctl list devices available | grep -E 'iPhone' | grep -Eo '[0-9A-F]{8}-([0-9A-F]{4}-){3}[0-9A-F]{12}' | head -1 || true)"
fi
[[ -n "${SIM_UDID}" ]] || {
  echo "ERROR: No available iPhone simulator found in Xcode." >&2
  exit 1
}

echo "==> Booting iOS Simulator (${SIM_UDID})"
xcrun simctl boot "${SIM_UDID}" >/dev/null 2>&1 || true
SIM_APP_BUNDLE="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}/Applications/Simulator.app"
if [[ -d "${SIM_APP_BUNDLE}" ]]; then
  open -a "${SIM_APP_BUNDLE}" --args -CurrentDeviceUDID "${SIM_UDID}"
else
  open -a Simulator --args -CurrentDeviceUDID "${SIM_UDID}"
fi
xcrun simctl bootstatus "${SIM_UDID}" -b

if [[ -f "${ROOT_DIR}/certs/server.pem" ]]; then
  echo "==> Trusting certs/server.pem in iOS Simulator keychain"
  xcrun simctl keychain "${SIM_UDID}" add-root-cert "${ROOT_DIR}/certs/server.pem" >/dev/null 2>&1 || true
fi

echo "==> Installing and launching ${APP_ID}"
xcrun simctl install "${SIM_UDID}" "${SIM_APP}"
xcrun simctl terminate "${SIM_UDID}" "${APP_ID}" >/dev/null 2>&1 || true
xcrun simctl launch "${SIM_UDID}" "${APP_ID}"

echo "==> Running on Simulator (${SIM_UDID})."
echo "    Inspect WebView: Safari > Develop > Simulator > localhost"
echo "    Screenshot:      DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl io ${SIM_UDID} screenshot /tmp/ios.png"
