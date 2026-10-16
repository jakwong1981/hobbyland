#!/usr/bin/env bash
# scripts/build-mobile.sh — build the hybrid Android APK and/or iOS IPA, and
# (for `ios`) optionally boot, trust certs, install, and launch in iOS Simulator.
#
# Usage:
#   ./scripts/build-mobile.sh <android|ios|all>
#
# Environment:
#   API_URL          Default backend URL baked into the app as the first-launch
#                    default (runtime-overridable via the in-app 伺服器 setting).
#                    Default: https://localhost:8089 (if certs/server.pem exists)
#                    or http://localhost:8089
#   ANDROID_KEYSTORE            Android release signing (optional). Path to a
#   ANDROID_KEYSTORE_PASSWORD   keystore; when set, ANDROID_KEYSTORE_PASSWORD and
#   ANDROID_KEY_ALIAS           ANDROID_KEY_ALIAS are required and the APK is
#   ANDROID_KEYSTORE_KEY_PASSWORD  signed with them (store-publishable). Without
#                                them the APK is signed with the debug keystore:
#                                installable via adb, not publishable to Play Store.
#   EXPORT_METHOD    iOS export method: development | ad-hoc | app-store | enterprise.
#                    Default: development
#   EXPORT_TEAM_ID   iOS signing team id (optional; Xcode auto-signing picks the
#                    local team when omitted).
#   ALLOW_UNSIGNED_IPA  Set to 1 to fall back to an unsigned IPA when the signed
#                    archive/export fails. Unsigned IPAs must be re-signed by the
#                    install tool (AltStore/Sideloadly) before use on a device.
#   LAUNCH_SIMULATOR For `ios`: 1 (default) builds, installs, trusts certs/server.pem,
#                    and launches the app in the iOS Simulator; set to 0 to skip.
#   IOS_SIMULATOR    Simulator device name or UDID (default: first booted or first
#                    available iPhone simulator, e.g. "iPhone 17 Pro").
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
DIST_DIR="${ROOT_DIR}/dist-mobile"
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

TARGET="${1:-}"
if [[ "${TARGET}" != "android" && "${TARGET}" != "ios" && "${TARGET}" != "all" ]]; then
  echo "Usage: $0 <android|ios|all>" >&2
  echo "  API_URL=https://your-host:8089 $0 all" >&2
  exit 2
fi

echo "==> Building frontend with default API URL: ${API_URL}"
VITE_API_BASE_URL="${API_URL}" pnpm --filter frontend exec tsc -p tsconfig.json
VITE_API_BASE_URL="${API_URL}" pnpm --filter frontend exec vite build

require_cocoapods() {
  command -v pod >/dev/null 2>&1 || {
    echo "ERROR: CocoaPods not found. Install with: brew install cocoapods (or gem install --user-install cocoapods)" >&2
    exit 1
  }
}

sync_platform() {
  echo "==> Syncing Capacitor shell: $1"
  pnpm --filter mobile exec cap sync "$1"
}

case "${TARGET}" in
  android) sync_platform android ;;
  ios) require_cocoapods; sync_platform ios ;;
  all)
    sync_platform android
    if [[ "$(uname -s)" == "Darwin" ]]; then
      require_cocoapods
      sync_platform ios
    fi
    ;;
esac

mkdir -p "${DIST_DIR}"
STAMP="$(date +%Y%m%d-%H%M%S)"

