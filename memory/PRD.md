## PHASE 9M.3 — Watermark Quotation + Stempel Center + Kekurangan Invoice (2026-06) — DONE (Verified render PNG)
- **Watermark Quotation**: quotation dengan status ≠ ACCEPTED mendapat watermark (default "DRAFT", teks diatur via `quotation_watermark_text` di template). Field baru di tab Template Dokumen + preview mendukungnya.
- **Stempel di tengah**: PAID (invoice) & LUNAS (kwitansi) diposisikan di pusat halaman A4 memakai `_d.pagesize` (bukan koordinat tetap) — terverifikasi center via render PNG.
- **Kekurangan pembayaran (invoice partial)**: invoice dengan outstanding>0 menampilkan baris "Sudah Dibayar" dan "Kekurangan Pembayaran" (merah) dari total tagihan.


## PHASE 9M.2 — Preview Multi-Dokumen + Stempel di Tengah (2026-06) — DONE (Verified curl)
- **Preview Quotation & Kwitansi**: `POST /api/doc-template/preview` menerima `kind` (invoice/quotation/receipt). UI tab Template Dokumen punya dropdown jenis + tombol Preview → iframe. Ketiganya terverifikasi 200 `%PDF-`.
- **Stempel di tengah**: watermark PAID (invoice) & LUNAS (kwitansi) dipindah ke pusat halaman A4 (105mm × 148.5mm), font 72, alpha 0.25 — berlaku di `build_document_pdf` dan `_render_receipt_pdf`. `_render_receipt_pdf(r, tpl=None)` kini menerima tpl untuk preview.


## PHASE 9M.1 — Upload Logo + Preview PDF + Stempel Kwitansi (2026-06) — DONE (Verified curl + screenshot)
- **Upload logo file**: tab Template Dokumen kini punya input file (base64 → `logo_url`, maks 2MB) + preview logo, selain input URL.
- **Preview PDF real-time**: `POST /api/doc-template/preview` merender contoh invoice dari template yang sedang diedit (belum disimpan) — tombol "Preview PDF" menampilkan hasil di iframe (dengan stempel + QR).
- **Stempel LUNAS di kwitansi**: `_render_receipt_pdf` menambahkan watermark diagonal (teks `paid_stamp_text`) bila `outstanding_total<=0` (kwitansi pembayaran lunas). Terverifikasi via kwitansi publik 200 `%PDF-`.


## PHASE 9M — Document Template + PAID Stamp + QR (2026-06) — DONE (Verified curl E2E + screenshot)
- **Template dokumen (Super Admin)**: `GET/PUT /api/doc-template` (key `doc_template` di company_settings). Atur warna utama/aksen, font (Helvetica/Times-Roman/Courier), judul (Invoice/Quotation/Kwitansi), logo, teks footer, teks stempel, toggle QR, dan Base URL publik. UI: Settings → tab "Template Dokumen" (admin-only).
- **Stempel PAID/LUNAS**: invoice dengan outstanding<=0 atau status PAID mendapat watermark diagonal (teks dapat diatur) di semua render invoice.
- **QR Code di Invoice/Quotation/Kwitansi**: setiap PDF menampilkan QR menuju endpoint publik `GET /api/public/documents/{invoice|quotation|receipt}/{id}?sig=HMAC` (signature HMAC-SHA256 dgn JWT_SECRET). Dapat diakses customer TANPA login; sig salah → 403. `public_url` disertakan di payload portal (invoices & receipts) untuk share/download.
- Refactor: semua render invoice/quotation/kwitansi (staff, portal, publik) memakai helper terpusat `_render_invoice_pdf/_render_quotation_pdf/_render_receipt_pdf` + `build_document_pdf(tpl, qr_url, paid)`. Lib baru: `qrcode[pil]`.
- Catatan: `JWT_SECRET` di .env ber-tanda kutip (dotenv melepasnya) — QR generate & verify pakai `_doc_sig` yang sama sehingga selalu konsisten.


## PHASE 9L.1 — Portal Upload Dokumen + Unduh Invoice/Kwitansi PDF (2026-06) — DONE (Verified curl + screenshot)
- **Upload dokumen dari portal**: `POST /api/portal/documents` (multipart doc_type+file, maks 10MB) → Emergent Object Storage, scoped ke `customer_id` token (source=portal). Tipe: PASSPORT/KTP/KK/PHOTO/VISA/VACCINE_CERT/OTHER. UI: pilih tipe + tombol Unggah di kartu Dokumen.
- **Unduh PDF**: `GET /api/portal/invoices/{id}/pdf` & `GET /api/portal/receipts/{id}/pdf` (auth via header atau `?auth=` token; ownership-checked). Reuse `build_document_pdf` (invoice) & builder kwitansi. Dashboard payload kini menyertakan `receipts` (dari `db.schedule_payments`).
- Keamanan terverifikasi: token staff → 401 pada endpoint portal; tanpa token → 401; PDF valid (`%PDF-`).


## PHASE 9L — Customer Portal (2026-06) — DONE (Verified curl E2E + screenshot)
- **Portal terpisah** (`/portal/login`, `/portal`), token JWT khusus (`type=customer_access`, klaim `customer_id`, exp 7 hari). Token staff & portal saling ditolak (401) — terverifikasi.
- **Login OTP** (Email via Emergent email; WhatsApp via n8n webhook `portal.otp`; jika n8n nonaktif OTP tetap dibuat & di-log + `debug_otp` di response untuk preview). OTP 6 digit, exp 5 menit, maks 5 percobaan, bisa kirim ulang. Tanpa self-registration (hanya customer terdaftar; email tak dikenal tak membocorkan keberadaan).
- **Endpoints**: `POST /api/portal/auth/request-otp`, `POST /api/portal/auth/verify-otp`, `GET /api/portal/me`, `GET /api/portal/dashboard`. Koleksi `customer_otps`.
- **Portal view (read-only, scoped ke customer)**: Profile, Booking (+Package, Departure, Payment Schedule dgn status/outstanding), Invoice, Documents, Refund Status, Ringkasan Pembayaran (Total/Paid/Outstanding/Next Due). Online payment disiapkan tahap berikutnya (view-only).


# Safar Travel CRM — Product Requirements (Living Doc)

## PHASE 9K.3 — Target 1 Tahun + Edit (2026-06) — DONE (Verified curl + screenshot)
- Target **hanya Super Admin** yang bisa set (backend `require_role("super_admin")`, frontend `isAdmin`; sales PUT single & bulk → 403 terverifikasi).
- **Set Target 1 Tahun sekaligus**: `PUT /api/sales/targets/bulk` {sales_id, targets:[{period,revenue_target,pax_target}×12]}. Dialog "Set 1 Tahun" menampilkan 12 bulan ke depan (mulai bulan terpilih), prefill target existing, isi-cepat + "Terapkan ke semua", "Simpan 12 Bulan".
- **Edit revisi**: tombol "Edit Bulan Ini" (single-month upsert) tetap ada per sales. `GET /api/sales/targets` kini mendukung `sales_id` untuk prefill.

## PHASE 9K.2 — Menu tweaks + Target default (2026-06) — DONE
- Menu **Approval** & **Approval Center** digabung jadi satu "Approval" → `/approval-center` (hub terpadu; rute `/approvals` tetap untuk aksi review/link "Open"). Berlaku di menu super_admin & accounting.
- Menu & judul halaman **N8N** diganti jadi **AI Automation** (icon Bot).
- **Sales Activity**: default periode = bulan berjalan sehingga kartu "Target Bulanan" + tombol "Set Target" (Super Admin) dan progress langsung tampil tanpa perlu pilih bulan manual.

## PHASE 9K.1 — Dashboard Activity Widget + Monthly Targets (2026-06) — DONE (Verified curl + screenshots)
- **Dashboard Widget** (`SalesActivityWidget.jsx`): di Super Admin Executive Dashboard — ringkasan bulan ini: total aktivitas, Top 3 Activity Score, Top 3 Revenue; link ke `/sales-activity`.
- **Target Bulanan**: koleksi `sales_targets` {sales_id, period(YYYY-MM), revenue_target, pax_target}. `GET /api/sales/targets?period=` (owner-scoped), `PUT /api/sales/targets` (super_admin only; sales→403 terverifikasi).
- **Progress**: `/api/sales/performance?period=YYYY-MM` kini menyertakan revenue_target/pax_target + revenue_progress/pax_progress (%). Kartu "Target Bulanan" di halaman `/sales-activity` menampilkan progress bar Revenue & Pax per sales; Super Admin punya tombol "Set Target".

## PHASE 9K — Sales Activity & Performance (2026-06) — DONE (Verified: curl RBAC + scoping, screenshots admin+sales)
- **Akses**: `require_permission("sales.view")` → Super Admin (lihat semua sales) + Sales (lihat diri sendiri). Accounting diblok (403, terverifikasi). Menu "Sales Activity" (super_admin) / "My Activity" (sales), route `/sales-activity`.
- **Activity Tracking** (7 tipe): Call, WhatsApp, Email, Meeting (manual via `sales_activities`), Follow Up/Quotation/Booking (dihitung otomatis dari koleksi masing-masing).
- **Endpoints**: `POST /api/sales/activities` (log manual; super admin bisa `sales_id` on-behalf), `GET /api/sales/activities` (feed timeline gabungan, owner-scoped, filter type/frm/to), `GET /api/sales/performance?frm&to&sales_id` → KPI per sales (leads, follow_up, quotation, conversion, booking, pax, revenue, commission) + activity_breakdown + **activity_score** + rankings.
- **Activity Score** (supporting KPI, BUKAN pengganti revenue): Call=1, WhatsApp=1, Email=1, Meeting=3, Follow Up=2, Quotation=5, Booking=10.
- **Ranking**: by_revenue, by_pax, by_booking, by_conversion, by_activity.
- **Frontend** `SalesActivity.jsx`: admin → tabel KPI + breakdown + ranking (tabs) + feed; sales → KPI cards diri + breakdown + feed. Tombol "Log Activity" (Sales & Super Admin). Filter bulan + filter sales (admin).
- Collection baru: `sales_activities`.


