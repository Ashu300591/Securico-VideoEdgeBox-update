
#!/bin/bash
set -Eeuo pipefail
umask 077

PROJECT_DIR="$HOME/Securico-VideoEdgeBox"
REPO_URL="https://github.com/Ashu300591/Securico-VideoEdgeBox-update.git"
BRANCH="main"

WORK_DIR=""

cleanup() {
    if [[ -n "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR"
    fi
}
trap cleanup EXIT

fail() {
    echo
    echo "ERROR: $*" >&2
    exit 1
}

echo "======================================"
echo " Securico VideoEdgeBox File Updater"
echo "======================================"

[[ -d "$PROJECT_DIR" ]] ||
    fail "Project folder not found: $PROJECT_DIR"

[[ -f "$PROJECT_DIR/app.py" && -f "$PROJECT_DIR/listener.py" ]] ||
    fail "Existing application files are missing. Contact support."

command -v git >/dev/null 2>&1 ||
    fail "Git is not installed."

WORK_DIR="$(mktemp -d "$PROJECT_DIR/.update-tmp.XXXXXX")"

echo
echo "[1/3] Downloading files from GitHub..."

git clone --quiet --depth 1 --single-branch \
    --branch "$BRANCH" "$REPO_URL" "$WORK_DIR/repo" ||
    fail "GitHub download failed. Check network connectivity."

for file in app.py listener.py; do
    [[ -s "$WORK_DIR/repo/$file" ]] ||
        fail "$file is missing or empty in the GitHub repository."
done

echo "[2/3] Backing up current files..."

cp -a "$PROJECT_DIR/app.py" "$WORK_DIR/app.py.backup"
cp -a "$PROJECT_DIR/listener.py" "$WORK_DIR/listener.py.backup"

echo "[3/3] Installing downloaded files..."

# Keep backups until both replacements succeed.
if ! install -m 755 "$WORK_DIR/repo/app.py" "$PROJECT_DIR/app.py"; then
    cp -a "$WORK_DIR/app.py.backup" "$PROJECT_DIR/app.py"
    fail "Could not install app.py; previous file restored."
fi

if ! install -m 755 "$WORK_DIR/repo/listener.py" "$PROJECT_DIR/listener.py"; then
    cp -a "$WORK_DIR/app.py.backup" "$PROJECT_DIR/app.py"
    cp -a "$WORK_DIR/listener.py.backup" "$PROJECT_DIR/listener.py"
    fail "Could not install listener.py; previous files restored."
fi

echo
echo "======================================"
echo " UPDATE COMPLETED SUCCESSFULLY"
echo "======================================"
echo "Downloaded: app.py, listener.py"
echo "Destination: $PROJECT_DIR"
echo "No encryption was performed."
echo "Running application processes were not restarted."
echo "======================================"
