"""
Run with: pytest backend/tests/test_phase7_rbac_manual.py -o addopts=""
(The repo pytest.ini enables pytest-xdist which races the shared n8n_creds fixture.)

Phase 7 independent verification:
  - RBAC matrix for /api/integrations/n8n/* (Sales, Accounting, Super Admin) - all four endpoints
  - Additional n8n auth reject paths (no X-API-Key, stale timestamp)
  - All /v1/bookings structured validation error codes
  - HPP security matrix (Sales 403, Accounting 200, HPP stripped for Sales on /api/packages)
  - Manual booking flow -> booking_source=SALES, sales_type=MANUAL, sales_name=<user>
  - Frontend -> handled separately with Playwright
"""
import os, json, hmac, hashlib, time, uuid, pytest, requests
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"

# All tests share generated n8n credentials; force to same xdist worker to avoid
# generate races that invalidate creds mid-run.
pytestmark = pytest.mark.xdist_group("phase7-rbac")

SA = ("dedyirawan18@gmail.com", "Admin@123")
SALES = ("sales@safarcrm.com", "Sales@123")
ACC = ("accounting@safarcrm.com", "Account@123")


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def sign(secret, ts, body):
    return hmac.new(secret.encode(), (ts + "." + body).encode(), hashlib.sha256).hexdigest()


def sh(ak, sec, body, idem=None, ts=None):
    ts = ts or str(int(time.time()))
    d = {"X-API-Key": ak, "X-Timestamp": ts, "X-Signature": sign(sec, ts, body), "Content-Type": "application/json"}
    if idem:
        d["X-Idempotency-Key"] = idem
    return d


@pytest.fixture(scope="module")
def tokens():
    return {"sa": login(*SA), "sales": login(*SALES), "acc": login(*ACC)}


@pytest.fixture(scope="module")
def n8n_creds(tokens):
    r = requests.post(f"{BASE}/integrations/n8n/api-config/generate", headers=h(tokens["sa"]), timeout=30)
    assert r.status_code == 200
    j = r.json()
    return j["api_key"], j["api_secret"]