build_android() {
  command -v java >/dev/null 2>&1 || {
    echo "ERROR: java not found. Install JDK 21+ (e.g. brew install --cask temurin@21)." >&2
    exit 1
  }
  if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
    for candidate in "${HOME}/Library/Android/sdk" "${HOME}/Android/Sdk"; do
      [[ -d "${candidate}" ]] && export ANDROID_HOME="${candidate}" && break
    done
  fi
  if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
    echo "ERROR: Android SDK not found. Set ANDROID_HOME (e.g. ~/Library/Android/sdk)." >&2
    exit 1
  fi

  echo "==> Building Android release APK"
  local sign_args=()
  if [[ -n "${ANDROID_KEYSTORE:-}" ]]; then
    if [[ -z "${ANDROID_KEYSTORE_PASSWORD:-}" || -z "${ANDROID_KEY_ALIAS:-}" ]]; then
      echo "ERROR: ANDROID_KEYSTORE set but ANDROID_KEYSTORE_PASSWORD / ANDROID_KEY_ALIAS missing." >&2
      exit 1
    fi
    sign_args=(
      -P "RELEASE_STORE_FILE=${ANDROID_KEYSTORE}"
      -P "RELEASE_STORE_PASSWORD=${ANDROID_KEYSTORE_PASSWORD}"
      -P "RELEASE_KEY_ALIAS=${ANDROID_KEY_ALIAS}"
      -P "RELEASE_KEY_PASSWORD=${ANDROID_KEYSTORE_KEY_PASSWORD:-${ANDROID_KEYSTORE_PASSWORD}}"
    )
    echo "    Signing with keystore: ${ANDROID_KEYSTORE} (alias: ${ANDROID_KEY_ALIAS})"
  else
    echo "    No ANDROID_KEYSTORE configured — APK will be signed with the debug keystore (sideload-ready, not store-publishable)." >&2
  fi
  (cd mobile/android && ./gradlew assembleRelease --build-cache --parallel ${sign_args[@]+"${sign_args[@]}"})

  local apk
  apk="$(ls mobile/android/app/build/outputs/apk/release/*.apk | head -1)"
  cp "${apk}" "${DIST_DIR}/hobbyland-android-${STAMP}.apk"
  echo "==> APK: dist-mobile/hobbyland-android-${STAMP}.apk"
  echo "    Install with: adb install -r ${DIST_DIR}/hobbyland-android-${STAMP}.apk"
}

package_unsigned_ipa() {
  local derived="${ROOT_DIR}/mobile/ios/build/device"
  local payload_dir="${ROOT_DIR}/mobile/ios/build/payload"
  local out_ipa="${DIST_DIR}/hobbyland-ios-${STAMP}.ipa"

  echo "==> Building iOS release bundle (unsigned IPA — no Apple signing identity or team detected)"
  echo "    NOTE: unsigned IPAs cannot be installed on a device until re-signed by the install tool (AltStore/Sideloadly)." >&2
  xcodebuild -workspace "${ROOT_DIR}/mobile/ios/App/App.xcworkspace" \
    -scheme App \
    -configuration Release \
    -sdk iphoneos \
    -destination 'generic/platform=iOS' \
    -derivedDataPath "${derived}" \
    CODE_SIGN_IDENTITY="" \
    CODE_SIGNING_REQUIRED=NO \
    CODE_SIGNING_ALLOWED=NO \
    COMPILER_INDEX_STORE_ENABLE=NO \
    -quiet \
    build

  rm -rf "${payload_dir}"
  mkdir -p "${payload_dir}/Payload"
  cp -R "${derived}/Build/Products/Release-iphoneos/App.app" "${payload_dir}/Payload/App.app"
  ditto -c -k --sequesterRsrc --keepParent "${payload_dir}/Payload" "${out_ipa}"
  rm -rf "${payload_dir}"
  echo "==> IPA (unsigned): dist-mobile/hobbyland-ios-${STAMP}.ipa"
}

