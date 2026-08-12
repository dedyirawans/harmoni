# Contoh Workflow n8n untuk Safar Travel CRM

Ada 2 file workflow siap-import di folder ini:

| File | Arah | Fungsi |
|---|---|---|
| `1_crm_to_whatsapp.json` | CRM ➜ n8n ➜ WhatsApp | Kirim notifikasi WA otomatis saat ada booking/invoice/pembayaran/reminder/order confirmation |
| `2_whatsapp_to_crm_conversation.json` | WhatsApp ➜ n8n ➜ CRM | Catat pesan WA masuk pelanggan ke CRM (muncul di N8N Inbox) |

---

## A. Cara Import ke n8n
1. Buka n8n Anda ➜ tombol **"+"** (New Workflow) ➜ menu titik-tiga kanan atas ➜ **Import from File**.
2. Pilih salah satu file `.json` di folder ini.
3. Workflow muncul lengkap dengan node-nya. Lakukan penyesuaian di bawah, lalu **Save** dan **Activate** (toggle kanan atas).

---

## B. Setup Workflow 1 — CRM ➜ WhatsApp (WAJIB)
1. Klik node **"Webhook (CRM Event)"** ➜ salin **Production URL**-nya.
2. Tempel URL itu ke CRM: menu **Integration ➜ n8n Webhook ➜ Webhook URL**, aktifkan toggle, **Simpan**.
3. Klik node **"Send WhatsApp"** ➜ ganti:
   - **URL**: `https://GANTI-DENGAN-URL-PROVIDER-WHATSAPP-ANDA/api/send` ➜ isi endpoint kirim WA dari provider Anda (mis. WA Cloud API / Twilio / Fonnte / Wablas).
   - **Authorization**: `Bearer GANTI_TOKEN_PROVIDER_WA` ➜ token milik provider Anda.
   - Body `to` & `message` biasanya sudah cocok; sesuaikan nama field bila provider Anda berbeda (mis. `phone`, `text`).
4. Save ➜ Activate.
5. Uji: di CRM klik **Kirim Test Event**. Cek eksekusi masuk di n8n & WA terkirim.

> Node **"Compose WA Message"** sudah otomatis menyusun teks berbeda per event (booking.created, invoice.created, payment.recorded, payment.reminder, order.confirmation, conversation.reply). Boleh Anda edit kalimatnya.

---

## C. Setup Workflow 2 — WhatsApp ➜ CRM (opsional, untuk chatbot)
Prasyarat: di CRM buka **Integration ➜ N8N API Credentials ➜ Generate** ➜ salin **API Key** & **API Secret**.

1. Klik node **"Buat Signature HMAC"** ➜ edit 3 baris paling atas:
   ```js
   const CRM_API_URL = 'https://crm-access-control-3.preview.emergentagent.com';
   const API_KEY     = 'PASTE_API_KEY_ANDA';
   const API_SECRET  = 'PASTE_API_SECRET_ANDA';
   ```
2. Klik node **"Webhook (Pesan WA Masuk)"** ➜ salin Production URL ➜ pasang sebagai tujuan (webhook) di provider WA Anda untuk pesan masuk.
3. Save ➜ Activate.
4. Uji: kirim pesan WA dari HP ke nomor bisnis Anda ➜ cek pesan muncul di CRM menu **N8N ➜ Inbox**.

> Penting: node HTTP Request dikirim sebagai **raw body** persis string yang ditandatangani (jangan diubah), agar tanda tangan HMAC valid. Header wajib: `X-API-Key`, `X-Timestamp`, `X-Signature`, `X-Idempotency-Key`.

---

## D. Endpoint CRM yang bisa dipanggil dari n8n (semua butuh HMAC)
- `POST /api/v1/conversations` — catat pesan WA (dipakai Workflow 2)
- `GET  /api/v1/packages/{id}/availability` — cek sisa seat
- `POST /api/v1/bookings` — buat order AUTO SALES (butuh `external_booking_id` untuk anti-duplikat)
- `POST /api/v1/customers`, `POST /api/v1/leads`

Untuk membuat order/booking, salin pola HMAC dari node **"Buat Signature HMAC"** dan ganti `url` + `payload`-nya.
