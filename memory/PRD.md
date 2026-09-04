## PUBLISH PREP — Clean Slate + Rebranding (PT Harmoni Wisata Internusa) — DONE ✅
- Reset akun demo: hapus semua akun demo lama; hanya 1 Super Admin ter-seed = irawandedy185@gmail.com (password kuat di backend/.env SUPER_ADMIN_PASSWORD). User sales/accounting dibuat in-app oleh Super Admin.
- Clean slate data: wipe customers/leads/follow_ups/quotations/bookings/invoices/payments/travelers/documents/packages/departures/komisi/notifikasi/mmbc_bookings/history dll. Konfigurasi (role_permissions, system_settings, tax_masters, deduction_types, ppn_config) DIPERTAHANKAN.
- Demo seeding di-gate env SEED_DEMO_DATA (default "false"). Set "true" untuk seed ulang data+user demo.
- Rebranding: company_name default -> "PT Harmoni Wisata Internusa" (backend seed + BrandingContext + Reports fallback). Panel "Demo accounts" dihapus dari Login.jsx.
- Script pembersihan: /app/scripts/prepare_publish_cleanup.py. Login baru terverifikasi 200 + token.

## HOTEL — Master Hotel Agoda (1,35 juta) + Pencarian Hotel by-Nama (2026-08) — DONE ✅ (live terbukti)
- **Impor master hotel** dari CSV Agoda → koleksi `agoda_hotels`: **1.354.615 hotel** (hotelId, name, cityId, city, country, starRating, lat/lng, photo, url, reviewCount, ratingAverage, currency, type). Index: name_lower, (cityId, reviewCount), hotelId, reviewCount. Waktu impor ~132 detik.
- **Endpoint** `GET /api/hotel/hotels/search?q=&cityId=&limit=` (semua staff): prefix match nama (index-backed, cepat), opsional filter cityId, sort by jumlah ulasan; q kosong tanpa cityId → [] (hindari dump).
- **Frontend `HotelPicker.jsx`**: di Hotel List Search, ganti input Hotel ID mentah → cari hotel **by nama** (typeahead) dari database Agoda, pilih jadi chip (nama + #id), + fallback ketik Hotel ID manual. Hasil pilihan otomatis mengisi `hotelId[]` untuk live search.
- **VERIFIED LIVE**: cari "hilton" → Hilton Kuala Lumpur (#6961,5★,14861 ulasan) dll; pilih Millennium Hotel Sirih (#48666) → Live Hotel List Search 200, Rp600.000. Kota juga versi **search nama** (52k kota, `GET /api/hotel/cities?q=`) sesuai permintaan.
- File CSV mentah 1,3GB di /tmp dihapus setelah impor selesai (cities + hotels sudah di Mongo).


## HOTEL — Master Data Kota Agoda (2026-08) — DONE ✅ (live search terbukti jalan)
- **Impor master kota resmi Agoda** dari file data hotel (`E342B777...EN.csv`, 1.35GB, 1.354.617 hotel). Diambil **52.051 kota unik** (city_id ↔ nama ↔ negara ↔ jumlah hotel) → koleksi `agoda_cities` (index name_lower, count, cityId).
- **PENTING — City ID seed lama SALAH & sudah diganti**: Jakarta = **8691** (bukan 9395), Bangkok = 9395, Kuala Lumpur = 14524, Tokyo = 5085, Mecca = **78591**, Medina = **23028**, Bali = 17193.
- **Endpoint** `GET /api/hotel/cities?q=&limit=` (semua staff): tanpa q → kota terpopuler (by jumlah hotel); dengan q → cari nama (regex, sort by popularitas). **Alias Indonesia→Inggris**: makkah/mekah/mekkah→mecca, madinah/madina→medina (Agoda pakai nama Inggris).
- **Frontend**: `CityCombobox.jsx` sekarang mencari server-side (debounce 250ms) dari master + fallback ketik City ID manual. Endpoint & UI `hotel_cities` manual lama (POST/DELETE, CityManager) dihapus (master sudah komprehensif). `CityManager.jsx` menjadi file yatim (tak diimpor).
- **VERIFIED LIVE**: `POST /api/hotel/search` cityId 8691 (Jakarta), 28-30 Sep 2026 → status 200, **3 hotel nyata** (Millennium Hotel Sirih Rp600.000/4★, Holiday Inn Express, ANA Hotel). Kredensial Agoda aktif. (Catatan: 403 sebelumnya = rate-limit + City ID salah.)
- CSV mentah 1.35GB ada di `/tmp/agoda_data/` (untuk potensi impor master HOTEL by-name berikutnya bila diminta).


## HOTEL — Aktivasi Kredensial Agoda + Autocomplete Kota (2026-08) — DONE ✅
- **Kredensial Agoda AKTIF**: Site ID `1973232`, API Key `75c1...3e00` (dienkripsi Fernet at-rest). Test Koneksi = **200 sukses** (~142ms). CATATAN: input user berformat `SiteID:Key`, disimpan hanya bagian Key (backend menyusun header `SiteID:Key`).
- **Rate limit Agoda**: pencarian tunggal normal = 200; probe cepat berturut-turut memicu **403** (batas laju sisi Agoda), bukan bug. Live City Search 9395 sempat 200 count 0 (tergantung ketersediaan tanggal).
- **Autocomplete Kota by nama** (Agoda tak punya lookup nama→ID publik → admin-managed):
  - Backend: koleksi `hotel_cities` + `GET /api/hotel/cities` (semua staff, auto-seed 14 kota umum), `POST /api/hotel/cities` & `DELETE /api/hotel/cities/{id}` (super_admin). Diverifikasi: sales GET 200, sales POST 403.
  - Frontend: `CityCombobox.jsx` (Command+Popover, cari kota by nama, fallback ketik City ID manual) menggantikan input City ID di Hotel Search; `CityManager.jsx` (kelola nama↔cityId) di API Settings (super_admin).
  - Seed kota (best-effort, EDITABLE oleh admin): Jakarta 9395, Makkah 16901, Madinah 17047, Jeddah 16480, Bali 17193, Bandung 16057, Surabaya 18054, Yogyakarta 16063, Singapore 4064, KL 13170, Bangkok 3216, Tokyo 14690, Dubai 2758, Istanbul 12060. ⚠️ City ID selain 9395 belum terverifikasi live (kena rate-limit saat probe) — admin sebaiknya verifikasi via uji pencarian & koreksi bila hasil tak sesuai.


## PHASE HOTEL-3 — Integrasi Hotel ke Sales & Customer (2026-08) — DONE ✅ (backend pytest 13/13 + frontend 100%)
- **Add hotel ke Quotation**: dari hasil Hotel Search, tombol "+ Quotation" → `AddToQuotationDialog` (pilih customer existing / buat baru dedup by WA+nama, pilih quotation DRAFT/SENT existing ATAU buat baru, jumlah kamar). Endpoint `POST /api/hotel/add-to-quotation`.
- **Snapshot harga beku**: `_hotel_item_snapshot` menyimpan nights = checkout−checkin, total = dailyRate×nights×rooms, `agoda_daily_rate` (TERPISAH dari HPP), source `AGODA_API`, landingURL/imageURL, dll. Quotation lama tak tergantung data API live. Contoh terverifikasi: 1.5jt × 3 malam × 2 kamar = **9jt**.
- **Total terpisah**: `hotel_items[]`, `hotel_total`, `grand_total_with_hotel` disimpan di quotation. **Total paket inti (base/diskon/pajak/total) TIDAK diubah** → konversi ke Booking/Accounting/Tax tetap sama, hotel TIDAK ikut ke booking (sesuai spec item 12). QuotationCreate + create/update_quotation menyertakan hotel_items (update mempertahankan hotel lama bila body kosong).
- **Quotation baru "hotel-only"** diizinkan tanpa paket (package_name `(Hotel Only)`). Bisa juga append ke quotation existing.
- **Provider abstraction**: `HotelProvider` → `AgodaProvider` (registry `HOTEL_PROVIDERS`) untuk ekstensi provider masa depan tanpa merombak Customer/Quotation/Booking.
- **Customer & timeline**: pemilih "Untuk Customer" di Hotel Search; search dengan customer_id mencatat "Hotel Search" ke timeline; add-to-quotation mencatat `sales_activities` ("Hotel Added to Quotation", source AGODA_API) + aktivitas `hotel` di Customer-360.
- **PDF Quotation**: bagian **HOTEL** (tabel hotel/kamar/tanggal/malam/kamar/rate/total) + baris **TOTAL ESTIMASI (termasuk hotel)**. Kredensial tak pernah muncul.
- **Reporting**: `GET /api/hotel/stats` {hotel_searches, hotel_quotations, hotel_revenue} + strip di modul Hotel (bukan merombak Sales Dashboard/Reports). Scoped per sales.
- **RBAC/Keamanan**: add-to-quotation butuh `quotation.manage` → Sales 200, **Accounting 403**. `/api/hotel/stats` di-gate `quotation.manage` (Accounting 403) agar revenue hotel tak bocor; strip stats hanya render utk super_admin/sales. Sales tetap tak akses HPP. Kredensial Agoda tetap terenkripsi & tak terekspos.
- **Frontend**: `AddToQuotationDialog.jsx`, `HotelSearch.jsx` (customer ctx + triggers), `HotelWorkspace.jsx` (stats strip gated), `Quotations.jsx` (badge "Hotel (n)" + dialog rincian + "+ Hotel"/"Estimasi").
- **TIDAK dibuat** (di luar dok Agoda): booking confirmation/reservasi/cancel/refund. Booking Agoda hanya via redirect landingURL.
- **CATATAN**: Tanpa API Key Agoda live, Hotel Search real return 401 → alur "+Quotation" dari kartu hasil belum bisa diuji E2E via UI (backend add-to-quotation sudah diverifikasi API). Tests: `/app/backend/tests/test_hotel3_addquotation.py`, `/app/test_reports/iteration_58.json`.


## PHASE HOTEL-2 — Hotel Search & Availability (2026-08) — DONE ✅ (backend curl + testing_agent frontend 11/11)
- **2 tipe pencarian**: **City Search** (cityId) & **Hotel List Search** (hotelId[] multi, dipisah koma). Toggle tab di form.
- **Form modern**: Destinasi/City ID (dengan datalist COMMON_CITIES: Jakarta 9395, Makkah 16901, Madinah 17047, dst), Check-in/out (date, min hari ini), Dewasa, Anak + **Children Ages dinamis** (jumlah input usia = jumlah anak, auto-sinkron), Mata Uang (13: IDR/USD/SGD/MYR/THB/JPY/KRW/EUR/GBP/SAR/AED/AUD/CHF), Bahasa (8 kode Agoda: id-id/en-us/ja-jp/ko-kr/zh-cn/th-th/ms-my/ar-ae).
- **Filter server (City only)**: sortBy (12 opsi Agoda: Recommended, PriceAsc/Desc, StarRating Asc/Desc, 7 ReviewScore), minimumStarRating, minimumReviewScore, dailyRate min/max, discountOnly.
- **Backend** (`server.py`): `HotelSearchRequest` + `_build_agoda_criteria` (validasi: format YYYY-MM-DD, checkout>checkin, checkin≥hari ini, len(childrenAges)==numberOfChildren, city butuh cityId / hotel butuh hotelId[]). Payload Agoda LT benar: `criteria.additional.{currency,language,maxResult,discountOnly,occupancy{numberOfAdult,numberOfChildren,childrenAges},sortBy,minimumStarRating,minimumReviewScore,dailyRate{min,max}}` + `cityId`/`hotelId`.
- **`_agoda_call`**: timeout 25s (handle `requests.Timeout`→pesan khusus), mapping status 400/401/403/404/410/500/503/506 ke pesan Indonesia ramah via `_hotel_user_msg`. POST `/api/hotel/search` mengembalikan **200 anggun** `{results,count,status,error,partial,message,cached}` (error Agoda TIDAK dilempar sebagai 4xx/5xx agar UI tak crash; detail teknis hanya di API Logs).
- **Cache**: koleksi `hotel_search_cache`, TTL 10 menit, key = sha256(criteria+searchType). Hanya cache hasil sukses (>0). Badge "Dari cache" & "Sebagian hasil" (206) di UI.
- **Result mapping** (`_normalize_hotel`): hotelId, hotelName, roomtypeName, starRating, reviewScore, reviewCount, currency, dailyRate, crossedOutRate, discountPercentage, imageURL, landingURL, includeBreakfast, freeWifi → kartu hotel modern (badge diskon %, harga coret, bintang, ulasan, sarapan/wifi) + **dialog detail** dengan tombol **Book on Agoda** (buka `landingURL` apa adanya, tidak dikonstruksi manual).
- **Filter klien** (tidak mengubah hasil Agoda): min bintang/skor, harga min/maks, sarapan, wifi, diskon.
- **State UX**: loading "Mencari…" + tombol disabled (cegah duplikat via `inFlight` ref), empty (204/0 hasil), error, partial (206).
- **Search History** diperkaya: tipe, tujuan (cityId/hotelIds), tanggal, tamu, currency, hasil, status, oleh — tanpa kredensial.
- **RBAC**: Hotel Search & History = semua staff; API Settings & Logs = super_admin. **Hotel dihapus dari menu Accounting** sesuai spec. Diverifikasi: Sales 403 di /hotel/logs, 200 di /hotel/search.
- **TIDAK diimplementasikan** (di luar dokumentasi PDF): booking confirmation, reservasi kamar, cancellation, refund. Ruang lingkup: Search → Availability → Info Hotel → Redirect ke landingURL Agoda.
- **CATATAN**: API Key Agoda asli belum diisi → semua pencarian nyata mengembalikan 401 (EXPECTED). Setelah key valid diisi di API Settings, kartu hasil & dialog detail akan tampil. Tests: `/app/test_reports/iteration_57.json`.


## PHASE HOTEL-1 — Modul Hotel & Fondasi Integrasi Agoda API (2026-06) — DONE ✅ (testing_agent: backend 10/10, frontend ~95%)
- **Navigasi**: 1 menu "Hotel" (icon Hotel) di sidebar super_admin/sales/accounting → route `/hotel` (nav.js `ROUTE_PERMS['/hotel']=null`, App.js `/hotel`→HotelWorkspace). Pola tab seperti "AI & WhatsApp".
- **HotelWorkspace.jsx**: 4 tab — Hotel Search & Search History (semua staff); API Settings & API Logs (super_admin only, tab digate via `user.role`).
- **API Settings (super_admin)** `ApiSettings.jsx`: form Provider(Agoda), Site ID, API Key (password), Endpoint (default `http://affiliateapi7643.agoda.com/affiliateservice/lt_v1`), Bahasa (id-id), Currency (IDR), Status Aktif. Tombol Simpan + Test Koneksi.
- **KEAMANAN**: API Key dienkripsi at-rest dgn **Fernet** (`_enc/_dec`, `ENCRYPTION_KEY` di backend/.env) → disimpan sebagai `api_key_enc`, TIDAK pernah plaintext (diverifikasi di DB). Response ke frontend hanya `api_key_masked` + `api_key_set` (tidak pernah key penuh). `_hotel_log` membuang api_key/authorization/site_id dari log. PUT settings hanya menimpa key bila field diisi (partial update aman).
- **Backend endpoints** (server.py): GET/PUT `/api/hotel/settings` (super_admin), POST `/api/hotel/test-connection` (super_admin), POST `/api/hotel/search` (semua staff, via `_agoda_call`+`AgodaHotelService`), GET `/api/hotel/logs` (super_admin), GET `/api/hotel/search-history` (semua staff). Model hasil ternormalisasi (hotelId, hotelName, starRating, dailyRate, dst).
- **Verified**: RBAC 403 utk Sales di settings/logs; masking benar; test-connection & search gagal anggun (401 dgn kredensial dummy — EXPECTED, belum ada key asli); log tanpa secret. Tests: `/app/backend/tests/test_hotel_module.py`, report `/app/test_reports/iteration_56.json`.
- **CATATAN**: Kredensial Agoda asli belum diisi user; saat key valid tersedia, ulangi Hotel Search → hasil akan muncul.


## Enhancement — Gallery Editor + Lightbox + Include/Exclude Paket (2026-06) — DONE ✅ (curl + UI verified)
- **Gallery Manager (ProductDetail overview)**: komponen `GalleryManager` — tambah banyak foto (multi-upload base64), hapus per foto, "Jadikan Cover", preview besar (lightbox klik gambar). Simpan via PUT /packages/{pid} (kirim full pkg + patch, `model_dump()` menyimpan). Cover juga bisa diklik untuk lightbox.
- **Include/Exclude**: field `include`, `exclude` di `PackageModel` (auto-persist create+update). Ditampilkan di Overview detail (Include hijau / Exclude merah). Input textarea di dialog New Package (`new-include`/`new-exclude`) & Edit Package (`edit-include`/`edit-exclude`).
- **Verified**: PUT package → include/exclude tersimpan, gallery bertambah; screenshot menampilkan galeri + lightbox + Include list.
- **BELUM**: PageHeader untuk Users/Documents/WhatsApp/AI/Knowledge Base (ditunda; menyusul).

## Enhancement — PageHeader ke 4 halaman + Cover Upload New Package (2026-06) — DONE ✅ (UI verified)
- **PageHeader** diterapkan ke Quotations, Accounting, Suppliers, Reports (import + ganti blok judul lama). Konsisten dengan Dashboard/Bookings/Products.
- **New Package cover**: field "Cover Image URL" teks diganti kontrol upload gambar (file→base64) dengan preview + tombol Hapus (ganti/edit dengan upload ulang). testid: new-cover-upload / new-cover-preview / new-cover-clear.
- **Verified**: 4 halaman page-header=1; dialog New Package menampilkan kontrol upload cover.
- **BELUM**: editor galeri per-gambar di halaman DETAIL product (preview/tambah/hapus/set-cover) — masih read-only; jadi item berikutnya.

## Enhancement — Header Halaman Konsisten + company_name di Customer 360 (2026-06) — DONE ✅ (UI verified)
- **PageHeader** komponen baru (`components/PageHeader.jsx`): judul (font-display 3xl) + subjudul + slot actions + garis pemisah bawah. Diterapkan di Bookings, Products, SuperAdminDashboard, SalesDashboard, AccountingDashboard untuk tampilan seragam.
- **company_name di Customer 360**: ditampilkan di header profil (`c360-company`) DAN baris "Nama Perusahaan" di tab Overview. `/360` mengembalikan company_name. Verified tampil "PT Uji Edit Perusahaan".

## Enhancement — Auto-Expire Quotation + Polish Dialog/Border (2026-06) — DONE ✅ (curl + UI verified)
- **Auto-Expire Quotation**: `GET /api/quotations` kini otomatis set status quotation DRAFT/SENT (belum converted) menjadi **EXPIRED** bila usia > 7 hari (via `update_many`, `timedelta`). Verified: quotation di-backdate → jadi EXPIRED, lalu dipulihkan.
- **Polish Dialog**: overlay pakai backdrop-blur + `bg-slate-900/40`, konten `rounded-xl` + `shadow-xl` + border slate. Berlaku ke semua dialog.
- **Garis lebih jelas & tebal**: `index.css` — header tabel 2px, baris tabel 1.5px, border-t/border-b 1.5px, tablist underline, warna garis konsisten `--line`. Membuat batas kolom/baris/section lebih rapi di seluruh app.
- **Verified (screenshot)**: tabel Customers batas baris lebih tegas & rapi, dialog New Customer bersih dengan blur; nama perusahaan tampil di daftar.

## Fitur — Badge Kedaluwarsa, Nama Perusahaan di Detail, Setting Domain, Polish UI (2026-06) — DONE ✅ (curl + UI verified)
1. **Badge "Kedaluwarsa"**: di daftar Quotations (terbit + 7 hari, kecuali ACCEPTED/EXPIRED/REJECTED/converted) dan Invoices (terbit + 3 hari, hanya yang outstanding>0 & belum PAID). Inline expiry check di Quotations.jsx & Accounting.jsx (tab Invoice).
2. **Nama Perusahaan (company_name)**: tampil di header profil Customer 360 (+testid c360-company), dapat diinput saat Add Customer (Customers.jsx) dan Edit Customer (Customer360 EditCustomerButton). Backend `CustomerCreate` + list search sudah mendukung.
3. **Setting Domain**: field "Domain / URL Aplikasi" (`app_domain`) di Settings > Company; model `CompanySettingsUpdate` + PUT /company-settings menyimpannya. Verified tersimpan.
4. **(item 4 satukan semua setting) DITUNDA** atas permintaan user.
5. **Polish UI (seluruh app)** sesuai `/app/design_guidelines.json` (pertahankan warna biru/slate): Card (border-slate-200 shadow-sm), Button (active:scale), Badge (rounded-full pill), index.css (scrollbar halus, selection, popper z-index). Diterapkan via komponen shadcn global sehingga berdampak ke seluruh halaman.
- **Verified**: badge Kedaluwarsa muncul di Quotation (QT-00005) & Invoice overdue; company_name persist di detail & edit; app_domain tersimpan; UI tampil rapi & profesional (screenshot). Data backdate uji sudah dipulihkan.

## Fitur — Masa Berlaku, Kontak/Alamat Customer di PDF, Nama Perusahaan, Integrasi Conversation AI→CRM (2026-06) — DONE ✅ (curl + PDF-render verified)
1. **Masa berlaku**: Invoice = tanggal terbit + 3 hari; Quotation = + 7 hari (`_valid_until_label`).
2. **Tampil di PDF**: baris "Masa Berlaku s/d: DD Bulan YYYY" di invoice & quotation.
3. **Kontak customer di PDF**: No. HP + Email customer ditambahkan di blok Customer (invoice, quotation, kwitansi) via `_customer_contact` (lookup by customer_id/booking).
4. **Alamat customer di PDF**: alamat (address, kota, provinsi, kodepos, negara) tampil bila ada; dikosongkan bila tidak ada.
5. **Nama Perusahaan customer**: field `company_name` di `CustomerCreate`, form Add/Edit Customers, kolom daftar, dan **pencarian** CRM (ditambah ke `$or` list_customers + placeholder search).
6. **Integrasi Conversation AI→CRM**: helper `_mirror_crm_conversation` mencerminkan chat WhatsApp masuk (INBOUND) dan balasan AI/outbound (`_wa_enqueue_outbound`) ke koleksi `conversations` dengan `customer_id`, sehingga muncul di submenu Conversation CRM + Customer 360 dan bisa dianalisa AI.
- **Verified**: PDF invoice (Masa Berlaku 22 Agustus) & quotation (26 Agustus) menampilkan HP/email/alamat + masa berlaku; create+search company_name OK; webhook WA inbound → 1 conversation ter-mirror ke customer (INBOUND/CUSTOMER). Data uji dibersihkan.

## Enhancement — Tanggal & Tempat TTD + Opsi Ukuran/Posisi Stempel (2026-06) — DONE ✅ (PDF-render verified)
- **Baris tempat & tanggal**: field baru `signer_place` (Settings). Blok tanda tangan kini menampilkan baris "Kota, DD Bulan YYYY" (mis. "Jakarta, 19 Agustus 2026") di atas "Hormat kami," — tanggal mengikuti tanggal dokumen (Indonesia). Helper `_id_dateline(tpl, iso_date)`.
- **Opsi stempel**: field `stamp_scale` (0.4–2.0), `stamp_offset_x`, `stamp_offset_y` (Settings, slider). `_compose_sign_stamp` memakai skala & offset, dan `paste` clip-safe (stempel besar tidak error). Layout live dari Settings (tanda tangan tetap beku per dokumen).
- **UI Settings**: input Kota/Tempat + 3 slider (Ukuran %, Geser ↔, Geser ↕).
- **Verified**: render invoice dengan place "Jakarta", scale 1.6, offset (40,-10) → baris "Jakarta, 19 Agustus 2026" tampil, stempel membesar & bergeser, latar putih tetap terhapus. Data uji dibersihkan.

## Enhancement — TTD & Stempel: hapus latar putih otomatis (2026-06) — DONE ✅ (PDF-render verified)
- Helper `_remove_white_bg(img)` di backend mengubah piksel putih/near-putih menjadi transparan (soft ramp lo=208..hi=246 untuk tepi anti-alias, tetap menghormati transparansi asli). Diterapkan pada tanda tangan DAN stempel di `_compose_sign_stamp` (saat render), jadi berlaku juga untuk PNG yang sudah diunggah.
- Hasil: stempel di belakang tanda tangan tampak menyatu natural — tidak ada kotak putih. Verified dengan uji PNG berlatar putih (tanda tangan garis biru + stempel lingkaran merah) → keduanya transparan & stempel tembus di belakang tanda tangan.

## Update — Jabatan hanya Super Admin + Bekukan tanda tangan di dokumen terbit (2026-06) — DONE ✅ (curl-verified)
- **Jabatan (title) hanya Super Admin**: `PUT /api/auth/me/profile` kini hanya menerima `signature` (field `title` dihapus dari `MyProfileUpdate`). Dialog "Profil & Tanda Tangan" (kanan-atas) menampilkan Jabatan **read-only** + catatan bahwa jabatan hanya diubah Super Admin via User Management. Jadi sales hanya bisa ganti tanda tangannya sendiri.
- **Bekukan tanda tangan**: helper `_freeze_signer(kind,doc,tpl,collection)` — saat dokumen pertama kali di-render/terbit, snapshot signer (name/title/signature_url/stamp_url) disimpan di field `signature_snapshot` pada dokumen (invoices/quotations/schedule_payments) dan selalu dipakai untuk render berikutnya. Perubahan tanda tangan user/default TIDAK mengubah dokumen yang sudah terbit. `_signature_block` memakai stempel dari snapshot.
- **Verified (curl+DB)**: INV1 diterbitkan → snapshot "Dedy Irawan"; default signer diganti "NAMA BARU"+ttd baru → INV1 render ulang tetap "Dedy Irawan" (beku), INV2 baru = "NAMA BARU". `PUT /auth/me/profile {title:'HACK'}` diabaikan (title user tetap null).

## Fitur — Tanda Tangan, Nama, Jabatan & Stempel di Invoice/Kwitansi/Quotation (2026-06) — DONE ✅ (curl + PDF-render + UI verified)
- **Aturan penanda tangan**: Quotation → Nama/Jabatan/TTD milik SALES pembuatnya (via `sales_pic_id`). Quotation dari AI/Auto Sales → pakai default Settings. Invoice & Kwitansi → selalu default Settings. Stempel → selalu dari Settings, dipakai semua dokumen.
- **Backend** (`server.py`):
  - `doc_template` + defaults + `DocTemplateUpdate`: tambah `signer_name`, `signer_title`, `signature_url`, `stamp_url`.
  - User model (`UserCreate`/`UserUpdate`) + create/update: tambah `title` (jabatan) & `signature` (PNG data URL). Endpoint self-service `PUT /api/auth/me/profile` (title+signature) untuk semua user.
  - Helper: `_load_pil_image`, `_compose_sign_stamp` (Pillow: komposit TTD di depan + stempel semi-transparan di belakang → 1 PNG), `_signature_block` (blok kanan-bawah: "Hormat kami," → gambar → Nama garis-bawah tebal → Jabatan), `_resolve_signer(kind,doc,tpl)`.
  - `build_document_pdf(..., signer=)` render blok; `_render_invoice/quotation/receipt_pdf` + preview meneruskan signer sesuai aturan.
- **Frontend**:
  - Settings > Template Dokumen: field Nama Penanda Tangan, Jabatan, upload TTD Default (PNG), upload Stempel (PNG) — maks 2MB, data URL.
  - User Management create/edit: field Jabatan + upload Tanda Tangan Digital per user.
  - Menu profil kanan-atas: dialog "Profil & Tanda Tangan" (jabatan + TTD) agar tiap sales upload sendiri.
- **Verified**: Quotation nyata (Andi Pratama) tampil TTD+jabatan miliknya; Invoice & Kwitansi nyata tampil default (Dedy Irawan/Direktur); stempel menimpa TTD; semua preview & PDF endpoint 200; UI baru muncul tanpa error.

## Fix — Preview PDF Quotation gagal di halaman Settings (2026-06) — DONE ✅ (curl + screenshot-verified)
- **Gejala**: Di Settings > Template Dokumen, klik "Preview PDF" untuk Quotation → toast "Gagal membuat preview". `POST /api/doc-template/preview` return HTTP 500.
- **Akar masalah**: `quotation_terms` (rich-text) tersimpan dengan tag HTML tidak seimbang (ada `</b>` tanpa `<b>` pembuka). Parser mini-HTML ReportLab `Paragraph` menolaknya: `Parse error: saw </b> instead of expected </para>`. `_clean_terms` mempertahankan `<b>/<i>/<u>` tapi tidak menyeimbangkannya.
- **Fix**: `_clean_terms` (server.py ~L4180) sekarang: (1) menyeimbangkan tag inline b/i/u via stack (buang closer nyasar, tutup opener yang belum ditutup), (2) escape ampersand nyasar (`&` bukan entity) → `&amp;`. Ini membuat rich-text malformed apa pun aman dirender.
- **Verified**: quotation/invoice/receipt preview (template lengkap) → HTTP 200 PDF valid; 8 stress test rich-text malformed lolos tanpa error; screenshot Settings preview tampil.

## Fix — "ResizeObserver loop" error overlay saat pilih filter tipe customer (2026-06) — DONE ✅ (screenshot-verified)
- **Gejala**: Pilih tipe customer di CRM > Customers memunculkan overlay ERROR merah berulang: "ResizeObserver loop completed with undelivered notifications" (dari `bundle.js` handleError).
- **Sifat**: Warning browser jinak (dipicu Radix Select/Recharts saat re-measure layout), BUKAN bug fungsional. Hanya muncul karena CRA dev overlay menangkapnya.
- **Fix**: `frontend/src/index.js` menambahkan global `error` listener (capture) yang men-`stopImmediatePropagation` + `preventDefault` untuk pesan ResizeObserver dan menyembunyikan overlay dev jika sempat tampil.
- **Verified**: buka/ganti filter tipe berulang (VIP/Prospect/All types/Umrah) → `OVERLAY_PRESENT: False`, UI bersih.

## Fix P0 — Customer 360 "Customer not available (403 / not found)" (2026-06) — DONE ✅ (curl + testing_agent 100%)
- **Root cause**: `GET /api/customers/{cid}/360` return HTTP 500 (bukan 403). Koleksi `quotations` hasil seeding 10F menyimpan field `lead_id` sebagai `ObjectId` mentah, sedangkan `serialize()` hanya meng-convert `_id` → FastAPI gagal encode JSON. Frontend `Customer360.jsx` menampilkan pesan generik "Customer not available (403 / not found)" untuk semua non-200.
- **Fix**: (1) `serialize()` (server.py ~L204) kini meng-convert SEMUA field ObjectId top-level → string. (2) Migrasi data: 50 quotations dengan `lead_id` ObjectId di-convert ke string. (3) `scripts/seed_10f3.py` L81 diperbaiki agar simpan `str(ld["_id"])`.
- **Verified**: 129/129 customer `/360` HTTP 200 (curl). testing_agent iter_55: Super Admin 5/5 & Sales 3/3 buka Customer 360 sukses; path 403 non-owned tetap graceful. Frontend 100%.


## Cover 16:9 Crop + Cover di Overview Product Management (2026-06) — DONE ✅ (curl-verified)
- **16:9 auto-crop**: `POST /packages/{pid}/cover` kini center-crop gambar ke rasio 16:9 (Pillow) + resize maks 1280px → simpan JPEG. Verified: upload 1000×1000 → tersaji 1000×562 (ratio 1.779 ≈ 16:9), image/jpeg.
- **Cover di overview**: kartu paket di Product Management (`Products.jsx`) diubah dari tinggi tetap `h-28` → `aspect-video` (16:9) sehingga cover tampil proporsional & seragam di grid overview (TOUR & UMRAH).


## Galeri Paket + Kelola Cover di Product Management (2026-06) — DONE ✅ (curl + screenshot verified)
- **Galeri paket**: setiap paket kini punya `gallery` (3 foto: cover + 2 foto travel) — di-set di seed_10f1.py (fungsi `gallery_for`) & diisi ke 16 paket existing. Tampil di halaman detail paket.
- **Kelola Cover (Product Management)**: backend `POST /packages/{pid}/cover` (upload/replace, validasi JPG/PNG/WEBP maks 8MB → simpan object storage, cover_image = URL publik `/api/public/package-cover/{pid}?v=ts`), `DELETE /packages/{pid}/cover` (hapus), `GET /public/package-cover/{pid}` (serve publik tanpa auth untuk <img>). Semua admin ops = permission `product.manage`.
- **Frontend** `Products.jsx`: komponen `CoverControls` overlay pada tiap kartu paket — tombol Upload/Ganti (file picker) + hapus (merah), hanya untuk user `product.manage`. stopPropagation agar tidak memicu navigasi kartu.
- Verified curl: upload→URL publik, public serve 200 image/png, Sales upload 403, delete 200, 16/16 paket punya gallery≥3. Screenshot Product Management: cover per destinasi tampil + kontrol Ganti/Hapus/Upload.


## Enhancements after 10F: Reset script + Umrah scheme + Cover images + Commission approval (2026-06) — DONE ✅
- **Master reset+reseed**: `/app/scripts/reset_reseed_10f.py` — hapus SEMUA data demo/transaksional lama + semua user selain super_admin/accounting, lalu reseed 10F-1..10F-5 berurutan, recompute seat departure, ensure Umrah scheme, jalankan engine komisi + SA approval. Preserved: SA/Accounting/roles/permissions/Tax/AI/WhatsApp/API.co.id/company_files.
- **DIJALANKAN**: seluruh data demo lama (customers 142, leads 93, bookings 40, quotations 68, packages 40, conversations 67, dll) DIHAPUS; kini HANYA data 10F fresh: 130 customers, 85 leads, 16 packages, 18 departures, 50 quotations, 24 bookings, 12 suppliers, 53 conversations, 5 sales.
- **Umrah commission scheme** ACTIVE dibuat ("Skema Komisi Umrah", basis PAID, tier 250k/350k/500k per pax, non-auto).
- **Cover image** ditambahkan ke seed_10f1.py: tiap paket tour/umrah punya `cover_image` (Unsplash sesuai destinasi: Japan/Korea/Turkiye/Thailand/Swiss/Singapore/France/Bali; Umrah = Kaaba/Madinah).
- **Commission approval**: closing 2026-08 = **CLOSED + sa_approval APPROVED** (payable), Rp600.000, 3 sales (Fajar 300k, Andi 200k, Rina Maharani 100k). Payout→PAID **digated ke 2026-09** oleh business rule existing (`_current_month() < payout_month`) — bukan bug, sesuai aturan payout bulan berikutnya.


## PHASE 10F-6 — Demo Data Validation & Dashboard Consistency (2026-06) — DONE ✅ (read-only validasi + 1 cleanup)
- Validasi menyeluruh koleksi seed 10F (customers/leads/quotations/bookings/payments/commission/suppliers/conversations): SEMUA relasi & konsistensi PASS.
- **Cleanup 1 error nyata**: 16 departure punya `available_seat` basi (10F-3 meng-`$inc` confirmed_pax tanpa update available). Diperbaiki `available_seat = quota − confirmed_pax` (+status FULL/ALMOST FULL/OPEN). Hanya menyentuh koleksi `departures`. 0 inkonsistensi tersisa.
- **Dashboard live dari DB** (BUKAN hardcode): Super Admin (Users 12, Customers 142, Leads 93, Packages 40); Sales/Andi (My Leads 24, Quotations 9, Bookings 6, Commission); Accounting (Transactions, Pending Tax, Commission Payable, Gross Margin). Angka mencerminkan data seed nyata + data pra-eksisting.
- Preserved: Super Admin, Accounting, AI, Knowledge Base, Communication Style, WhatsApp, API.co.id, Roles, Permissions — TIDAK berubah. Tax TIDAK dimodifikasi.
- Variasi realistis dipertahankan (pending payment, overdue follow-up, lost lead, expired/cancelled quotation).


## PHASE 10F-5 — Demo Data: Supplier & WhatsApp Conversations (2026-06) — DONE ✅ (curl/db-validated)
- Seed idempoten `/app/scripts/seed_10f5.py` (guard 10F5). DB-only, TIDAK memanggil WhatsApp API / API.co.id; TIDAK menyentuh Tax/AI config/SA/Accounting.
- **12 Suppliers** realistis (Airline 2, Hotel 3, Transport 2, Tour Operator 2, Visa Provider 1, Muthawwif 1, Insurance 1) + **bank_accounts** (nomor fiktif; 4 supplier multi-rekening; tepat 1 primary per supplier).
- **16 conversation threads / 53 pesan** DEMO WhatsApp di koleksi `conversations`. sender_type: CUSTOMER 25 / AI 21 / SALES 7 (direction & ai_or_human konsisten). Semua pesan punya customer valid (53/53).
- **12 jenis percakapan** dicakup (Package/Price/Seat/Itinerary/Umrah/Payment Inquiry, Booking Intent, Follow Up, Human Handover, Not Interested, Package Comparison, Repeat Customer). Harga & nama paket mereferensi paket demo ASLI (mis. "Untuk 4 pax totalnya sekitar RpXX").
- **Atribusi**: 3 thread **AUTO SALES** (AI→Lead→Booking) tertaut ke booking AUTO SALES 10F-3 (customer+package konsisten, 3/3). 3 thread **Human Handover** (AI→REQUIRES_HUMAN→SALES→Booking) tertaut booking SALES. 2 pesan berstatus REQUIRES_HUMAN (muncul di inbox handover).
- Validasi: conversation→customer OK; AUTO SALES→booking→package/customer konsisten; booking→customer/package tetap valid dari fase sebelumnya.


## PHASE 10F-4 — Demo Data: Payment & Commission (2026-06) — DONE ✅ (curl-validated)
- Seed idempoten `/app/scripts/seed_10f4.py` (guard 10F4). Untuk 24 booking 10F-3: buat Invoice (db.invoices) + Payment (db.payments) + booking.payment_schedule (DP+Pelunasan) + paid_total/outstanding_total/payment_status. TIDAK menyentuh Tax/AI/WA/SA/Accounting.
- **Payment status**: PAID 9 / PARTIAL 8 / PENDING 4 / OVERDUE 3. Konsistensi 100%: outstanding = total − paid (PAID→0, PENDING→paid 0, PARTIAL→0<paid<total). Invoice status (Paid/Partially Paid/Unpaid/Overdue) sesuai logika `_recompute_invoice_status`.
- **Totals**: TOTAL Rp 1.339.385.000 | PAID Rp 745.871.000 | OUTSTANDING Rp 593.514.000.
- **Commission**: dihitung oleh **ENGINE EXISTING** (bukan hardcode) via `POST /commissions/closings/2026-08/calculate` (reopen→recalculate). Scheme aktif = "Skema Tier" basis PAID, product_type TOUR, non-auto, 100k/pax. Hasil: period 2026-08, 7 pax, **Rp 700.000**, status REVIEW/PENDING (belum PAYABLE — butuh approval SA + full payment). Terdistribusi 4 sales (Fajar 300k, Andi 200k, Rina Maharani 100k, Rina Sales 100k). AUTO SALES & non-TOUR & belum-lunas otomatis tidak dapat komisi (sesuai rule engine).
- Catatan: komisi hanya untuk booking TOUR lunas non-auto (sesuai satu-satunya scheme ACTIVE yang ada); booking UMRAH/AUTO tidak menghasilkan komisi karena tidak ada scheme yang cocok — ini perilaku engine existing, bukan bug.


## PHASE 10F-3 — Demo Data: Quotation & Booking (2026-06) — DONE ✅ (curl-validated)
- Seed idempoten `/app/scripts/seed_10f3.py` (guard `demo_seed_flags` batch=10F3). Reuse 85 lead 10F-2 + 16 paket/departure 10F-1. TIDAK membuat payment/commission (menyusul 10F-4). TIDAK menyentuh SA/Accounting/Tax/AI/WA/paket.
- **CATATAN ARSITEKTUR**: CRM ini TIDAK punya modul Order terpisah — alur = Quotation → convert → Booking. Jadi "Orders" = record Booking (unified). Order count = Booking count = 24.
- **50 Quotations** (QT-xxxxx), status bervariasi: CONVERTED 24, SENT 12, NEGOTIATION 4, FOLLOW UP 3, DRAFT 3, EXPIRED 2, CANCELLED 2. Semua mereferensi customer + package (+departure bila ada). Amounts konsisten (per_pax=selling_price, diskon 0/5/10%, tax 0 Non-PPN, total=subtotal−diskon).
- **24 Bookings** (BKG-xxxxx, reuse penomoran existing) dari quotation CONVERTED — converted_booking_id ter-set & 2 arah konsisten (pax & total quotation == booking, 0 mismatch). Status: CONFIRMED 18 / PENDING 5 / COMPLETED 1. Seat departure di-`$inc` (kecuali CANCELLED).
- **Atribusi**: 6/24 (25%) **AUTO SALES** (booking_source=AUTO SALES, created_by="AI AGENT", sales_type="AI"); 18/24 **SALES** (source=SALES, sales_type=MANUAL, ke sales user asli).
- Bugfix saat seeding: `lead_id` sempat tersimpan sebagai ObjectId (bukan str) → 500 di `GET /quotations`; diperbaiki jadi str (serialize hanya stringify `_id` top-level). Endpoint kembali 200.


## PHASE 10F-2 — Demo Data: Customers, Leads, Follow-ups, Sales Activities (2026-06) — DONE ✅ (curl-validated)
- Seed idempoten `/app/scripts/seed_10f2.py` (guard `demo_seed_flags` batch=10F2). Aditif; TIDAK membuat booking/payment/invoice/commission; TIDAK menyentuh SA/Accounting/Packages/Tax/AI/WhatsApp.
- **130 Customers** realistis Indonesia (13 kota + provinsi), status bervariasi (NEW/PROSPECT/ACTIVE/CUSTOMER/REPEAT CUSTOMER/INACTIVE), lead source bervariasi (10 sumber), semua ter-assign ke 5 sales dengan bobot performa berbeda (Andi 46 > Fajar 37 > Rina 24 > Rizky 15 > Siti 8). Kontak sintetis (@mail.demo), tanpa data pribadi nyata.
- **85 Leads** — SEMUA mereferensi paket ASLI 10F-1 (package_id + interested_package = package_name, 0 mismatch; destination konsisten dari paket) + terhubung ke customer. Stage sesuai CRM (NEW/CONTACTED/QUALIFIED/QUOTATION/NEGOTIATION/BOOKING/LOST).
- **113 Follow-ups** (db.follow_ups) — campuran: 41 completed, 41 overdue (pending+lewat due), 31 scheduled/upcoming. Tipe Call/WhatsApp/Email/Meeting. Terhubung ke lead & customer.
- **200 Sales Activities** (db.sales_activities, tipe Call/WhatsApp/Email/Meeting) + **162 timeline** (db.lead_activities: customer_contacted, whatsapp_chat, phone_call, package_presentation, quotation_requested, meeting).
- Validasi RBAC: Sales (Andi) hanya melihat 46 customer miliknya (data_scope own). Kredensial sales tetap Sales@123.


## PHASE 10F-1 — Demo Master Data Seed (Sales, Destinations, Packages, Departures) (2026-06) — DONE ✅ (curl-validated)
- Seed idempoten via `/app/scripts/seed_10f1.py` (guard koleksi `demo_seed_flags` batch=10F1). ADITIF — TIDAK menghapus paket lama (dipakai oleh booking existing) agar tidak merusak booking/report.
- Dibuat: **5 Sales user** realistis (Andi Pratama, Rina Maharani, Fajar Ramadhan, Siti Aulia, Rizky Saputra @harmoniwisata.co.id, role=sales, status active, data_scope own, password Sales@123), **14 Destinations** (koleksi `destinations`: 9 internasional + 5 domestik), **10 Tour packages** (TOUR-1001..1010), **6 Umrah packages** (UMR-1001..1006), **18 Departures** (Agu 2026–Jan 2027, utilisasi kursi bervariasi OPEN/ALMOST FULL/FULL).
- Setiap paket punya package_costs (HPP), package_itineraries, included/excluded, dan departure terhubung. HPP tetap terlindungi oleh `strip_hpp` (permission-based) — Sales TIDAK melihat HPP (diverifikasi: 0 kebocoran), Super Admin melihat HPP.
- PRESERVED: Super Admin (dedyirawan18@gmail.com), Accounting (accounting@safarcrm.com), roles, permissions, AI, WhatsApp, API.co.id, Tax — semua TIDAK berubah. Tidak membuat customer/lead/booking/payment/quotation/commission.


## Documents — Preview Inline + Filter Kategori & Pencarian (2026-06) — DONE ✅ (backend curl + FE smoke)
- **Preview inline**: `GET /files/{fid}/download?inline=1` kini set `Content-Disposition: inline` (bukan attachment) + dicatat sebagai aksi `PREVIEW` di log. Frontend: tombol mata (data-testid=preview-file-*) → dialog pratinjau (PDF via iframe, gambar via img); tombol Unduh di dalam preview. Hanya muncul untuk content_type image/* atau pdf.
- **Filter & pencarian**: input pencarian nama/deskripsi file (data-testid=file-search-input) + dropdown filter kategori (data-testid=file-category-filter, "Semua Kategori" + 9 kategori). Filtering di sisi klien atas daftar file yang sudah ter-scope RBAC.
- Verified: header inline vs attachment benar, log aksi [DOWNLOAD, PREVIEW], search+filter render. RBAC & scope tidak berubah.


## PHASE 10E-5 — File Download Center (Documents) + Regression (2026-06) — DONE ✅ (backend curl E2E; FE testing_agent)
- Menu baru **Documents** (`/documents`, terlihat semua role) — file internal perusahaan, BUKAN publik. Koleksi `company_files` + `file_downloads` (log).
- **Backend** (server.py): POST/GET/PUT/DELETE `/files[/{fid}]`, POST `/files/{fid}/replace` (versioning + version_history), GET `/files/{fid}/download` (authenticated header/?auth, cek akses+status, catat log IP/UA), GET `/files/download-logs`, GET `/files/meta`. Admin ops = super_admin only. Download = get_current_user via token; akses via `_file_access_ok` (super_admin all; else role ∈ allowed_roles atau user ∈ allowed_user_ids; status ACTIVE).
- **Access types**: ALL_STAFF/SALES/ACCOUNTING/SALES_ACCOUNTING/SPECIFIC (pilih user individual). Notifikasi otomatis ke role/user yang di-assign saat upload.
- **Validasi**: ekstensi pdf/doc/docx/xls/xlsx/csv/ppt/pptx/jpg/jpeg/png/zip; maks 25MB; file kosong ditolak.
- **Index baru**: company_files.category, company_files.created_at, file_downloads.file_id, file_downloads.timestamp.
- **Frontend** `FileDownload.jsx`: daftar file (nama/kategori/versi/uploader/tanggal/akses/status/aksi) + Upload/Edit/Replace/Delete + Download + dialog Log Unduhan (super_admin). Sales/Accounting: hanya lihat + download file yang diizinkan (tombol admin disembunyikan).
- Verified backend curl: upload SALES-access, bad-ext 400, SALES lihat/ACCOUNTING tidak, download 200/403/401, replace→v2 (history=1), SPECIFIC access, log tercatat, RBAC sales upload/logs/delete 403. Regression 10E-1/10E-2/10E-4 diuji via testing_agent.


## PHASE 10E-4 — Supplier Bank Accounts (multi) + Booking Number Display & Global Search (2026-06) — DONE ✅ (testing_agent iter_52: FE 100%; backend curl E2E)
### PART A — Supplier Bank Accounts
- Supplier kini punya array `bank_accounts` (id, bank_name, account_holder, account_number, is_primary, status). Field lama `bank_account` (string) tetap dipertahankan (kompatibilitas).
- Endpoint (super_admin/accounting): POST `/suppliers/{sid}/bank-accounts`, PUT `/suppliers/{sid}/bank-accounts/{aid}`, POST `/suppliers/{sid}/bank-accounts/{aid}/set-primary`, DELETE `/suppliers/{sid}/bank-accounts/{aid}`. Validasi bank_name+account_holder+account_number wajib; nomor rekening duplikat per supplier → 409. Hanya 1 primary (set primary meng-unset lainnya); tambah pertama auto-primary; hapus primary → auto-promote rekening lain.
- Frontend `Suppliers.jsx`: tombol "Kelola Bank" per baris → dialog `BankAccountsDialog` (tabel rekening + Add/Edit/Delete/Set Primary + checkbox utama + status). Kolom tabel "Bank Utama" menampilkan rekening primary (+badge jumlah).
### PART B — Booking Number & Search
- Nomor booking existing `BKG-xxxxx` DIPAKAI ULANG (tidak ada sistem penomoran kedua). Ditampilkan jelas sebagai badge biru di Booking List.
- `GET /bookings` kini menerima `search` (+ `status`). Search resolve nomor booking / nama customer / phone / whatsapp / email (via koleksi customers) → `$or` booking_number/customer_name/customer_id. Case-insensitive, whitespace-tolerant.
- Index DB baru: bookings.booking_number, bookings.customer_id, bookings.customer_name, customers.phone, customers.email, customers.whatsapp.
- Frontend `Bookings.jsx` (route `/booking`): input pencarian global "Cari nomor booking, nama customer, nomor HP, atau email..." (debounce 350ms) + filter status + tombol clear. Booking number sebagai badge prominent.
- Verified iter_52: 15/15 flow FE PASS. Backend curl: bank CRUD/primary/duplicate/validasi/RBAC 403; search number(case-insensitive)/name/email/wa-fragment/no-match/status/sales-scope semua OK. Data uji dibersihkan. Modul AI/WhatsApp/API.co.id/Tax/Accounting tidak tersentuh. (Minor a11y: DialogDescription ditambahkan.)


## PHASE 10E-2 — Forecasting CRUD (Manual Forecast) (2026-06) — DONE ✅ (testing_agent iter_51: FE 100%; backend curl E2E)
- **Forecast Manual CRUD** baru di koleksi `forecasts` (TERPISAH dari dashboard proyeksi otomatis Phase 9N). Field: period (YYYY-MM), salesperson_id/name, team, branch, forecast_revenue, forecast_pax, forecast_gross_profit, forecast_margin (auto = GP/Revenue×100 bila kosong), category, status, notes, is_deleted, audit metadata.
- **Backend** (server.py, semua `require_role("super_admin")`): GET `/forecast/meta` (categories/statuses/salespeople), GET `/forecast/records` (list + summary per periode & kategori), GET/POST/PUT/DELETE `/forecast/records[/{id}]`. Duplikat ditolak 409 (salesperson + period + category). Validasi 400 (period format YYYY-MM, salesperson wajib, angka ≥0). **Soft delete** (`is_deleted=true`) + audit via `log_audit(module="forecast")` untuk create/update/delete (user, waktu, old→new value).
- **Frontend** `Forecast.jsx` di-refactor jadi 2 tab: **Dashboard** (dashboard computed lama, utuh) + **Forecast Manual** (kartu ringkasan Revenue/Pax/GP/Margin, tabel ringkasan per periode, tabel records dengan aksi VIEW/EDIT/DELETE, dialog Add/Edit, dialog View, konfirmasi hapus "Apakah Anda yakin ingin menghapus forecast ini?").
- **RBAC**: `/forecast` tetap Super Admin only (Sales/Accounting tidak melihat menu; navigasi langsung → halaman 403). Sesuai keputusan user (tidak membuka ke Sales/Accounting).
- **Ruang lingkup dashboard**: integrasi hanya di halaman Forecasting (ringkasan total per periode) — TIDAK menyentuh Sales/Super Admin dashboard atau data aktual akuntansi (Forecast vs Actual tetap terpisah). Sesuai keputusan user.
- Verified iter_51: 9/9 flow PASS (2 tab, create margin auto 25%, duplikat 409 + dialog tetap terbuka, validasi period kosong, edit recompute, view metadata, soft delete + konfirmasi, summary update, RBAC sales 403). Backend curl: create/edit/delete/duplicate/validasi/RBAC/audit semua OK. Data uji dibersihkan.
- Tidak mengubah modul AI/WhatsApp/API.co.id/Customer/Booking/Accounting/Tax.


## PHASE 10E-1 — Customer Edit UI + Riwayat Perubahan (Audit) + User Reassign UI (2026-06) — DONE ✅ (testing_agent iter_50: FE 100%)
- **Edit Customer UI**: tombol "Edit Customer" (data-testid=edit-customer-btn) di profil Customer 360 → dialog `EditCustomerButton` (Customer360.jsx) dengan form field standar (nama, WA, HP, email, gender, tgl lahir, NIK, paspor, alamat, kota, provinsi, kode pos, negara, tipe, sumber, catatan). Kirim `PUT /api/customers/{id}`. Error nomor HP/WA duplikat (409) ditangani dengan toast ramah, dialog tetap terbuka.
- **Riwayat Perubahan (Audit) UI**: tab "Riwayat Perubahan" (data-testid=tab-audit) → `AuditTab` fetch `GET /api/customers/{id}/audit`, tampil timeline field-level (field, old→new, oleh siapa + role + waktu).
- **User Reassign UI** (Users.jsx): sudah lengkap dari sebelumnya — DELETE user 409 (ada data ter-assign) → dialog `reassign-dialog` (ringkasan data, pilih user tujuan, `POST /users/{id}/reassign` lalu arsip).
- Backend Phase 10E-1 (update_customer audit+409, customer_audit, delete_user 409, reassign) sudah ada & teruji curl dari sesi sebelumnya. Verified iter_50: edit notes sukses, 409 duplikat WA (6282323338838), audit-row muncul, archive dummy9g→reassign ke andi.sales sukses. Catatan: dummy9g DIPULIHKAN kembali (aktif) pasca-test agar kredensial valid.
- Non-blocking (LOW): warning hydration `<span>` di dalam `<option>` Users.jsx (dev-only, tak pengaruh fungsi).


## Brosur — Fix teks "LOGO AGENCY" & Tombol Hapus jelas (2026-06) — DONE ✅
- **Fix placeholder "LOGO AGENCY"**: prompt `_brochure_prompt` kini eksplisit MELARANG AI menggambar logo/placeholder/tulisan 'LOGO'/'LOGO AGENCY'/'YOUR LOGO' — cukup sisakan area kosong; logo asli ditempel sistem. Verified: brosur baru tampil dengan logo HWI asli (kanan atas), tanpa teks placeholder.
- **Tombol Hapus**: tiap kartu brosur kini punya tombol "Hapus" berlabel merah (super admin/canManage) + container flex-wrap agar rapi. (Sebelumnya hanya ikon.)


## Brosur — Fix Logo, Regenerate, Jadikan Utama, Kirim PDF WA, Watermark Kustom (2026-06) — DONE ✅
- **FIX LOGO tidak muncul**: brosur memakai `info = await get_settings_dict()` (baca system_settings, TANPA logo). Diubah ke `_get_doc_template()` yang merge `company_settings.company.logo` (data-URL) ke `logo_url`. Logo kini ter-stamp di atas gambar. (replace_all 2 lokasi generate).
- **Regenerate per kartu**: `POST /brochures/{bid}/regenerate` (kind AI) — pakai gen_meta tersimpan, buat ulang 1 gambar, replace storage record. UI tombol refresh per kartu.
- **Jadikan Utama**: `POST /brochures/{bid}/set-primary` — set is_primary (unset lainnya) + update `cover_image` paket ke URL brosur. UI tombol bintang (badge amber). `_brochure_out` menyertakan `is_primary`.
- **Kirim Brosur PDF via WA**: `send-brochure` kini pilih brosur is_primary (atau brochure_id), kirim sebagai `document` bila PDF, `image` bila gambar; fallback cover_image. Pesan tersimpan dgn type dinamis.
- **Watermark kustom**: `_stamp_brochure_image(img, info, opts)` menerima logo_position/logo_scale(0.05–0.4)/logo_opacity(0–255)/logo_margin. UI form: Ukuran Logo (%) + Opasitas Logo. Diteruskan ke generate/pdf/regenerate.
- Verified: set-primary ok (cover paket ter-update, is_primary benar), generate sukses, UI (scale/opacity/star/regen) tampil.


## Brosur AI — Preview, Logo Atas, Tanpa Itinerary, Unduh Gambar/PDF (2026-06) — DONE ✅
- **Preview**: dialog di BrochureTab menampilkan gambar penuh (object-contain) atau PDF via iframe (`?auth=token`), plus tombol unduh. Klik thumbnail/tombol "Preview".
- **Tanpa itinerary**: dihapus dari prompt AI (`_brochure_prompt`) & dari PDF (halaman itinerary dihapus → PDF kini 2 halaman: cover + Harga & Fasilitas). Verified /Page ≈2.
- **Watermark = LOGO dari Settings, di ATAS**: `_stamp_brochure_image(img, info, position)` menempel logo (logo_url dari settings) di atas gambar dengan backdrop transparan; posisi top-left/top-center/top-right (selector "Posisi Logo" di form). Bar teks bawah dihapus. Jika tak ada logo → gambar dibiarkan apa adanya.
- **Unduh Gambar & PDF**: `GET /brochures/{bid}/download?format=image|pdf`; untuk brosur gambar, `format=pdf` mengonversi gambar→PDF 1 halaman (reportlab) on-the-fly. UI kartu gambar punya tombol "Gambar" + "PDF"; kartu PDF punya "Unduh". Verified: image 200/png, image→pdf 200/application/pdf valid.
- Frontend: form kini punya selector Jumlah Varian + Posisi Logo; kartu punya Preview + unduh Gambar/PDF.
- Catatan: generate gambar AI kadang timeout gateway (~intermittent Nano Banana); generate-pdf & konversi terverifikasi. Endpoint mengembalikan varian yang sukses.


## Brosur AI — Varian, PDF Multi-Halaman, Watermark/Logo, Foto Referensi (2026-06) — DONE ✅
- **Varian brosur (1–3)**: `generate-infographic` menerima `variants` (1-3) & membuat beberapa gaya berbeda SECARA PARALEL (asyncio.gather → ~17s untuk 2, hindari timeout ingress). Mengembalikan list; mengembalikan varian yang sukses meski salah satu gagal (Nano Banana kadang balas tanpa gambar).
- **PDF multi-halaman**: `POST /packages/{pid}/brochures/generate-pdf` → cover infografis AI (Nano Banana) + halaman Itinerary (per hari) + halaman Harga & Fasilitas, disusun via reportlab, footer logo+kontak tiap halaman. Disimpan kind=AI_PDF (application/pdf). Verified: PDF 2MB multi-halaman valid.
- **Watermark & Logo**: helper `_stamp_brochure_image` menempelkan bar bawah (logo + company_name + phone/website dari settings) pada setiap gambar brosur AI; PDF punya footer branding di tiap halaman.
- **Foto referensi**: `reference_ids` (id brosur gambar terunggah) → di-decode base64 → dikirim sebagai `ImageContent` ke Nano Banana (mode editing) untuk dijadikan elemen visual. UI: seksi "Foto referensi untuk AI" (centang thumbnail). Upload foto = endpoint upload gambar yang sama.
- **Frontend** `BrochureTab.jsx`: dropdown Jumlah Varian, seksi foto referensi, tombol Generate Infografis / Generate PDF Multi-Halaman / Upload; galeri kartu dengan badge AI / AI PDF / Upload.
- Helpers baru: `_fetch_img_bytes`, `_stamp_brochure_image`, `_brochure_reference_images`, `_brochure_prompt`, `_nano_banana_image`.


## Brosur Paket: Upload/Download + Generate Infografis AI (2026-06) — DONE ✅ (AI E2E tervalidasi)
- **Lokasi**: tab "Brosur" di halaman Detail Paket (Product Management). Super Admin (product.manage) upload/generate/hapus; Sales (product.view) melihat & download.
- **Backend** (server.py, koleksi `package_brochures`):
  - `GET /packages/{pid}/brochures` (view) · `POST /packages/{pid}/brochures` upload PDF/gambar ≤15MB (manage) · `GET /brochures/{bid}/download` (auth header atau ?auth) attachment · `DELETE /brochures/{bid}` soft-delete (manage) · `GET /public/brochure/{bid}?sig=HMAC` (serve publik untuk provider WA).
  - `POST /packages/{pid}/brochures/generate-infographic` (manage): bangun prompt Indonesia dari data paket (nama/harga/durasi/destinasi/itinerary) + form (theme, highlights, promo, cta, extra) → **Gemini Nano Banana** `gemini-3.1-flash-image-preview` via emergentintegrations (EMERGENT_LLM_KEY) → simpan PNG ke Object Storage, record kind=AI. Verified E2E: menghasilkan infografis 761KB (tema hijau-emas, highlight fasilitas, itinerary, CTA).
- **Frontend**: komponen `components/BrochureTab.jsx` — form generate + tombol Generate/Upload + galeri kartu brosur (preview gambar, badge AI/Upload, Unduh, Hapus). Terhubung di `ProductDetail.jsx` (tab-brochures).
- **Integrasi WhatsApp brosur cepat**: `brochure-packages` kini menyertakan paket yang punya brosur gambar (atau cover); `send-brochure` otomatis memilih brosur GAMBAR terbaru (termasuk infografis AI) via URL publik ber-sig, fallback ke cover_image.


## Kirim Brosur Cepat (one-tap package brochure) (2026-06) — DONE ✅ (live send terkonfirmasi)
- Backend: `GET /whatsapp/brochure-packages` (paket ACTIVE yang punya cover_image) + `POST /whatsapp/conversations/{cid}/send-brochure` {package_id, caption?}. Caption otomatis: nama paket + destinasi·durasi + "Mulai Rp…/pax" + promo_text. Cover http(s) → dipakai langsung sebagai media_url; base64/data → decode → Object Storage → URL publik ber-sig. Cek `_wa_outbound_allowed`, simpan pesan (media_type=image), update conversation.
- Frontend `WhatsAppIntegration.jsx` MonitorTab: baris "Brosur cepat:" berisi tombol per paket (data-testid `wa-brochure-{id}`) — sekali klik kirim brosur ke conversation terpilih.
- Verified LIVE: set cover (gambar Kaaba) pada "Umrah Reguler 9 Hari" → brochure-packages=1 → send-brochure ke 6282323338838 → status SENT (message_id `cmszi5ov5...`), caption ter-generate benar. Uji media sebelumnya juga terbukti sampai (customer membalas "Ok makasih kak").


## Media WA Masuk + Uji Media Live + Grafik Follow-Up + Kartu AUTO SALES (2026-06) — DONE ✅
- **Uji Media Live**: gambar uji dikirim ke 6282323338838 via `POST /whatsapp/conversations/{cid}/send-media` → HTTP 200, provider API.CO.ID menerima (message_id `cmszhwk5...`, status SENT, media_url publik ter-serve). Pengiriman ke perangkat tetap tunduk aturan window 24 jam WhatsApp.
- **Media MASUK (inbound)**: `_apico_extract_message` kini mengekstrak `media_url`/`media_filename` (dari media_url/url/link/file_url/media.url), `_apico_process_inbound` menyimpan `media_url`/`media_type`/`media_filename` di pesan INBOUND. Panel chat merender media via `MediaBubble` (img/video/audio/link). CATATAN: belum di-E2E dgn webhook media nyata (butuh provider mengirim payload media inbound).
- **Grafik Follow-Up mingguan**: `/ai/followup/analytics` kini menyertakan `weekly[]` (per pekan Senin: sent, response, booking, response_rate, conversion_rate, 8 pekan terakhir). UI AnalyticsTab (AutoFollowUp.jsx) menambah ComposedChart recharts (bar Terkirim/Booking + garis Response%/Konversi%) + empty state. Verified render.
- **Kartu AUTO SALES (AI)** di Executive Dashboard: `executive-dashboard` sales block menambah `auto_sales_bookings`+`auto_sales_revenue` (booking_source=AUTO SALES per periode); SuperAdminDashboard menampilkan Kpi "AUTO SALES (AI)". Verified: Rp55jt / 1 booking.


## BUGFIX — AI bilang "seat penuh" setelah booking & booking duplikat (seat sisa 1) (2026-06) — DONE ✅ (simulator E2E)
- **Gejala**: saat sisa kursi 1, AI membuat booking (kursi terakhir terpakai). Ketika customer menyusul menunggu invoice, AI menjalankan CHECK_SEAT lagi → kursi 0 → keliru bilang "kuota penuh"; pada beberapa kasus AI memanggil CREATE_BOOKING lagi (tanpa departure_id pada retry) → booking DUPLIKAT.
- **Root cause**: di `_ai_create_booking`, cek ketersediaan kursi berjalan SEBELUM cek booking-existing (idempotency) → panggilan ulang kena error "seat penuh" sebelum guard; guard lama juga hanya cocok bila departure_id sama → retry tanpa departure_id lolos menjadi booking kedua.
- **Fix backend**: idempotency dipindah ke PALING AWAL (sebelum seat check) + fallback: bila tak ada match dgn departure_id, cocokkan customer_id+package_id+pax (AUTO SALES, ai_generated, non-CANCELLED) → kembalikan booking yang sama. Cegah duplikat sekaligus hindari error "penuh" untuk booking yang sudah ada.
- **Fix prompt**: (a) step (4d): JANGAN buat booking ulang bila sudah dibuat/terkonfirmasi di percakapan ini — pakai GET_PAYMENT_STATUS/GET_BOOKING; (b) step (6): saat customer tanya invoice/total/status atau menyusul setelah booking, WAJIB GET_PAYMENT_STATUS (by customer_id/booking_id), JANGAN CHECK_SEAT lagi & JANGAN pernah bilang "kursi/kuota penuh" ke customer yang SUDAH punya booking (kursinya sudah direservasi).
- **Verified (seat=1)**: register → konfirmasi (booking pakai kursi terakhir, seat→0) → customer tanya "total invoice saya?" → AI panggil GET_PAYMENT_STATUS → "INV-xxxx, Rp27.500.000, Unpaid" (BUKAN "penuh"), hanya 1 booking (tanpa duplikat). Data uji dibersihkan; quota departure direstore.
- Catatan: `_ait_create_customer` dedup by WhatsApp (1 WA = 1 customer) — perilaku benar (bukan bug).


## Kirim Media WhatsApp + Diskon Otomatis AI (2026-06) — DONE ✅ (backend curl E2E; FE smoke)
### Diskon Otomatis (AI tak lagi handover saat "diskon")
- `WA_HANDOVER_KEYWORDS`: dihapus "diskon","nego","negosiasi","tawar" → pertanyaan/permintaan diskon TIDAK lagi memicu handover.
- `_ai_pkg_public` kini mengekspos `max_discount_type`, `max_discount_value`, `discount_available`, `max_discount_note` (HPP tetap disembunyikan).
- `_journey_prompt` step (7): bila customer tanya diskon → AI cek field paket; discount_available true → sampaikan batas maks; false/0 → "belum ada diskon untuk paket ini saat ini" (tak mengarang). CREATE_BOOKING tetap meng-cap otomatis.
- Verified simulator: cap=0 → "belum tersedia program diskon" (tanpa handover); cap=10% → "diskon maksimal hingga 10%" (tanpa handover). Paket uji direset ke 0.

### Kirim Media WhatsApp (gambar/dokumen/audio/video + preview)
- Backend: `POST /whatsapp/conversations/{cid}/send-media` (super_admin, multipart: media_type/file/caption). Validasi tipe (image/document/audio/video) & ukuran ≤16MB, cek `_wa_outbound_allowed` (opt-out/blacklist). Upload ke Emergent Object Storage (`wa_media`), kirim via provider `send_message(media_url=...)`, simpan message dgn `media_url`/`media_type`/`media_filename`.
- Penyajian publik untuk provider fetch: `GET /public/wa-media/{media_id}?sig=HMAC` (`_wa_media_sig`, HMAC JWT_SECRET). Verified: sig benar→200 image/png, sig salah→403, tipe invalid→400.
- Frontend `WhatsAppIntegration.jsx` MonitorTab: dropdown tipe media + tombol attach (UploadCloud) + preview file (`MediaFilePreview`) + kirim; bubble merender media (`MediaBubble`: img/video/audio/link dokumen). Semua ber-data-testid (wa-media-*). Verified FE smoke: kontrol media render di /ai-hub → WhatsApp → Conversation Monitor.
- CATATAN: pengiriman ke provider LIVE hanya bisa E2E dgn recipient nyata (uji ke nomor SIM bogus menghasilkan 502 provider — path upload/URL/serve sudah tervalidasi). media_url memakai `_public_base` (PUBLIC_BASE_URL/frontend base) agar provider bisa mengunduh.


## AI Auto-Registrasi + Booking + Invoice + Diskon per Paket (2026-06) — DONE ✅ (simulator E2E)
- **Batas diskon per paket configurable**: `PackageModel` + CRUD kini punya `max_discount_type` (PERCENT/NOMINAL) & `max_discount_value` (default 0). UI form paket (create di Products.jsx & edit di ProductDetail.jsx) punya field "Maks Diskon (Tipe/Nilai)". Default 0 = AI tidak beri diskon kecuali admin set per paket.
- **Alur AI (`_journey_prompt` + `_ai_create_booking`)**: customer minta daftar → AI konfirmasi ringkas → setelah "YA": SEARCH_PACKAGE (ambil package_id/departure_id valid — WAJIB, tak menebak) → CREATE_CUSTOMER (bila baru) → CREATE_LEAD → CREATE_BOOKING (confirmed=true). Booking di-tag `booking_source=AUTO SALES`, `ai_generated=True`, `created_by=AI AGENT`; invoice status SELALU `Unpaid` (AI tak pernah PAID/LUNAS).
- **Diskon di-cap otomatis** ke max per paket (nominal/persen); AI WAJIB menyebut angka PERSIS dari OBSERVATION CREATE_BOOKING (invoice_number/discount/total). Verified: minta 25% pada paket cap 10% → tersimpan 10% (Rp5,5jt), total Rp49,5jt, AI menjelaskan cap dengan sopan.
- **Idempotency guard** di `_ai_create_booking`: cek booking existing (customer_id+package_id+departure_id+pax, AUTO SALES, non-CANCELLED) → kembalikan yang sama. Cegah booking/invoice duplikat saat AI re-invoke CREATE_BOOKING di turn lanjutan. Verified: 3x trigger → tetap 1 booking/1 invoice.
- **Simulator `/whatsapp/ai/simulate` kini persist pesan** inbound+AI reply ke `whatsapp_messages` → riwayat multi-turn berfungsi (meniru alur live webhook+worker). Reset juga hapus messages sim.
- Verified via curl multi-turn (Gemini live). Data uji dibersihkan; departure confirmed_pax direkonsiliasi; paket uji di-reset max_discount=0.
- **CATATAN untuk agent berikutnya**: di alur LIVE (`_wa_ai_process`), keyword handover memuat "diskon/nego/batal" → memicu handover ke sales SEBELUM journey jalan. Artinya diskon otomatis AI hanya berlaku bila customer TIDAK memakai kata "diskon" (mis. AI menawarkan sendiri). Bila user ingin AI menangani permintaan diskon langsung (tanpa handover), hapus "diskon"/"nego"/"tawar" dari `WA_HANDOVER_KEYWORDS` (line ~9046). Belum diubah (menunggu keputusan user).


## BUGFIX — AI diam saat ditanya itinerary (2026-06) — DONE ✅ (simulator)
- Root cause: pertanyaan itinerary butuh beberapa tool call (GET_ITINERARY gagal→SEARCH_PACKAGE→GET_ITINERARY) melampaui budget loop 4 → balasan kosong → fix sebelumnya mengembalikan handover diam (reply None) → `ai_status` PAUSED → AI berhenti merespon.
- Fix `_wa_ai_journey`: budget loop 4→6; tambah upaya terakhir "jawab langsung" bila loop habis; bila tetap kosong → kirim fallback ramah ("Mohon tunggu sebentar ya Kak…") dengan `handover=False` → customer TIDAK pernah didiamkan & AI tetap ACTIVE. Verified: itinerary dijawab jujur (data belum tersedia), ai_status tetap ACTIVE.
- Catatan: percakapan yang sudah terlanjur PAUSED dari bug lama perlu di-resume manual (tab Human Handover) agar AI membalas lagi.



- **Root cause 1 (greeting/closing berulang)**: `_wa_ai_journey` membuat sesi LLM baru tiap pesan TANPA riwayat percakapan → AI selalu mengira pesan pertama. **Fix**: inject 12 pesan terakhir dari `whatsapp_messages` ke system prompt + deteksi `is_first` (ada OUTBOUND sebelumnya?) + aturan wajib "jangan ulang salam/penutup; lanjutkan obrolan".
- **Root cause 2 (token `ACTION:{...}` terkirim ke customer)**: bila JSON tool gagal di-parse, kode lama mengembalikan `reply` mentah ke customer; balasan akhir juga tak disanitasi. **Fix**: ekstraksi ACTION via regex `ACTION:\s*(\{.*\})` (di mana pun), bila parse gagal → re-prompt (bukan kirim mentah), sanitasi balasan akhir membuang baris `ACTION:`/`OBSERVATION`, dan bila kosong → handover (tidak pernah membocorkan token).
- Verified simulator: turn 1 greet wajar tanpa leak; turn 2 (dengan riwayat) tidak mengulang greeting & query "hongkong" dijawab natural tanpa leak ACTION.
- Live provider Api.co.id: CONNECTED, webhook terdaftar+aktif, parser inbound/outbound diselaraskan (`message.received`→inbound, `message.sent/delivered/read`→diabaikan).



- **N8N dihapus dari UI**: menu "AI Automation" (/n8n) + halaman `N8N.jsx` dihapus; menu "Integration" (halaman n8n webhook/API config) + `Integration.jsx` dihapus; blok N8N di `Settings.jsx` (webhook URL, Enable N8N, SLA, template balasan cepat) dihapus. Route/perm `/n8n` & `/integration` dihapus dari nav.js & App.js.
- **N8N dinonaktifkan di backend**: `trigger_n8n()` → no-op, `_deliver_n8n()` → return `{skipped, reason:"n8n removed"}`. 150+ call site tetap valid (tidak ada pengiriman n8n). Endpoint `/integrations/n8n/*` & machine-to-machine `/n8n/*` menjadi dorman (tidak dipakai UI). Deep-link notifikasi `/n8n` → `/ai-hub`.
- **Konsolidasi menu AI & WhatsApp**: 6 menu (WhatsApp Integration, Knowledge Base, Communication Style, AI Tools, AI Monitoring, Auto Follow-Up) digabung jadi SATU menu **"AI & WhatsApp"** (`/ai-hub`, `AIWorkspace.jsx`) dengan 6 sub-tab yang me-render komponen halaman existing inline (Radix Tabs → hanya tab aktif yang mount). Sidebar jauh lebih ringkas.
- Verified: login 200, tidak ada compile error, sidebar hanya menampilkan "AI & WhatsApp" (tanpa n8n/Integration), sub-tab WhatsApp (Provider CONNECTED) & Auto Follow-Up ter-render.



### A/B Testing Follow-Up (2026-06) — DONE ✅ (backend E2E; FE render OK)
- Config (di settings follow-up): `ab_testing_enabled` (default OFF), `ab_min_sample` (20), `ab_style_a`, `ab_style_b`.
- `_afu_ab_choose`: bila enabled & belum ada pemenang → pilih varian **A/B acak 50/50**; bila pemenang terkunci → selalu pakai pemenang. Style varian di-inject ke prompt `_afu_generate_message(variant_style=...)`. Item queue simpan `ab_variant`. Berlaku untuk lead & payment follow-up.
- `_afu_ab_inc('sent')` saat item SENT (process_ready). `_afu_ab_count_responses` (idempotent, dipanggil tiap scan/run): tiap follow-up A/B terkirim → cek balasan customer setelah `sent_at` → +response (flag `ab_response_counted`). `_afu_ab_check_winner`: bila A & B ≥ `ab_min_sample` → kunci pemenang (response rate tertinggi).
- Endpoint: GET `/ai/followup/ab` (enabled, min_sample, styles, A/B sent/response/rate, winner), POST `/ai/followup/ab/reset`. UI: kartu "A/B Testing Pesan Follow-Up" di Settings (toggle, 2 style, min sample, stats badge A/B + pemenang + Reset).
- Verified E2E: seed A/B/B + balasan → A{sent2,resp1,50%}, B{sent2,resp2,100%}, **winner=B** otomatis. RBAC super_admin. Data uji dibersihkan; A/B di-reset & disabled.

### ⏳ PENDING — Aktifkan Live (uji kirim WhatsApp sungguhan)
- BLOCKED: menunggu user memberikan **API Key API.CO.ID** (+ base URL / phone number id + nomor tujuan uji) untuk diisi di tab Provider. Semua pipeline (writing time, queue, follow-up, A/B) siap; pengiriman kini mock (FAILED aman). Begitu key live diisi → jalankan uji kirim end-to-end + verifikasi typing indicator nyata.



- **Writing time engine** `_wa_writing_time(text, s)` menggantikan delay statis: dihitung dari **char count + word count + sentence count + kompleksitas** dengan **typing speed range** configurable (`typing_speed_min` 35 / `typing_speed_max` 60 char/dtk, variasi per-message via random), randomization ringan ±8% (bukan ekstrem), clamp `min_delay`(1)/`max_delay`(8) + **hard safety cap 12s** (`WA_WRITING_HARD_CAP`). Pesan sangat pendek → mepet min (mis. "Baik Kak." = 1.0s); pesan panjang tak berlebihan (≤8s). `_wa_typing_delay` = alias kompat.
- **Message segmentation** dibatasi **maks 3 bubble** (`split_max_messages`, default 3) — sisa digabung ke bubble terakhir (bukan spam banyak bubble). Aktif bila `message_splitting` ON.
- **Alur worker** (`_wa_process_queue_item`): START TYPING (`send_typing`) → hitung writing duration per-bubble → sleep → SEND (typing berhenti implisit saat send). Follow-up (Phase 10H) memakai jalur & writing time yang sama (bukan delay statis).
- **Queue records** (`whatsapp_outbound_queue`): tiap item kini simpan `writing_duration`, `typing_start`, `typing_stop`, `send_time`, `bubbles` selain message_id/conversation/content/status/queue_time.
- **UI** Safety & Messaging: field baru Kecepatan ketik min/maks + Maks bubble (segmentasi) + catatan batas aman keras.
- **Safety**: variasi murni untuk UX, memakai API resmi Api.co.id; BUKAN untuk bypass spam/enforcement/menyamar sebagai manusia.
- **Acceptance (unit) 10 pesan**: durasi 9/10 unik (2 pesan sangat pendek clamp ke 1.0s), semua ∈ [1,8]s & ≤12s, korelasi dgn panjang (pendek<panjang), variasi 5× pesan sama → 5 unik, segmentasi ≤3. E2E webhook: item queue punya writing_duration/typing_start/typing_stop/send_time, tidak ada duplicate message_id. Data uji dibersihkan.



- **Increment 2 (2026-06)** — trigger multi-sinyal & template: **Quotation Follow-Up** (`_afu_quotation_context` → intent QUOTATION_PENDING + konteks nomor/total/expiry quotation aktif), **Departure Nudge** (`_afu_departure_context` → paket dgn keberangkatan ≤ `departure_nudge_days` hari, sisa kursi faktual, tanpa false urgency), **Payment Follow-Up track** (`_afu_evaluate_payment_followups`, source=PAYMENT: booking belum lunas dgn jadwal jatuh tempo/overdue; **skip** bila PAID/CANCELLED/REFUNDED, refund/cancellation in-progress, opt-out/blacklist, tanpa conversation; maks `payment_followup_max`). `_afu_process_ready` kini menangani item tanpa lead (payment) + min-interval berbasis queue per customer. UI Settings: kartu **Trigger Lanjutan & Opt-Out** (toggle quotation/departure/payment + angka) + **Follow-Up Templates** (editor panduan gaya per 8 intent → `intent_guidance`). Config baru: quotation_followup_enabled, departure_nudge_enabled/days, payment_followup_enabled/max. Analytics + `payment_followup_sent`. Verified curl: quotation item (QT-AFU Rp27.5jt, context-aware) & payment item (BKG-AFUPAY overdue Rp20jt) tergenerate; guardrail PAID→0, refund-pending→0. Data uji dibersihkan & settings di-reset.
- Menu baru **AI Management → Auto Follow-Up** (`/auto-followup`, super_admin only; ROUTE_PERMS='super_admin'; Sales tersembunyi + redirect). Page `AutoFollowUp.jsx` 4 tab: Analytics, Settings & Rules, Follow-Up Queue, Leads & Preview. TANPA N8N.
- **Master switch** `enabled` default **OFF** → sistem tetap menjadwalkan & preview (dry-run) tapi TIDAK mengirim. Auto-send hanya jalan saat ON + API.CO.ID live key.
- **Scheduler** = platform cron `ai-followup-scan` (`.emergent/crons.yml`, `*/15`, `POST /api/cron/ai-followup`, Bearer WEBHOOK_CRON_SECRET, ack 2xx + BackgroundTasks). `_afu_cron_run` = evaluate+schedule lalu process-ready.
- **Lead fields** (dinamis): `auto_followup_status` (ACTIVE/PAUSED/STOPPED/COMPLETED/CONVERTED/HANDOVER/OPTED OUT, default ACTIVE), `followup_count`, `last_followup_at`, `customer_intent`, `followup_stopped_reason`.
- **Eligibility** (`_afu_evaluate_and_schedule`): lead stage ∈ NEW/CONTACTED/QUALIFIED/QUOTATION/NEGOTIATION; belum booking/paid (booking non-CANCELLED → CONVERTED); belum opt-out/blacklist (→ OPTED OUT); conversation bukan HUMAN HANDOVER (→ HANDOVER); ADA conversation WhatsApp (dasar interaksi, anti-spam); tidak ada follow-up pending; followup_count < max; **customer bukan yang bicara terakhir** (bila INBOUND terakhir → batalkan pending, STOP).
- **Trigger dinamis** (bukan fixed timer): anchor = pesan INBOUND terakhir (fallback conv.created); FU#N due bila elapsed ≥ schedule delay_hours[N]. Default rules FU1=24j, FU2=72j, FU3=168j (bisa diubah). Hormati **min_interval_hours** (24) & **daily_limit_per_customer** (1).
- **Context-aware AI** (`_afu_generate_message`, Gemini 3 Flash + `_kb_system_prompt` + comm style): baca 12 pesan terakhir + snapshot paket TERBARU (harga & sisa kursi live via `_afu_pkg_snapshot`); dilarang mengarang/false urgency; deteksi intent (`_afu_detect_intent`: PACKAGE/PRICE/AVAILABILITY/DOCUMENT/BOOKING_INTENT/PAYMENT_PENDING/QUOTATION_PENDING/GENERAL).
- **High purchase intent** (BOOKING_INTENT) → `_wa_handover` (assign sales + task + notif + stop auto follow-up), bukan auto-reply.
- **Follow-Up Queue** koleksi `ai_followup_queue` (lead_id, customer_id, conversation_id, followup_number, reason, intent, message, status SCHEDULED/READY/PROCESSING/SENT/CANCELLED/FAILED, scheduled_at, sent_at, dry_run). Pengiriman via **antrean WhatsApp Phase 10G** (`_wa_enqueue_outbound`) → hormati rate-limit/typing/delay/opt-out/business-hours; increment followup_count → COMPLETED saat max.
- **Endpoints** (semua super_admin): GET/PUT `/ai/followup/settings`, GET `/ai/followup/queue`, POST `/ai/followup/queue/{id}/cancel`, POST `/ai/followup/run` (dry-run manual), POST `/ai/followup/preview` (TEST FOLLOW-UP), GET `/ai/followup/leads`, POST `/ai/followup/leads/{lid}/status` (ACTIVE/PAUSED/STOPPED), GET `/ai/followup/analytics` (11 metrik + 3 rate). Cron `POST /cron/ai-followup`.
- **Acceptance curl 7/7 PASS**: TEST1 FU1 scheduled; TEST2 customer reply → cancelled; TEST3 booking → CONVERTED+cancel; TEST4 opt-out → OPTED OUT+cancel; TEST5 max → COMPLETED; TEST6 handover → HANDOVER+cancel; TEST7 harga/seat pakai data CRM terbaru (context-aware). Cron auth 200/401, analytics, RBAC sales 403. Frontend iter_49 100% (4 tab, settings persist, queue dry-run scan + cancel, leads preview context-aware, pause/resume/stop, RBAC). Data uji & settings di-reset ke default.



- **Message Debounce**: pesan customer beruntun digabung jadi 1 konteks sebelum AI membalas. `_wa_debounce_schedule`/`_wa_debounce_fire` (in-memory per conversation, reset timer tiap pesan, window = `debounce_window` detik). Webhook `_apico_process_inbound` kini memanggil debounce (bukan `_wa_ai_process` langsung). Verified: 2 pesan beruntun → hanya 1 balasan AI.
- **Outbound Queue + background worker**: `_wa_ai_process` kini meng-ENQUEUE balasan (`whatsapp_outbound_queue`, status QUEUED). Worker `_wa_outbound_worker` (asyncio task dari startup) klaim item atomik via `find_one_and_update` (QUEUED→SENDING), cek rate limit (blokir → balik QUEUED + `next_attempt_at`+30s, maks 30 attempt → FAILED), typing + delay, kirim via provider, simpan message + update conversation → SENT/FAILED. Webhook balas HTTP 200 cepat (non-blocking).
- **Message Splitting**: `_wa_split_message` memecah balasan panjang jadi beberapa bubble (per paragraf/kalimat, batas `split_max_chars`) bila `message_splitting` aktif. Verified: 1 balasan → 5 bubble.
- **Follow-up cap**: sebelum enqueue, hitung AI outbound + queue pending sejak INBOUND terakhir; bila ≥ `max_followup` → skip + log FOLLOWUP_CAP (cegah spam tanpa balasan customer).
- **Config baru** di `whatsapp_safety_settings`: `message_splitting`, `split_max_chars` (default 320). Endpoint `GET /whatsapp/outbound-queue` (items + counts QUEUED/SENDING/SENT/FAILED). `messaging-monitor` diperluas: `followup_capped`, `queue_pending`.
- **Frontend**: tab baru **Safety & Messaging** di `/whatsapp` (`SafetyTab` di WhatsAppIntegration.jsx) — Messaging Monitor (11 metrik + badge antrean, auto-refresh 8dtk), toggle Messaging/AI/Read receipt/Typing/Marketing, Human-like Delay (min/max/typing_speed), Debounce & Splitting, Rate Limit & Follow-up Cap, Business Hours/Out-of-Office (jam buka/tutup + off_hours_behavior + away message), tombol Simpan. Semua ber-`data-testid` (wa-safety-*).
- Verified: FE iter_48 100% (render, save-persist across reload, business hours, RBAC Sales 403 + menu tersembunyi). Backend curl E2E (debounce 2→1, splitting 5 bubble, worker proses queue, monitor, RBAC 403). Data uji dibersihkan & settings di-reset ke default.


## PHASE 10G — WhatsApp Safety, Human-like Messaging & Anti-Spam — INCREMENT 1 (2026-06) — DONE ✅ (backend curl E2E)
- **Sudah ada dari fase sebelumnya** (memenuhi 10G): API resmi Api.co.id (bukan WAHA/web-automation), read receipt (mark_as_read + read_at), typing indicator (rate-limit ≤1/3dtk), natural delay, duplicate protection (webhook idempotent + message_id dedup), handover stop-AI, opt-out guard (`_wa_outbound_allowed`), template approved-only, message status (RECEIVED/SENT + timestamps).
- **Baru (Increment 1)**: `whatsapp_safety_settings` (GET/PUT `/whatsapp/safety`) — messaging_enabled, ai_auto_reply, read_receipt, typing_indicator, min/max_delay, typing_speed, debounce_window, rate_per_minute/hour/day, max_followup, business_hours + opening/closing, off_hours_behavior (AUTO_RESPONSE/WAIT_UNTIL_BUSINESS_HOURS/HUMAN_HANDOVER), away_message, marketing_enabled.
- **Wired ke outbound AI** (`_wa_ai_process`): cek messaging_enabled → business hours/out-of-office behavior → **rate limiter** (per menit/jam/hari → blok + log RATE_LIMIT) → typing (bila aktif) → **delay configurable** (typing_speed + min/max + randomisasi ringan). Human-like murni untuk UX (tidak untuk bypass).
- **Monitoring** GET `/whatsapp/messaging-monitor`: messages today, inbound/outbound, AI/human responses, failed, rate-limit events, opt-out customers, handover.
- Verified curl: safety get/put persist, monitor 9 metrik, RBAC sales 403.
- **BELUM (Increment 2 — backlog)**: Message Debounce (gabung pesan beruntun jadi 1 context), Outbound Queue + background worker (QUEUED→…→READ), message splitting, follow-up cooldown, Safety & Messaging **UI tab** + Messaging Monitor UI, Business Hours/Out-of-Office UI.


## PHASE 10F — AI Monitoring, Quality Control & Improvement (2026-06) — DONE ✅ (backend curl E2E; FE iter_47 100%)
- Menu **AI Management → AI Monitoring** (`/ai-monitoring`, super_admin only). Page `AIMonitoring.jsx` 4 tab: Dashboard, Response Quality, Error Log, Knowledge Gaps.
- **Dashboard** GET `/ai/monitoring/dashboard`: 10 counts (total conversations, AI handled, human handover, new customers, new leads, orders, bookings, AUTO SALES, AI→SALES, failed responses) + 6 performance rate (AI resolution, handover, lead creation, order creation, booking conversion, response failure).
- **Response Quality** GET `/ai/monitoring/quality` + POST `/ai/monitoring/flag` (GOOD/NEEDS_IMPROVEMENT/INCORRECT/OUTDATED_KNOWLEDGE → simpan `quality_flag` + `ai_response_flags`).
- **Error Log** GET `/ai/monitoring/errors`: AI/handover errors (whatsapp_logs ok=false), tool errors (ai_action_logs), API errors (whatsapp_api_logs).
- **Knowledge Gaps** GET `/ai/monitoring/gaps`: top handover reasons, top packages, flagged responses → POST `/ai/monitoring/to-faq` untuk konversi ke FAQ. Perubahan knowledge tetap manual (tidak otomatis) — sesuai aturan.
- Verified curl: dashboard 10 counts + perf, quality, errors, gaps, to-faq (create+cleanup), flag ok, RBAC sales 403. Frontend iter_47 100% (semua tab, empty states, RBAC). Data uji dibersihkan.
- Acceptance #10 sudah dijamin oleh desain 10B–10E: AI pakai data CRM, tak mengarang harga/seat/itinerary, ikut communication style, minta konfirmasi sebelum transaksi, handover bila perlu, semua percakapan tersimpan.


## PHASE 10E — AI Customer Journey & Automation (2026-06) — DONE ✅ (backend curl E2E; simulator live-Gemini)
- **Agentic journey loop** `_wa_ai_journey(conv, text)`: AI Gemini menjalankan alur customer journey memakai **AI Tools (10D)** via protokol `ACTION: {json}` (loop terkontrol maks 4 langkah, observasi di-feedback). Alur: (1) customer baru → tanya nama/kebutuhan → CREATE_CUSTOMER + CREATE_LEAD (Source WHATSAPP AI), (2) interest → CREATE/UPDATE lead, (3) rekomendasi paket (SEARCH_PACKAGE + CHECK_SEAT, tanpa mengarang harga/seat), (4) beli → KONFIRMASI → CREATE_ORDER→CREATE_BOOKING, (5) info invoice/nominal/jatuh tempo, (6) status pembayaran via GET_PAYMENT_STATUS.
- `_wa_ai_process` di-refactor memakai journey loop; keyword handover diperkaya (marah, komplain, refund, batal, negosiasi, diskon, permintaan khusus, dll). Handover: AI emit `[HANDOVER] <alasan>` → `_wa_handover` (assign sales + task + notifikasi + stop AI). Resume via `/whatsapp/conversations/{id}/resume-ai` (existing).
- **Simulator** `POST /api/whatsapp/ai/simulate` (super_admin, tanpa perlu WhatsApp live) → jalankan journey pada conversation sim, kembalikan reply + tools_used + handover; param `reset` & `confirmed`. UI tab **AI Journey** (chat simulator, badge tool & handover).
- Verified curl (Gemini live): greet customer baru (tanya nama), interest → tool CREATE_CUSTOMER dipanggil + balasan personal, komplain+refund → handover otomatis dengan alasan. Frontend compile OK; tab AI Journey terpasang. Data sim dibersihkan.
- Catatan: order/booking otomatis mensyaratkan `confirmed=true` (aturan 10D) & data valid; high-risk tetap request-only.


## PHASE 10A-REWORK — Migrasi Provider WhatsApp WAHA → Api.co.id — TAHAP 1 (2026-06) — DONE ✅ (backend curl E2E; FE test pending)
- **Provider abstraction**: `WhatsAppProvider` (interface) + `ApiCoWhatsAppProvider` (satu service: auth Bearer, timeout 20s, retry exponential backoff untuk 5xx/timeout, error normalization kategori AUTH_ERROR/RATE_LIMIT/INVALID_PHONE/INVALID_TEMPLATE/WINDOW_CLOSED/PROVIDER_ERROR/TIMEOUT/UNKNOWN, logging ke `whatsapp_api_logs` tanpa menyimpan Authorization/API key). Method: health, get_phone_numbers, send_message(text/media/template), mark_as_read, send_typing (rate-limit ≤1/3dtk/customer), get_customer, check_window, get_templates.
- **Env**: `APICO_BASE_URL=https://chat.api.co.id`, `APICO_API_KEY`, `APICO_WHATSAPP_PHONE_NUMBER_ID` (server-side). Config juga via Super Admin (koleksi `whatsapp_provider_config`, API key terenkripsi `_enc`, hanya mask ke frontend).
- **Endpoints** (super_admin): GET/PUT `/whatsapp/provider`, POST `/whatsapp/provider/test-connection` (→ `/api/v1/public/health`), GET `/whatsapp/provider/phone-numbers` (→ `/api/v1/public/phone-numbers`), GET `/whatsapp/api-logs`. Endpoint lama tetap: conversations, messages, send, logs, ai-config, resume-ai, handover.
- **Webhook** publik `POST /api/webhooks/api-co-id/whatsapp`: simpan raw event (`whatsapp_webhook_events`), ack 200 cepat, proses async (BackgroundTasks), **idempotent** by event_id/message_id, parser fleksibel. Flow inbound: simpan pesan (external_provider=API_CO_ID) → resolve customer (normalisasi 08/62/+62 → 62…, tanpa duplikat) → upsert conversation → **mark as read** via provider → AI (`_wa_ai_process` pakai 10B/10C/10D existing) → **typing + writing-time delay** → send via provider.
- **Message model** dinormalisasi: external_provider, external_message_id, direction, sender_type, status, read_at/sent_at.
- **WAHA dihapus**: semua endpoint accounts/connect/qr/test/disconnect + `_wa_call`/`_wa_headers`/`_wa_get_account` + webhook lama dihapus. Data lama tidak dihapus; migrasi tag `provider=API_CO_ID`. Send text/AI reply kini via Api.co.id `/api/v1/public/messages/send`.
- **Frontend** `WhatsAppIntegration.jsx` di-rework: tab **Provider** (base URL, API Key masked, Test Connection, Load Phone Numbers + pilih, Save), Conversation Monitor, AI Agent/Knowledge/Style/Rules, Human Handover, WhatsApp Logs, **API Logs** (endpoint/method/status/durasi/kategori error). Tab WAHA (Accounts/Connection+QR/Configuration) dihapus.
- Verified curl (12 acceptance): provider get/save (key masked ••••y123), test-connection ERROR graceful, phone-numbers 502 graceful, webhook inbound → customer+conversation dibuat (08123456789→628123456789), webhook duplicate idempotent, api-logs tercatat, no active WAHA routes, RBAC sales 403. Data uji dibersihkan.
## PHASE 10A-REWORK — TAHAP 2 (2026-06) — DONE ✅ (backend curl E2E; FE iter_46 100% after Dialog-import fix)
- **Templates**: GET `/whatsapp/templates?sync=1` (sync dari provider → `whatsapp_templates`), POST create, POST `/{id}/submit`, POST `/templates/send` (gate: hanya status APPROVED). UI tab Templates (list/sync/create/submit).
- **Consent**: POST `/whatsapp/customers/{cid}/consent` (OPT_IN/OPT_OUT/UPDATE) → simpan `wa_consent` + `whatsapp_consent_logs` + sync provider bila ada apico_customer_id.
- **Blacklist**: PATCH `/whatsapp/customers/{cid}/blacklist` → `wa_blacklisted` + sync provider.
- **24h Window**: GET `/whatsapp/customers/{cid}/window-status` (provider).
- **AI Outbound Rule**: `_wa_outbound_allowed()` blokir kirim bila blacklist / opt-out; dipanggil di `_wa_ai_process`, `templates/send`, dan filter broadcast.
- **Broadcast** (super_admin, wajib template APPROVED, auto-filter blacklist/opt-out): POST `/whatsapp/broadcast`, GET `/broadcast/jobs`, GET `/broadcast/jobs/{id}`, POST `/broadcast/jobs/{id}/cancel` → simpan `broadcast_job_id` (`whatsapp_broadcasts`). UI tab Broadcast.
- **Webhook Health**: GET `/whatsapp/webhooks`, POST `/whatsapp/webhooks/{id}/enable`, GET `/whatsapp/webhook-health`, GET `/whatsapp/health` (CONNECTED/DEGRADED/ERROR). UI tab Webhook Health.
- Semua panggilan lewat `ApiCoWhatsAppProvider` (logging/retry/kategori error). Verified curl: templates sync 200, send-unapproved 400, consent OPT_OUT, blacklist, broadcast butuh APPROVED (400), webhook-health, health=ERROR tanpa key, webhooks graceful AUTH_ERROR, RBAC 403.
- **Masih ditunda (backlog)**: Media Upload UI (`/media/upload`), configurable writing-time (min/max/typing_speed/word_count/complexity + UI), debounce pesan masuk, scheduled cron health check, sync `getConversations`/`getMessages` dari provider, Consent/Blacklist UI di Customer 360.


## PHASE 10D — AI Agent CRM Tools & Actions (Super Admin) (2026-06) — DONE ✅ (testing_agent iter_44: FE 100%; backend curl E2E)
- Menu baru **AI Management → AI Tools** (`/ai-tools`, super_admin only; ROUTE_PERMS='super_admin'; Sales/Accounting 403 — terverifikasi). Page `AITools.jsx` 3 tab: Permission Matrix, Tool Test, Audit Log.
- **Lapisan tool aman** — AI TIDAK punya akses DB langsung; semua lewat dispatcher `_ai_tool_dispatch(tool, params, ctx)`. 27 tool terdaftar (`AI_TOOL_REGISTRY`): 11 READ (SEARCH/GET customer, SEARCH/GET package, GET_ITINERARY, CHECK_SEAT, GET_DEPARTURE, GET_PAYMENT_STATUS, GET_BOOKING, GET_FAQ, GET_COMPANY_POLICY), 8 WRITE (CREATE/UPDATE customer, CREATE_LEAD, CREATE_ORDER, CREATE_BOOKING, CREATE_FOLLOWUP, ASSIGN_SALES, REQUEST_HUMAN_HANDOVER), 8 HIGH_RISK (CANCEL_BOOKING, REFUND, CHANGE_PRICE/HPP/TAX/COMMISSION/ACCOUNTING, DELETE_TRANSACTION).
- **Aturan dispatcher**: (1) cek Permission Matrix (`ai_tool_permissions`) — Super Admin on/off tiap tool; disabled → ditolak. (2) HIGH_RISK tidak pernah dieksekusi AI → buat REQUEST approval (`ai_action_requests`, status PENDING) + notif super_admin. (3) CREATE_ORDER/CREATE_BOOKING butuh `confirmed=true` (konfirmasi customer) → tanpa itu balas needs_confirmation. (4) eksekusi handler; error → tidak mengarang, balas error. (5) SEMUA aksi dicatat di `ai_action_logs` (agent, conversation_id, customer_id, tool, params, result, ok, approval_required, timestamp).
- **Price & seat safety**: harga selalu dari Package Master (`compute_pax_price`/tax engine); GET_PACKAGE meng-strip HPP/cost/margin (terverifikasi); CHECK_SEAT via `_availability` (tidak mengarang seat).
- **CREATE_BOOKING/ORDER** memakai ulang jalur AUTO SALES existing (validasi customer/package ACTIVE/pax/departure/seat, reserve `confirmed_pax`, idempotency, buat invoice) — di-tag `booking_source=AUTO SALES`, `source_channel=WHATSAPP AI`, `attribution=AUTO SALES`, `created_by=AI AGENT`, `ai_generated=True`. ASSIGN_SALES → `attribution=AI → SALES` + `original_source=WHATSAPP AI`.
- **Frontend**: Permission Matrix (toggle switch per tool, grup READ/WRITE, badge risiko/konfirmasi), Tool Test playground (pilih tool + params JSON + toggle confirmed → eksekusi, tampil hasil/REQUEST/needs_confirmation), Audit Log (tabel aksi AI).
- Endpoints (semua `require_role("super_admin")`): GET `/ai/tools`, PUT `/ai/tools/{tool}`, POST `/ai/tools/execute`, GET `/ai/action-logs`, GET `/ai/requests`.
- Verified curl: 27 tools, READ ok, HPP stripped, CHECK_SEAT ok, CREATE_BOOKING needs_confirmation, REFUND→request_created (tak dieksekusi), disable→blocked, audit tercatat, RBAC sales 403. Frontend iter_44 100%.
- CATATAN: eksekusi otonom live di chat WhatsApp DITUNDA (sesuai pilihan user) sampai WAHA di-host — infrastruktur & playground siap.


## PHASE 10C — AI Communication Style, Personality & Brand Voice (Super Admin) (2026-06) — DONE ✅ (testing_agent iter_43: FE 100%; backend curl E2E)
- Menu baru **AI Management → Communication Style** (`/communication-style`, super_admin only; ROUTE_PERMS='super_admin'; Sales/Accounting 403 + menu tersembunyi — terverifikasi). Page `CommunicationStyle.jsx` 2 tab: Profiles, Preview.
- Koleksi `communication_profiles` — field: profile_name, language (AUTO/ID/EN), tone[] (Friendly/Professional/Warm/Helpful/Casual/Formal, multi), formality, personality, greeting_style, closing_style, emoji_usage (OFF/LIMITED/NORMAL, default LIMITED), response_length (SHORT/MEDIUM/DETAILED, default MEDIUM), sales_style, brand_voice, examples[{customer,ideal_ai}], do_list[], dont_list[], status, version, history[].
- **Beberapa profil, satu ACTIVE**: `POST /activate` set target ACTIVE & sisanya INACTIVE (single source of truth). **Versioning**: PUT bump version + push snapshot ke history (tak terhapus); `/{id}/versions`. Archive = soft (ARCHIVED).
- **Communication Preview**: `POST /api/communication/preview` (Gemini 3 Flash) — pilih profil/aktif + nama customer opsional + pesan customer → balasan AI bergaya + `profile_used` + package/knowledge count. Deteksi bahasa ID/EN (AUTO).
- **Style engine** `_comm_style_block(profile)` menyusun instruksi brand voice: bahasa, tone, emoji, panjang jawaban, consultative selling (dilarang memaksa/spam/klaim palsu/'pasti'/'termurah' tanpa data), greeting/closing (tak diulang), DO/DON'T, contoh ideal (tiru gaya), personalisasi nama (tidak berlebihan), alur respons (Understand→Retrieve→Validate→Answer→Offer Next Step), JANGAN mengaku manusia.
- **Diterapkan ke semua kanal**: profil ACTIVE otomatis dipakai `_wa_ai_process` (auto-reply WhatsApp Phase 10A) DAN `kb_test_ai` (Test AI KB Phase 10B) via `_comm_active_block()`. `_kb_system_prompt` menerima `comm_block`.
- Endpoints (semua `require_role("super_admin")`): `/communication/meta`, GET/POST/PUT/DELETE `/communication/profiles` (+`/{id}/activate`, `/{id}/versions`), POST `/communication/preview`.
- Verified curl: create ACTIVE→v2 setelah edit (history=1), activate single-active, preview bergaya "Ramah CS" tanpa mengarang (menawarkan handover) pakai 7 paket, RBAC sales=403, archive. Frontend iter_43 100%.


## PHASE 10B — AI Knowledge Base Center (Super Admin) (2026-06) — DONE ✅ (testing_agent iter_42: FE 100%; backend curl E2E)
- Menu baru **AI Management → Knowledge Base** (`/knowledge-base`, super_admin only; ROUTE_PERMS='super_admin'). Sales/Accounting: menu tersembunyi + backend 403 (terverifikasi). Page `KnowledgeBase.jsx` 4 tab: Articles, FAQ, Package Knowledge, Test AI.
- Koleksi `knowledge_articles` (title, category[17], content, status DRAFT/ACTIVE/INACTIVE/ARCHIVED, priority, effective_from/until) + **versioning** (setiap PUT bump version & push snapshot ke `history[]`, tidak pernah dihapus; endpoint `/articles/{id}/versions`). Archive = soft (status ARCHIVED, reason).
- Koleksi `knowledge_faqs` (question, answer, category, keywords[], status). CRUD penuh.
- 17 kategori: PRODUCT, PACKAGE TOUR, PACKAGE UMRAH, DESTINATION, ITINERARY, HOTEL, AIRLINE, VISA, DOCUMENT, PAYMENT, REFUND, CANCELLATION, FAQ, COMPANY INFORMATION, TERMS & CONDITIONS, CUSTOMER SERVICE, OTHER.
- **Package Knowledge** = read-only dari CRM Package Master (single source of truth; tidak ada DB paket terpisah). `GET /api/knowledge/packages` merakit paket + jadwal departure (tanggal/harga/sisa kursi/hotel/maskapai).
- **Priority & effective date**: `_kb_build_context()` menyusun konteks berurutan: (1) Data Paket, (2) Kebijakan Perusahaan aktif, (3) FAQ aktif, (4) Pengetahuan umum. Hanya artikel status ACTIVE & dalam rentang tanggal efektif yang dipakai.
- **Test AI Knowledge**: `POST /api/knowledge/test-ai` (Gemini 3 Flash / gemini-3-flash-preview, Emergent LLM key) → `answer`, `source_data`, `knowledge_used`, `package_used`. Sistem prompt melarang mengarang harga/seat/jadwal/itinerary/hotel/maskapai/visa/kebijakan; bila data tak ada → jawab "informasi belum tersedia" + saran human handover.
- **Integrasi WhatsApp AI**: `_wa_ai_process` kini memakai `_kb_build_context()` + `_kb_system_prompt()` (menggabungkan style/rules/knowledge dari ai-config WhatsApp) → auto-reply WA pakai Knowledge Base + data paket terkini, tetap dengan token `[HANDOVER]`.
- Endpoints (semua `require_role("super_admin")`): `/knowledge/categories`, GET/POST/PUT/DELETE `/knowledge/articles` (+`/{id}/versions`), GET/POST/PUT/DELETE `/knowledge/faqs`, GET `/knowledge/packages`, POST `/knowledge/test-ai`.
- Verified curl: create article→v2 setelah edit (history=1), FAQ, packages=7, test-ai jawaban nyata pakai 2 knowledge + 7 package, archive. Frontend iter_42 100% (CRUD, versi dialog, expand paket, Test AI badges, RBAC).


## PHASE 10A — WhatsApp (WAHA) — TAHAP 3 (Frontend Super Admin UI) (2026-06) — DONE ✅ (testing_agent iter_41: FE 100%)
- Menu baru "WhatsApp Integration" (super_admin only) → route `/whatsapp` (`WhatsAppIntegration.jsx`); `ROUTE_PERMS['/whatsapp']='super_admin'`; Sales/Accounting tidak melihat menu & diarahkan ke /dashboard (RBAC terverifikasi).
- 11 tab dalam 1 halaman: Accounts (CRUD akun WAHA, api_key masked, dialog tambah/edit/archive), Connection+QR (status koneksi, Connect/Test/Disconnect, tampil QR image dari `/qr`), Configuration (Webhook URL + Verify Token + Salin), Conversation Monitor (list + thread bubble + kirim manual), AI Agent (toggle enabled, greeting, handover keywords), AI Knowledge, AI Style, AI Rules (4 tab UI dari satu config `/whatsapp/ai-config`, save parsial via PUT), Human Handover (list HUMAN HANDOVER + Aktifkan AI/resume-ai), WhatsApp Logs (kind=wa), API Logs (kind=API).
- Wiring ke endpoint backend Tahap 1&2 yang sudah ada (tanpa endpoint baru). WAHA belum di-host → Connect/QR/Send error 4xx/502 ditangani dengan toast, UI tidak crash.
- Semua elemen ber-`data-testid`. Verified iter_41: seluruh 11 tab render, buat/edit/hapus akun, simpan 4 AI config, empty states, RBAC Sales/Accounting.
- BELUM: Tahap 4 (Sales frontend — Customer 360 tab WhatsApp, takeover/chat, kirim template manual); sambungkan QR ke engine WAHA saat URL tersedia.


## PHASE 10A — WhatsApp (WAHA) — TAHAP 2 (AI Agent) (2026-06) — DONE (curl E2E, Gemini)
- AI auto-reply via Gemini (gemini-3-flash-preview, Emergent LLM key) dipicu di webhook saat pesan customer masuk & conversation `ai_status=ACTIVE`. Konteks = paket CRM aktif (nama/harga/destinasi/durasi/sisa kursi) — TANPA HPP; pakai AI Style/Rules/Knowledge dari config.
- Config: `GET/PUT /api/whatsapp/ai-config` (super_admin): enabled, knowledge, style, rules, greeting, handover_keywords. Disimpan di `whatsapp_ai_config` (_id=main).
- Human Handover: keyword customer (mis. "bicara dengan sales") atau AI balas token `[HANDOVER]` → status=HUMAN HANDOVER, ai_status=PAUSED, buat Task (source=whatsapp_handover) untuk assigned sales + notifikasi + AI berhenti auto-reply.
- `POST /api/whatsapp/conversations/{id}/resume-ai` (sales/super_admin) → AI aktif kembali; `POST .../handover` manual.
- Verified: pertanyaan paket → balasan Gemini Bahasa Indonesia pakai data paket asli; keyword → HUMAN HANDOVER + task; resume-ai → AI ACTIVE. Data uji dibersihkan.
- Tahap 3 (frontend) → SELESAI (lihat entri Tahap 3 di atas).


## PHASE 10A — Native WhatsApp (WAHA) Integration — TAHAP 1 (Backend) (2026-06) — DONE (curl E2E, tanpa N8N)
- Engine: WAHA (self-hosted) — user belum hosting; kode+endpoint siap, tinggal isi Base URL/API Key. AI = Gemini (Tahap 2). Kredensial dienkripsi Fernet (`_enc/_dec`), di-mask, tidak pernah ke frontend/localStorage.
- Endpoints (semua `require_role("super_admin")` kecuali webhook): GET/POST/PUT/DELETE `/api/whatsapp/accounts` (verify_token auto-generated, api_key masked); `/accounts/{id}/connect|qr|test|disconnect` (best-effort ke WAHA, error aman tanpa bocor token); `GET/POST /api/whatsapp/webhook/{aid}` (GET verify hub.verify_token→challenge, POST terima message + optional HMAC verify); `/conversations`, `/conversations/{id}/messages`, `/conversations/{id}/send` (text/image/document via WAHA), `/whatsapp/logs`.
- Collections: whatsapp_accounts, whatsapp_conversations (status AI ACTIVE/WAITING CUSTOMER/HUMAN HANDOVER/CLOSED, ai_status, handover_status, assigned_sales), whatsapp_messages (unique index `message_id` untuk dedup), whatsapp_logs (WEBHOOK/SEND/CONNECT/TEST/API + IN/OUT).
- Customer identification: match by phone suffix regex → link customer_id; jika tidak ada → is_new_customer=True, TIDAK buat customer duplikat.
- Verified: dedup (webhook 2x id sama → 1 message/1 conversation), verify-token (200 valid / 403 salah), RBAC (sales→403), api_key masked (••••-123), no-duplicate-customer, logging.
- BELUM: Tahap 2 (AI Agent Gemini + Knowledge/Style/Rules + Human Handover task/notif + Resume AI), Tahap 3 (frontend menu WhatsApp Integration 11 submenu + Customer 360 → Conversations).


## PHASE 9P — Final UAT & Production Readiness (2026-06) — DONE ✅ READY FOR PRODUCTION
- UAT menyeluruh via testing_agent (iter 39 & 40): backend 28 PASSED / 1 SKIPPED / 0 FAILED; frontend RBAC 100%. Suite: `/app/backend/tests/test_phase9p_uat.py`. Laporan lengkap: `/app/memory/PHASE_9P_UAT.md`.
- CRITICAL/HIGH bugs = 0. MEDIUM (AUTO SALES `sales_pic_id` placeholder pada seed BKG-00016) → FIXED (di-null-kan) & re-verified.
- Terverifikasi: RBAC (Sales/Accounting 403 pada HPP/N8N/Forecast/Tax/Supplier), refund cap, commission month/payout+1, tax snapshot immutability, balance sheet, idempotency (no duplicate booking), audit trail, soft-delete finansial, error tanpa stack trace.
- Non-blocking: (LOW) `/packages/{id}/availability` shape (1 seat test skipped); (INFO) refactor server.py pasca-produksi.


## PHASE 9O — N8N Monitoring & Reliability (2026-06) — DONE (curl E2E + screenshot)
- **N8N Health** (5 kartu di monitor): Connection, Last Request, Last Response (+code), API Latency (avg processing_time), Error Rate — dari `n8n_api_logs`. Endpoint `GET /api/integrations/n8n/monitor` diperluas dengan `health`, `workflow_logs`, `api_logs`.
- **Workflow Log** (tab baru): Workflow ID, Event, Customer, Booking, Timestamp, Status (SUCCESS/FAILED/SKIPPED), Error/reason — dari `db.n8n_logs`.
- **Error**: status FAILED menampilkan reason (l.error/reason).
- **Retry**: `POST /api/integrations/n8n/workflow/{log_id}/retry` (super_admin) re-deliver event outbound (idempotent; inbound booking dedup via external_booking_id/idempotency_keys → tidak buat booking duplikat). Tombol Retry hanya pada baris FAILED. Sales → 403.
- **API Log** (tab baru): Timestamp, Endpoint, Method, Status, Code, Latency, API Key (masked `api_key_mask`), Error — tanpa kredensial plaintext.
- **AUTO SALES**: `POST /api/v1/bookings` sudah paksa `booking_source="AUTO SALES"`, `sales_pic_id=None`, `sales_user_id=None` + idempotency (tidak diubah).


## Enhancement Batch 5 — Approval Detail Panel + Auto Sinkron Pax (2026-06) — DONE (curl E2E + screenshots)
- **Approval Detail Panel**: Dialog Detail di Approval Center kini menampilkan `CostBreakdown` untuk cancellation (Total Dibayar, Cancellation Fee, Non-Refundable, Other, Estimasi Refund) & refund (Proposed, Deductions list, Total Deduction, Approved, Bank) + tombol Approve/Revise/Reject langsung di dalam dialog (tanpa buka halaman lain). Data dari `GET /api/approval-center/detail/{source}/{aid}`.
- **Auto Sinkron saat Tambah/Hapus Peserta**: Toggle "Auto sinkron pax" (localStorage, `booking.manage`) di tab Peserta BookingDetail. Bila aktif, setiap tambah/hapus peserta otomatis memanggil `sync-pax` (pax booking = jumlah peserta + regenerate invoice). Handler `afterTraveler` dipakai di TravelerDialog onSaved & TravelerCard onChange.


## Enhancement Batch 4 — Inline Approval (Cancellation/Refund) + Sinkron Pax (2026-06) — DONE (curl E2E + screenshot)
- **Approval inline Cancellation/Refund**: `_collect_approvals` set `actionable=True` untuk cancellation/refund saat status `ACCOUNTING_REVIEWED` (giliran Super Admin). Endpoint terpadu `POST /api/approval-center/action/{source}/{aid}` kini mendispatch source `cancellation`→`approve_cancellation` & `refund`→`approve_refund` (Approve/Reject/Revise langsung dari Approval Center, tetap menghormati langkah Accounting Review). Reject/Revise wajib reason (400 bila kosong).
- **Sinkron Pax↔Peserta**: `POST /api/bookings/{bid}/sync-pax` (booking.manage) set `pax` = jumlah peserta aktif, hitung ulang harga (tiered utk PRIVATE) + regenerate semua invoice. Tombol "Sinkron Pax" di tab Peserta BookingDetail (muncul saat mismatch). Verified: pax 1→3, total 15jt, invoice updated.


## Enhancement Batch 3 — Regenerate All + PIC Report + Tiered Pricing + Approval Buttons (2026-06) — DONE (curl E2E + screenshots)
- **Regenerate Semua**: `POST /api/bookings/{bid}/invoices/regenerate-all` (invoice.manage) hitung ulang semua invoice satu booking. Tombol "Regenerate Semua" di tab Invoice BookingDetail.
- **Laporan Perpindahan PIC**: `GET /api/reports/pic-changes` (super_admin) dari `lead_activities type=pic_change` (waktu, customer, dari→ke, Satuan/Massal, oleh). Tab "Perpindahan PIC" di Reports (super_admin only via flag admin).
- **Harga Tiered Otomatis**: `_booking_invoice_amounts` kini, untuk paket `sub_category==PRIVATE`, memakai `compute_pax_price(pkg, pax_count, room_type)` sehingga per-pax mengikuti bracket jumlah peserta terkini saat regenerate. Terverifikasi: 4 peserta → tier 3-5 → per_pax 35jt. (create_invoice tetap pakai harga terkunci; tiered hanya saat regenerate.)
- **Tombol Approval (bug fix)**: Approval Center kini menampilkan Approve/Revise/Reject untuk item PENDING dari sumber `adjustment` DAN `commission` (sebelumnya commission hanya "Open"). Endpoint terpadu baru `POST /api/approval-center/action/{source}/{aid}` (super_admin) mendispatch ke adjustment & commission closing. `_collect_approvals` set `actionable` untuk commission REVIEW/CLOSED yang belum di-approve.


## Enhancement Batch 2 — PIC Audit/Bulk + Invoice Edit/Delete/Regenerate + Pax Badge (2026-06) — DONE (curl E2E + screenshots)
- **Peringatan Selisih Peserta**: BookingDetail menampilkan `PaxCountBadge` (tab Peserta) + banner kuning `invoice-pax-warning` di tab Invoice bila jumlah peserta terdaftar ≠ pax booking.
- **Riwayat Ganti PIC**: `update_customer` & bulk reassign mencatat `log_activity(type=pic_change)` → tampil di timeline Customer 360.
- **Pindah PIC Massal**: `POST /api/customers/bulk-reassign-pic` (super_admin). UI: checkbox pilih customer + bulk bar + dialog `BulkPicDialog` di Customers.jsx.
- **Regenerate Invoice**: `POST /api/invoices/{iid}/regenerate` (invoice.manage) hitung ulang nominal dari booking + peserta terkini. Tombol Regenerate di tiap invoice.
- **Edit & Hapus Invoice (Super Admin)**: `PUT /api/invoices/{iid}` (edit pax/harga/diskon/pajak/jatuh tempo, recompute total) + `DELETE /api/invoices/{iid}` (ditolak bila ada pembayaran). UI: `EditInvoiceDialog` + tombol Edit/Delete.
- Helper `_booking_invoice_amounts(b, pax_count)` dipakai bersama oleh regenerate.


## Enhancement — Customer PIC Reassign + Booking "Peserta" + Invoice by Participants (2026-06) — DONE (Verified curl E2E + screenshot)
- **Ganti PIC Sales (Super Admin)**: `CustomerUpdate` now accepts `sales_pic_id`; `PUT /api/customers/{id}` resolves new PIC name+branch. Only super_admin may reassign (sales → 403). UI: `ChangePicButton` (UserCog icon) di profil Customer 360, dialog pilih sales user.
- **Teks "jamaah" → "peserta"** di menu Booking (`Bookings.jsx`, `BookingDetail.jsx`).
- **Invoice nominal by participants**: `POST /api/bookings/{id}/invoice` kini hitung nominal = per_pax_price paket × jumlah peserta (travelers) terdaftar di booking (fallback booking.pax bila 0). Diskon & pajak diskala proporsional per peserta. Verified BKG-00002 (pax=2, 1 peserta) → subtotal 50jt, tax 110rb, total 48.61jt.


## PHASE 9N — Sales & Financial Forecasting (2026-06) — DONE (Verified curl E2E + RBAC 403 + screenshots)
- Backend `GET /api/forecast/dashboard` (super_admin only, `require_role`). Returns: sales_forecast, cash_flow_forecast, receivable_forecast, upcoming_expense, upcoming_commission.
- Sales Forecast: pipeline weighted by STAGE_PROBABILITY (NEW 10%/CONTACTED 20%/QUALIFIED 30%/QUOTATION 50%/NEGOTIATION 70%/BOOKING 90%). Deal value = lead.budget → fallback quotation total. Buckets: Current/Next/Next-3-Months (weighted, pipeline raw, actual booked).
- Cash Flow Forecast: 6-month window. Cash In = booking payment_schedule outstanding by due_date. Cash Out = supplier outstanding (amount−paid) + commission payout + refund PENDING. Net per month. ACTUAL current month = realized payments in vs expenses/refunds-paid/supplier-paid out.
- Receivable Forecast (payment_schedule outstanding), Upcoming Expense (supplier + refund), Upcoming Commission (commission_items by payout_month).
- Frontend: new `Forecast.jsx` page, route `/forecast` gated by perm "super_admin" (hasPerm returns true only for super_admin). Menu "Forecasting" added. Recharts bar/line. ACTUAL vs FORECAST badges throughout — never mixed with accounting actuals.


## PHASE 9N — Internal AI Sales Assistant UI (2026-06) — DONE (Verified curl E2E + screenshot)
- Backend `POST /api/sales/ai-assist/{customer_id}` (mode: summary/followup/suggestion) via Gemini 3 Flash; HPP/modal/margin stripped; requires_approval=True.
- Frontend: New "AI Assistant" tab in Customer 360 (`Customer360.jsx` → `AIAssistantTab`) with 3 action cards: Ringkas Customer, Draft Follow-Up, Saran Respons & Paket.
- Result panel with Copy button + amber notice "Draft perlu disetujui sales sebelum dikirim" (human-in-the-loop). Loading & error states handled.
- Verified: login sales → /crm/:id → AI tab → summary returns real Indonesian output rendered in UI.


## PHASE 9M.5 — Fix Preview Error + Rich-Text Terms (2026-06) — DONE (Verified testing_agent iteration_37: BE 14/14, FE 100%)
- **Bug fix**: preview PDF (khususnya Quotation) gagal 500 karena HTML tak aman dari contentEditable/`<br>` merusak reportlab. `_clean_terms()` kini menormalkan `<br ...>`→`<br/>`, tag b/i/u ber-atribut → tag polos, `<ol>/<ul>/<li>`→daftar bernomor/butir, buang tag lain. Diterapkan di terms & footer semua PDF.
- **Rich-text editor Terms**: field Terms Invoice & Quotation di tab Template Dokumen kini editor sederhana (contentEditable) dengan toolbar Bold/Italic/Underline/• list/1. list; hasil HTML tersimpan & dirender rapi di PDF.


## PHASE 9M.4 — Editable Terms & Conditions Invoice/Quotation (2026-06) — DONE (Verified render PNG/text)
- Tab Template Dokumen kini punya editor **Terms & Conditions — Invoice** dan **— Quotation** (`invoice_terms`, `quotation_terms` di template). Bila diisi, T&C ini yang tampil di PDF (memprioritaskan template; fallback ke terms dokumen bila template kosong). Terverifikasi: invoice & quotation menampilkan T&C dari template; preview menghormati nilai form.


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
