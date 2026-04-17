#!/usr/bin/env bash
# Production deployer for refresh-numbers (Caddy-based, matches account_manger style)
# Must be run as root on the target server.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/nobodycp/refresh-numbers/main/deploy/deploy.sh | sudo bash
#
# Options:
#   --domain DOMAIN    Public domain (default: rn.prosim.ps)
#   --dir DIR          Install directory (default: /opt/refresh-numbers)
#   --user USER        System user  (default: refresh-numbers)
#   --port PORT        Local gunicorn port (default: 5005)

set -euo pipefail

DOMAIN="rn.prosim.ps"
APP_DIR="/opt/refresh-numbers"
APP_USER="refresh-numbers"
PORT="5005"
REPO_URL="https://github.com/nobodycp/refresh-numbers.git"
CADDY_SITES_DIR="/etc/caddy/sites"
CADDY_FRAGMENT="refresh-numbers.caddy"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) DOMAIN="$2"; shift 2 ;;
        --dir)    APP_DIR="$2"; shift 2 ;;
        --user)   APP_USER="$2"; shift 2 ;;
        --port)   PORT="$2"; shift 2 ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

log()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m %s\n" "$*" >&2; }
err()  { printf "\033[1;31mxx\033[0m %s\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || err "Run as root (sudo bash ...)"

# ---------- 0. preflight ----------
log "Preflight: verifying Caddy is installed and running"
command -v caddy >/dev/null || err "Caddy is not installed. (Expected — account_manger uses Caddy.)"
systemctl is-active --quiet caddy || err "Caddy service is not running. Start it: systemctl start caddy"

if [[ ! -f /etc/caddy/Caddyfile ]]; then
    err "/etc/caddy/Caddyfile not found — abort."
fi

# Make sure Caddyfile imports /etc/caddy/sites/*.caddy (same convention as account_manger)
if ! grep -qE "^\s*import\s+/etc/caddy/sites/\*\.caddy" /etc/caddy/Caddyfile; then
    warn "/etc/caddy/Caddyfile does not import /etc/caddy/sites/*.caddy — adding it now"
    cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak.refresh-numbers
    printf 'import /etc/caddy/sites/*.caddy\n\n%s\n' "$(cat /etc/caddy/Caddyfile)" > /etc/caddy/Caddyfile.tmp
    mv /etc/caddy/Caddyfile.tmp /etc/caddy/Caddyfile
fi
mkdir -p "$CADDY_SITES_DIR"

# Guard: no other caddy site owns the domain already
if grep -rEl "^[[:space:]]*${DOMAIN//./\\.}[[:space:]]*\{" "$CADDY_SITES_DIR" 2>/dev/null \
   | grep -v "/$CADDY_FRAGMENT$" >/dev/null; then
    err "Another Caddy site already serves $DOMAIN in $CADDY_SITES_DIR. Adjust manually or use --domain."
fi

# Port must be free (or already ours)
if ss -tlnp 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$PORT$"; then
    OWNER=$(ss -tlnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $NF}' | head -1)
    if [[ "$OWNER" != *"refresh-numbers"* ]] && ! systemctl is-active --quiet refresh-numbers.service 2>/dev/null; then
        err "Port $PORT is in use by: $OWNER. Use --port NNNN."
    fi
fi

# Remove any leftover nginx config from earlier attempts
if [[ -L /etc/nginx/sites-enabled/refresh-numbers ]] || [[ -f /etc/nginx/sites-available/refresh-numbers ]]; then
    log "Cleaning up previous nginx refresh-numbers config (Caddy handles TLS now)"
    rm -f /etc/nginx/sites-enabled/refresh-numbers
    rm -f /etc/nginx/sites-available/refresh-numbers
    if command -v nginx >/dev/null && systemctl is-active --quiet nginx; then
        nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
    fi
fi

log "Preflight OK"
log "Plan: app=$APP_DIR user=$APP_USER port=$PORT domain=$DOMAIN (SSL via Caddy)"

# ---------- 1. system packages ----------
log "Installing system packages"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip libpq-dev

# ---------- 2. system user ----------
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    log "Creating system user: $APP_USER"
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

# ---------- 3. clone / update ----------
# $APP_DIR may be owned by $APP_USER while this script runs as root;
# run git as the owning user (or root if dir doesn't exist yet).
export GIT_TERMINAL_PROMPT=0

if [[ -d "$APP_DIR/.git" ]]; then
    log "Updating existing clone at $APP_DIR"
    OWNER_UID=$(stat -c '%u' "$APP_DIR")
    OWNER_NAME=$(id -nu "$OWNER_UID" 2>/dev/null || echo root)
    if [[ "$OWNER_NAME" == "root" || "$OWNER_UID" == "0" ]]; then
        git -C "$APP_DIR" pull --ff-only
    else
        sudo -u "$OWNER_NAME" git -C "$APP_DIR" pull --ff-only
    fi
else
    log "Cloning repo into $APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
fi

# ---------- 4. venv ----------
log "Installing Python dependencies"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# ---------- 5. .env ----------
if [[ ! -f "$APP_DIR/.env" ]]; then
    warn ".env not found — creating a template (edit it and re-run)"
    GEN_SECRET=$(python3 -c 'import secrets;print(secrets.token_hex(32))')
    cat > "$APP_DIR/.env" <<EOF
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DB=recharge_desk
PG_USER=recharge_readonly
PG_PASSWORD=CHANGE_ME

# HMAC signing secret for session tokens — keep secret, rotating invalidates live sessions.
SECRET_KEY=${GEN_SECRET}
EOF
elif ! grep -q '^SECRET_KEY=' "$APP_DIR/.env"; then
    log "Adding SECRET_KEY to existing .env"
    GEN_SECRET=$(python3 -c 'import secrets;print(secrets.token_hex(32))')
    printf '\nSECRET_KEY=%s\n' "$GEN_SECRET" >> "$APP_DIR/.env"
fi
chmod 640 "$APP_DIR/.env"

# App state files (nonces, cooldowns, logs) must be writable by the service user.
mkdir -p "$APP_DIR/logs"
touch "$APP_DIR/security.sqlite3" 2>/dev/null || true
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ---------- 6. systemd ----------
log "Installing systemd service"
SERVICE_FILE="/etc/systemd/system/refresh-numbers.service"
sed -e "s|__USER__|$APP_USER|g" \
    -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|__PORT__|$PORT|g" \
    "$APP_DIR/deploy/refresh-numbers.service" > "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable refresh-numbers.service
systemctl restart refresh-numbers.service

sleep 2
if ! systemctl is-active --quiet refresh-numbers.service; then
    warn "Service failed. Recent logs:"
    journalctl -u refresh-numbers.service -n 30 --no-pager || true
    err "Fix .env and run: systemctl restart refresh-numbers"
fi
log "App running on 127.0.0.1:$PORT"

# ---------- 7. Caddy fragment ----------
log "Writing Caddy site fragment"
FRAG_PATH="$CADDY_SITES_DIR/$CADDY_FRAGMENT"
cat > "$FRAG_PATH" <<EOF
# Managed by refresh-numbers deploy.sh — do not edit by hand.
$DOMAIN {
    encode gzip
    reverse_proxy 127.0.0.1:$PORT
}
EOF
chmod 644 "$FRAG_PATH"

log "Reloading Caddy"
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
systemctl reload caddy

log "Done."
log "Visit: https://$DOMAIN"
log "Logs : journalctl -u refresh-numbers -f"
log "Caddy: journalctl -u caddy -f"
