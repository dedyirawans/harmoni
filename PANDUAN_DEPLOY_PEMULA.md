# Panduan Deploy CRM ke VPS — Versi Pemula (Ubuntu)

Panduan ini dibuat sesederhana mungkin. Anda cukup **copy-paste** perintah satu per satu.
Yang perlu Anda siapkan sebelum mulai:
- IP VPS + password root (dari penyedia VPS Anda)
- 1 nama domain (opsional tapi disarankan), mis. `crm.perusahaananda.com`
- Aplikasi sudah di-"Save to GitHub" dari Emergent (dapat link repo, mis. `https://github.com/namaanda/harmoni-crm.git`)

> Ganti tulisan **HURUF BESAR** (mis. `IP_VPS_ANDA`, `DOMAIN_ANDA`, `PASSWORD_...`) dengan data Anda sendiri.

---

## LANGKAH 1 — Masuk ke VPS lewat SSH
Di komputer Anda buka **Terminal** (Mac/Linux) atau **PowerShell/CMD** (Windows), ketik:
```bash
ssh root@IP_VPS_ANDA
```
Masukkan password saat diminta. Kalau berhasil, tampilan berubah jadi `root@namavps:~#`.

---

## LANGKAH 2 — Perbarui Ubuntu (biar aman & terbaru)
Copy-paste semua ini, tekan Enter, tunggu selesai:
```bash
apt update && apt upgrade -y
```

---

## LANGKAH 3 — Install program yang dibutuhkan
Ini menginstal Git, Nginx (web server), dan Python:
```bash
apt install -y git nginx python3.11 python3.11-venv python3-pip build-essential curl
```

Install Node.js + Yarn (untuk membangun tampilan web):
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g yarn
```
Cek berhasil (harus muncul nomor versi):
```bash
node -v && yarn -v && python3.11 --version
```

---

## LANGKAH 4 — Install Database MongoDB
Copy-paste blok ini seluruhnya:
```bash
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
apt update && apt install -y mongodb-org
systemctl enable --now mongod
```
Cek MongoDB jalan (harus muncul `ok: 1`):
```bash
mongosh --eval 'db.runCommand({ ping: 1 })'
```

---

## LANGKAH 5 — Ambil kode aplikasi dari GitHub
Ganti link di bawah dengan link repo GitHub Anda:
```bash
cd /opt
git clone https://github.com/NAMA_ANDA/NAMA_REPO.git harmoni-crm
cd harmoni-crm
```
> Jika repo Anda privat, Git akan minta username + token GitHub.

---

## LANGKAH 6 — Siapkan Backend (mesin aplikasi)
```bash
cd /opt/harmoni-crm/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
```
> Langkah pip ini agak lama (beberapa menit), itu normal.

### Buat file pengaturan `.env`
Jalankan (ini membuat file otomatis — GANTI nilai yang perlu):
```bash
cat > /opt/harmoni-crm/backend/.env << 'EOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="harmoni_crm"
CORS_ORIGINS="*"
JWT_SECRET="GANTI_DENGAN_KODE_ACAK_PANJANG"
SUPER_ADMIN_EMAIL="irawandedy185@gmail.com"
SUPER_ADMIN_PASSWORD="Harmoni#Wisata2025"
SEED_DEMO_DATA="false"
FRONTEND_URL="https://DOMAIN_ANDA"
EOF
```
Untuk membuat kode acak `JWT_SECRET`, jalankan perintah ini lalu salin hasilnya ke dalam file:
```bash
openssl rand -hex 32
```
(Edit file dengan `nano /opt/harmoni-crm/backend/.env`, ganti `GANTI_DENGAN_KODE_ACAK_PANJANG`, simpan dengan `Ctrl+O` Enter, keluar `Ctrl+X`.)

### Tes backend jalan
```bash
uvicorn server:app --host 0.0.0.0 --port 8001
```
Buka browser: `http://IP_VPS_ANDA:8001/api/` — kalau ada respon, berarti OK.
Kembali ke terminal, tekan **Ctrl+C** untuk berhenti (nanti kita jalankan otomatis).

---

## LANGKAH 7 — Buat Backend jalan otomatis (selalu hidup)
Buat file service:
```bash
cat > /etc/systemd/system/harmoni-backend.service << 'EOF'
[Unit]
Description=Harmoni CRM Backend
After=network.target mongod.service

[Service]
WorkingDirectory=/opt/harmoni-crm/backend
EnvironmentFile=/opt/harmoni-crm/backend/.env
ExecStart=/opt/harmoni-crm/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```
Nyalakan:
```bash
systemctl daemon-reload
systemctl enable --now harmoni-backend
systemctl status harmoni-backend
```
Kalau tulisannya **active (running)** hijau → berhasil. Tekan `q` untuk keluar.

---

## LANGKAH 8 — Bangun Tampilan Web (Frontend)
```bash
cd /opt/harmoni-crm/frontend
echo 'REACT_APP_BACKEND_URL=https://DOMAIN_ANDA' > .env
yarn install
yarn build
```
> Kalau belum punya domain, sementara pakai: `echo 'REACT_APP_BACKEND_URL=http://IP_VPS_ANDA' > .env`
> `yarn build` juga agak lama, sabar ya.

---

## LANGKAH 9 — Atur Nginx (agar web bisa dibuka dari internet)
```bash
cat > /etc/nginx/sites-available/harmoni-crm << 'EOF'
server {
    listen 80;
    server_name DOMAIN_ANDA;

    root /opt/harmoni-crm/frontend/build;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 25M;
    }

    location / {
        try_files $uri /index.html;
    }
}
EOF
```
> Ganti `DOMAIN_ANDA`. Belum punya domain? Ganti jadi IP VPS Anda.

Aktifkan:
```bash
ln -s /etc/nginx/sites-available/harmoni-crm /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```
Sekarang buka browser: `http://DOMAIN_ANDA` (atau `http://IP_VPS_ANDA`) → halaman login CRM muncul!

---

## LANGKAH 10 — Pasang HTTPS (gembok hijau, gratis) — butuh domain
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d DOMAIN_ANDA
```
Ikuti pertanyaannya (isi email, ketik `Y`). Selesai → situs jadi `https://` otomatis.

---

## SELESAI! 🎉
Buka `https://DOMAIN_ANDA`, login dengan:
- Email: `irawandedy185@gmail.com`
- Password: `Harmoni#Wisata2025`
Segera ganti password dari menu profil setelah masuk.

---

## Kalau ada perubahan aplikasi nanti (update)
```bash
cd /opt/harmoni-crm && git pull
cd backend && source venv/bin/activate && pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
systemctl restart harmoni-backend
cd ../frontend && yarn install && yarn build
systemctl reload nginx
```

## Kalau ada masalah — cek log
```bash
systemctl status harmoni-backend      # status backend
journalctl -u harmoni-backend -n 50   # 50 baris log backend terakhir
systemctl status nginx                # status web server
```

## Catatan penting
1. Fitur AI: `EMERGENT_LLM_KEY` hanya jalan di Emergent. Di VPS, isi API key LLM Anda sendiri (OpenAI/Google) di `.env` bila butuh fitur AI.
2. Backup database rutin: `mongodump --out /opt/backup-$(date +%F)`
3. Firewall (opsional, biar aman): `ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable`