build_ios() {
  [[ "$(uname -s)" == "Darwin" ]] || {
    echo "ERROR: iOS builds require macOS with Xcode installed." >&2
    exit 1
  }
  xcodebuild -version >/dev/null 2>&1 || {
    echo "ERROR: xcodebuild not functional. Install Xcode.app in /Applications/Xcode.app." >&2
    exit 1
  }

  if [[ ! -d mobile/ios ]]; then
    echo "==> iOS platform missing — adding it"
    require_cocoapods
    pnpm --filter mobile exec cap add ios
    pnpm --filter mobile exec cap sync ios
  fi

  mkdir -p "${ROOT_DIR}/mobile/ios/build"

  local has_signing_identity=0
  if ! security find-identity -v -p codesigning 2>/dev/null | grep -q "0 valid identities found"; then
    has_signing_identity=1
  fi

  if [[ "${has_signing_identity}" == "1" || -n "${EXPORT_TEAM_ID:-}" ]]; then
    local method="${EXPORT_METHOD:-development}"
    local archive="${ROOT_DIR}/mobile/ios/build/App.xcarchive"
    local export_dir="${ROOT_DIR}/mobile/ios/build/export"
    local export_options="${ROOT_DIR}/mobile/ios/build/ExportOptions.plist"

    echo "==> Archiving signed iOS app (method: ${method})"
    rm -rf "${archive}" "${export_dir}"

    local team_plist=""
    if [[ -n "${EXPORT_TEAM_ID:-}" ]]; then
      team_plist="<key>teamID</key><string>${EXPORT_TEAM_ID}</string>"
    fi
    cat > "${export_options}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key><string>${method}</string>
  <key>signingStyle</key><string>automatic</string>
  <key>stripSwiftSymbols</key><true/>
  <key>thinning</key><string>&lt;none&gt;</string>
  ${team_plist}
</dict>
</plist>
PLIST

    local team_args=()
    if [[ -n "${EXPORT_TEAM_ID:-}" ]]; then
      # The checked-in Xcode project has no team configured — the env var must
      # reach the archive step too, not just the export options plist.
      team_args=("DEVELOPMENT_TEAM=${EXPORT_TEAM_ID}")
    fi

    if (cd mobile/ios/App \
      && xcodebuild -workspace App.xcworkspace -scheme App -configuration Release \
          -destination 'generic/platform=iOS' \
          -archivePath "${archive}" \
          -allowProvisioningUpdates \
          -parallelizeTargets \
          COMPILER_INDEX_STORE_ENABLE=NO \
          ${team_args[@]+"${team_args[@]}"} \
          -quiet \
          archive) && \
      xcodebuild -exportArchive \
        -archivePath "${archive}" \
        -exportOptionsPlist "${export_options}" \
        -exportPath "${export_dir}" \
        -allowProvisioningUpdates \
        -quiet; then
      local ipa
      ipa="$(ls "${export_dir}"/*.ipa | head -1)"
      cp "${ipa}" "${DIST_DIR}/hobbyland-ios-${STAMP}.ipa"
      echo "==> IPA: dist-mobile/hobbyland-ios-${STAMP}.ipa"
    elif [[ "${ALLOW_UNSIGNED_IPA:-0}" == "1" ]]; then
      echo "WARN: signed archive/export failed; ALLOW_UNSIGNED_IPA=1 set — falling back to an unsigned IPA build." >&2
      package_unsigned_ipa
    else
      echo "ERROR: signed archive/export failed. Fix the xcodebuild errors above (team id, signing cert, provisioning profile), or re-run with ALLOW_UNSIGNED_IPA=1 to force an unsigned IPA." >&2
      exit 1
    fi
  else
    package_unsigned_ipa
  fi

  local launch_sim="${LAUNCH_SIMULATOR:-}"
  if [[ -z "${launch_sim}" ]]; then
    [[ "${TARGET}" == "ios" ]] && launch_sim="1" || launch_sim="0"
  fi
  if [[ "${launch_sim}" == "1" ]]; then
    SKIP_WEB=1 "${ROOT_DIR}/scripts/run-ios-simulator.sh"
  fi
}

case "${TARGET}" in
  android) build_android ;;
  ios) build_ios ;;
  all)
    build_android
    if [[ "$(uname -s)" == "Darwin" ]]; then
      build_ios
    else
      echo "==> Skipping iOS build (not macOS)"
    fi
    ;;
esac

echo "==> Done. Artifacts in dist-mobile/:"
ls -lh "${DIST_DIR}" | tail -n +2
