
#!/bin/bash
set -Eeuo pipefail
umask 077

RUN_USER="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

PROJECT_DIR="$USER_HOME/Securico-VideoEdgeBox"
DEST_DIR="$PROJECT_DIR/templates"
DEST_FILE="$DEST_DIR/network.html"

BASE_URL="https://raw.githubusercontent.com/Ashu300591/Securico-VideoEdgeBox-update/main"
WORK_DIR=""

cleanup() {
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf -- "$WORK_DIR"
    fi
}
trap cleanup EXIT

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

echo "=== Securico Network Page Updater ==="

[[ -d "$PROJECT_DIR" ]] || fail "Project folder not found."
command -v curl >/dev/null 2>&1 || fail "curl is not installed."

WORK_DIR="$(mktemp -d)"

echo "[1/3] Downloading network.html..."

curl -fsSL --retry 3 --connect-timeout 15 \
    "$BASE_URL/network.html" \
    -o "$WORK_DIR/network.html" ||
    fail "Download failed."

[[ -s "$WORK_DIR/network.html" ]] ||
    fail "Downloaded file is empty."

echo "[2/3] Preparing destination..."
mkdir -p "$DEST_DIR"

echo "[3/3] Installing network.html..."

TEMP_FILE="$(mktemp "$DEST_DIR/.network.html.XXXXXX")"
trap 'rm -f -- "${TEMP_FILE:-}"; cleanup' EXIT

install -m 644 "$WORK_DIR/network.html" "$TEMP_FILE"

if [[ -n "${SUDO_USER:-}" ]]; then
    chown "$RUN_USER:$(id -gn "$RUN_USER")" "$TEMP_FILE"
fi

mv -f -- "$TEMP_FILE" "$DEST_FILE"
TEMP_FILE=""

echo "SUCCESS: $DEST_FILE updated."
