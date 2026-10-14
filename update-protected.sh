sudo tee /usr/local/bin/update-protected >/dev/null <<'SCRIPT'
#!/bin/bash
set -Eeuo pipefail
umask 077

# Resolve the actual user's home directory,
# even when the updater is executed with sudo.
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
    USER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
else
    USER_HOME="$HOME"
fi

PROJECT_DIR="$USER_HOME/Securico-VideoEdgeBox"
BASE_URL="https://raw.githubusercontent.com/Ashu300591/Securico-VideoEdgeBox-update/main"

FILES=(
    "app.py"
    "listener.py"
    "templates/network.html"
)

WORK_DIR=""

fail() {
    echo
    echo "ERROR: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR"
    fi
}
trap cleanup EXIT

echo "======================================"
echo " Securico VideoEdgeBox File Updater"
echo "======================================"

[[ -d "$PROJECT_DIR" ]] ||
    fail "Project folder not found: $PROJECT_DIR"

command -v curl >/dev/null 2>&1 ||
    fail "curl is not installed."

WORK_DIR="$(mktemp -d "$PROJECT_DIR/.update-tmp.XXXXXX")"

mkdir -p "$WORK_DIR/backup" "$WORK_DIR/download"

echo
echo "[1/3] Downloading files from GitHub..."

# Download all files before modifying existing ones.
for file in "${FILES[@]}"; do

    echo "Downloading: $file"

    mkdir -p "$(dirname "$WORK_DIR/download/$file")"

    if ! curl -fsSL --connect-timeout 15 \
        --max-time 120 \
        "$BASE_URL/$file" \
        -o "$WORK_DIR/download/$file"; then

        fail "Could not download $file. Existing files are unchanged."
    fi

    [[ -s "$WORK_DIR/download/$file" ]] ||
        fail "Downloaded $file is empty."
done

echo
echo "[2/3] Backing up existing files..."

for file in "${FILES[@]}"; do

    if [[ -f "$PROJECT_DIR/$file" ]]; then

        mkdir -p "$(dirname "$WORK_DIR/backup/$file")"

        cp -a "$PROJECT_DIR/$file" \
              "$WORK_DIR/backup/$file"
    fi

done

echo
echo "[3/3] Installing updated files..."

rollback() {
    echo "Installation failed. Restoring previous files..."

    for file in "${FILES[@]}"; do
        if [[ -f "$WORK_DIR/backup/$file" ]]; then
            cp -a "$WORK_DIR/backup/$file" \
                  "$PROJECT_DIR/$file" || true
        else
            rm -f "$PROJECT_DIR/$file" || true
        fi
    done
}

for file in "${FILES[@]}"; do

    echo "Installing: $file"

    mkdir -p "$(dirname "$PROJECT_DIR/$file")"

    if ! install -m 755 \
        "$WORK_DIR/download/$file" \
        "$PROJECT_DIR/$file"; then

        rollback
        fail "Installation failed; rollback attempted."
    fi

done

# Restore ownership when run with sudo.
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
    chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" \
        "$PROJECT_DIR/app.py" \
        "$PROJECT_DIR/listener.py" \
        "$PROJECT_DIR/templates/network.html"
fi

echo
echo "======================================"
echo " UPDATE COMPLETED SUCCESSFULLY"
echo "======================================"
echo "Updated files:"
echo " - app.py"
echo " - listener.py"
echo " - templates/network.html"
echo
echo "Destination: $PROJECT_DIR"
echo "PyArmor: NOT USED"
echo "Encryption: NOT PERFORMED"
echo "======================================"
SCRIPT

sudo chmod 755 /usr/local/bin/update-protected