## PHASE 9J — Supplier Management (2026-06) — DONE (Verified iteration_35, Frontend 100% + backend 18/18 after fix)
- **Akses**: HANYA Super Admin + Accounting (`_SUP_ROLE = require_role("super_admin","accounting")`). Menu "Suppliers" (route `/suppliers`, perm `hpp.view`) muncul untuk 2 role tsb; Sales → 403.
- **Suppliers tab**: Supplier Master CRUD (name, type[Airline/Hotel/Transport/Visa/…], contact, email, phone, address, tax_info/NPWP, bank_account, status). Endpoints `POST/GET/PATCH /api/suppliers`, `DELETE` (soft-archive, super_admin only, reason wajib).
- **Supplier Costs tab**: pilih paket → tambah biaya (supplier, service, quantity, unit_cost, invoice, payment_status); `total_cost = qty*unit_cost`. `POST/GET/DELETE /api/supplier-costs` + `GET /api/supplier-costs/summary`.
- **Payments & Aging tab**: invoice supplier (amount, paid, due_date); `outstanding=amount-paid`, status PAID/PARTIAL/UNPAID, aging bucket current/1-30/31-60/60+. `POST/GET/PATCH /api/supplier-payments`.
- **HPP Integration**: ProductDetail Costing/HPP tab menampilkan "Linked Supplier Costs" + menambahkan Supplier Cost ke Total Cost (HPP), Gross Profit & Margin dihitung ulang.
- **Bug fix (iteration_35)**: duplikasi nama fungsi `_aging_bucket` (shadowing) → aging supplier selalu "Current". Fungsi Phase 9J di-rename `_sup_aging_bucket`. Verified via curl (due -15 hari → aging `1-30`).
- Collections: suppliers, supplier_costs, supplier_payments.


## PHASE 9I Enhancements Batch 2 (2026-06) — DONE (Verified iteration_34, Frontend 100% + backend curl)
- **Manifest Excel (.xlsx)**: `GET /operations/departures/{did}/manifest.xlsx` (openpyxl; role super_admin/accounting). Tombol "Excel" + "PDF" di detail departure.
- **Sales Alerts Widget**: `GET /operations/sales-alerts` (owner-scoped, booking sales ≤60 hari dengan issue payment/dokumen/paspor) → `SalesAlertsWidget` di Sales Dashboard; klik → /booking/{id}.
- **Passenger Filter**: filter Payment (PAID/PARTIAL/UNPAID) & Document (COMPLETE/INCOMPLETE) di tab Passengers (komponen `PassengersTab`), dengan penghitung hasil.
- Non-blocking: Recharts ResponsiveContainer width/height(-1) warning (kosmetik, pre-existing).


## PHASE 9I Enhancements (2026-06) — DONE (Verified iteration_33 + re-fix)
- **Room Type dropdown** (SINGLE/DOUBLE/TRIPLE/QUAD) di tab Rooming (Operations.jsx).
- **Unduh Manifest PDF**: `GET /operations/departures/{did}/manifest.pdf` (reportlab; role super_admin/accounting; token via header/?auth) → tabel penumpang (nama, L/P, paspor±EXP, room/group/bus, payment, docs). Tombol `download-manifest-btn` di detail departure.
- **Seat availability badge** menonjol di halaman Departures (hijau/amber/merah "Seat Habis").
- **Global Departure Alerts widget**: `GET /operations/alerts-summary` (departure ≤30 hari dengan alert) → widget `DepartureAlertsWidget` di Dashboard Super Admin & Accounting; klik → /operations.
- Catatan: 1 edit room_type→Select sempat hilang akibat race edit paralel same-file, sudah di-reapply. INGAT: edit server.py/berkas sama HARUS sekuensial.


## PHASE 9I — Departure Management / Operations (2026-06) — DONE (Verified iteration_32/33, Frontend 100% + backend curl)
- **Akses**: HANYA Super Admin + Accounting (`require_role("super_admin","accounting")`). Menu "Operations" muncul untuk 2 role tsb; Sales tidak melihatnya (API 403).
- **Endpoint baru** (`server.py`): `GET /operations/departures?within=all|7|14|30|60` (list + Total/Booked/Available Seat + Status + filter Upcoming); `GET /operations/departures/{did}` (Dashboard: total/booked/available, paid/partial/unpaid, documents_complete/missing, required_docs; Passenger List: customer, gender, passport(+expired), payment/document/booking status; Alerts); `PATCH /operations/travelers/{tid}/rooming` (room/group/bus/room_type per jamaah).
- **Booked seat** dihitung dari sum(pax) booking non-CANCELLED. **Alerts**: SEAT_ALMOST_FULL/SEAT_FULL, PAYMENT_DUE, PASSPORT_EXPIRED, DOCS_INCOMPLETE, DEPARTURE_APPROACHING(≤14 hari).
- **Dokumen wajib per paket**: UMROH/UMROH_PLUS = KTP,KK,PASSPORT,PHOTO,VISA,VACCINE_CERT,SISKOPATUH; TOUR = KTP,PASSPORT. DOCUMENT_TYPES frontend diperluas: +KK, VISA_TRANSIT, VACCINE_CERT, SISKOPATUH.
- **Frontend**: `Operations.jsx` (master-detail): daftar departure + filter Upcoming; detail dengan panel Alerts + tab Dashboard / Passengers / Rooming (edit & simpan room/group/bus). Route `/operations`.
- Backlog kecil: room_type sebaiknya dropdown; Recharts ResponsiveContainer warning (kosmetik) di Dashboard.


## PHASE 9H — Data Validation & Duplicate Prevention (2026-06) — DONE (Verified iteration_31, Frontend 100% + backend curl)
- **Customer Duplicate** (non-blocking warning): `GET /api/customers/check-duplicate?phone&whatsapp&email&passport_number` (didaftarkan DI ATAS `/customers/{cid}` agar tak ter-shadow). UI Add Customer: `useEffect` debounce 400ms → kotak `customer-dup-warning` menampilkan kandidat + field yang cocok; user tetap bisa lanjut.
- **N8N Duplicate / Idempotency**: `convert_to_booking` menerima `idempotency_key`/`external_order_id`/`n8n_workflow_id`; jika idempotency_key sudah dipakai → kembalikan booking sama (dedupe lintas-quotation, tanpa double-reserve). Terverifikasi curl.
- **Booking & Seat Validation**: sebelum booking validasi customer, package, pax≥1, harga>0 (total & per_pax), departure (ada & tidak CLOSED/CANCELLED), dan **available_seat ≥ pax** (seat 0/kurang → 400). Booking **mereservasi kursi** (`$inc confirmed_pax +pax`); status CANCELLED → `$inc -pax` (kursi dikembalikan). Terverifikasi curl (pax>quota 400, reserve, release).
- **Price Validation**: harga booking berasal dari config paket/departure (via quotation); override = diskon yang butuh approval sebelum convert (sudah ada).
- **Financial Validation**: `record_payment` menolak amount ≤ 0 dan amount > outstanding (hitung dari total − pembayaran non-VOID) dengan pesan 'Gunakan adjustment workflow'. `create_refund` menolak amount > refundable (paid non-VOID − refund sebelumnya). Terverifikasi curl + UI (toast 'melebihi outstanding').
- Catatan: parallel `search_replace` pada server.py berulang menyebabkan lost-write; SELALU edit server.py sekuensial (single write per pesan).


## PHASE 9G — Audit Trail, Soft Delete & Data Security (2026-06) — DONE (Verified iteration_29+30, Frontend 100%)
- **Audit Trail**: `log_audit` diperluas dengan field **reason** (wajib pada aksi destruktif) & **session_id** (dari header `X-Session-Id`, di-inject global via `frontend/src/lib/api.js`). Mencatat 14 modul (customer, lead, quotation, booking, invoice, payment, refund, commission, tax, package, hpp, user, permission, settings) + old/new/IP/user-agent. Endpoint `GET /api/audit-logs` filter: module, action, user_q, date_from, date_to.
- **Halaman Audit Log** (`AuditLog.jsx`): filter modul/user/tanggal, kolom Alasan & IP/Sesi, baris expandable menampilkan Nilai Lama vs Nilai Baru (JSON).
- **Soft Delete Master Data** (Super Admin only, reason wajib): Customer, Lead, User kini **soft archive** (`is_deleted=True`, status `ARCHIVED`, `archived_by/at`) — bukan hard delete. Endpoint: `DELETE /{customers|leads|users}/{id}?reason=`, `POST /{...}/{id}/restore`, `PATCH /customers/{cid}/status`. List punya param `include_archived`. UI: toggle "Show archived" + tombol Archive/Restore (gated `useAuth` super_admin) di Customers & Users.
- **Transaction Protection**: transaksi finansial tak punya hard-delete. **VOID Payment** baru (`POST /api/payments/{pid}/void`, Super Admin only, reason wajib) — set status VOID, `_recompute_invoice_status` mengabaikan payment VOID, invoice status ter-update. `GET /api/invoices/{iid}/payments` (baru) menampilkan riwayat + item VOID dicoret + tombol Void di BookingDetail.
- **Sensitive Data (HPP)**: sudah ter-cover sebelumnya (`strip_hpp` + perm `hpp.view`); Sales tak melihat HPP. Terkonfirmasi RBAC UI (Sales tak melihat kontrol arsip/void).
- **Catatan penting untuk agent berikutnya**: JANGAN lakukan `search_replace` PARALEL pada file yang sama (`server.py`) — menyebabkan race & edit hilang. Terapkan edit ke file yang sama secara SEKUENSIAL.


## Document CRUD Actions (2026-06) — DONE (Verified iteration_28.json, Frontend 100%)
- Backend: `POST /api/customers/{cid}/documents` (upload dokumen level customer + metadata Passport/Visa), `DELETE /api/documents/{doc_id}` (soft delete), `POST /api/documents/{doc_id}/replace` (ganti file + metadata). Helper `_find_doc` (lookup by uuid `id` ATAU ObjectId `_id`) + `_doc_scope_ok` (RBAC scoping booking/customer). customer_360 & /documents/expiring kini menyertakan dokumen customer-level. Memperbaiki bug laten: status/download dokumen sebelumnya query by uuid padahal `serialize()` menimpa `id` dengan ObjectId → 404 senyap; kini keempat endpoint dokumen resolve via `_find_doc` dan update by `_id`.
- Frontend: Customer 360 tab Documents punya tombol **Upload Dokumen** + aksi per baris **View / Replace / Delete** (dialog upload & replace, metadata khusus Passport/Visa). BookingDetail kartu jamaah kini punya ikon **View + Delete**, dan upload pada dokumen yang sudah ada otomatis **replace** (tanpa duplikat).
- Catatan (backlog kecil): token JWT masih via query `?auth=` untuk buka dokumen di tab baru (pola lama download); Dialog perlu `DialogDescription` untuk a11y.

