"""Backend tests for Safar Travel CRM: Auth, RBAC, User Mgmt, Audit, Role Permissions, HPP."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://crm-access-control-3.preview.emergentagent.com"
API = f"{BASE_URL}/api"

SUPER = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES = {"email": "sales@safarcrm.com", "password": "Sales@123"}
ACCT = {"email": "accounting@safarcrm.com", "password": "Account@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    return data["token"], data["user"]


@pytest.fixture(scope="session")
def super_token():
    tok, _ = _login(SUPER)
    return tok


@pytest.fixture(scope="session")
def sales_token():
    tok, _ = _login(SALES)
    return tok


@pytest.fixture(scope="session")
def acct_token():
    tok, _ = _login(ACCT)
    return tok


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Auth ----------
class TestAuth:
    def test_login_super(self):
        tok, user = _login(SUPER)
        assert user.get("role") in ("super_admin", "SUPER_ADMIN", "SuperAdmin", "super")

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": SUPER["email"], "password": "wrong"}, timeout=10)
        assert r.status_code in (400, 401)

    def test_me_endpoint(self, super_token):
        r = requests.get(f"{API}/auth/me", headers=H(super_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "permissions" in d or "user" in d or "role" in d

    def test_forgot_password_success(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": SUPER["email"]}, timeout=20)
        # Should succeed regardless (don't reveal if user exists)
        assert r.status_code in (200, 202)

    def test_forgot_password_unknown_email(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "nobody-xyz@example.com"}, timeout=20)
        assert r.status_code in (200, 202)

    def test_reset_password_invalid_token(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": "invalid-token-xyz", "new_password": "NewPass@123"}, timeout=10)
        assert r.status_code in (400, 401, 404)


# ---------- RBAC ----------
class TestRBAC_Sales:
    def test_sales_hpp_forbidden(self, sales_token):
        r = requests.get(f"{API}/hpp", headers=H(sales_token), timeout=10)
        assert r.status_code == 403, f"Expected 403 got {r.status_code}"

    def test_sales_users_forbidden(self, sales_token):
        r = requests.get(f"{API}/users", headers=H(sales_token), timeout=10)
        assert r.status_code == 403

    def test_sales_audit_forbidden(self, sales_token):
        r = requests.get(f"{API}/audit-logs", headers=H(sales_token), timeout=10)
        assert r.status_code == 403

    def test_sales_role_perms_forbidden(self, sales_token):
        r = requests.get(f"{API}/role-permissions", headers=H(sales_token), timeout=10)
        assert r.status_code == 403


class TestRBAC_Accounting:
    def test_acct_hpp_ok(self, acct_token):
        r = requests.get(f"{API}/hpp", headers=H(acct_token), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))

    def test_acct_users_forbidden(self, acct_token):
        r = requests.get(f"{API}/users", headers=H(acct_token), timeout=10)
        assert r.status_code == 403

    def test_acct_role_perms_forbidden(self, acct_token):
        r = requests.get(f"{API}/role-permissions", headers=H(acct_token), timeout=10)
        assert r.status_code == 403


class TestRBAC_SuperAdmin:
    def test_super_users_ok(self, super_token):
        r = requests.get(f"{API}/users", headers=H(super_token), timeout=10)
        assert r.status_code == 200

    def test_super_hpp_ok(self, super_token):
        r = requests.get(f"{API}/hpp", headers=H(super_token), timeout=10)
        assert r.status_code == 200

    def test_super_audit_ok(self, super_token):
        r = requests.get(f"{API}/audit-logs", headers=H(super_token), timeout=10)
        assert r.status_code == 200

    def test_super_role_perms_ok(self, super_token):
        r = requests.get(f"{API}/role-permissions", headers=H(super_token), timeout=10)
        assert r.status_code == 200

    def test_unauthenticated_denied(self):
        r = requests.get(f"{API}/users", timeout=10)
        assert r.status_code in (401, 403)


# ---------- User Management CRUD ----------
class TestUserCRUD:
    created_id = None

    def test_create_user(self, super_token):
        uniq = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST User {uniq}",
            "username": f"test_{uniq}",
            "email": f"test_{uniq}@example.com",
            "password": "TestPass@123",
            "role": "sales",
        }
        r = requests.post(f"{API}/users", json=payload, headers=H(super_token), timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        d = r.json()
        uid = d.get("id") or d.get("_id") or d.get("user", {}).get("id")
        assert uid, f"No id returned: {d}"
        TestUserCRUD.created_id = uid
        assert d.get("email") == payload["email"] or d.get("user", {}).get("email") == payload["email"]

    def test_get_created_user_in_list(self, super_token):
        assert TestUserCRUD.created_id
        r = requests.get(f"{API}/users", headers=H(super_token), timeout=10)
        assert r.status_code == 200
        users = r.json()
        if isinstance(users, dict):
            users = users.get("users", users.get("data", []))
        ids = [u.get("id") or u.get("_id") for u in users]
        assert TestUserCRUD.created_id in ids

    def test_update_user(self, super_token):
        uid = TestUserCRUD.created_id
        assert uid
        r = requests.put(f"{API}/users/{uid}", json={"name": "TEST User Updated"}, headers=H(super_token), timeout=10)
        assert r.status_code in (200, 204), f"{r.status_code} {r.text}"

    def test_delete_user(self, super_token):
        uid = TestUserCRUD.created_id
        assert uid
        r = requests.delete(f"{API}/users/{uid}", headers=H(super_token), timeout=10)
        assert r.status_code in (200, 204)


# ---------- Audit Log ----------
class TestAudit:
    def test_audit_has_entries(self, super_token):
        r = requests.get(f"{API}/audit-logs", headers=H(super_token), timeout=10)
        assert r.status_code == 200
        data = r.json()
        if isinstance(data, dict):
            data = data.get("logs", data.get("data", []))
        assert isinstance(data, list)
