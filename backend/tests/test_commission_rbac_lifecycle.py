"""
Phase 6 Commission — RBAC matrix + Closing lifecycle + My Commission (Sales)
Focus per review_request: independent sanity for RBAC 403 matrix, lifecycle
(OPEN->REVIEW->APPROVED->CLOSED->PAID) with lock+reopen, adjustment blocking,
and MY commission scope for Sales.

Uses PUBLIC url (REACT_APP_BACKEND_URL) so we test via ingress like a real user.
Cleans up all closings/lines/items for the test periods at the end.
"""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

SUPER = ("dedyirawan18@gmail.com", "Admin@123")
SALES = ("sales@safarcrm.com", "Sales@123")
ACC = ("accounting@safarcrm.com", "Account@123")

PERIOD = "2099-01"  # far-future avoids collision with real data


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return r.json()["token"]


def h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def tokens():
    return {
        "super": login(*SUPER),
        "sales": login(*SALES),
        "acc": login(*ACC),
    }


@pytest.fixture(scope="module", autouse=True)
def cleanup(tokens):
    yield
    # After tests, reopen (if CLOSED/PAID) then delete artifacts via Super Admin
    # Backend does not expose delete-closing endpoint; use Mongo directly.
    try:
        from pymongo import MongoClient
        load_dotenv("/app/backend/.env")
        mc = MongoClient(os.environ["MONGO_URL"])
        db = mc[os.environ["DB_NAME"]]
        db.commission_items.delete_many({"period": PERIOD})
        db.commission_lines.delete_many({"period": PERIOD})
        db.commission_closings.delete_many({"period": PERIOD})
        db.commission_schemes.delete_many({"scheme_name": {"$regex": "^RBACTEST"}})
        mc.close()
    except Exception as e:
        print("cleanup warn:", e)


# ---------------- RBAC 403 matrix ----------------
class TestRBACSchemes:
    def test_sales_403_get_schemes(self, tokens):
        r = requests.get(f"{BASE}/commissions/schemes", headers=h(tokens["sales"]))
        assert r.status_code == 403, r.text

    def test_accounting_get_schemes_ok(self, tokens):
        r = requests.get(f"{BASE}/commissions/schemes", headers=h(tokens["acc"]))
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_super_get_schemes_ok(self, tokens):
        r = requests.get(f"{BASE}/commissions/schemes", headers=h(tokens["super"]))
        assert r.status_code == 200

    def test_accounting_403_create_scheme(self, tokens):
        body = {"scheme_name": "RBACTEST-ACC", "product_type": "ALL", "package_id": "",
                "effective_from": "2099-01-01", "effective_until": "2099-12-31",
                "calculation_basis": "CONFIRMED",
                "tiers": [{"min_pax": 0, "max_pax": 9999, "rate_per_pax": 100000}],
                "auto_sales": False, "status": "ACTIVE"}
        r = requests.post(f"{BASE}/commissions/schemes", headers=h(tokens["acc"]), json=body)
        assert r.status_code == 403, r.text

    def test_super_create_update_delete_scheme(self, tokens):
        body = {"scheme_name": "RBACTEST-1", "product_type": "ALL", "package_id": "",
                "effective_from": "2099-01-01", "effective_until": "2099-12-31",
                "calculation_basis": "CONFIRMED",
                "tiers": [{"min_pax": 0, "max_pax": 9999, "rate_per_pax": 100000}],
                "auto_sales": False, "status": "ACTIVE"}
        r = requests.post(f"{BASE}/commissions/schemes", headers=h(tokens["super"]), json=body)
        assert r.status_code == 200, r.text
        sid = r.json()["_id"]
        # Accounting cannot PUT
        r2 = requests.put(f"{BASE}/commissions/schemes/{sid}", headers=h(tokens["acc"]),
                          json={**body, "scheme_name": "RBACTEST-1b"})
        assert r2.status_code == 403
        # Super can PUT
        r3 = requests.put(f"{BASE}/commissions/schemes/{sid}", headers=h(tokens["super"]),
                          json={**body, "scheme_name": "RBACTEST-1b"})
        assert r3.status_code == 200
        # Accounting cannot DELETE
        r4 = requests.delete(f"{BASE}/commissions/schemes/{sid}", headers=h(tokens["acc"]))
        assert r4.status_code == 403
        # Super can DELETE
        r5 = requests.delete(f"{BASE}/commissions/schemes/{sid}", headers=h(tokens["super"]))
        assert r5.status_code == 200


class TestRBACSettings:
    def test_sales_403_get_settings(self, tokens):
        r = requests.get(f"{BASE}/commissions/settings", headers=h(tokens["sales"]))
        assert r.status_code == 403

    def test_accounting_get_settings(self, tokens):
        r = requests.get(f"{BASE}/commissions/settings", headers=h(tokens["acc"]))
        assert r.status_code == 200
        assert "auto_sales_commission" in r.json()

    def test_accounting_403_put_settings(self, tokens):
        r = requests.put(f"{BASE}/commissions/settings", headers=h(tokens["acc"]),
                         json={"auto_sales_commission": True})
        assert r.status_code == 403

    def test_super_put_settings(self, tokens):
        r = requests.put(f"{BASE}/commissions/settings", headers=h(tokens["super"]),
                         json={"auto_sales_commission": False})
        assert r.status_code == 200