## PHASE 9F — Document Management (2026-06) — DONE (Backend + Frontend, Verified)
- **Frontend (Phase 9F UI)**: metadata upload khusus Passport & Visa via `DocMetaDialog` di BookingDetail (input Nomor Dokumen, Tanggal Terbit, Tanggal Kedaluwarsa + file); dokumen lain tetap upload cepat. Kartu jamaah + tab Documents Customer 360 menampilkan nomor dokumen, tanggal exp, dan **badge peringatan expiry** (90/60/30 hari & overdue via helper `expiryTone`/`daysUntil`). Widget **"Dokumen Akan Kedaluwarsa"** (`ExpiringDocsWidget`, fetch `GET /api/documents/expiring?within=90`) ditampilkan di halaman **Tasks** DAN **Dashboard (Sales + Super Admin)**; klik item → navigate ke booking. Sales owner-scoped (empty state bila tidak punya). Upload PASSPORT kini **auto-sync** `traveler.passport_number` & `passport_expiry`.
- **Verified**: iteration_27.json — Frontend 100% (7/7 acceptance: widget di Tasks & Dashboard, dialog metadata khusus Passport/Visa, KTP quick upload, badge expiry di kartu jamaah & C360, RBAC Sales empty). Backend curl (metadata tersimpan, /documents/expiring days_left=25, passport sync).
- **Metadata**: upload dokumen (`POST /api/travelers/{tid}/documents`) kini menerima `document_number`, `issue_date`, `expiry_date` (+ doc_type, upload date, uploaded_by, status yang sudah ada). Mendukung dokumen customer (KTP/Passport/KK/Visa/Insurance/Ticket/Other) & transaksi (Quotation/Invoice/Payment Proof/Refund/Supplier Invoice/Booking Confirmation).
- **Expiry Warning** (Passport/Visa) di 90/60/30 hari + overdue: cron `_run_auto_scan` kirim notifikasi `DOCUMENT_EXPIRY` ke Sales pemilik + Super Admin (idempotent). Endpoint `GET /api/documents/expiring?within=90` (scoped) untuk daftar dokumen akan kedaluwarsa.
- **Access/Security**: download (`GET /api/documents/{id}/download`) kini RBAC-scoped — Sales hanya dokumen booking miliknya; Accounting hanya `FINANCIAL_DOC_TYPES`; Super Admin full. Storage aman via object storage; download WAJIB autentikasi (Bearer/token), tidak ada public URL.
- **Verified (curl)**: expiring endpoint (passport days_left 30), cron → DOCUMENT_EXPIRY muncul di notifikasi Super Admin, metadata tersimpan.

- **Payment Plan** (`POST /api/bookings/{id}/payment-plan`, perm payment.manage → accounting/super_admin; Sales 403): FULL (1 item), DP (DP + Pelunasan), INSTALLMENT (N cicilan). Auto-calc sehingga Σ amount = total booking (remainder di item terakhir). Field per item: payment_number, label, due_date, amount, paid_amount, outstanding, status.
- **Statuses schedule**: PENDING, PARTIAL, PAID, OVERDUE, CANCELLED (auto dari paid_amount + due_date).
- **Record collection** (`PATCH /api/bookings/{id}/schedule/{n}/record`): tambah paid_amount, hitung outstanding & status item + total booking. Auto naik status booking CONFIRMED→PARTIAL_PAID (ada bayar) dan →PAID saat outstanding=0.
- **Full Payment → Commission Eligibility**: saat outstanding total = 0 → payment_status=PAID, full_payment_date=today, commission_eligible=True + notifikasi COMMISSION_ELIGIBLE ke sales (mengikuti Full Payment Date; payout month rule via engine existing).
- **Reminder** (cron `_run_auto_scan`): per item schedule pada 7/3/1 hari sebelum, due date, & overdue → notifikasi ke Sales + kirim WhatsApp via n8n (event `payment.reminder`) + **tercatat di Conversation History** (OUTBOUND SYSTEM/AUTO), idempotent per hari.
- **Security**: Sales tak bisa ubah amount/plan (403); Accounting mengelola; Super Admin adjustment via Approval Center (Phase 9C).
- **Kwitansi PDF otomatis**: tiap pencatatan cicilan membuat kwitansi (`KW-xxxxx`) di koleksi `schedule_payments`; endpoint `GET /api/receipts/{id}/pdf` (perm booking.view) meng-render PDF (reportlab: no kwitansi, tanggal, booking, customer, termin, jumlah dibayar, sisa termin, sisa total, penerima). Frontend membuka PDF otomatis saat record + tombol **Kwitansi** per termin untuk unduh ulang.
- **UI**: tab "Payment Schedule" di BookingDetail (ringkasan Total/Paid/Outstanding, tabel jadwal + status, Generate Plan & Record + Kwitansi per item untuk yang berhak).
- **Verified (curl + screenshot)**: DP auto-calc, OVERDUE/PENDING auto, Sales 403, record→PARTIAL_PAID, lunas→PAID+commission_eligible+full_payment_date.

- **Booking Timeline** (`GET /api/bookings/{id}/timeline`): jalur normal Lead→Quotation→Quotation Converted→Booking→Payment→Documents→Departure→Completed; jalur cancellation Booking→Cancellation Requested→Super Admin Approval→Refund Calculation→Refund Approved→Refund Paid. Tiap step punya flag done + tanggal/detail. UI: tab "Timeline" di BookingDetail (stepper vertikal + Status Audit).
- **Booking statuses**: DRAFT, PENDING, CONFIRMED, PARTIAL_PAID, PAID, READY, COMPLETED, CANCELLED, REFUNDED.
- **Workflow validation** (`PATCH /api/bookings/{id}/status`, perm booking.manage): transisi dibatasi `BOOKING_TRANSITIONS` (mis. DRAFT tak bisa langsung PAID; CONFIRMED→COMPLETED ditolak). Ke PARTIAL_PAID/PAID **wajib ada transaksi payment**. Kontrol status via dropdown di BookingDetail (super_admin/booking.manage), minta alasan.
- **Audit**: setiap perubahan status disimpan di `booking.status_history` {old_status, new_status, user, role, reason, at} + `log_audit` + trigger n8n `booking.updated`.
- **Verified (curl + screenshot)**: timeline normal/cancellation, CONFIRMED→PAID tanpa payment=400, CONFIRMED→COMPLETED skip=400 (pesan pilihan valid), CONFIRMED→CANCELLED sukses + audit tercatat, UI cancellation-branch + Status Audit.
- Catatan: aksi Refund/Cancellation tetap via flow existing; detail Commission/Conversation di BookingDetail belum ditambah (tersedia di Customer 360).

- **Menu Approval Center** (`/approval-center`) — RBAC: Super Admin full; Accounting subset finance; Sales blocked (403).
- **Aggregated read** (`GET /api/approval-center?type=&status=`): normalisasi lintas sumber — REFUND (refund_requests), CANCELLATION (cancellation_requests), COMMISSION (commission_closings, super_admin saja), + generic adjustments (PRICE/PAYMENT/ACCOUNTING_ADJUSTMENT/OTHER dari koleksi `approvals`). Kolom: approval #, type, reference, customer, amount, requested by, date, status, action.
- **Dashboard** (`GET /api/approval-center/stats`): Pending, Approved Today, Rejected Today, Total This Month.
- **Generic approval workflow** (net-new, tak mengganggu flow existing): `POST /api/approval-center/adjustments` (accounting/super_admin buat pengajuan) + `POST /api/approval-center/adjustments/{id}/action` (super_admin only: APPROVE/REJECT/REQUEST_REVISION; **reason wajib** untuk Reject/Revision) + history log (user/action/date/comment). Notifikasi APPROVAL_PENDING ke super_admin & hasil ke pemohon.
- **Detail** (`GET /api/approval-center/detail/{source}/{id}`): transaction/customer/amount/reason/evidence + history (timeline utk refund/cancellation, history utk adjustment). Refund/Cancellation/Commission memakai tombol **Open** (deep-link) ke halaman existing (Approvals/Commission) agar state-machine teruji tidak diubah.
- **Security verified (curl)**: accounting list tanpa COMMISSION; sales 403; accounting action 403; reject tanpa reason 400; super_admin approve→APPROVED(history 2). Screenshot UI OK.

- **Notification Center**: bell di header (badge unread, dropdown per-user + per-role, titik prioritas, klik→navigate+mark-read, Mark all read). API: `GET /api/notifications`, `GET /api/notifications/unread-count`, `PATCH /{id}/read`, `POST /read-all`. Helper `notify(...)` dengan dedupe.
- **Event notifications wired**: NEW_LEAD (create_lead), FOLLOW_UP (create_follow_up), NEW_PAYMENT (role accounting) + PAYMENT_RECEIVED (sales) di record_payment. Approval/refund/commission ke super_admin tetap via `_notify` existing.
- **Scheduled notifications & auto-tasks** (cron `POST /api/cron/notifications-tasks`, Bearer `WEBHOOK_CRON_SECRET`, ack 2xx + BackgroundTasks, tiap 15 mnt via `.emergent/crons.yml`): FOLLOW_UP_DUE/OVERDUE, QUOTATION_EXPIRING(+task belum di-follow-up 3 hari), INVOICE_DUE/OVERDUE + PAYMENT_OVERDUE(+task tagih), CUSTOMER_REPLY handover(+task), booking tanpa dokumen(+task). Semua idempotent via `dedupe`.
- **Task Center** (`/tasks`, page `Tasks.jsx`): MY TASKS list + stats (Due Today/Overdue/Upcoming/Completed), filter status, ganti status inline, dialog New Task & New Follow Up (type Call/WhatsApp/Meeting/Email/Other + reminder Today/Tomorrow/3/7 Days/Custom). API: `GET /api/tasks`, `GET /api/tasks/stats`, `POST /api/tasks`, `PATCH /api/tasks/{id}`. Collections: `tasks`, extended `notifications`.
- **RBAC**: notifications per user_id/role; tasks scoped (super_admin all, lainnya assigned/created). Follow-up auto-membuat task + notifikasi ke sales pemilik.
- **Verified (curl + screenshot)**: create lead→NEW_LEAD notif; create follow-up→auto task (overdue=1) + notif; cron→FOLLOW_UP_OVERDUE + 11 auto tasks; cron auth 200 / no-auth 401; bell badge 24 + dropdown; Tasks page stats & list.
- Catatan: sebagian tipe enumerasi (Commission eligible/paid, Tax Deadline, Supplier Payment Due, System/N8N Error) BELUM di-wire ke event nyata — framework `notify()` siap, tinggal panggil di titik event terkait bila diperlukan.

