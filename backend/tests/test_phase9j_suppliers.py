"""Phase 9J - Supplier Management backend tests.

Tests cover:
- Supplier CRUD (super_admin & accounting)
- Supplier Costs CRUD (total_cost = qty*unit_cost, summary, delete)
- Supplier Payments (outstanding, status, aging bucket)
- HPP integration (supplier-costs?package_id used by ProductDetail)
- RBAC: sales user is forbidden (403)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
ACCT = {"email": "accounting@safarcrm.com", "password": "Account@123"}
SALES = {"email": "sales@safarcrm.com", "password": "Sales@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def acct_token():
    try:
        return _login(ACCT)
    except AssertionError:
        pytest.skip("accounting user not seeded")


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES)


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def created_ids():
    return {"supplier": None, "cost": None, "payment": None, "package": None}


# ============ Suppliers ============
class TestSuppliers:
    def test_create_supplier(self, admin_token, created_ids):
        payload = {
            "name": f"TEST_Supplier_{int(time.time())}",
            "type": "Hotel",
            "contact": "Ali",
            "email": "ali@test.com",
            "phone": "0812345",
            "bank_account": "BCA 123-456",
        }
        r = requests.post(f"{API}/suppliers", json=payload, headers=H(admin_token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == payload["name"]
        assert d["type"] == "Hotel"
        assert d["bank_account"] == payload["bank_account"]
        assert "_id" in d
        created_ids["supplier"] = d["_id"]

    def test_list_suppliers_contains_created(self, admin_token, created_ids):
        r = requests.get(f"{API}/suppliers", headers=H(admin_token))
        assert r.status_code == 200
        ids = [s["_id"] for s in r.json()]
        assert created_ids["supplier"] in ids

    def test_create_missing_name(self, admin_token):
        r = requests.post(f"{API}/suppliers", json={"type": "Hotel"}, headers=H(admin_token))
        assert r.status_code == 400


# ============ Supplier Costs ============
class TestSupplierCosts:
    @pytest.fixture(scope="class")
    def pkg_id(self, admin_token, created_ids):
        r = requests.get(f"{API}/packages", headers=H(admin_token))
        assert r.status_code == 200
        pkgs = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        if not pkgs:
            pytest.skip("no packages available for supplier-cost test")
        created_ids["package"] = pkgs[0]["_id"]
        return pkgs[0]["_id"]

    def test_create_cost_total(self, admin_token, created_ids, pkg_id):
        payload = {
            "package_id": pkg_id,
            "supplier_id": created_ids["supplier"],
            "service": "Hotel Makkah 5N",
            "quantity": 3,
            "unit_cost": 1500000,
            "payment_status": "UNPAID",
        }
        r = requests.post(f"{API}/supplier-costs", json=payload, headers=H(admin_token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_cost"] == 3 * 1500000
        assert d["supplier_name"]  # denormalized
        created_ids["cost"] = d["_id"]

    def test_list_by_package(self, admin_token, created_ids, pkg_id):
        r = requests.get(f"{API}/supplier-costs?package_id={pkg_id}", headers=H(admin_token))
        assert r.status_code == 200
        rows = r.json()
        ids = [c["_id"] for c in rows]
        assert created_ids["cost"] in ids

    def test_summary(self, admin_token, pkg_id):
        r = requests.get(f"{API}/supplier-costs/summary?package_id={pkg_id}", headers=H(admin_token))
        assert r.status_code == 200
        s = r.json()
        assert s["total_supplier_cost"] >= 4500000
        assert s["count"] >= 1

    def test_invalid_qty(self, admin_token, created_ids, pkg_id):
        r = requests.post(f"{API}/supplier-costs", json={
            "package_id": pkg_id, "supplier_id": created_ids["supplier"],
            "quantity": 0, "unit_cost": 100
        }, headers=H(admin_token))
        assert r.status_code == 400

    def test_delete_cost(self, admin_token, created_ids, pkg_id):
        r = requests.delete(f"{API}/supplier-costs/{created_ids['cost']}", headers=H(admin_token))
        assert r.status_code == 200
        # verify removed
        r2 = requests.get(f"{API}/supplier-costs?package_id={pkg_id}", headers=H(admin_token))
        assert created_ids["cost"] not in [c["_id"] for c in r2.json()]


# ============ Supplier Payments (aging) ============
class TestSupplierPayments:
    def test_create_partial(self, admin_token, created_ids):
        from datetime import date, timedelta
        due = (date.today() - timedelta(days=15)).isoformat()  # overdue -> "1-30"
        r = requests.post(f"{API}/supplier-payments", json={
            "supplier_id": created_ids["supplier"], "invoice_number": "INV-TEST-1",
            "due_date": due, "amount": 1000000, "paid": 400000,
        }, headers=H(admin_token))
        assert r.status_code == 200, r.text
        d = r.json()
        created_ids["payment"] = d["_id"]

    def test_list_computes_outstanding_status_aging(self, admin_token, created_ids):
        r = requests.get(f"{API}/supplier-payments", headers=H(admin_token))
        assert r.status_code == 200
        rows = {p["_id"]: p for p in r.json()}
        p = rows.get(created_ids["payment"])
        assert p, "created payment not in list"
        assert p["outstanding"] == 600000
        assert p["status"] == "PARTIAL"
        assert p["aging"] == "1-30"

    def test_paid_full_status(self, admin_token, created_ids):
        from datetime import date
        r = requests.post(f"{API}/supplier-payments", json={
            "supplier_id": created_ids["supplier"], "invoice_number": "INV-TEST-2",
            "due_date": date.today().isoformat(), "amount": 500000, "paid": 500000,
        }, headers=H(admin_token))
        assert r.status_code == 200
        pid = r.json()["_id"]
        rows = requests.get(f"{API}/supplier-payments", headers=H(admin_token)).json()
        p = next(x for x in rows if x["_id"] == pid)
        assert p["outstanding"] == 0
        assert p["status"] == "PAID"
        assert p["aging"] == "current"

    def test_amount_required_positive(self, admin_token, created_ids):
        r = requests.post(f"{API}/supplier-payments", json={
            "supplier_id": created_ids["supplier"], "amount": 0
        }, headers=H(admin_token))
        assert r.status_code == 400


# ============ RBAC ============
class TestRBAC:
    def test_sales_forbidden_suppliers(self, sales_token):
        r = requests.get(f"{API}/suppliers", headers=H(sales_token))
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"

    def test_sales_forbidden_costs(self, sales_token):
        r = requests.get(f"{API}/supplier-costs", headers=H(sales_token))
        assert r.status_code == 403

    def test_sales_forbidden_payments(self, sales_token):
        r = requests.get(f"{API}/supplier-payments", headers=H(sales_token))
        assert r.status_code == 403

    def test_sales_cannot_create_supplier(self, sales_token):
        r = requests.post(f"{API}/suppliers", json={"name": "X"}, headers=H(sales_token))
        assert r.status_code == 403

    def test_accounting_can_access(self, acct_token):
        r = requests.get(f"{API}/suppliers", headers=H(acct_token))
        assert r.status_code == 200
        r2 = requests.get(f"{API}/supplier-costs", headers=H(acct_token))
        assert r2.status_code == 200
        r3 = requests.get(f"{API}/supplier-payments", headers=H(acct_token))
        assert r3.status_code == 200


# ============ HPP integration precondition ============
class TestHPPIntegration:
    """Frontend ProductDetail uses GET /supplier-costs?package_id -> ensure endpoint returns list."""

    def test_package_supplier_costs_endpoint(self, admin_token, created_ids):
        if not created_ids.get("package"):
            pytest.skip("no package id")
        r = requests.get(f"{API}/supplier-costs?package_id={created_ids['package']}", headers=H(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)
