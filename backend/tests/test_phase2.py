"""Phase 2 backend tests: CRM customers, leads/pipeline, follow-ups, sales dashboard, search, data ownership."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://github-workflow-14.preview.emergentagent.com"
API = f"{BASE_URL}/api"

SUPER = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES_A = {"email": "sales@safarcrm.com", "password": "Sales@123"}
SALES_B = {"email": "salesb@safarcrm.com", "password": "SalesB@123"}
ACCT = {"email": "accounting@safarcrm.com", "password": "Account@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed {creds['email']} {r.status_code} {r.text}"
    return r.json()["token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def tok_super():
    return _login(SUPER)


@pytest.fixture(scope="module")
def tok_sales_a():
    return _login(SALES_A)


@pytest.fixture(scope="module")
def tok_sales_b():
    return _login(SALES_B)


@pytest.fixture(scope="module")
def tok_acct():
    return _login(ACCT)


# store created ids across tests
STATE = {}


# ---------- Customers ----------
class TestCustomers:
    def test_sales_a_create_customer(self, tok_sales_a):
        uniq = uuid.uuid4().hex[:8]
        payload = {
            "full_name": f"TEST_Cust_{uniq}",
            "whatsapp": f"628123{uniq[:6]}",
            "email": f"testcust_{uniq}@example.com",
            "city": "Jakarta",
            "customer_type": "Prospect",
            "customer_source": "instagram",
            "notes": "test customer",
        }
        r = requests.post(f"{API}/customers", json=payload, headers=H(tok_sales_a), timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        d = r.json()
        cid = d.get("id") or d.get("_id")
        assert cid, d
        STATE["customer_id"] = cid
        STATE["customer_name"] = payload["full_name"]
        assert d.get("full_name") == payload["full_name"]

    def test_sales_a_list_sees_own(self, tok_sales_a):
        r = requests.get(f"{API}/customers", headers=H(tok_sales_a), timeout=10)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("customers", []))
        ids = [c.get("id") or c.get("_id") for c in items]
        assert STATE["customer_id"] in ids

    def test_sales_a_get_360(self, tok_sales_a):
        cid = STATE["customer_id"]
        r = requests.get(f"{API}/customers/{cid}/360", headers=H(tok_sales_a), timeout=10)
        assert r.status_code == 200
        d = r.json()
        # timeline expected
        assert "customer" in d or "timeline" in d or "id" in d

    def test_sales_b_list_does_not_see_a_customer(self, tok_sales_b):
        r = requests.get(f"{API}/customers", headers=H(tok_sales_b), timeout=10)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("customers", []))
        ids = [c.get("id") or c.get("_id") for c in items]
        assert STATE["customer_id"] not in ids, "Sales B should not see Sales A customer"

    def test_sales_b_get_a_customer_403(self, tok_sales_b):
        cid = STATE["customer_id"]
        r = requests.get(f"{API}/customers/{cid}", headers=H(tok_sales_b), timeout=10)
        assert r.status_code in (403, 404), f"Expected 403/404 got {r.status_code}"

    def test_sales_b_get_a_customer_360_forbidden(self, tok_sales_b):
        cid = STATE["customer_id"]
        r = requests.get(f"{API}/customers/{cid}/360", headers=H(tok_sales_b), timeout=10)
        assert r.status_code in (403, 404)

    def test_accounting_customers_forbidden(self, tok_acct):
        r = requests.get(f"{API}/customers", headers=H(tok_acct), timeout=10)
        assert r.status_code == 403

    def test_super_sees_all_customers(self, tok_super):
        r = requests.get(f"{API}/customers", headers=H(tok_super), timeout=10)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("customers", []))
        ids = [c.get("id") or c.get("_id") for c in items]
        assert STATE["customer_id"] in ids

    def test_add_customer_note(self, tok_sales_a):
        cid = STATE["customer_id"]
        r = requests.post(f"{API}/customers/{cid}/notes", json={"note": "TEST note"}, headers=H(tok_sales_a), timeout=10)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"


# ---------- Leads / Pipeline ----------
class TestLeads:
    def test_sales_a_create_lead(self, tok_sales_a):
        uniq = uuid.uuid4().hex[:8]
        payload = {
            "customer_id": STATE.get("customer_id"),
            "source": "instagram",
            "interested_package": f"TEST_Lead_{uniq} Umrah Regular 12 days",
            "destination": "Mecca",
            "pax": 2,
            "budget": 50000000,
            "status": "NEW",
            "notes": "test lead",
        }
        r = requests.post(f"{API}/leads", json=payload, headers=H(tok_sales_a), timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        d = r.json()
        lid = d.get("id") or d.get("_id")
        assert lid
        STATE["lead_id"] = lid
        # Default stage stored in "status"
        assert (d.get("status") or "NEW").upper() == "NEW"

    def test_lead_appears_in_list(self, tok_sales_a):
        r = requests.get(f"{API}/leads", headers=H(tok_sales_a), timeout=10)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("leads", []))
        ids = [l.get("id") or l.get("_id") for l in items]
        assert STATE["lead_id"] in ids

    def test_move_stage(self, tok_sales_a):
        lid = STATE["lead_id"]
        r = requests.patch(f"{API}/leads/{lid}/stage", json={"stage": "CONTACTED"}, headers=H(tok_sales_a), timeout=10)
        assert r.status_code in (200, 204), f"{r.status_code} {r.text}"
        # verify persisted (stage is stored in "status" field)
        r2 = requests.get(f"{API}/leads/{lid}", headers=H(tok_sales_a), timeout=10)
        if r2.status_code == 200:
            assert (r2.json().get("status") or "").upper() == "CONTACTED"

    def test_move_stage_qualified(self, tok_sales_a):
        lid = STATE["lead_id"]
        r = requests.patch(f"{API}/leads/{lid}/stage", json={"stage": "QUALIFIED"}, headers=H(tok_sales_a), timeout=10)
        assert r.status_code in (200, 204)

    def test_sales_b_cannot_see_lead(self, tok_sales_b):
        r = requests.get(f"{API}/leads", headers=H(tok_sales_b), timeout=10)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("leads", []))
        ids = [l.get("id") or l.get("_id") for l in items]
        assert STATE["lead_id"] not in ids

    def test_sales_b_cannot_move_a_lead(self, tok_sales_b):
        lid = STATE["lead_id"]
        r = requests.patch(f"{API}/leads/{lid}/stage", json={"stage": "LOST"}, headers=H(tok_sales_b), timeout=10)
        assert r.status_code in (403, 404)

    def test_accounting_leads_forbidden(self, tok_acct):
        r = requests.get(f"{API}/leads", headers=H(tok_acct), timeout=10)
        assert r.status_code == 403


# ---------- Follow ups ----------
class TestFollowUps:
    def test_create_followup(self, tok_sales_a):
        from datetime import datetime, timedelta
        due = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        payload = {
            "customer_id": STATE.get("customer_id"),
            "lead_id": STATE.get("lead_id"),
            "due_date": due,
            "activity_type": "Call",
            "notes": "TEST_fu follow up",
        }
        r = requests.post(f"{API}/follow-ups", json=payload, headers=H(tok_sales_a), timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        d = r.json()
        fid = d.get("id") or d.get("_id")
        assert fid
        STATE["fu_id"] = fid

    def test_list_followups(self, tok_sales_a):
        r = requests.get(f"{API}/follow-ups", headers=H(tok_sales_a), timeout=10)
        assert r.status_code == 200

    def test_complete_followup(self, tok_sales_a):
        fid = STATE["fu_id"]
        # try PATCH complete
        r = requests.patch(f"{API}/follow-ups/{fid}/complete", headers=H(tok_sales_a), timeout=10)
        if r.status_code == 404:
            r = requests.patch(f"{API}/follow-ups/{fid}", json={"status": "completed"}, headers=H(tok_sales_a), timeout=10)
        assert r.status_code in (200, 204), f"{r.status_code} {r.text}"

    def test_sales_b_cannot_list_a_followups(self, tok_sales_b):
        r = requests.get(f"{API}/follow-ups", headers=H(tok_sales_b), timeout=10)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("follow_ups", []))
        ids = [f.get("id") or f.get("_id") for f in items]
        assert STATE["fu_id"] not in ids


# ---------- Sales Dashboard ----------
class TestSalesDashboard:
    def test_sales_a_dashboard(self, tok_sales_a):
        r = requests.get(f"{API}/sales/dashboard", headers=H(tok_sales_a), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # expect KPI-like keys
        keys_lower = [k.lower() for k in d.keys()]
        # accept common naming
        expected_any = ["new_leads", "follow_up_today", "overdue", "my_quotations", "my_bookings", "my_pax", "upcoming_departure", "outstanding_customer", "estimated_sales", "conversion_rate"]
        matched = sum(1 for k in expected_any if k in keys_lower)
        assert matched >= 5, f"Dashboard KPIs missing. keys={list(d.keys())}"

    def test_accounting_sales_dashboard_forbidden(self, tok_acct):
        r = requests.get(f"{API}/sales/dashboard", headers=H(tok_acct), timeout=10)
        assert r.status_code == 403


# ---------- Global Search ----------
class TestSearch:
    def test_search_customer_by_name(self, tok_sales_a):
        q = STATE.get("customer_name", "")[:10]
        r = requests.get(f"{API}/search", params={"q": q}, headers=H(tok_sales_a), timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        # should have some structure
        assert isinstance(d, (list, dict))

    def test_search_accounting_forbidden(self, tok_acct):
        r = requests.get(f"{API}/search", params={"q": "abc"}, headers=H(tok_acct), timeout=10)
        assert r.status_code == 403


# ---------- HPP still forbidden for Sales ----------
class TestHPPStillForbidden:
    def test_sales_hpp_403(self, tok_sales_a):
        r = requests.get(f"{API}/hpp", headers=H(tok_sales_a), timeout=10)
        assert r.status_code == 403


# ---------- Cleanup ----------
class TestZZZCleanup:
    def test_delete_lead(self, tok_sales_a):
        lid = STATE.get("lead_id")
        if not lid:
            pytest.skip("no lead")
        r = requests.delete(f"{API}/leads/{lid}", headers=H(tok_sales_a), timeout=10)
        assert r.status_code in (200, 204, 404)

    def test_delete_customer(self, tok_sales_a):
        cid = STATE.get("customer_id")
        if not cid:
            pytest.skip("no customer")
        r = requests.delete(f"{API}/customers/{cid}", headers=H(tok_sales_a), timeout=10)
        assert r.status_code in (200, 204, 404)