- **Customer 360°** (`GET /api/customers/{id}/360`, page `/crm/{id}`): profil lengkap (Customer ID, Type, Phone, WhatsApp, Email, Gender, DOB, Lead Source, Assigned Sales, Since, Last Activity, NIK, Address), 9 statistik (Total Leads/Quotations/Bookings/Pax/Sales/Paid/Outstanding/Refund/Last Booking dari DB), dan 11 tab: Overview, Leads, Quotations, Bookings, Payments, Refunds, Commissions, Conversations (bubble WA + sender/channel/workflow id), Follow Ups, Documents, Activity Timeline (lead/quotation/booking/payment/document/cancellation/refund/commission).
- **Global Search** (`GET /api/search?q=`, header input): mencari customer name/phone/WhatsApp/email/ID, booking/quotation/invoice number, package name/code, payment reference, refund number, conversation. Hasil dikelompokkan: Customer, Lead, Quotation, Booking, Invoice, Payment, Package, Refund, Conversation. Klik → Customer 360 terkait.
- **RBAC**: `crm.view` + `owner_filter`; Sales owner-scoped (search & 360 hanya customer miliknya, non-owned → 403). HPP tidak pernah tampil. Tanpa data dummy.
- **Perbaikan**: invalid/malformed customer id di `/360` kini balas 404 (bukan 500).
- **Testing**: iteration_26 — Frontend 100% (search 3 pola, click-navigate, 11 tab, RBAC Sales), Backend 7/9 pytest (2 minor sudah ditangani/di-skip sesuai konvensi `_id`). File: `/app/backend/tests/test_phase9a_search_c360.py`.

- **Assign / Tangani**: percakapan handover bisa di-claim CS via tombol **"Tangani"** di header thread → tampil badge "Ditangani: <nama>" + tombol **"Lepas"**; indikator "● <nama>" di list item. `POST /api/integrations/n8n/conversations/assign` (super_admin, body {customer_id/whatsapp, release?}) simpan/hapus di koleksi `n8n_inbox_assignments` (key=customer_id atau `wa:<no>`). Anti-balas-ganda: bila membalas percakapan yang ditangani orang lain → konfirmasi dulu.
- **SLA Handover**: monitor menghitung `waiting_minutes` (sejak pesan INBOUND terakhir bila belum dibalas) & `sla_overdue` bila status REQUIRES_HUMAN dan waiting > `n8n_sla_minutes`. Ambang **SLA Handover (menit)** diatur di Settings → Global → Integration & Notifications (default 15). UI: badge merah "SLA <n>m" di list item + KPI "SLA Overdue" di dashboard N8N.
- Verifikasi: curl (assign→"Dedy Irawan"; SLA=1 → sla_overdue=1, waiting 6m>1m) + screenshot (header "Ditangani: Dedy Irawan"+Lepas, list "● Dedy Irawan", badge "SLA 7m").

- **Template CS Kustom**: dikelola Super Admin di **Settings → Global → "Template Balasan Cepat N8N Inbox"** (tambah/ubah/hapus label+teks). Disimpan di `system_settings.settings.n8n_reply_templates` (pakai PUT `/api/system-settings` yang sudah ada, tanpa endpoint baru). N8N Inbox memuat template ini via GET `/api/system-settings` (fallback ke 4 default bila kosong); chip kirim satu ketuk.
- **Filter "Perlu CS"**: toggle Semua / Perlu CS di Inbox — menyaring percakapan `status=REQUIRES_HUMAN` + badge jumlah, agar handover mudah diprioritaskan.
- **Sender indicator**: reply CS kini menyimpan `sender_name` (nama user). Bubble menampilkan label pengirim: nama customer (inbound), "AI Bot" (AI), "AUTO SALES / System" (SYSTEM), "<Nama> · Sales/CS" (SALES).
- Verifikasi: curl (template persist Salam Pembuka/Minta Data Jamaah, reply sender_name="Dedy Irawan") + screenshot (Settings editor card, Inbox filter Perlu CS=1, bubble label AI Bot/Sales-CS/nama).

- **Unread indicator**: monitor menghitung `unread_count` per percakapan (jumlah pesan INBOUND dengan timestamp > `last_read_at`). UI: titik biru + nama tebal + badge merah per item, badge total di tab Inbox. `POST /api/integrations/n8n/conversations/read` (super_admin) menandai dibaca (koleksi `n8n_inbox_reads` key=customer_id atau `wa:<no>`); dipanggil otomatis saat percakapan dibuka.
- **Search Inbox**: kotak cari client-side by nama customer / nomor WhatsApp.
- **Quick-Reply Templates CS**: 4 template siap pakai (Jam Operasional, Minta Data Jamaah, Cek Ketersediaan, Info Pembayaran) sebagai chip di atas kotak balasan; klik = kirim satu ketuk via endpoint reply.
- Verifikasi: curl (unread 2→0 setelah read) + screenshot (badge unread + dot + search box + 4 chip template + thread bubble).

- **Retry Failed Sync**: tab Sync Logs (`N8N.jsx`) kolom Retry + Action; baris FAILED punya tombol Retry → `POST /api/integrations/n8n/sync/{log_id}/retry` (super_admin). Re-deliver ke n8n bila base_url ada; hasil SUCCESS/FAILED/REJECTED + retry_count++ (idempotent, non-destruktif).
- **Centralized Conversation Inbox**: tab baru "Inbox" di `/n8n` (super_admin only). 2 panel: kiri daftar percakapan per-customer (nama/last message/HANDOVER badge), kanan thread bubble (customer kiri, AI/SALES/OUTBOUND kanan biru) + kotak balasan CS.
- **CS Reply**: `POST /api/integrations/n8n/conversations/reply` (super_admin) — simpan conversation OUTBOUND (sender_type SALES, ai_or_human HUMAN, status SENT), set customer.conversation_status=AGENT_REPLIED, trigger event `conversation.reply` ke n8n. Thread endpoint `GET /api/integrations/n8n/conversations/thread?customer_id|whatsapp` (super_admin) menangani percakapan tanpa customer_id (match by whatsapp).
- **Order Confirmation auto-reply**: sudah otomatis di backend — `v1_create_booking` (AUTO SALES) trigger `order.confirmation` (booking_number, customer, package, total, customer_phone) ke n8n saat booking dibuat.
- **RBAC**: semua endpoint baru super_admin only; Sales/Accounting tidak melihat menu N8N.
- Verifikasi: curl (thread 3 msg, reply OUTBOUND success, retry REJECTED tanpa base_url) + screenshot UI Inbox (bubble kiri/kanan, balasan CS terkirim & tampil).


## Phase 8J — N8N Admin Monitoring & Order Sync (2026-06) — DONE
- **Menu N8N khusus Super Admin** (`/n8n` → `N8N.jsx`; tidak tampil untuk Sales/Accounting; backend monitor 403 utk non-super_admin).
- **Dashboard**: `GET /api/integrations/n8n/monitor` (super_admin) — Connection Status, Last Sync, Messages Today (in/out/AI), Human Handover, Orders Today, AUTO SALES Orders, Failed Requests, API Errors (dari koleksi conversations, bookings AUTO SALES, n8n_api_logs, config).
- **Conversation Monitoring**: daftar per-customer (last message, AI status, status, last activity). **Order Monitoring**: order AUTO SALES (order id/customer/package/departure/pax/date/source/booking&payment status). **Sync Logs**: request id/event/method/direction/timestamp/status(SUCCESS/FAILED)/response/error/retry.
- **Test Connection**: tombol → `POST /integrations/n8n/test` (Connected + response time / Failed).
- **Availability Safety** (sudah ada Phase 7): `POST /v1/bookings` menolak bila available_seat < pax (DEPARTURE_FULL), package harus ACTIVE; seat berkurang hanya setelah booking CRM berhasil. Idempotency via external_booking_id (no duplicate). AUTO SALES → sales_pic_id=NULL (bukan salesperson, tanpa komisi kecuali di-assign; sesuai Phase 8E).
- **Access Control**: Super Admin full; Accounting & Sales tidak melihat menu & 403 di endpoint monitor.
- Verifikasi: curl (monitor stats real + RBAC 403 Accounting/Sales) + screenshot UI (9 KPI, 4 tab, connection banner). Backlog: field `publish_to_n8n` per package (ditunda agar tak regresi read N8N).

## Phase 8I — N8N Customer Communication Integration (2026-06) — DONE
- Membangun di atas Phase 6/7 (HMAC `n8n_auth`, rate-limit, ACTIVE-only reads, AUTO SALES + idempotent booking). Delta baru:
- **Conversation Log** (koleksi `conversations`): POST `/api/v1/conversations` (n8n_auth) mencatat pesan — conversation_id, customer_id, whatsapp, channel, direction (INBOUND/OUTBOUND), message, message_type, sender_type (CUSTOMER/AI/SALES/SYSTEM), receiver, ai_or_human, n8n_workflow_id, status, timestamp. **Customer matching** by whatsapp (existing → dipakai; else auto-create Source=N8N, PIC=AUTO SALES, sales_pic_id=NULL). **Idempotency** via external_message_id / X-Idempotency-Key.
- **Human Handover**: `requires_human:true` → status REQUIRES_HUMAN + customer.conversation_status=HUMAN_HANDOVER + event `conversation.handover` ke N8N.
- **History**: GET `/api/v1/conversations?customer_id|whatsapp` (n8n) & GET `/api/customers/{cid}/conversations` (crm.view) — kronologis.
- **Availability**: GET `/api/v1/packages/{id}/availability` (n8n) & `/api/packages/{id}/availability` (CRM) → package_name, departure_date, total_seat, booked_seat (pax non-cancelled), available_seat (live).
- **Frontend**: tab **WhatsApp Chat** di Customer360 (bubble kiri customer / kanan AI, badge HANDOVER, kronologis).
- **Security**: semua endpoint N8N wajib HMAC (X-API-Key/X-Timestamp/X-Signature); tanpa signature → 401. Scope terbatas (customer communication + order capture), bukan akses penuh DB.
- **Tests**: `tests/test_phase8i_n8n_conv.py` — e2e HMAC: availability, inbound(customer)+AI reply+handover, history kronologis (3), AUTO SALES booking + idempotent (no duplicate), 401 tanpa signature → SEMUA PASS. Frontend chat diverifikasi via screenshot.

