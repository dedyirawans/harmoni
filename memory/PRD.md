# Safar Travel CRM — Product Requirements (Living Doc)

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
