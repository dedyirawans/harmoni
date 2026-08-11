# Safar Travel CRM — Product Requirements (Living Doc)

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
- Phase 3: Product/Package management with HPP write-side, Booking & travelers, Quotations/Invoices.

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
