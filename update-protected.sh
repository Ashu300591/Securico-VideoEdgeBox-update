
sudo tee /usr/local/bin/update-protected >/dev/null <<'SCRIPT'
#!/bin/bash
set -Eeuo pipefail
umask 077

PROJECT_DIR="$HOME/Securico-VideoEdgeBox"
VENV_DIR="$PROJECT_DIR/myenv"
REPO_URL="https://github.com/Ashu300591/Securico-VideoEdgeBox-update.git"
BRANCH="main"

WORK_DIR=""
DEPLOYING=0
HAD_APP=0
HAD_LISTENER=0
HAD_RUNTIME=0
RUNTIME_NAME=""

fail() {
    echo
    echo "ERROR: $*" >&2
    exit 1
}

rollback() {
    local status=$?
    if [[ $status -ne 0 && $DEPLOYING -eq 1 ]]; then
        echo
        echo "Update failed. Restoring previous files..."

        if [[ $HAD_APP -eq 1 && -f "$WORK_DIR/backup/app.py" ]]; then
            cp -a "$WORK_DIR/backup/app.py" "$PROJECT_DIR/app.py" || true
        else
            rm -f "$PROJECT_DIR/app.py"
        fi

        if [[ $HAD_LISTENER -eq 1 && -f "$WORK_DIR/backup/listener.py" ]]; then
            cp -a "$WORK_DIR/backup/listener.py" "$PROJECT_DIR/listener.py" || true
        else
            rm -f "$PROJECT_DIR/listener.py"
        fi

        if [[ -n "$RUNTIME_NAME" ]]; then
            rm -rf "$PROJECT_DIR/$RUNTIME_NAME"
            if [[ $HAD_RUNTIME -eq 1 && -d "$WORK_DIR/backup/$RUNTIME_NAME" ]]; then
                cp -a "$WORK_DIR/backup/$RUNTIME_NAME" "$PROJECT_DIR/$RUNTIME_NAME" || true
            fi
        fi

        echo "Rollback attempted. Check the files before restarting services."
    fi

    if [[ -n "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR"
    fi
    exit "$status"
}
trap rollback EXIT

echo "======================================"
echo " Securico VideoEdgeBox Protected Update"
echo "======================================"

[[ -d "$PROJECT_DIR" ]] ||
    fail "Project folder not found: $PROJECT_DIR"

[[ -f "$VENV_DIR/bin/activate" ]] ||
    fail "Python environment not found: $VENV_DIR"

[[ -f "$PROJECT_DIR/app.py" && -f "$PROJECT_DIR/listener.py" ]] ||
    fail "Existing app.py or listener.py is missing. Contact support."

command -v git >/dev/null 2>&1 ||
    fail "Git is not installed. Contact support."

# Always use the project's own Python environment.
source "$VENV_DIR/bin/activate"

PYTHON="$VENV_DIR/bin/python"
PYARMOR="$VENV_DIR/bin/pyarmor"

[[ -x "$PYTHON" ]] || fail "Project Python is unavailable."
[[ -x "$PYARMOR" ]] || fail "PyArmor is unavailable in the project environment."

WORK_DIR="$(mktemp -d "$PROJECT_DIR/.update-tmp.XXXXXX")"
mkdir -p "$WORK_DIR/backup" "$WORK_DIR/source" "$WORK_DIR/build"

echo
echo "[1/5] Downloading approved source files..."

git clone --quiet --depth 1 --single-branch \
    --branch "$BRANCH" "$REPO_URL" "$WORK_DIR/repo" ||
    fail "Download failed. Check network access and GitHub repository."

for file in app.py listener.py; do
    [[ -s "$WORK_DIR/repo/$file" ]] ||
        fail "$file is missing or empty in the repository root."
    cp "$WORK_DIR/repo/$file" "$WORK_DIR/source/$file"
done

echo "[2/5] Protecting files with PyArmor..."

"$PYARMOR" gen -O "$WORK_DIR/build" \
    "$WORK_DIR/source/app.py" \
    "$WORK_DIR/source/listener.py" ||
    fail "PyArmor failed. Check its license and error messages."

for file in app.py listener.py; do
    [[ -s "$WORK_DIR/build/$file" ]] ||
        fail "PyArmor did not generate $file."
done

RUNTIME_PATH=""
for candidate in "$WORK_DIR"/build/pyarmor_runtime_*; do
    if [[ -d "$candidate" ]]; then
        [[ -z "$RUNTIME_PATH" ]] ||
            fail "Multiple runtime packages generated. Contact support."
        RUNTIME_PATH="$candidate"
    fi
done

[[ -n "$RUNTIME_PATH" ]] ||
    fail "PyArmor runtime package was not generated."

RUNTIME_NAME="$(basename "$RUNTIME_PATH")"

[[ -f "$RUNTIME_PATH/__init__.py" ]] ||
    fail "PyArmor runtime is incomplete."

echo "[3/5] Checking generated runtime..."

RUNTIME_NAME="$RUNTIME_NAME" PYTHONPATH="$WORK_DIR/build" \
    "$PYTHON" -c \
    'import importlib, os; importlib.import_module(os.environ["RUNTIME_NAME"])' ||
    fail "Generated runtime cannot be imported on this device."

echo "[4/5] Preparing safe installation..."

# Preserve the original files before changing anything.
cp -a "$PROJECT_DIR/app.py" "$WORK_DIR/backup/app.py"
cp -a "$PROJECT_DIR/listener.py" "$WORK_DIR/backup/listener.py"
HAD_APP=1
HAD_LISTENER=1

if [[ -e "$PROJECT_DIR/$RUNTIME_NAME" ]]; then
    [[ -d "$PROJECT_DIR/$RUNTIME_NAME" ]] ||
        fail "Existing runtime path is not a directory."
    cp -a "$PROJECT_DIR/$RUNTIME_NAME" "$WORK_DIR/backup/$RUNTIME_NAME"
    HAD_RUNTIME=1
fi

# Prepare the new runtime on the same filesystem.
cp -a "$RUNTIME_PATH" "$WORK_DIR/new-runtime"

# From this point, any failure triggers rollback.
DEPLOYING=1

rm -rf "$PROJECT_DIR/$RUNTIME_NAME"
mv "$WORK_DIR/new-runtime" "$PROJECT_DIR/$RUNTIME_NAME"

install -m 755 "$WORK_DIR/build/app.py" "$PROJECT_DIR/app.py"
install -m 755 "$WORK_DIR/build/listener.py" "$PROJECT_DIR/listener.py"

echo "[5/5] Verifying installed files..."

[[ -s "$PROJECT_DIR/app.py" && -s "$PROJECT_DIR/listener.py" ]] ||
    fail "Installed scripts are missing."

[[ -f "$PROJECT_DIR/$RUNTIME_NAME/__init__.py" ]] ||
    fail "Installed runtime is missing."

# Test the runtime from its final location.
(
    cd "$PROJECT_DIR"
    "$PYTHON" -c \
        "import $RUNTIME_NAME"
) || fail "Installed runtime check failed."

DEPLOYING=0

echo
echo "======================================"
echo " UPDATE COMPLETED SUCCESSFULLY"
echo "======================================"
echo "Protected files: app.py, listener.py"
echo "Runtime: $RUNTIME_NAME"
echo "Location: $PROJECT_DIR"
echo
echo "Your existing application processes were not restarted."
echo "Restart services only after confirming the update."
echo "======================================"
SCRIPT
sudo chmod 755 /usr/local/bin/update-protected
echo "Setup complete. Run: update-protected"
