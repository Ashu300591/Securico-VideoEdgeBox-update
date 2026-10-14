
sudo tee /usr/local/bin/update-protected >/dev/null <<'SCRIPT'
#!/bin/bash
set -Eeuo pipefail
umask 077

PROJECT_DIR="$HOME/Securico-VideoEdgeBox"
BASE_URL="https://raw.githubusercontent.com/Ashu300591/Securico-VideoEdgeBox-update/main"

WORK_DIR=""

fail() {
    echo
    echo "ERROR: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$WORK_DIR" ]]; then
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
echo "[1/3] Downloading plain Python files from GitHub..."

for file in app.py listener.py; do
    if ! curl -fsSL --connect-timeout 15 \
        "$BASE_URL/$file" -o "$WORK_DIR/download/$file"; then
        fail "Could not download $file. Existing files are unchanged."
    fi

    [[ -s "$WORK_DIR/download/$file" ]] ||
        fail "Downloaded $file is empty. Existing files are unchanged."
done

echo "[2/3] Backing up existing files..."

for file in app.py listener.py; do
    if [[ -e "$PROJECT_DIR/$file" ]]; then
        cp -a "$PROJECT_DIR/$file" "$WORK_DIR/backup/$file"
    fi
done

echo "[3/3] Copying downloaded files into main folder..."

# Replace the files only after both downloads succeed.
for file in app.py listener.py; do
    if ! install -m 755 "$WORK_DIR/download/$file" "$PROJECT_DIR/$file"; then
        echo "Installation failed. Restoring previous files..."

        for restore in app.py listener.py; do
            if [[ -f "$WORK_DIR/backup/$restore" ]]; then
                cp -a "$WORK_DIR/backup/$restore" \
                    "$PROJECT_DIR/$restore" || true
            fi
        done

        fail "Installation failed; rollback attempted."
    fi
done

echo
echo "======================================"
echo " UPDATE COMPLETED SUCCESSFULLY"
echo "======================================"
echo "Downloaded: app.py, listener.py"
echo "Destination: $PROJECT_DIR"
echo "PyArmor: NOT USED"
echo "Encryption: NOT PERFORMED"
echo "======================================"
SCRIPT

sudo chmod 755 /usr/local/bin/update-protected
