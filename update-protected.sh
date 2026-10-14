
#!/bin/bash
set -Eeuo pipefail
umask 077

RUN_USER="${SUDO_USER:-mackennas}"
USER_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

PROJECT_DIR="$USER_HOME/Securico-VideoEdgeBox"
BASE_URL="https://raw.githubusercontent.com/Ashu300591/Securico-VideoEdgeBox-update/main"

WORK_DIR=""

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf -- "$WORK_DIR"
    fi
}
trap cleanup EXIT

echo "======================================"
echo " Securico VideoEdgeBox File Updater"
echo "======================================"

[[ -d "$PROJECT_DIR" ]] || fail "Project folder not found: $PROJECT_DIR"
command -v curl >/dev/null 2>&1 || fail "curl is not installed."

WORK_DIR="$(mktemp -d "$PROJECT_DIR/.update-tmp.XXXXXX")"
mkdir -p "$WORK_DIR/download" "$WORK_DIR/backup"

# Repository path|destination path relative to project
FILES=(
    "app.py|app.py"
    "listener.py|listener.py"
    "templates/network.html|templates/network.html"
)

echo
echo "[1/3] Downloading files from GitHub..."

for entry in "${FILES[@]}"; do
    source="${entry%%|*}"
    destination="${entry#*|}"

    mkdir -p "$WORK_DIR/download/$(dirname "$destination")"

    if ! curl -fsSL --retry 3 --connect-timeout 15 \
        "$BASE_URL/$source" \
        -o "$WORK_DIR/download/$destination"; then
        fail "Could not download $source. Existing application files were not changed."
    fi

    [[ -s "$WORK_DIR/download/$destination" ]] ||
        fail "Downloaded file is empty: $source"
done

echo
echo "[2/3] Backing up existing files..."

for entry in "${FILES[@]}"; do
    destination="${entry#*|}"
    current="$PROJECT_DIR/$destination"

    if [[ -f "$current" ]]; then
        mkdir -p "$WORK_DIR/backup/$(dirname "$destination")"
        cp -a "$current" "$WORK_DIR/backup/$destination"
    fi
done

rollback() {
    echo "Installation failed. Attempting rollback..."

    for entry in "${FILES[@]}"; do
        destination="${entry#*|}"
        current="$PROJECT_DIR/$destination"
        backup="$WORK_DIR/backup/$destination"

        if [[ -f "$backup" ]]; then
            cp -a "$backup" "$current" || true
        elif [[ -f "$WORK_DIR/download/$destination" ]]; then
            rm -f "$current" || true
        fi
    done
}

echo
echo "[3/3] Installing updated files..."

mkdir -p "$PROJECT_DIR/templates"

for entry in "${FILES[@]}"; do
    destination="${entry#*|}"

    if ! install -m 644 \
        "$WORK_DIR/download/$destination" \
        "$PROJECT_DIR/$destination"; then
        rollback
        fail "Installation failed. Rollback was attempted."
    fi
done

chmod 755 "$PROJECT_DIR/app.py" "$PROJECT_DIR/listener.py"

chown "$RUN_USER:$(id -gn "$RUN_USER")" \
    "$PROJECT_DIR/app.py" \
    "$PROJECT_DIR/listener.py" \
    "$PROJECT_DIR/templates/network.html"

echo
echo "======================================"
echo " UPDATE COMPLETED SUCCESSFULLY"
echo "======================================"
echo "Updated: app.py"
echo "Updated: listener.py"
echo "Updated: templates/network.html"
echo "PyArmor: NOT USED"
echo "Encryption: NOT PERFORMED"
echo "Application services: NOT RESTARTED"
echo "======================================"
