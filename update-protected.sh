
#!/bin/bash
set -Eeuo pipefail
umask 077

# ==========================================
# Securico VideoEdgeBox Protected Updater
# ==========================================

PROJECT_DIR="$HOME/Securico-VideoEdgeBox"
VENV_DIR="$PROJECT_DIR/venv"
REPO_URL="https://github.com/Ashu300591/Securico-VideoEdgeBox-update.git"
BRANCH="main"

WORK_DIR=""
DEPLOYING=0
RUNTIME_NAME=""

fail() {
    echo
    echo "ERROR: $*" >&2
    exit 1
}

rollback() {
    local status=$?

    if [[ "$status" -ne 0 && "$DEPLOYING" -eq 1 ]]; then
        echo
        echo "Update failed. Restoring previous files..."

        for file in app.py listener.py; do
            if [[ -f "$WORK_DIR/backup/$file" ]]; then
                cp -a "$WORK_DIR/backup/$file" "$PROJECT_DIR/$file" || true
            fi
        done

        # Remove newly installed runtime packages.
        for path in "$PROJECT_DIR"/pyarmor_runtime_*; do
            if [[ -d "$path" ]]; then
                rm -rf "$path"
            fi
        done

        # Restore all previously backed-up runtime packages.
        if [[ -d "$WORK_DIR/backup/runtimes" ]]; then
            for path in "$WORK_DIR/backup/runtimes"/pyarmor_runtime_*; do
                if [[ -d "$path" ]]; then
                    cp -a "$path" "$PROJECT_DIR/" || true
                fi
            done
        fi

        echo "Rollback attempted. Verify files before restarting services."
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

# 1. Validate project and environment.
[[ -d "$PROJECT_DIR" ]] ||
    fail "Project folder not found: $PROJECT_DIR"

[[ -f "$VENV_DIR/bin/activate" ]] ||
    fail "Virtual environment not found: $VENV_DIR"

[[ -f "$PROJECT_DIR/app.py" && -f "$PROJECT_DIR/listener.py" ]] ||
    fail "Existing application files are missing. Contact support."

command -v git >/dev/null 2>&1 ||
    fail "Git is not installed."

# Use the project's existing virtual environment.
source "$VENV_DIR/bin/activate"

PYTHON="$VENV_DIR/bin/python"
PYARMOR="$VENV_DIR/bin/pyarmor"

[[ -x "$PYTHON" ]] ||
    fail "Python is unavailable in venv."

[[ -x "$PYARMOR" ]] ||
    fail "PyArmor is unavailable in venv."

# Keep temporary files on the same filesystem as the project.
WORK_DIR="$(mktemp -d "$PROJECT_DIR/.update-tmp.XXXXXX")"

mkdir -p \
    "$WORK_DIR/backup/runtimes" \
    "$WORK_DIR/repo"

echo
echo "[1/5] Downloading source files from GitHub..."

git clone --quiet --depth 1 --single-branch \
    --branch "$BRANCH" \
    "$REPO_URL" "$WORK_DIR/repo" ||
    fail "GitHub download failed. Check network connectivity."

cd "$WORK_DIR/repo"

for file in app.py listener.py; do
    [[ -s "$WORK_DIR/repo/$file" ]] ||
        fail "$file is missing or empty in the GitHub repository root."
done

echo "[2/5] Protecting files with PyArmor..."

# Requested PyArmor command.
"$PYARMOR" gen -O dist app.py listener.py ||
    fail "PyArmor failed. Check trial license restrictions."

BUILD_DIR="$WORK_DIR/repo/dist"

for file in app.py listener.py; do
    [[ -s "$BUILD_DIR/$file" ]] ||
        fail "Protected output missing: $file"
done

# Discover the generated runtime package.
RUNTIME_PATH=""

for candidate in "$BUILD_DIR"/pyarmor_runtime_*; do
    if [[ -d "$candidate" ]]; then
        [[ -z "$RUNTIME_PATH" ]] ||
            fail "Multiple PyArmor runtimes generated."

        RUNTIME_PATH="$candidate"
    fi
done

[[ -n "$RUNTIME_PATH" ]] ||
    fail "PyArmor runtime was not generated."

RUNTIME_NAME="$(basename "$RUNTIME_PATH")"

[[ -f "$RUNTIME_PATH/__init__.py" ]] ||
    fail "PyArmor runtime is incomplete."

echo "[3/5] Validating generated runtime..."

RUNTIME_NAME="$RUNTIME_NAME" \
PYTHONPATH="$BUILD_DIR" \
"$PYTHON" -c \
'import importlib, os; importlib.import_module(os.environ["RUNTIME_NAME"])' ||
    fail "Generated runtime failed its import test."

echo "[4/5] Backing up current application..."

cp -a "$PROJECT_DIR/app.py" "$WORK_DIR/backup/app.py"
cp -a "$PROJECT_DIR/listener.py" "$WORK_DIR/backup/listener.py"

# Back up every existing PyArmor runtime.
for path in "$PROJECT_DIR"/pyarmor_runtime_*; do
    if [[ -d "$path" ]]; then
        cp -a "$path" "$WORK_DIR/backup/runtimes/"
    fi
done

# Prepare the new runtime before modifying the application.
cp -a "$RUNTIME_PATH" "$WORK_DIR/new-runtime"

# Deployment starts here. Any subsequent failure triggers rollback.
DEPLOYING=1

# Replace existing runtime packages with the matching new runtime.
for path in "$PROJECT_DIR"/pyarmor_runtime_*; do
    if [[ -d "$path" ]]; then
        rm -rf "$path"
    fi
done

mv "$WORK_DIR/new-runtime" "$PROJECT_DIR/$RUNTIME_NAME"

# Install both protected scripts into the main folder.
install -m 755 "$BUILD_DIR/app.py" "$PROJECT_DIR/app.py"
install -m 755 "$BUILD_DIR/listener.py" "$PROJECT_DIR/listener.py"

echo "[5/5] Verifying installed files..."

[[ -s "$PROJECT_DIR/app.py" ]] ||
    fail "Installed app.py is missing."

[[ -s "$PROJECT_DIR/listener.py" ]] ||
    fail "Installed listener.py is missing."

[[ -f "$PROJECT_DIR/$RUNTIME_NAME/__init__.py" ]] ||
    fail "Installed runtime is missing."

# Test the installed runtime from the application directory.
(
    cd "$PROJECT_DIR"

    RUNTIME_NAME="$RUNTIME_NAME" \
    PYTHONPATH="$PROJECT_DIR" \
    "$PYTHON" -c \
    'import importlib, os; importlib.import_module(os.environ["RUNTIME_NAME"])'
) || fail "Installed runtime verification failed."

# All deployment checks passed.
DEPLOYING=0

echo
echo "======================================"
echo " UPDATE COMPLETED SUCCESSFULLY"
echo "======================================"
echo "Protected files: app.py, listener.py"
echo "Runtime: $RUNTIME_NAME"
echo "Location: $PROJECT_DIR"
echo
echo "Existing application processes were not restarted."
echo "Test the application before restarting services."
echo "======================================"