## Phase 8H — Report Download, Export & Validation (2026-06) — DONE
- **Export & Print** untuk 8 laporan Phase 8G: tombol Excel / CSV / PDF / Print (A4) + Riwayat di toolbar `/reports`.
- **Endpoint** `GET /api/mgmt-reports/{key}/export?format=xlsx|csv|pdf` (token via Bearer header atau `?auth=`), plus `GET /api/report-exports` (riwayat).
  - **Excel** (openpyxl): company name, report name, periode, generated date, filter, header berwarna, data, TOTAL/SUMMARY, auto-width. Sheet title disanitasi (hapus `/ \ * ? : [ ]`).
  - **PDF** (reportlab): logo + company, judul, periode, generated, filter, tabel, summary, nomor halaman.
  - **CSV**: tabular saja (+ summary rows).
- **Penamaan file**: `[NamaReport]_[Period]_[GeneratedDate].[ext]` (mis. `Laporan_Laba_Rugi_Agustus_2026_2026-08-12.xlsx`).
- **Report Export History** (koleksi `report_exports`): report_name, user, waktu, format, filter, file_name. Accounting/SA lihat semua; Sales lihat milik sendiri.
- **Validation** (`_validate_report`): total baris vs summary harus konsisten; jika tidak → **409** dan export dibatalkan (P&L gross=rev-hpp, Neraca balanced, Penjualan/Piutang/Utang total baris=summary).
- **RBAC export** mengikuti REPORT_META finance flag: Sales 403 untuk Laba Rugi/Neraca/Arus Kas/Rekap Pajak/Utang; boleh export Penjualan/Kinerja Tim/Piutang (own-scoped).
- **Print A4**: CSS `@media print` (hide UI, tampilkan `#print-area` + header print company/report/periode).
- **Tests**: iteration_25.json — backend 51/51 (8 report × 3 format × RBAC/filename/history + regresi 8G) + frontend 100% (toolbar, download 3 format, Riwayat, Sales 3-tab + own export).

## Phase 8G — Financial & Management Reports (2026-06) — DONE
- **Menu Reports** (`/reports` → `Reports.jsx`, sebelumnya Placeholder) dengan 8 laporan dari data transaksi aktual (tanpa dummy):
  1. **Laba Rugi**: Pendapatan (Tour/Umrah/Lainnya), HPP (Flight/Hotel/Visa/Transport/Supplier/Other dari package_costs×pax), Gross Profit, Operating Expense (Salary/Marketing/Office/Transportation/Commission/Bank Fee/Other), Net Profit — nominal + persentase + margin.
  2. **Neraca**: Asset/Liability/Equity; retained_earnings = balancing figure → selalu balance (warning bila selisih).
  3. **Arus Kas**: Operating/Investing/Financing + Opening/Cash In/Out/Net/Ending.
  4. **Penjualan**: per-booking + summary (booking/pax/gross/net/paid/outstanding).
  5. **Kinerja Tim**: metrik per sales (leads/qualified/quotations/converted/bookings/pax/value/conversion/follow-up/overdue/commission) + ranking (revenue/pax/conversion/booking).
  6. **Rekap Pajak**: PPN (taxable/DPP/output/input/payable) pakai tarif Tax Configuration (bukan hardcode); PPh21/PPh23 struktur (kosong, no dummy).
  7. **Utang Usaha (AP)**: vendor + aging.
  8. **Piutang Usaha (AR)**: invoice + aging + sales.
- **Endpoints**: `/api/mgmt-reports/*` (prefix terpisah agar tak ke-shadow `/reports/{name}`). Filter: preset tanggal (daily/weekly/monthly/quarterly/yearly/custom) + product_type/package/sales/destination/status/vendor/customer/month/year/tax_type. Summary cards + tabel di setiap laporan.
- **RBAC**: Finance reports (P&L/Neraca/Arus Kas/Rekap Pajak/AP) = require_role(accounting, super_admin) → **Sales 403**. Sales-facing (Penjualan/Kinerja Tim/Piutang) own-scoped (sales lihat data sendiri). ROUTE_PERMS `/reports`=null (enforcement per-endpoint). Menu Reports ditambahkan ke Sales.
- **Catatan data**: tidak ada koleksi fixed asset/kapital/pinjaman/vendor-bill/employee → baris terkait bernilai 0 (data nyata, bukan dummy).
- **Tests**: iteration_24.json — backend 10/10 (RBAC + math P&L/Neraca/Arus Kas + tax config rate + scoping) + frontend 100% (8 tab render, role-filter, balance OK tanpa NaN, tab-switch race fixed). File: test_phase8g_mgmt_reports.py.

## Phase 8F — Tax Configuration & Tax Management (2026-06) — DONE
- **Tax menu** (`/tax`, sebelumnya Placeholder) → halaman baru `Tax.jsx` dengan 5 tab: Dashboard, Tax Transactions, Tax Master, PPN Configuration, Tax Reports. Diakses Accounting & Super Admin (RBAC tax.view/tax.manage); Sales tidak punya menu & di-block 403.
- **PPN Configuration (versioned)**: koleksi `ppn_configurations` — field config_name, tax_type, tax_rate, dpp_percentage, effective_from/until, status, description. CRUD (POST/PUT/DELETE-deactivate). **Versioning**: perubahan tarif = buat konfigurasi baru; `resolve_ppn_config(date)` memilih config ACTIVE yg range-nya mencakup tanggal (effective_from desc → yg terbaru menang).
- **Snapshot non-destruktif** (pilihan user = a): setiap invoice BARU menyimpan snapshot `tax_type, tax_config_version, tax_rate, dpp_percentage, dpp_amount` via `tax_snapshot()` (disuntik di create_invoice & AUTO SALES). Perhitungan nominal PPN TETAP pakai engine kategori (tanpa regresi harga). Transaksi lama tidak berubah.
- **Tax Transactions**: GET /tax-transactions (filter tanggal) → per-invoice (Invoice, Date, Customer, Tax Type, Rate%, DPP, Tax Amount, Config Version).
- **Tax Dashboard**: GET /tax-dashboard → active_config banner, total_dpp/ppn, taxable/non-taxable, transaction_count, by_type, by_month (6 bln) + 2 chart.
- **Tax Master**: mendukung PPN/PPh21/PPh23/OTHER (TAX_TYPES diperluas; tax_type configurable). CRUD via /tax-masters yg sudah ada.
- **Tax Reports**: GET /tax-reports (wrap report_tax) → summary + rows dengan filter tanggal.
- **Audit + Reason**: perubahan PPN config (rate/DPP/effective/type) tercatat di audit_log dengan old/new + **reason wajib** (di-enforce backend 400 & frontend). Seed default config "PPN Besaran Tertentu 1.1% (V1)".
- **Tests**: iteration_23.json — backend 15/15 + regresi 22/22 (8D/8E) pass; frontend 100% (5 tab render, PPN new/edit dgn reason, Sales 403). File: test_phase8f_tax_config.py.

## Phase 8E — Commission by Package & Monthly Payout (2026-06) — DONE
- **Commission Master** (tab rename dari "Commission Scheme"): commission dapat di-assign ke **Package spesifik** via **searchable dropdown** (GET /api/commissions/master-packages, super_admin). Field: Commission Name, Product Type, Package, Method (PER_PAX), Calculation Basis, Effective/End Date, Status, Tier (Min Pax → Amount/Pax), Notes. Model CommissionScheme diperluas: commission_method, notes.
- **Priority**: Package-specific > Product-specific > Default (via _scheme_rank yg sudah ada). Tier per-pax dipilih dari TOTAL eligible pax per scheme group.
- **Eligibility**: hanya booking lunas penuh (PAID basis). DP/Partial/Outstanding → tidak dapat komisi (tidak muncul).
- **Earning & Payout**: Commission earned pada Full Payment Date → Commission Month = bulan lunas; **Payout Month = bulan berikutnya** (helper _next_month). Closing menyimpan payout_month + sa_approval (PENDING default).
- **Payout gating**: PATCH /commissions/closings/{p}/status status=PAID hanya bila status=CLOSED **DAN** sa_approval=APPROVED **DAN** current_month ≥ payout_month (else 400). Tombol "Process Payment" disabled hingga syarat terpenuhi.
- **Lifecycle**: Calculate→REVIEW, Close (REVIEW→CLOSED), SA Approval terpisah, lalu Process Payment (→PAID). REOPEN super_admin.
- **Super Admin Approval** di APPROVAL → tab "Sales Commission" (GET /commissions/pending-approval): Approve / Reject / Request Revision (reason wajib) via PATCH /commissions/closings/{p}/approval; **Adjust** per-line (reason wajib) diizinkan SA walau CLOSED (set_line_adjustment relax + recompute closing total).
- **Statuses** per booking (_commission_status): NOT ELIGIBLE / ELIGIBLE / PENDING CLOSING / CLOSED / PENDING PAYOUT / APPROVED / PAID / REJECTED.
- **Sales My Commission**: tabel per-booking (Booking, Customer, Package, Departure, Pax, Full Payment Date, Tier, Commission, Commission Month, Payout Month, Status). Sales tidak dapat ubah amount.
- **Accounting Commission**: GET /commissions/accounting-summary → grup Current / Upcoming Payout / Pending Approval / Paid (Payout Overview tiles di /commission).
- **RBAC**: master-packages/pending-approval/approval = super_admin only (sales+accounting 403); scheme create/edit = super_admin only; accounting-summary & closings = commission.manage; /commissions/my = commission.view. AUTO SALES exclude kecuali auto_sales_commission ON (tak berubah).
- **Bug fix penting**: `serialize()` kini juga mengekspos `id` (selain `_id`) — memperbaiki key React & edit/delete Commission Master (sebelumnya `s.id` undefined). Backward-compatible (field tambahan).
- **Tests**: iteration_22.json — backend 17/17 pytest (priority, tier, eligibility, payout gating, approval reason-required, SA adjust-on-CLOSED, RBAC, per-booking my) + frontend 100% (Commission Master + package combobox, Payout Overview, SA approval tab, Sales per-booking table). File: test_phase8e_commission.py.

