sudo tee /usr/local/bin/update-protected >/dev/null <<'SCRIPT'
#!/bin/bash
set -Eeuo pipefail
umask 077

RUN_USER="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

PROJECT_DIR="$USER_HOME/Securico-VideoEdgeBox"
BASE_URL="https://raw.githubusercontent.com/Ashu300591/Securico-VideoEdgeBox-update/main"

WORK_DIR=""

fail() {
    echo
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

FILES=("app.py" "listener.py" "network.html")

echo
echo "[1/3] Downloading files from GitHub..."

for file in "${FILES[@]}"; do
    if ! curl -fsSL --retry 3 --connect-timeout 15 \
        "$BASE_URL/$file" -o "$WORK_DIR/download/$file"; then
        fail "Could not download $file. Existing files are unchanged."
    fi

    [[ -s "$WORK_DIR/download/$file" ]] ||
        fail "Downloaded $file is empty."
done

echo
echo "[2/3] Backing up existing files..."

for file in "${FILES[@]}"; do
    if [[ "$file" == "network.html" ]]; then
        destination="$PROJECT_DIR/templates/network.html"
    else
        destination="$PROJECT_DIR/$file"
    fi

    if [[ -f "$destination" ]]; then
        mkdir -p "$WORK_DIR/backup/$(dirname "$file")"
        cp -a "$destination" "$WORK_DIR/backup/$file"
    fi
done

echo
echo "[3/3] Installing updated files..."

rollback() {
    echo "Installation failed. Restoring previous files..."

    for file in "${FILES[@]}"; do
        if [[ "$file" == "network.html" ]]; then
            destination="$PROJECT_DIR/templates/network.html"
        else
            destination="$PROJECT_DIR/$file"
        fi

        if [[ -f "$WORK_DIR/backup/$file" ]]; then
            cp -a "$WORK_DIR/backup/$file" "$destination" || true
        else
            rm -f "$destination"
        fi
    done
}

mkdir -p "$PROJECT_DIR/templates"

for file in "${FILES[@]}"; do
    if [[ "$file" == "network.html" ]]; then
        destination="$PROJECT_DIR/templates/network.html"
    else
        destination="$PROJECT_DIR/$file"
    fi

    if ! install -m 644 "$WORK_DIR/download/$file" "$destination"; then
        rollback
        fail "Installation failed; rollback attempted."
    fi
done

chmod 755 "$PROJECT_DIR/app.py" "$PROJECT_DIR/listener.py"

if [[ -n "${SUDO_USER:-}" ]]; then
    chown "$RUN_USER:$(id -gn "$RUN_USER")" \
        "$PROJECT_DIR/app.py" \
        "$PROJECT_DIR/listener.py" \
        "$PROJECT_DIR/templates/network.html"
fi

echo
echo "======================================"
echo " UPDATE COMPLETED SUCCESSFULLY"
echo "======================================"
echo "Updated: app.py"
echo "Updated: listener.py"
echo "Updated: templates/network.html"
echo "PyArmor: NOT USED"
echo "Encryption: NOT PERFORMED"
echo "======================================"
SCRIPT

sudo chmod 755 /usr/local/bin/update-protected