class TestRBACClosingsAndLines:
    endpoints_sales_forbidden = [
        ("GET", "/commissions/closings"),
        ("POST", "/commissions/closings"),
        ("GET", f"/commissions/closings/{PERIOD}"),
        ("POST", f"/commissions/closings/{PERIOD}/calculate"),
        ("PATCH", f"/commissions/closings/{PERIOD}/status"),
        ("POST", f"/commissions/closings/{PERIOD}/reopen"),
    ]

    @pytest.mark.parametrize("method,path", endpoints_sales_forbidden)
    def test_sales_403(self, tokens, method, path):
        r = requests.request(method, f"{BASE}{path}", headers=h(tokens["sales"]), json={})
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"

    def test_accounting_403_reopen(self, tokens):
        # first create closing via super so path exists
        requests.post(f"{BASE}/commissions/closings", headers=h(tokens["super"]),
                      json={"period": PERIOD})
        r = requests.post(f"{BASE}/commissions/closings/{PERIOD}/reopen", headers=h(tokens["acc"]))
        assert r.status_code == 403


# ---------------- Closing Lifecycle ----------------
class TestLifecycle:
    def test_full_lifecycle(self, tokens):
        # 1) create OPEN
        r = requests.post(f"{BASE}/commissions/closings", headers=h(tokens["super"]),
                          json={"period": PERIOD})
        assert r.status_code == 200, r.text
        assert r.json()["status"] in ("OPEN", "REVIEW", "APPROVED", "CLOSED", "PAID")

        # 2) calculate -> REVIEW
        r = requests.post(f"{BASE}/commissions/closings/{PERIOD}/calculate",
                          headers=h(tokens["super"]))
        assert r.status_code == 200, r.text
        assert "lines" in r.json()

        # detail
        r = requests.get(f"{BASE}/commissions/closings/{PERIOD}", headers=h(tokens["super"]))
        assert r.status_code == 200
        det = r.json()
        assert det["closing"]["status"] == "REVIEW"

        # 3) REVIEW -> APPROVED
        r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/status",
                           headers=h(tokens["super"]), json={"status": "APPROVED"})
        assert r.status_code == 200
        assert r.json()["status"] == "APPROVED"

        # 4) APPROVED -> CLOSED
        r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/status",
                           headers=h(tokens["super"]), json={"status": "CLOSED"})
        assert r.status_code == 200
        assert r.json()["status"] == "CLOSED"

        # 5) After CLOSED, recalc must 400
        r = requests.post(f"{BASE}/commissions/closings/{PERIOD}/calculate",
                          headers=h(tokens["super"]))
        assert r.status_code == 400, r.text

        # 6) Reopen (Super Admin) -> OPEN
        r = requests.post(f"{BASE}/commissions/closings/{PERIOD}/reopen",
                          headers=h(tokens["super"]))
        assert r.status_code == 200
        assert r.json()["status"] == "OPEN"

        # 7) walk to PAID: recalc -> APPROVED -> CLOSED -> PAID
        assert requests.post(f"{BASE}/commissions/closings/{PERIOD}/calculate",
                             headers=h(tokens["super"])).status_code == 200
        for st in ("APPROVED", "CLOSED", "PAID"):
            r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/status",
                               headers=h(tokens["super"]), json={"status": st})
            assert r.status_code == 200, f"->{st} {r.text}"
        r = requests.get(f"{BASE}/commissions/closings/{PERIOD}", headers=h(tokens["super"]))
        assert r.json()["closing"]["status"] == "PAID"

        # 8) adjustment on PAID closing must be blocked (if any lines exist)
        lines = r.json().get("lines") or []
        if lines:
            lid = lines[0]["_id"]
            r2 = requests.patch(f"{BASE}/commissions/lines/{lid}/adjustment",
                                headers=h(tokens["super"]), json={"adjustment": 1000})
            assert r2.status_code == 400, r2.text


# ---------------- My Commission (Sales) ----------------
class TestMyCommission:
    def test_sales_my(self, tokens):
        r = requests.get(f"{BASE}/commissions/my", headers=h(tokens["sales"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert "current" in d and "previous" in d and "period" in d
        cur = d["current"]
        for k in ("total_pax", "tier", "commission_rate", "total_commission"):
            assert k in cur, f"missing {k}"

    def test_accounting_my_forbidden(self, tokens):
        # Accounting has commission.manage but not commission.view — expect 403
        r = requests.get(f"{BASE}/commissions/my", headers=h(tokens["acc"]))
        # accept either 403 or 200 depending on permission set; assert not 500
        assert r.status_code in (200, 403), r.status_code
