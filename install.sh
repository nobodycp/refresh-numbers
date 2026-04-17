#!/usr/bin/env bash
# One-shot installer for refresh-numbers
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/nobodycp/refresh-numbers/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/nobodycp/refresh-numbers/main/install.sh | bash -s -- --port 8080

set -euo pipefail

REPO_URL="https://github.com/nobodycp/refresh-numbers.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/refresh-numbers}"
PORT="5000"
HOST="0.0.0.0"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)        PORT="$2"; shift 2 ;;
        --host)        HOST="$2"; shift 2 ;;
        --dir)         INSTALL_DIR="$2"; shift 2 ;;
        --no-run)      NO_RUN=1; shift ;;
        -h|--help)
            cat <<EOF
Usage: install.sh [options]
  --port PORT     Port to bind (default: 5000)
  --host HOST     Host to bind (default: 0.0.0.0)
  --dir  DIR      Install directory (default: ~/refresh-numbers)
  --no-run        Install only, do not start the server
EOF
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

log()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m %s\n" "$*" >&2; }
err()  { printf "\033[1;31mxx\033[0m %s\n" "$*" >&2; exit 1; }

command -v git    >/dev/null || err "git is not installed"
command -v python3 >/dev/null || err "python3 is not installed"

log "Target directory: $INSTALL_DIR"
if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Repository already exists, pulling latest changes"
    git -C "$INSTALL_DIR" pull --ff-only
else
    log "Cloning repository"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

if [[ ! -d ".venv" ]]; then
    log "Creating virtual environment"
    python3 -m venv .venv
fi

log "Installing dependencies"
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [[ ! -f ".env" ]]; then
    warn ".env not found — creating a template"
    cat > .env <<'EOF'
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DB=recharge_desk
PG_USER=recharge_readonly
PG_PASSWORD=CHANGE_ME
EOF
    warn "Edit $INSTALL_DIR/.env with real DB credentials, then re-run."
    if [[ -z "${NO_RUN:-}" ]]; then
        exit 1
    fi
fi

if [[ -n "${NO_RUN:-}" ]]; then
    log "Installation complete. Start the server manually with:"
    echo "  cd $INSTALL_DIR && source .venv/bin/activate && python app.py"
    exit 0
fi

log "Starting server on http://$HOST:$PORT"
export FLASK_RUN_HOST="$HOST"
export FLASK_RUN_PORT="$PORT"
exec python -c "
import os
from app import app
app.run(host=os.environ['FLASK_RUN_HOST'], port=int(os.environ['FLASK_RUN_PORT']))
"