# ---------- RBAC matrix for n8n integration endpoints ----------
class TestN8nRBAC:
    ENDPOINTS = [
        ("GET", "/integrations/n8n/api-config"),
        ("PUT", "/integrations/n8n/api-config"),
        ("POST", "/integrations/n8n/api-config/generate"),
        ("GET", "/integrations/n8n/api-logs"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_sales_forbidden(self, tokens, method, path):
        r = requests.request(method, f"{BASE}{path}", headers=h(tokens["sales"]), json={} if method == "PUT" else None, timeout=30)
        assert r.status_code == 403, f"Sales expected 403 on {method} {path}, got {r.status_code} {r.text[:200]}"

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_accounting_forbidden(self, tokens, method, path):
        r = requests.request(method, f"{BASE}{path}", headers=h(tokens["acc"]), json={} if method == "PUT" else None, timeout=30)
        assert r.status_code == 403, f"Accounting expected 403 on {method} {path}, got {r.status_code} {r.text[:200]}"

    def test_sa_get_config_masked(self, tokens):
        r = requests.get(f"{BASE}/integrations/n8n/api-config", headers=h(tokens["sa"]), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j.get("api_key", "").startswith("••••"), f"api_key not masked: {j.get('api_key')}"
        assert "api_secret" not in j or not j.get("api_secret"), "plaintext api_secret must not leak"

    def test_sa_get_logs(self, tokens):
        r = requests.get(f"{BASE}/integrations/n8n/api-logs", headers=h(tokens["sa"]), timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- Additional n8n machine-auth reject paths ----------
class TestN8nAuthReject:
    def test_missing_api_key(self, n8n_creds):
        ak, sec = n8n_creds
        body = json.dumps({})
        ts = str(int(time.time()))
        r = requests.post(f"{BASE}/v1/customers", data=body, headers={
            "X-Timestamp": ts, "X-Signature": sign(sec, ts, body), "Content-Type": "application/json"
        }, timeout=30)
        assert r.status_code == 401

    def test_stale_timestamp(self, n8n_creds):
        ak, sec = n8n_creds
        body = json.dumps({})
        ts = str(int(time.time()) - 600)  # 10 min old
        r = requests.post(f"{BASE}/v1/customers", data=body, headers=sh(ak, sec, body, ts=ts), timeout=30)
        assert r.status_code == 401

    def test_valid_signature_accepted(self, n8n_creds):
        ak, sec = n8n_creds
        r = requests.get(f"{BASE}/v1/packages", headers=sh(ak, sec, ""), timeout=30)
        assert r.status_code == 200


# ---------- HPP security matrix ----------
class TestHPPSecurity:
    def test_sales_hpp_forbidden(self, tokens):
        r = requests.get(f"{BASE}/hpp", headers=h(tokens["sales"]), timeout=30)
        assert r.status_code == 403

    def test_accounting_hpp_ok(self, tokens):
        r = requests.get(f"{BASE}/hpp", headers=h(tokens["acc"]), timeout=30)
        assert r.status_code == 200

    def test_sales_packages_hpp_stripped(self, tokens):
        r = requests.get(f"{BASE}/packages", headers=h(tokens["sales"]), timeout=30)
        assert r.status_code == 200
        for p in r.json():
            for k in ("hpp", "total_cost", "gross_profit", "gross_margin"):
                assert k not in p, f"Field {k} must be stripped for Sales, found in package {p.get('package_name')}"


# ---------- v1 booking validation error codes ----------
class TestV1BookingValidation:
    @pytest.fixture(scope="class")
    def active_pkg(self, tokens):
        r = requests.post(f"{BASE}/packages", headers=h(tokens["sa"]), json={
            "package_name": "QA-N8N-ACTIVE", "product_type": "UMROH", "sub_category": "OPEN_TRIP",
            "selling_price": 15000000, "status": "ACTIVE", "min_quota_pax": 1
        }, timeout=30)
        assert r.status_code in (200, 201), r.text
        pid = r.json()["_id"]
        yield pid
        requests.delete(f"{BASE}/packages/{pid}", headers=h(tokens["sa"]), timeout=30)

    @pytest.fixture(scope="class")
    def draft_pkg(self, tokens):
        r = requests.post(f"{BASE}/packages", headers=h(tokens["sa"]), json={
            "package_name": "QA-N8N-DRAFT", "product_type": "UMROH", "selling_price": 1, "status": "DRAFT"
        }, timeout=30)
        pid = r.json()["_id"]
        yield pid
        requests.delete(f"{BASE}/packages/{pid}", headers=h(tokens["sa"]), timeout=30)

    @pytest.fixture(scope="class")
    def cust(self, n8n_creds):
        ak, sec = n8n_creds
        body = json.dumps({"full_name": "QA V1 Cust", "whatsapp": "+62998QATEST"})
        r = requests.post(f"{BASE}/v1/customers", data=body, headers=sh(ak, sec, body), timeout=30)
        return r.json()["customer"]["_id"]

    def test_customer_not_found(self, n8n_creds, active_pkg):
        ak, sec = n8n_creds
        body = json.dumps({"customer_id": "000000000000000000000000", "package_id": active_pkg, "pax": 1})
        r = requests.post(f"{BASE}/v1/bookings", data=body, headers=sh(ak, sec, body), timeout=30)
        assert r.status_code == 400
        j = r.json()
        assert j.get("success") is False and j.get("error_code") == "CUSTOMER_NOT_FOUND"

    def test_package_not_found(self, n8n_creds, cust):
        ak, sec = n8n_creds
        body = json.dumps({"customer_id": cust, "package_id": "000000000000000000000000", "pax": 1})
        r = requests.post(f"{BASE}/v1/bookings", data=body, headers=sh(ak, sec, body), timeout=30)
        assert r.status_code == 400
        assert r.json().get("error_code") == "PACKAGE_NOT_FOUND"

    def test_package_not_active(self, n8n_creds, cust, draft_pkg):
        ak, sec = n8n_creds
        body = json.dumps({"customer_id": cust, "package_id": draft_pkg, "pax": 1})
        r = requests.post(f"{BASE}/v1/bookings", data=body, headers=sh(ak, sec, body), timeout=30)
        assert r.json().get("error_code") == "PACKAGE_NOT_ACTIVE"

    def test_invalid_pax(self, n8n_creds, cust, active_pkg):
        ak, sec = n8n_creds
        body = json.dumps({"customer_id": cust, "package_id": active_pkg, "pax": 0})
        r = requests.post(f"{BASE}/v1/bookings", data=body, headers=sh(ak, sec, body), timeout=30)
        assert r.json().get("error_code") == "INVALID_PAX"

    def test_departure_not_found(self, n8n_creds, cust, active_pkg):
        ak, sec = n8n_creds
        body = json.dumps({"customer_id": cust, "package_id": active_pkg, "pax": 1,
                           "departure_id": "000000000000000000000000"})
        r = requests.post(f"{BASE}/v1/bookings", data=body, headers=sh(ak, sec, body), timeout=30)
        assert r.json().get("error_code") == "DEPARTURE_NOT_FOUND"

    def test_price_invalid(self, n8n_creds, cust, active_pkg):
        ak, sec = n8n_creds
        body = json.dumps({"customer_id": cust, "package_id": active_pkg, "pax": 1, "total": 1})
        r = requests.post(f"{BASE}/v1/bookings", data=body, headers=sh(ak, sec, body), timeout=30)
        assert r.json().get("error_code") == "PRICE_INVALID"

    def test_invalid_traveler(self, n8n_creds, cust, active_pkg):
        ak, sec = n8n_creds
        body = json.dumps({"customer_id": cust, "package_id": active_pkg, "pax": 1,
                           "travelers": [{"full_name": ""}]})
        r = requests.post(f"{BASE}/v1/bookings", data=body, headers=sh(ak, sec, body), timeout=30)
        assert r.json().get("error_code") == "INVALID_TRAVELER"


# ---------- Manual booking flow (Sales -> quotation -> SA approve/accept -> convert) ----------
class TestManualBookingFlow:
    def test_manual_booking_sales_manual(self, tokens):
        sa, sales = tokens["sa"], tokens["sales"]
        # Sales creates customer
        r = requests.post(f"{BASE}/customers", headers=h(sales), json={
            "full_name": "QA Manual Cust", "whatsapp": "+62997QATEST", "customer_source": "REFERRAL"
        }, timeout=30)
        assert r.status_code in (200, 201), r.text
        cid = r.json()["_id"]

        # Sales creates lead
        r = requests.post(f"{BASE}/leads", headers=h(sales), json={
            "customer_id": cid, "product_type": "UMROH", "budget": 20000000, "notes": "qa manual"
        }, timeout=30)
        assert r.status_code in (200, 201), r.text
        lead_id = r.json()["_id"]

        # SA creates active package
        r = requests.post(f"{BASE}/packages", headers=h(sa), json={
            "package_name": "QA-MANUAL-PKG", "product_type": "UMROH", "sub_category": "OPEN_TRIP",
            "selling_price": 18000000, "status": "ACTIVE", "min_quota_pax": 1
        }, timeout=30)
        pkg_id = r.json()["_id"]

        # Sales creates quotation (no discount -> auto-APPROVED)
        r = requests.post(f"{BASE}/quotations", headers=h(sales), json={
            "customer_id": cid, "package_id": pkg_id, "lead_id": lead_id, "pax": 2,
            "room_type": "QUAD", "discount_type": "PERCENT", "discount_value": 0
        }, timeout=30)
        assert r.status_code in (200, 201), r.text
        q = r.json()
        qid = q["_id"]
        assert q["discount_status"] == "APPROVED"
        sales_name = q["sales_pic_name"]

        # SA sets ACCEPTED
        r = requests.patch(f"{BASE}/quotations/{qid}/status", headers=h(sa), json={"status": "ACCEPTED"}, timeout=30)
        assert r.status_code == 200, r.text

        # SA converts to booking (booking.manage may be super_admin only)
        r = requests.post(f"{BASE}/quotations/{qid}/convert", headers=h(sa), json={}, timeout=30)
        assert r.status_code in (200, 201), r.text
        bk = r.json()
        try:
            assert bk["booking_source"] == "SALES", bk
            assert bk["sales_type"] == "MANUAL", bk
            assert bk["sales_name"] == sales_name, bk
            assert bk["sales_name"] != "AUTO SALES"
            assert bk["sales_user_id"] is not None
            assert bk["created_by"] != "SYSTEM"
        finally:
            # cleanup
            bid = bk.get("_id")
            requests.delete(f"{BASE}/bookings/{bid}", headers=h(sa), timeout=30)
            requests.delete(f"{BASE}/quotations/{qid}", headers=h(sa), timeout=30)
            requests.delete(f"{BASE}/leads/{lead_id}", headers=h(sa), timeout=30)
            requests.delete(f"{BASE}/customers/{cid}", headers=h(sa), timeout=30)
            requests.delete(f"{BASE}/packages/{pkg_id}", headers=h(sa), timeout=30)


# ---------- v1 scope: unavailable endpoints ----------
class TestV1Scope:
    @pytest.mark.parametrize("path", ["/v1/hpp", "/v1/users", "/v1/audit-logs", "/v1/commission-schemes", "/v1/tax-rules"])
    def test_no_out_of_scope_endpoints(self, n8n_creds, path):
        ak, sec = n8n_creds
        r = requests.get(f"{BASE}{path}", headers=sh(ak, sec, ""), timeout=30)
        assert r.status_code in (401, 403, 404, 405), f"{path} unexpectedly {r.status_code}"
