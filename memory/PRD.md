# Safar Travel CRM — Product Requirements (Living Doc)

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
