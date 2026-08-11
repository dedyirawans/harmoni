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
- Build CRM module (customers + leads) with Sales data-ownership filtering on backend queries.
- Build Product/Package management with HPP/costing fields (write side).
