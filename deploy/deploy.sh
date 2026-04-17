#!/usr/bin/env bash
# Production deployer for refresh-numbers
# Must be run as root on the target server.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/nobodycp/refresh-numbers/main/deploy/deploy.sh | sudo bash
#   curl -fsSL https://raw.githubusercontent.com/nobodycp/refresh-numbers/main/deploy/deploy.sh | sudo bash -s -- --domain rn.prosim.ps --email admin@prosim.ps
#
# Defaults:
#   domain  = rn.prosim.ps
#   app dir = /opt/refresh-numbers
#   user    = refresh-numbers
#   port    = 5005

set -euo pipefail

DOMAIN="rn.prosim.ps"
EMAIL=""
APP_DIR="/opt/refresh-numbers"
APP_USER="refresh-numbers"
PORT="5005"
REPO_URL="https://github.com/nobodycp/refresh-numbers.git"
SKIP_CERTBOT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)       DOMAIN="$2"; shift 2 ;;
        --email)        EMAIL="$2"; shift 2 ;;
        --dir)          APP_DIR="$2"; shift 2 ;;
        --user)         APP_USER="$2"; shift 2 ;;
        --port)         PORT="$2"; shift 2 ;;
        --no-ssl)       SKIP_CERTBOT=1; shift ;;
        -h|--help)
            sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

log()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m %s\n" "$*" >&2; }
err()  { printf "\033[1;31mxx\033[0m %s\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || err "Run as root (sudo bash ...)"

# ---------- 0. preflight: make sure we don't clash with existing services ----------
log "Preflight checks (no changes will be made yet)"

# 0.1 port must be free (or already owned by our own service)
if ss -tlnp 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$PORT$"; then
    OWNER=$(ss -tlnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $NF}' | head -1)
    if [[ "$OWNER" != *"refresh-numbers"* ]] && ! systemctl is-active --quiet refresh-numbers.service 2>/dev/null; then
        err "Port $PORT is already in use by: $OWNER
     Pick a different port with: --port 5006 (or any free one)"
    fi
    log "Port $PORT already bound by our own service — will be restarted"
fi

# 0.2 nginx server_name must not already exist elsewhere
if [[ -d /etc/nginx ]]; then
    CONFLICT=$(grep -rEl "server_name[[:space:]]+[^;]*\b${DOMAIN//./\\.}\b" /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null \
              | grep -v "/refresh-numbers$" || true)
    if [[ -n "$CONFLICT" ]]; then
        err "Domain $DOMAIN is already configured in nginx here:
$CONFLICT
     Remove/adjust that config first, or use a different --domain."
    fi
fi

# 0.3 if app dir already exists, make sure it's our repo (not another project)
if [[ -e "$APP_DIR" && ! -d "$APP_DIR/.git" ]]; then
    err "$APP_DIR exists and is NOT a git clone. Refusing to overwrite. Move it or pick --dir."
fi
if [[ -d "$APP_DIR/.git" ]]; then
    EXISTING_URL=$(git -C "$APP_DIR" config --get remote.origin.url || echo "")
    if [[ -n "$EXISTING_URL" && "$EXISTING_URL" != *"refresh-numbers"* ]]; then
        err "$APP_DIR is a git clone of a different repo: $EXISTING_URL"
    fi
fi

log "Preflight OK — no conflicts detected"
log "Plan:"
printf "     app dir : %s\n" "$APP_DIR"
printf "     user    : %s\n" "$APP_USER"
printf "     port    : %s (127.0.0.1 only)\n" "$PORT"
printf "     domain  : %s\n" "$DOMAIN"
printf "     service : refresh-numbers.service\n"
printf "     ssl     : %s\n" "$([[ $SKIP_CERTBOT -eq 0 ]] && echo yes || echo no)"

# ---------- 1. system packages ----------
log "Installing system packages"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip nginx libpq-dev
if [[ $SKIP_CERTBOT -eq 0 ]]; then
    apt-get install -y certbot python3-certbot-nginx
fi

# ---------- 2. system user ----------
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    log "Creating system user: $APP_USER"
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

# ---------- 3. clone / update repo ----------
if [[ -d "$APP_DIR/.git" ]]; then
    log "Updating existing clone at $APP_DIR"
    git -C "$APP_DIR" pull --ff-only
else
    log "Cloning repo into $APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
fi

# ---------- 4. venv & dependencies ----------
log "Creating virtualenv & installing dependencies"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# ---------- 5. .env ----------
if [[ ! -f "$APP_DIR/.env" ]]; then
    warn ".env not found — creating a template"
    cat > "$APP_DIR/.env" <<'EOF'
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DB=recharge_desk
PG_USER=recharge_readonly
PG_PASSWORD=CHANGE_ME
EOF
    warn "Edit $APP_DIR/.env and set a real password, then re-run this script."
fi
chmod 640 "$APP_DIR/.env"

# ---------- 6. ownership ----------
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ---------- 7. systemd ----------
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
    warn "Service failed to start. Recent logs:"
    journalctl -u refresh-numbers.service -n 30 --no-pager || true
    err "Fix .env / credentials and run: systemctl restart refresh-numbers"
fi
log "Service is running on 127.0.0.1:$PORT"

# ---------- 8. nginx ----------
log "Configuring nginx for $DOMAIN"
NGX_FILE="/etc/nginx/sites-available/refresh-numbers"
sed -e "s|__DOMAIN__|$DOMAIN|g" \
    -e "s|__PORT__|$PORT|g" \
    "$APP_DIR/deploy/nginx.conf" > "$NGX_FILE"
ln -sf "$NGX_FILE" /etc/nginx/sites-enabled/refresh-numbers

nginx -t
systemctl reload nginx

# ---------- 9. TLS ----------
if [[ $SKIP_CERTBOT -eq 0 ]]; then
    log "Requesting Let's Encrypt certificate for $DOMAIN"
    CERTBOT_ARGS=(--nginx -d "$DOMAIN" --redirect --non-interactive --agree-tos)
    if [[ -n "$EMAIL" ]]; then
        CERTBOT_ARGS+=(--email "$EMAIL")
    else
        CERTBOT_ARGS+=(--register-unsafely-without-email)
    fi
    certbot "${CERTBOT_ARGS[@]}" || warn "Certbot failed — the site will stay on HTTP for now. Check DNS points to this server."
fi

log "Done."
log "Visit: https://$DOMAIN (or http://$DOMAIN if SSL was skipped)"
log "Logs : journalctl -u refresh-numbers -f"