## Phase 8D — Super Admin Executive Dashboard (2026-06) — DONE
- **Executive Dashboard** menggantikan total dashboard SA lama (Dashboard.jsx: sales→SalesDashboard, accounting→AccountingDashboard, else→SuperAdminDashboard.jsx).
- **Periode**: default bulan berjalan + filter `<input type=month>` (exec-period-filter). Metrik period-scoped (revenue invoice, cash in/out, booking/pax/HPP/gross profit periode) vs kumulatif (receivable, refund, commission payable, outstanding).
- **KPI Sales**: leads (total/new/qualified/lost), quotation (total/converted/conversion rate), booking (total/pax/value).
- **KPI Financial**: Revenue (invoice), Cash In, Cash Out, Net Cash Flow, Outstanding Receivable, Refund Paid.
- **Profitability**: Revenue (booking), HPP/COGS (= package.total_cost × pax), Gross Profit, Gross Margin, Commission Payable. (Seed cost ≈80% harga jual utk 5 package yg di-booking → GM demo 74.6%.)
- **Tax & Refund**: DPP, PPN, PPh, Tax Payable, Refund pending/approved/outstanding.
- **Company Outstanding** (drill-down): unpaid/overdue invoice & receivable→/accounting, pending refund→/approvals, pending commission & commission payable→/commission, supplier→/accounting, tax payable→/tax.
- **Charts** (Recharts): Revenue+HPP+Gross Profit trend 6 bln (ComposedChart), Cash Flow in/out, Lead Funnel, Receivable Aging, Revenue by Package, Sales Performance per PIC.
- Backend: GET /api/executive-dashboard (require_role('super_admin'); param `month`=YYYY-MM). **Sales & Accounting → 403.**
- **Tests**: iteration_21.json — backend 5/5 pytest (200 + 13 keys + trend 6 bln + month filter + profitability arithmetic + RBAC 403), frontend 100% (4 KPI groups, 6 charts, 6 outstanding tiles clickable, period filter; regresi Sales/Accounting dashboard tetap). File: test_phase8d_executive.py.

## Phase 8C — Accounting Dashboard (2026-06) — DONE
- **Accounting Dashboard** di route `/` (Dashboard.jsx branch `role==='accounting'` → AccountingDashboard.jsx; Sales→SalesDashboard, Super Admin→dashboard lama tak diubah).
- **KPI**: Money In (revenue/invoice/payment/DP/installment/final), Money Out (expense/supplier/refund/commission payable/operational), Receivable aging (total/current/1-30/31-60/61-90/>90), Refund (requested/pending/approved/paid/outstanding), Tax (DPP/PPN/PPh/tax payable).
- **Charts**: Cash Flow (in vs out), Cash In Trend, Receivable Aging, Payment Status, Revenue by Package, Expense Breakdown.
- **Accounting Outstanding**: tiles klik → /accounting, /approvals, /commission, /tax (unpaid/overdue invoice, receivable, pending refund, pending commission, tax payable).
- Backend: GET /api/accounting-dashboard (require accounting.view; **Sales 403**). Data aktual dari invoices/payments/expenses/refund_requests/commission_lines.
- **Tests**: iteration_20.json (frontend 100%: 30 testids real numbers, 6 charts, clickable outstanding; Sales blocked, Super Admin dashboard tak berubah). Backend curl-verified.

## Phase 8B — Sales Dashboard (2026-06) — DONE
- **Sales Dashboard** di route `/` (Dashboard.jsx branch `role==='sales'` → SalesDashboard.jsx; Super Admin & Accounting tetap dashboard lama — tidak diubah).
- **KPI** (owner-scoped): Lead (new/active/qualified/lost), Quotation (total/outstanding/converted/conversion rate), Booking (total/pax/sales/avg pax), Follow Up (due today/upcoming/overdue/completed), Commission bulan ini (pax/tier/estimated/approved/paid).
- **My Outstanding**: tiles klik → navigasi (lead belum follow up→/sales, quotation→/quotations, follow up→/follow-ups, payment→/booking, upcoming departure→/booking).
- **Charts** (Recharts): Sales Trend (line 6 bln), Lead Funnel (Lead→Qualified→Quotation→Negotiation→Booking→Paid), Booking & Pax Trend, Lead Source, Package Performance (tabel top 10).
- Backend: GET /api/sales-dashboard (require sales.view, owner-scoped sales_pic_id; super_admin bisa ?sales_id=). **Security**: Sales hanya data sendiri, tidak ada HPP/cost/profit/margin.
- **Tests**: iteration_19.json (frontend 100%: 15 KPI real owner-scoped, 6 outstanding tiles clickable, 4 charts + package table; regression Super Admin/Accounting tetap dashboard lama). Fix route slugs + rename testid duplikat.

## Phase 8A — New Lead & Package Integration (2026-06) — DONE
- **My Sales → New Lead**: field "Interested Package" kini **searchable dropdown** (PackageCombobox) dari Package Master, hanya status **ACTIVE** (Tour + Umrah). Cari by package name/code/type/destination; opsi menampilkan name, code, type, destination, duration, departure terdekat, selling price, available seat.
- **Auto Destination**: dipilih package → Destination terisi otomatis & **READ-ONLY** (tidak bisa diketik); ganti package → destination ikut berubah.
- **Relasi**: lead menyimpan package_id, package_type, package_name, destination_id, destination_name (di-enrich backend dari package_id — FK ke Package Master; tidak sekadar text). Validasi: package wajib dipilih.
- Backend: GET /api/lead-packages (sales.view, ACTIVE only + seat/departure), POST /api/leads enrich dari package_id. Model LeadCreate/LeadUpdate diperluas.
- **Tests**: iteration_18.json (frontend 6/6) + curl backend (ACTIVE-only, persist package_id/destination_id). Phase 1–8/4B tetap berfungsi.

## Phase 4B — Refund Deduction & Non-Refundable Cost (2026-06) — DONE
- **Formula**: Final Refund = Total Paid − Total Deduction + Refund Adjustment, di-clamp ke ≥ Rp0. Total Deduction tidak boleh melebihi Total Paid (warning + clamp).
- **Deduction Type master** (collection deduction_types, 15 default: Cancellation Fee/Flight/Hotel/Visa/Transport/Handling/Muthawwif/Guide/Insurance/Meal/Airport Tax/Supplier Cost/Administration Fee/Bank Fee/Other). SA dapat tambah/hapus (system types tidak bisa dihapus).
- **Deduction methods**: FIXED, PERCENTAGE (%×total paid), PER_PAX, PER_TRAVELER, FULL_NON_REFUNDABLE. **Source**: Package/Departure/Booking/Traveler/Supplier/Manual Adjustment. Tiap item punya non_refundable flag + attachment_url + notes + added_by.
- **Refund policy** per Package/Departure (collection refund_policies, SA set) → saat cancellation approve, sistem generate Suggested Deductions (prioritas Departure > Package).
- **Versioning**: setiap perubahan (add/del deduction, adjustment, approval) menambah versions[] (version, changed_by, date, reason, previous/new amount). History tidak di-overwrite.
- **Manual adjustment** (SA only, reason wajib) +/−. **Payment cap**: proses pembayaran tidak boleh melebihi approved refund (400); dukung partial → PARTIALLY_REFUNDED → REFUNDED.
- **Impact**: /refund-requests/{id}/impact (accounting/SA, 403 utk sales) → revenue/HPP/gross profit/refund/non-refundable/net impact + tax (original/cancelled/final, dari booking tax, tidak hardcode). **Commission impact**: cancellation setelah closing final → commission_adjustments (pax_delta −1), tidak hapus closing.
- **n8n events**: refund.calculated/submitted/approved/rejected/processing/partially_paid/completed.
- **Reports**: /refund-reports/summary & /refund-reports/deduction-breakdown (accounting/SA; sales own).
- **RBAC**: Sales request/view only; Accounting add/propose deduction + review + process (tidak bisa adjust/approve); SA deduction master + adjustment + approve + policy + reopen. Semua di-enforce backend.
- **Tests**: iteration_17.json (frontend 4/4) + test_phase4b_deductions.py (backend 20/20). Phase 1–8 tetap berfungsi.

## Phase 8 — Cancellation & Refund Approval Workflow (2026-06) — DONE
- **Prinsip**: SEMUA cancellation/partial cancellation/refund WAJIB approval Super Admin. Tidak ada yang final tanpa Accounting Review → Super Admin Approval.
- **Cancellation flow**: Sales Request (Booking Detail, pilih full/partial pax + reason/detail/docs) → REQUESTED → Accounting Review (input cancellation_fee/non_refundable/supplier/other_deduction + recommendation, hitung estimated_refund = paid − fee − nonref − other) → ACCOUNTING_REVIEWED → Super Admin APPROVE/REJECT/REQUEST_REVISION. APPROVE → booking CANCELLED (atau PARTIALLY_CANCELLED), seat departure ter-update, traveler dibatalkan, + **auto-create Refund Request (CALCULATED)**. REJECT (reason wajib) → booking tetap aktif. REOPEN super_admin only.
- **Refund flow**: CALCULATED → Accounting Review (bank + recommendation + docs) → ACCOUNTING_REVIEWED → Super Admin APPROVE (boleh override proposed_refund) → APPROVED → Accounting Process Payment → REFUNDED / PARTIALLY_REFUNDED. Tombol Process 403 sebelum APPROVED.
- **RBAC (backend-enforced)**: cancellation.request (all), cancellation.review (accounting+SA), cancellation.approve (SA only), refund.request/review/process (accounting+SA), refund.approve (SA only), refund.view (all, sales own). Sales approve→403, Accounting approve→403, Accounting process sebelum approve→403.
- **Menu Approval** (SA), Cancellation & Refund (Accounting), Cancellations (Sales own read-only). **Notifikasi real** (collection notifications, /api/notifications per user/role) di setiap tahap. **Audit trail** + timeline per request (tidak dihapus).
- **Tests**: iteration_16.json — backend 17/17 + 2/2, frontend 100% (3 role E2E). Files: test_phase8_cancel_refund.py, test_phase8_frontend_ext.py, qa8_seed.py.

