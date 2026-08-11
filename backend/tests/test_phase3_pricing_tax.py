"""Phase 3 - Tiered pricing, min_quota_pax, tour_price_portion, category tax settings."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("dedyirawan18@gmail.com", "Admin@123")


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def created_ids():
    ids = []
    yield ids
    # cleanup
    tok = _login(*ADMIN)
    for pid in ids:
        try:
            requests.delete(f"{API}/packages/{pid}", headers=_h(tok), timeout=10)
        except Exception:
            pass


# ---------- Settings: category tax ----------
class TestCategoryTaxSettings:
    def test_update_category_tax(self, admin_tok):
        payload = {
            "settings": {
                "category_tax": {
                    "umroh_percent": 0,
                    "tour_percent": 1.1,
                    "umroh_plus_percent": 1.1,
                }
            }
        }
        r = requests.put(f"{API}/system-settings", headers=_h(admin_tok), json=payload, timeout=15)
        assert r.status_code == 200, r.text

    def test_get_settings_reflects_tax(self, admin_tok):
        r = requests.get(f"{API}/system-settings", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        ct = (r.json().get("settings") or {}).get("category_tax") or {}
        assert float(ct.get("tour_percent", 0)) == 1.1
        assert float(ct.get("umroh_plus_percent", 0)) == 1.1


# ---------- PRIVATE tiered pricing ----------
class TestPrivateTieredPricing:
    def test_create_private_umroh_with_tiers(self, admin_tok, created_ids):
        body = {
            "package_name": "TEST_priv_umroh",
            "product_type": "UMROH",
            "sub_category": "PRIVATE",
            "destination": "Makkah",
            "selling_price": 40000000,
            "status": "ACTIVE",
            "pricing_tiers": [
                {"min_pax": 1, "max_pax": 2, "price": 60000000},
                {"min_pax": 3, "max_pax": 5, "price": 50000000},
                {"min_pax": 6, "max_pax": 10, "price": 40000000},
            ],
        }
        r = requests.post(f"{API}/packages", headers=_h(admin_tok), json=body, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sub_category"] == "PRIVATE"
        assert len(d["pricing_tiers"]) == 3
        created_ids.append(d["_id"])

    def test_get_price_tier_1_pax(self, admin_tok, created_ids):
        pid = created_ids[0]
        r = requests.get(f"{API}/packages/{pid}/price?pax=1", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mode"] == "private"
        assert d["price_per_pax"] == 60000000

    def test_get_price_tier_4_pax(self, admin_tok, created_ids):
        pid = created_ids[0]
        r = requests.get(f"{API}/packages/{pid}/price?pax=4", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert r.json()["price_per_pax"] == 50000000

    def test_get_price_tier_8_pax(self, admin_tok, created_ids):
        pid = created_ids[0]
        r = requests.get(f"{API}/packages/{pid}/price?pax=8", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert r.json()["price_per_pax"] == 40000000


# ---------- OPEN_TRIP min_quota_pax ----------
class TestOpenTripMinQuota:
    def test_create_open_trip_tour(self, admin_tok, created_ids):
        body = {
            "package_name": "TEST_ot_tour",
            "product_type": "TOUR",
            "sub_category": "OPEN_TRIP",
            "destination": "Bali",
            "selling_price": 10000000,
            "min_quota_pax": 10,
            "status": "ACTIVE",
        }
        r = requests.post(f"{API}/packages", headers=_h(admin_tok), json=body, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sub_category"] == "OPEN_TRIP"
        assert d["min_quota_pax"] == 10
        created_ids.append(d["_id"])

    def test_open_trip_full_pax(self, admin_tok, created_ids):
        pid = created_ids[1]
        r = requests.get(f"{API}/packages/{pid}/price?pax=10", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["mode"] == "open_trip"
        assert d["price_per_pax"] == 10000000

    def test_open_trip_under_quota_price_rises(self, admin_tok, created_ids):
        pid = created_ids[1]
        r = requests.get(f"{API}/packages/{pid}/price?pax=5", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        d = r.json()
        # min_quota_pax(10) * base(10M) / pax(5) = 20M
        assert d["price_per_pax"] == 20000000


# ---------- UMROH_PLUS tour_price_portion + tax ----------
class TestUmrohPlusTax:
    def test_create_umroh_plus_with_tour_portion(self, admin_tok, created_ids):
        body = {
            "package_name": "TEST_upx_pkg",
            "product_type": "UMROH_PLUS",
            "sub_category": "OPEN_TRIP",
            "destination": "Turkey",
            "selling_price": 50000000,
            "tour_price_portion": 20000000,
            "status": "ACTIVE",
        }
        r = requests.post(f"{API}/packages", headers=_h(admin_tok), json=body, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tour_price_portion"] == 20000000
        created_ids.append(d["_id"])

    def test_umroh_plus_tax_only_on_tour_portion(self, admin_tok, created_ids):
        pid = created_ids[2]
        r = requests.get(f"{API}/packages/{pid}", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        pkg = r.json()["package"]
        assert pkg.get("tax_percent") == 1.1
        # 20M * 1.1% = 220000
        assert pkg.get("tax_amount") == round(20000000 * 1.1 / 100)

    def test_umroh_no_tax(self, admin_tok, created_ids):
        # umroh private package
        pid = created_ids[0]
        r = requests.get(f"{API}/packages/{pid}", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        pkg = r.json()["package"]
        assert pkg.get("tax_amount", 0) == 0
