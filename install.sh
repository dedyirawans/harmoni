#!/usr/bin/env bash
#
# install.sh — Auto-installer CRM (React + FastAPI + MongoDB) ke VPS Ubuntu.
# Cukup jalankan sebagai root:  sudo bash install.sh
# Script akan bertanya beberapa hal lalu memasang semuanya otomatis.
#
set -euo pipefail

# ----- Warna sederhana -----
G="\033[0;32m"; Y="\033[1;33m"; R="\033[0;31m"; N="\033[0m"
say()  { echo -e "${G}==>${N} $1"; }
warn() { echo -e "${Y}!! ${N} $1"; }
die()  { echo -e "${R}XX ${N} $1"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Jalankan sebagai root:  sudo bash install.sh"

APP_DIR="/opt/harmoni-crm"
PIP_EXTRA="https://d33sy5i8bnduwe.cloudfront.net/simple/"

echo "=================================================="
echo "  Auto-Installer CRM — PT Harmoni Wisata Internusa"
echo "=================================================="
echo

# ----- Input dari pengguna -----
read -rp "1) Link repo GitHub (mis. https://github.com/nama/repo.git): " REPO_URL
[ -n "${REPO_URL}" ] || die "Link repo wajib diisi."

read -rp "2) Domain (mis. crm.domainanda.com) — kosongkan jika belum punya: " DOMAIN
read -rp "3) Email Super Admin [irawandedy185@gmail.com]: " ADMIN_EMAIL
ADMIN_EMAIL="${ADMIN_EMAIL:-irawandedy185@gmail.com}"
read -rp "4) Password Super Admin [Harmoni#Wisata2025]: " ADMIN_PASS
ADMIN_PASS="${ADMIN_PASS:-Harmoni#Wisata2025}"

# Tentukan URL backend untuk frontend
if [ -n "${DOMAIN}" ]; then
  SERVER_NAME="${DOMAIN}"
  BACKEND_URL="https://${DOMAIN}"
else
  IP="$(hostname -I | awk '{print $1}')"
  SERVER_NAME="${IP}"
  BACKEND_URL="http://${IP}"
  warn "Tidak ada domain — memakai IP ${IP} (HTTPS dilewati)."
fi

echo
say "Konfigurasi: repo=${REPO_URL}  server=${SERVER_NAME}  admin=${ADMIN_EMAIL}"
read -rp "Lanjut instalasi? (y/n): " OK
[ "${OK}" = "y" ] || die "Dibatalkan."

# ----- LANGKAH 2: update sistem -----
say "Memperbarui sistem..."
export DEBIAN_FRONTEND=noninteractive
apt update -y && apt upgrade -y

# ----- LANGKAH 3: dependency dasar -----
say "Memasang git, nginx, python, curl..."
apt install -y git nginx python3.11 python3.11-venv python3-pip build-essential curl gnupg openssl lsb-release

say "Memasang Node.js 20 + Yarn..."
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
fi
command -v yarn >/dev/null 2>&1 || npm install -g yarn

# ----- LANGKAH 4: MongoDB 7 -----
if ! command -v mongod >/dev/null 2>&1; then
  say "Memasang MongoDB 7..."
  CODENAME="$(lsb_release -cs)"
  case "${CODENAME}" in
    noble|jammy|focal) MONGO_CN="${CODENAME}";;
    *) MONGO_CN="jammy"; warn "Codename ${CODENAME} tak dikenal, pakai jammy.";;
  esac
  curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu ${MONGO_CN}/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list
  apt update -y && apt install -y mongodb-org
fi
systemctl enable --now mongod
sleep 3
mongosh --quiet --eval 'db.runCommand({ ping: 1 })' >/dev/null 2>&1 && say "MongoDB OK." || warn "MongoDB belum merespon, cek: systemctl status mongod"

# ----- LANGKAH 5: clone kode -----
if [ -d "${APP_DIR}/.git" ]; then
  say "Repo sudah ada, menarik update..."
  git -C "${APP_DIR}" pull
else
  say "Mengunduh kode dari GitHub..."
  git clone "${REPO_URL}" "${APP_DIR}"
fi

# ----- LANGKAH 6: backend -----
say "Menyiapkan backend (virtualenv + dependencies)... (agak lama)"
cd "${APP_DIR}/backend"
python3.11 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --extra-index-url "${PIP_EXTRA}"
deactivate

say "Membuat file backend/.env..."
JWT="$(openssl rand -hex 32)"
cat > "${APP_DIR}/backend/.env" << EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="harmoni_crm"
CORS_ORIGINS="*"
JWT_SECRET="${JWT}"
SUPER_ADMIN_EMAIL="${ADMIN_EMAIL}"
SUPER_ADMIN_PASSWORD="${ADMIN_PASS}"
SEED_DEMO_DATA="false"
FRONTEND_URL="${BACKEND_URL}"
EOF

# ----- LANGKAH 7: systemd service -----
say "Membuat service backend (otomatis hidup)..."
cat > /etc/systemd/system/harmoni-backend.service << EOF
[Unit]
Description=Harmoni CRM Backend
After=network.target mongod.service

[Service]
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${APP_DIR}/backend/.env
ExecStart=${APP_DIR}/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now harmoni-backend
sleep 4
systemctl is-active --quiet harmoni-backend && say "Backend RUNNING." || warn "Backend belum aktif, cek: journalctl -u harmoni-backend -n 50"

# ----- LANGKAH 8: build frontend -----
say "Membangun tampilan web (frontend)... (agak lama)"
cd "${APP_DIR}/frontend"
echo "REACT_APP_BACKEND_URL=${BACKEND_URL}" > .env
yarn install
CI=false yarn build

# ----- LANGKAH 9: nginx -----
say "Mengatur Nginx..."
cat > /etc/nginx/sites-available/harmoni-crm << EOF
server {
    listen 80;
    server_name ${SERVER_NAME};

    root ${APP_DIR}/frontend/build;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 25M;
    }

    location / {
        try_files \$uri /index.html;
    }
}
EOF
ln -sf /etc/nginx/sites-available/harmoni-crm /etc/nginx/sites-enabled/harmoni-crm
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ----- LANGKAH 10: HTTPS (jika ada domain) -----
if [ -n "${DOMAIN}" ]; then
  say "Memasang HTTPS (Let's Encrypt)..."
  apt install -y certbot python3-certbot-nginx
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${ADMIN_EMAIL}" --redirect || \
    warn "Certbot gagal (pastikan domain sudah mengarah ke IP VPS). Situs tetap bisa via http://"
fi

echo
echo "=================================================="
say "SELESAI! Buka:  ${BACKEND_URL}"
echo "   Login  : ${ADMIN_EMAIL}"
echo "   Sandi  : ${ADMIN_PASS}"
echo "   (Segera ganti sandi dari menu profil.)"
echo "--------------------------------------------------"
echo "Cek status : systemctl status harmoni-backend"
echo "Lihat log  : journalctl -u harmoni-backend -n 50"
echo "=================================================="
