# Panduan Deploy ke VPS + MongoDB — PT Harmoni Wisata Internusa (Safar CRM)

Stack: **React (frontend)** + **FastAPI/Python 3.11 (backend, uvicorn)** + **MongoDB**.
Panduan ini memakai **Ubuntu 22.04 VPS**, **Nginx** reverse proxy, dan **systemd**.

---

## 0. Prasyarat
- 1 VPS (Ubuntu 22.04), min 2GB RAM (disarankan 4GB), akses `root`/sudo + SSH.
- 1 domain, arahkan A record ke IP VPS (mis. `crm.perusahaananda.com`).
- Kode aplikasi sudah di GitHub (pakai tombol **"Save to GitHub"** di Emergent).

---

## 1. Update sistem & tools dasar
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl nginx build-essential
```

## 2. Install Python 3.11
```bash
sudo apt install -y python3.11 python3.11-venv python3-pip
```

## 3. Install Node 20 + Yarn (untuk build frontend)
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g yarn
```

## 4. Install MongoDB 7 (Community)
```bash
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update && sudo apt install -y mongodb-org
sudo systemctl enable --now mongod
mongosh --eval 'db.runCommand({ ping: 1 })'   # cek jalan
```
> Alternatif tanpa install: pakai **MongoDB Atlas** (gratis M0) → dapatkan connection string `mongodb+srv://...` dan pakai sebagai `MONGO_URL`.

**Amankan MongoDB (buat user & aktifkan auth):**
```bash
mongosh
> use admin
> db.createUser({user:"crmadmin", pwd:"GANTI_PASSWORD_KUAT", roles:[{role:"root",db:"admin"}]})
> exit
sudo sed -i 's/#security:/security:\n  authorization: enabled/' /etc/mongod.conf
sudo systemctl restart mongod
```
Maka `MONGO_URL="mongodb://crmadmin:GANTI_PASSWORD_KUAT@localhost:27017"`.

---

## 5. Clone kode
```bash
cd /opt
sudo git clone https://github.com/USERNAME/REPO.git harmoni-crm
sudo chown -R $USER:$USER /opt/harmoni-crm
cd /opt/harmoni-crm
```

## 6. Setup Backend (FastAPI)
```bash
cd /opt/harmoni-crm/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
# PENTING: paket emergentintegrations butuh index khusus:
pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
```

**Buat file `backend/.env`:**
```env
MONGO_URL="mongodb://crmadmin:GANTI_PASSWORD_KUAT@localhost:27017"
DB_NAME="harmoni_crm"
CORS_ORIGINS="https://crm.perusahaananda.com"
JWT_SECRET="<acak-panjang, mis. hasil: openssl rand -hex 32>"
SUPER_ADMIN_EMAIL="irawandedy185@gmail.com"
SUPER_ADMIN_PASSWORD="Harmoni#Wisata2025"
SEED_DEMO_DATA="false"
FRONTEND_URL="https://crm.perusahaananda.com"

# --- Opsional/integrasi (isi bila dipakai) ---
# EMERGENT_LLM_KEY hanya berfungsi di platform Emergent.
# Untuk fitur AI di VPS, ganti dengan API key Anda sendiri (OpenAI/Anthropic/Google):
# OPENAI_API_KEY="sk-..."
# MMBC_USERNAME="..."
# MMBC_PASSWORD="..."
```
> **Catatan integrasi:** `EMERGENT_LLM_KEY` tidak jalan di luar Emergent. Fitur AI perlu API key LLM Anda sendiri. Kredensial MMBC & n8n diisi ulang lewat env / menu API Settings.

**Uji backend jalan:**
```bash
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001
# buka terminal lain: curl http://localhost:8001/api/  -> harus balas
```

## 7. Backend sebagai service (systemd)
Buat `/etc/systemd/system/harmoni-backend.service`:
```ini
[Unit]
Description=Harmoni CRM Backend (FastAPI)
After=network.target mongod.service

[Service]
User=www-data
WorkingDirectory=/opt/harmoni-crm/backend
EnvironmentFile=/opt/harmoni-crm/backend/.env
ExecStart=/opt/harmoni-crm/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo chown -R www-data:www-data /opt/harmoni-crm
sudo systemctl daemon-reload
sudo systemctl enable --now harmoni-backend
sudo systemctl status harmoni-backend
```

## 8. Build Frontend (React)
```bash
cd /opt/harmoni-crm/frontend
# set backend URL -> DOMAIN publik (bukan localhost)
echo 'REACT_APP_BACKEND_URL=https://crm.perusahaananda.com' > .env
yarn install
yarn build       # hasil: folder /opt/harmoni-crm/frontend/build
```

## 9. Nginx reverse proxy
Buat `/etc/nginx/sites-available/harmoni-crm`:
```nginx
server {
    listen 80;
    server_name crm.perusahaananda.com;

    # Frontend static
    root /opt/harmoni-crm/frontend/build;
    index index.html;

    # API -> backend (semua route /api diteruskan ke uvicorn)
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        client_max_body_size 25M;   # untuk upload logo/file
    }

    # SPA fallback (react-router)
    location / {
        try_files $uri /index.html;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/harmoni-crm /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 10. HTTPS (SSL gratis Let's Encrypt)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d crm.perusahaananda.com
# auto-renew sudah aktif via systemd timer
```

---

## 11. Selesai — cek
- Buka `https://crm.perusahaananda.com` → halaman login PT Harmoni Wisata Internusa.
- Login Super Admin → seed otomatis membuat akun admin (karena `SEED_DEMO_DATA=false`, tanpa data demo).

## 12. Update aplikasi ke depan (setiap ada perubahan)
```bash
cd /opt/harmoni-crm && git pull
# backend:
cd backend && source venv/bin/activate && pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
sudo systemctl restart harmoni-backend
# frontend:
cd ../frontend && yarn install && yarn build && sudo systemctl reload nginx
```

## 13. Backup MongoDB (disarankan cron harian)
```bash
mongodump --uri="$MONGO_URL" --out /opt/backups/$(date +%F)
```

---

### Ringkasan port & alur
- Browser → **Nginx :443** → static (frontend) + `/api` → **uvicorn :8001** → **MongoDB :27017**
- Semua route backend berprefix `/api` (sudah sesuai kode).

### Gotcha penting
1. `emergentintegrations` butuh `--extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/` saat `pip install`.
2. `EMERGENT_LLM_KEY` **tidak berfungsi** di luar Emergent → pakai API key LLM sendiri untuk fitur AI.
3. `REACT_APP_BACKEND_URL` frontend harus **domain publik HTTPS**, bukan `localhost`.
4. Jangan pakai `--reload` di production (pakai `--workers 2` lewat systemd).