## Phase 7 — N8N Integration API & AUTO SALES (2026-06) — DONE
- **N8N API config** (Super Admin only, require_role): base_url, webhook_url, crm_api_url, environment, connection_status, api_key (masked di GET), api_secret & webhook_secret disimpan **terenkripsi Fernet** (ENCRYPTION_KEY di backend/.env). Endpoint: GET/PUT /api/integrations/n8n/api-config, POST .../generate (kredensial ditampilkan sekali), GET .../api-logs. Sales & Accounting → 403.
- **Machine API `/api/v1/*`** diamankan `n8n_auth`: X-API-Key + X-Signature=HMAC-SHA256(secret, timestamp+"."+body) + X-Timestamp (±300s anti-replay) + X-Idempotency-Key + rate limit 120/60s. Endpoint: POST customers/leads/bookings/payments/communications, PUT bookings/{id}, GET packages/departures/customers/{id}/bookings/{id}. HPP di-strip pada /v1/packages. Tidak ada akses HPP/Tax/Commission/Users/Settings/Audit.
- **Idempotency**: external_booking_id (+ collection idempotency_keys, unique). Request duplikat → tidak buat booking kedua (return idempotent=true).
- **AUTO SALES**: booking via n8n → booking_source=AUTO SALES, sales_type=AUTO, sales_user_id=NULL, sales_name="AUTO SALES", created_by="SYSTEM"; auto-buat Invoice; badge ungu AUTO SALES di list Booking. Manual → SALES/MANUAL + user saat ini.
- **Booking validation** (structured error): CUSTOMER_NOT_FOUND, PACKAGE_NOT_FOUND/NOT_ACTIVE, INVALID_PAX, DEPARTURE_NOT_FOUND/DEPARTURE_FULL, PRICE_INVALID, INVALID_TRAVELER.
- **Communication log** n8n: source=N8N, automation=true, channel=WHATSAPP, muncul di Customer 360 timeline. **API log** (masked) untuk Super Admin.
- **Webhook CRM→n8n events** diperluas: lead.created/updated, quotation.*, booking.created/updated/cancelled, invoice.created, payment.created/recorded/confirmed/overdue, payment.reminder, departure.updated.
- **RBAC final**: VISIBLE ONLY IF PERMITTED + ACCESSIBLE ONLY IF AUTHORIZED, semua divalidasi backend.
- **Tests**: iteration_15.json — backend 21/21 + 29/29, frontend 100%. Files: test_phase7_n8n_api.py, test_phase7_rbac_manual.py.
- ⚠️ Generate credentials selalu me-rotate secret; Super Admin generate sekali sebelum wiring workflow n8n asli.

## Phase 6 — Sales Commission & Monthly Closing (2026-06) — DONE
- **Rules (user-confirmed)**: tier rate FLAT untuk semua pax berdasar tier total pax sales; tanggal periode ikut Calculation Basis (PAID=tgl lunas, CONFIRMED/BOOKED=tgl booking, COMPLETED=tgl selesai/departure); eligible pax = jumlah traveler booking; sumber = Bookings + Invoices/Payments.
- **Scheme** (commission_schemes): scheme_name, product_type ALL/UMROH/TOUR/UMROH_PLUS, package_id, effective_from/until, calculation_basis (BOOKED/CONFIRMED/PAID/COMPLETED), tiers [{min_pax,max_pax,rate_per_pax}], auto_sales, status. Edit HANYA Super Admin (require_role); Accounting view-only.
- **Monthly Closing** (commission_closings): status OPEN→CALCULATING→REVIEW→APPROVED→CLOSED→PAID. Calculate menghitung lines+items; CLOSED mengunci (recalc/adjustment 400). REOPEN hanya Super Admin. Set PAID menandai semua line payment_status=PAID.
- **Report lines** (commission_lines): Sales, Total Pax, Tier, Rate, Total Commission, Adjustment (editable sebelum CLOSED), Final Commission, Payment Status. Drill-down per sales (commission_items).
- **Anti-duplikasi**: unique index (booking_id, traveler_id, period); traveler yang sudah masuk periode lain di-skip → tidak double-count antar bulan.
- **AUTO SALES**: booking source AUTO SALES tidak dapat komisi kecuali setting auto_sales_commission=ON (default OFF, Super Admin only) + scheme khusus auto_sales.
- **RBAC**: scheme edit/settings PUT/reopen = super_admin only; calculate/close/report/adjust/payment = commission.manage (Accounting kini punya commission.manage); /commissions/my = commission.view (Sales lihat milik sendiri). Legacy PUT /commission-settings dikunci super_admin.
- **Frontend** `/commission` (Commission.jsx): SA/Accounting → tab Monthly Closing + Commission Scheme (+ Settings SA only); Sales → My Commission (4 kartu + previous closing).
- **Acceptance test PASS**: A=5→Rp500k(0-9), B=12→Rp1.8jt(10-19), C=25→Rp6.25jt(20+); Sept exclude Aug-closed; CLOSED recalc ditolak. Tests: iteration_14.json (backend 19/19, frontend 100%), test_commission_acceptance.py.

## Phase 6 — Integrations: n8n + WhatsApp (2026-06) — DONE
- WhatsApp dikirim VIA n8n saja (backend POST JSON ke webhook n8n; n8n teruskan ke WA). User punya instance n8n sendiri.
- Config n8n (Super Admin only, perm settings.manage): webhook_url, enabled, per-event toggles, WhatsApp templates. Page baru `/integration` (perm integration.view, super_admin).
- Event auto-trigger (fire-and-forget via asyncio): quotation.created, quotation.sent, quotation.accepted, booking.created, invoice.created, payment.recorded. Setiap kiriman dicatat di collection `n8n_logs` (ok/skipped/error, status_code, payload) — tercatat walau n8n disabled (skipped=true).
- Payment reminder dispatch: POST /api/payment-reminders/dispatch hitung invoice H-30/H-14/H-7/H-3/DUE/OVERDUE, render template WA (placeholder {customer_name}{invoice_number}{outstanding}{due_date}{stage}{company_name}) + nomor WA customer, kirim ke n8n. Return {total, dispatched, n8n_enabled}.
- Endpoints: GET/PUT /api/integrations/n8n, GET /api/integrations/n8n/events, POST /api/integrations/n8n/test, GET /api/integrations/n8n/logs, POST /api/payment-reminders/dispatch.
- RBAC: semua endpoint n8n = settings.manage (Sales & Accounting → 403). Verified iteration_13.json (backend 16/16, frontend 100%).
- Fix: dedupe menu "Accounting" ganda di nav super_admin.

## Phase 5 — Accounting, HPP & Tax Engine (2026-06) — DONE
- Accounting Workspace (/accounting) tabs: Dashboard (Gross Sales/Discount/Net/Tax/Revenue/Cost/Gross Profit/Margin), Invoice, Receivable, Expense (CRUD), Refund (CRUD), HPP report, Tax, Reports.
- Tax Master fully configurable (Tax Code/Name/Type/Rate/Base/Effective From-Until/Treatment/Account/Active), no hardcoded rates, all changes audit-logged; treatments NON_TAXABLE/PPN_TERTENTU/PPN_STANDARD/CUSTOM_TAX/UMRAH_MURNI/UMRAH_PLUS. Seeded 4 defaults.
- Reports: revenue, tax (taxable/non-taxable/DPP/by package/by period/reconciliation), expense, profitability, sales, receivable, hpp — export Excel(openpyxl)/CSV/PDF(reportlab).
- New perms: hpp.edit, expense.view/manage, refund.manage, tax.manage, commission.manage. Security matrix verified: Sales→HPP/Tax/Accounting=403; Accounting→n8n(settings.manage)/Commission(commission.manage)=403; SA full.
- New collections: tax_masters, expenses, refunds. Tests: backend curl full pass; frontend 100% (iteration_12.json).

## Feature: Discount type + Super-Admin-only approval (2026-06)
- Quotation discount kini bisa PERCENT (%) atau AMOUNT (Rp nominal); backend hitung discount_amount + ekuivalen % untuk threshold approval.
- Approval super-admin-only: PATCH /quotations/{id}/status ACCEPTED butuh perm quotation.approve (403 utk Sales); discount-approval juga quotation.approve. Sales hanya buat/edit quotation. UI: tombol Accept & Approve/Reject hanya untuk Super Admin. Verified iteration_11.json (frontend 100%).

## Feature: Edit Quotation (2026-06)
- Quotation dapat diedit selama status DRAFT/SENT dan belum converted; backend PUT /quotations/{id} recompute amounts & tolak (400) jika ACCEPTED/converted. Tombol Pencil di /quotations, dialog "Edit Quotation". Verified iteration_10.json (frontend 100%).

## Bug fix (2026-06)
- Super Admin 403 on /quotations: hasPerm (AuthContext) now bypasses for role super_admin, matching backend ALL_PERMISSIONS. Verified iteration_9.json (frontend 100%).

## UI polish (2026-06)
- Dashboard charts recolored: multi-color pipeline bars, gradient area for monthly trend, vivid donut + colored source bars.
- List pages (Quotations, Bookings, Accounting invoices/receivables/reminders) converted to real tables with blue headers, column dividers, and zebra rows.
- Quotations menu confirmed present for Super Admin.

