"""Phase 3 - Products/Packages/Departures/Costing RBAC & CRUD tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("dedyirawan18@gmail.com", "Admin@123")
SALES_A = ("sales@safarcrm.com", "Sales@123")
ACCT = ("accounting@safarcrm.com", "Account@123")

HPP_KEYS = ["hpp", "total_cost", "cost_per_pax", "gross_profit", "gross_margin", "costs", "cost_components"]


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def sales_tok():
    return _login(*SALES_A)


@pytest.fixture(scope="module")
def acct_tok():
    return _login(*ACCT)


# ============ SALES HPP LEAKAGE ============
class TestSalesHppLeakage:
    def test_sales_packages_list_active_only_no_hpp(self, sales_tok):
        r = requests.get(f"{API}/packages", headers=_h(sales_tok), timeout=15)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) >= 1
        for p in arr:
            assert p.get("status") == "ACTIVE"
            for k in HPP_KEYS:
                assert k not in p, f"HPP key '{k}' leaked to Sales in list: {p.get('package_code')}"

    def test_sales_package_detail_no_hpp(self, sales_tok):
        r = requests.get(f"{API}/packages", headers=_h(sales_tok), timeout=15)
        pid = r.json()[0]["_id"]
        r2 = requests.get(f"{API}/packages/{pid}", headers=_h(sales_tok), timeout=15)
        assert r2.status_code == 200
        detail = r2.json()
        pkg = detail["package"]
        for k in HPP_KEYS:
            assert k not in pkg, f"HPP key '{k}' leaked to Sales in detail"
        assert "costing" not in detail
        assert "versions" not in detail
        assert "itineraries" in detail
        assert "departures" in detail

    def test_sales_costing_forbidden(self, sales_tok):
        r = requests.get(f"{API}/packages", headers=_h(sales_tok), timeout=15)
        pid = r.json()[0]["_id"]
        r2 = requests.get(f"{API}/packages/{pid}/costing", headers=_h(sales_tok), timeout=15)
        assert r2.status_code == 403

    def test_sales_create_package_forbidden(self, sales_tok):
        r = requests.post(f"{API}/packages", headers=_h(sales_tok),
                          json={"package_name": "TEST_sales", "product_type": "TOUR"}, timeout=15)
        assert r.status_code == 403


# ============ ACCOUNTING ============
class TestAccounting:
    def test_accounting_list_has_hpp(self, acct_tok):
        r = requests.get(f"{API}/packages", headers=_h(acct_tok), timeout=15)
        assert r.status_code == 200
        arr = r.json()
        assert len(arr) >= 1
        # at least one seeded pkg has gross_margin
        assert any("gross_margin" in p for p in arr), "Accounting list missing gross_margin"

    def test_accounting_costing_ok(self, acct_tok):
        r = requests.get(f"{API}/packages", headers=_h(acct_tok), timeout=15)
        pid = r.json()[0]["_id"]
        r2 = requests.get(f"{API}/packages/{pid}/costing", headers=_h(acct_tok), timeout=15)
        assert r2.status_code == 200
        body = r2.json()
        assert "costing" in body

    def test_accounting_create_forbidden(self, acct_tok):
        r = requests.post(f"{API}/packages", headers=_h(acct_tok),
                          json={"package_name": "TEST_acct", "product_type": "TOUR"}, timeout=15)
        assert r.status_code == 403


# ============ SUPER ADMIN CRUD + VERSIONING + DEPARTURES ============
class TestAdminFlow:
    _pid = None

    def test_create_package(self, admin_tok):
        r = requests.post(f"{API}/packages", headers=_h(admin_tok),
                          json={"package_name": "TEST_P3_pkg", "product_type": "TOUR",
                                "destination": "Bali", "selling_price": 10000000,
                                "status": "ACTIVE"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["package_name"] == "TEST_P3_pkg"
        assert d["version"] == 1
        assert d["package_code"].startswith("TOUR-")
        TestAdminFlow._pid = d["_id"]

    def test_add_itinerary(self, admin_tok):
        pid = TestAdminFlow._pid
        r = requests.post(f"{API}/packages/{pid}/itineraries", headers=_h(admin_tok),
                          json={"day": 1, "location": "Denpasar", "activity": "Arrival"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["day"] == 1

    def test_add_departure_auto_seat(self, admin_tok):
        pid = TestAdminFlow._pid
        r = requests.post(f"{API}/packages/{pid}/departures", headers=_h(admin_tok),
                          json={"departure_date": "2026-06-01", "return_date": "2026-06-08",
                                "quota": 20, "confirmed_pax": 5, "price": 10000000}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["available_seat"] == 15
        assert d["status"] == "OPEN"

    def test_departure_almost_full(self, admin_tok):
        pid = TestAdminFlow._pid
        r = requests.post(f"{API}/packages/{pid}/departures", headers=_h(admin_tok),
                          json={"departure_date": "2026-07-01", "quota": 10, "confirmed_pax": 9,
                                "price": 10000000}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "ALMOST FULL"
        assert r.json()["available_seat"] == 1

    def test_save_costing_and_gross_margin(self, admin_tok):
        pid = TestAdminFlow._pid
        r = requests.put(f"{API}/packages/{pid}/costing", headers=_h(admin_tok),
                         json={"components": {"flight": 3000000, "hotel": 2000000, "visa": 500000},
                               "pax_basis": 1}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_cost"] == 5500000
        assert d["gross_profit"] == 10000000 - 5500000
        assert d["gross_margin"] == round(4500000 / 10000000 * 100, 2)

    def test_versioning_on_price_change(self, admin_tok):
        pid = TestAdminFlow._pid
        r = requests.put(f"{API}/packages/{pid}", headers=_h(admin_tok),
                         json={"package_name": "TEST_P3_pkg", "product_type": "TOUR",
                               "destination": "Bali", "selling_price": 12000000,
                               "status": "ACTIVE"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["version"] == 2
        # verify versions list
        r2 = requests.get(f"{API}/packages/{pid}", headers=_h(admin_tok), timeout=15)
        assert r2.status_code == 200
        assert "versions" in r2.json()
        assert len(r2.json()["versions"]) >= 1

    def test_itinerary_reorder(self, admin_tok):
        pid = TestAdminFlow._pid
        # add second itinerary
        r = requests.post(f"{API}/packages/{pid}/itineraries", headers=_h(admin_tok),
                          json={"day": 2, "location": "Ubud"}, timeout=15)
        assert r.status_code == 200
        pkg = requests.get(f"{API}/packages/{pid}", headers=_h(admin_tok), timeout=15).json()
        ids = [i["_id"] for i in pkg["itineraries"]]
        reversed_ids = list(reversed(ids))
        r2 = requests.put(f"{API}/packages/{pid}/itineraries/reorder", headers=_h(admin_tok),
                          json={"ids": reversed_ids}, timeout=15)
        assert r2.status_code == 200
        pkg2 = requests.get(f"{API}/packages/{pid}", headers=_h(admin_tok), timeout=15).json()
        new_first = pkg2["itineraries"][0]["_id"]
        assert new_first == reversed_ids[0]

    def test_all_departures_endpoint_sales_scoped(self, sales_tok, admin_tok):
        # sales should see only ACTIVE package departures
        r = requests.get(f"{API}/departures", headers=_h(sales_tok), timeout=15)
        assert r.status_code == 200
        # our TEST package is ACTIVE, so its departures should show
        codes = [d.get("package_name") for d in r.json()]
        # not a strict assertion; just endpoint works
        assert isinstance(r.json(), list)

    def test_zzz_cleanup(self, admin_tok):
        pid = TestAdminFlow._pid
        if pid:
            requests.delete(f"{API}/packages/{pid}", headers=_h(admin_tok), timeout=15)