## Phase 4 — Quotation, Booking, Traveler, Document, Invoice, Payment (2026-06) — DONE
- **Quotation**: create from customer+package+pax+room+add-ons+discount; base price auto from Package Master (sales cannot alter). Amounts (subtotal/discount/tax/total) computed server-side. Statuses DRAFT/SENT/ACCEPTED/REJECTED/CONVERTED. Endpoints /api/quotations (+/status, /discount-approval, /pdf, /convert).
- **Discount approval** (configurable in Settings `discount_approval`): 0–sales_max% auto-approve (SALES); sales_max–approval_max% PENDING (APPROVAL); >approval_max% PENDING (SUPER_ADMIN). Accept/Convert blocked until APPROVED. Super Admin approves via /discount-approval (perm quotation.approve).
- **Quotation & Invoice PDF** (reportlab): company logo, customer, package, itinerary, pax, pricing, discount, tax, total, T&C, sales PIC. Served via ?auth=<token>.
- **Convert to Booking**: accepted+approved quotation → booking (BKG-#####) snapshotting package_version; no re-input. Booking sources: SALES, AUTO SALES, ADMIN, AGENT, PARTNER, WEBSITE, OTHER (AUTO SALES reserved for n8n Phase 7).
- **Traveler/Jamaah**: many per booking (full/passport name, NIK, passport+expiry, DOB, gender, nationality, phone, emergency contact, room type, special request).
- **Documents** (Emergent Object Storage): KTP/Passport/Photo/Visa/Marriage Book/Other; statuses Missing/Uploaded/Verified/Rejected; upload multipart, download via ?auth, status update.
- **Invoice**: generated from booking (INV-#####) with amount/discount/tax/total/due date; status auto Unpaid/Partially Paid/Paid/Overdue from payments vs total.
- **Payment**: record date/amount/type/method/bank/ref/notes (attachment_url string — file attach simplified); recompute invoice status.
- **Receivable**: total invoice − payment = outstanding; aging Current/1-30/31-60/61-90/90+.
- **Payment Reminder**: GET /api/payment-reminders computes H-30/H-14/H-7/H-3/DUE/OVERDUE structure for n8n (no notification sent yet).
- **RBAC**: Sales(quotation.manage, booking.manage, traveler.manage, document.manage, invoice.view, payment.view) own-scoped; Accounting(booking.view, invoice.manage, payment.manage, receivable.view, document.manage) all-scoped; Super Admin full + quotation.approve.
- Collections: quotations, bookings, travelers, documents, invoices, payments. Frontend pages: Quotations, Bookings, BookingDetail, Accounting.
- Tests: backend full curl E2E pass; frontend 22/22 (iteration_8.json). Object storage initialized at startup.


## Original Problem Statement
Build Phase 1 of a CRM Tour & Travel + Umrah web app (modern, clean, responsive, production-ready) with 3 roles: SUPER ADMIN, SALES, ACCOUNTING. Foundation & strict Role-Based Access Control.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). JWT Bearer auth. All routes under `/api`.
- **Frontend**: React 19 + React Router 7 + Tailwind + shadcn/ui. Bearer token in localStorage.
- **Auth**: Custom JWT (bcrypt hashing). Password reset via Emergent-managed Resend email.
- **RBAC**: `require_permission(perm)` and `require_role(...)` dependencies enforce access at the API layer (returns 403). Frontend mirrors with `ROUTE_PERMS` + `RequirePermission` guard.

## User Choices
JWT custom auth · real reset emails (Resend) · English UI · modern/professional design · seeded accounts.

## Roles & Permissions
- **super_admin**: all 22 permissions (cannot be restricted).
- **sales**: dashboard, crm, sales, packages, departures, commission, notifications (default data_scope = own).
- **accounting**: accounting, transactions, hpp, tax, commission, reports+export, notifications.
Super Admin can edit sales/accounting permissions via Settings > Roles & Permissions.

## Seeded Accounts (see /app/memory/test_credentials.md)
- Super Admin: dedyirawan18@gmail.com / Admin@123
- Sales: sales@safarcrm.com / Sales@123
- Accounting: accounting@safarcrm.com / Account@123

## Implemented (2026-06)
- Auth: login, logout, forgot/reset/change password, session, protected routes, brute-force-safe login.
- User Management (Super Admin only): CRUD, status toggle, role + data_scope (own/branch/all).
- Strict backend RBAC (verified: Sales→403 on hpp/users/audit; Accounting→200 hpp, 403 users).
- Role-based sidebar (menus auto-change per role) + 403 Forbidden page.
- HPP/Costing page restricted to Super Admin & Accounting (API-enforced).
- Audit Log (user, timestamp, module, action, record id, old/new value, IP, user agent) with module filter.
- Company Settings + Global Settings (numbering, payment methods, lead/booking sources, categories, tax, commission, n8n, notifications).
- Role-based dashboard placeholders + placeholder pages for future modules.
- DB collections: users, roles(implied), permissions(catalog), role_permissions, company_settings, system_settings, audit_logs, password_reset_tokens.
- Testing: backend 23/23 pytest pass; frontend 100% critical flows.

## Backlog (next phases)
- P1: CRM (customers/leads/follow-up), Sales pipeline & quotations, Product/Package management, Booking & travelers.
- P1: Accounting transactions, Tax reports, Commission payouts, Reports with export.
- P2: Integration (N8N/WhatsApp), branch-scoped data queries for Sales, dashboard analytics widgets.

## Next tasks
- Phase 4: Quotations, Bookings & travelers (versioned pricing), Invoices/Payments.

## Phase 3.2 — Product Filters + Dashboard Charts (2026-06) — DONE
- Product Management: Category filter (package-type-filter) + Sub-Category filter (package-sub-filter); backend list_packages accepts sub_category param.
- SEAT_IN_COACH now supports min_quota_pax with the SAME pricing logic as OPEN_TRIP (pax<quota → per-pax = quota*base/pax). Backend /packages/{id}/price handles both; UI shows Min Kuota Pax input + detail breakdown for both sub-categories.
- Package category & sub-category editable after creation (edit-type-select + Sub Kategori in edit dialog).
- Dashboard: data + charts only (removed quick-action nav buttons + placeholder). New GET /api/dashboard/charts (leads_by_stage, leads_by_source, monthly_leads, packages_by_type; ownership-scoped for Sales). Super Admin stat cards now real (Users/Customers/Leads/Packages). Charts via recharts.
- Tests: frontend 100% (iteration_7.json); backend curl-verified.

## Phase 3.1 — Product Categorization & Advanced Pricing/Tax (2026-06) — DONE
- **Categories**: UMROH / TOUR / UMROH_PLUS with human labels; **Sub-categories**: PRIVATE / OPEN_TRIP / SEAT_IN_COACH.
- **PRIVATE tiered pricing**: array of {min_pax, max_pax, price}; /packages/{id}/price returns per-pax by pax bracket.
- **OPEN_TRIP min quota**: min_quota_pax; when pax < quota, per-pax price = min_quota_pax*base/pax.
- **UMROH_PLUS tour_price_portion**: only tour portion taxed.
- **Category tax settings** (Settings > Global > 'Pajak per Kategori Produk'): umroh_percent(0)/tour_percent(1.1)/umroh_plus_percent(1.1). TOUR taxed on selling_price, UMROH_PLUS on tour_price_portion, UMROH untaxed.
- UI: shared component ProductAdvancedFields.jsx used in create + edit dialogs; ProductDetail overview shows Sub Category + Pajak Kategori and tier/min-quota breakdown.
- Tests: backend 12/12 (test_phase3_pricing_tax.py), frontend 9/9 flows + Phase1-3 regression clean (iteration_6.json).

## Phase 3 — Product / Tour & Umrah Package Management (2026-06) — DONE
- **Packages**: master (code, name, TOUR/UMRAH type, category, destination, duration, pricing tiers, tax, commission, status DRAFT/ACTIVE/INACTIVE/ARCHIVED, promo, terms, Umrah details incl. Makkah/Madinah hotel+nights, airline, visa, muthawwif, room type). Grid + filters + search.
- **Itinerary builder**: per-day CRUD, duplicate, and drag-and-drop reorder (admin); read-only for Sales.
- **Departures**: CRUD with auto available_seat = quota − confirmed_pax and status OPEN/ALMOST FULL/FULL. Global /departures browse for Sales.
- **Costing / HPP**: cost components (flight, hotel, visa, transport, guide, muthawwif, handling, meal, insurance, other) → total cost, gross profit, gross margin. VIEW: Super Admin + Accounting; EDIT: Super Admin only.
- **Versioning**: changing selling price snapshots old version into package_versions and bumps version.
- **RBAC**: Super Admin manages everything; Sales views only ACTIVE packages and NEVER receives HPP/cost/margin (stripped in API); Accounting views packages + costing read-only, cannot edit. Route guard now accepts multiple perms (product.view OR hpp.view) so Accounting reaches /products.
- New collections: packages, package_versions, package_itineraries, package_costs, departures.
- Tests: backend 16/16 Phase 3 + 31/31 regression; frontend 100% (iteration_4 + iteration_5). Files: /app/backend/tests/test_phase3_packages.py.

## Phase 2 — CRM & Sales Management (2026-06) — DONE
- **Customers**: master (full_name, whatsapp, email, gender, DOB, NIK, passport, address, city, country, type, source, tags, notes) with auto code CUST-#####. Ownership-scoped list/search + type filter.
- **Customer 360**: profile, KPIs, and unified Timeline (lead activities, follow-ups, communications, notes) + quick actions (note, log message, schedule follow-up).
- **Leads & Pipeline**: lead master (LEAD-#####) + Kanban across NEW→CONTACTED→QUALIFIED→QUOTATION→NEGOTIATION→BOOKING→PAID→COMPLETED (+LOST); stage moves logged to sales_pipeline + lead_activities.
- **Follow Ups**: today/overdue/upcoming/completed tabs, activity types, mark complete.
- **Sales Dashboard**: 10 KPIs + 5 quick actions. **Global Search** (customers/leads) in header.
- **Communications** log collection prepared for future n8n/WhatsApp.
- **Strict data ownership** (owner_filter/can_access_record): Sales sees only own data; HPP/cost/margin blocked (403). Super Admin data_scope=all. Accounting blocked from CRM/Sales (403).
- New collections: customers, leads, lead_activities, customer_notes, communications, follow_ups, sales_pipeline. Seeded demo data for Sales A (rina.sales) + second Sales user (andi.sales) for ownership tests.
- Tests: backend 50/50 (Phase1 regression + Phase2), frontend 100% acceptance. Files: /app/backend/tests/test_phase2.py.
