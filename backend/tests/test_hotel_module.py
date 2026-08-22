"""Hotel module (Agoda) backend tests - RBAC, masking, graceful failure."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback to frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES = {"email": "sales@safarcrm.com", "password": "Sales@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES)


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# ---------- RBAC ----------
class TestHotelRBAC:
    def test_settings_admin_200(self, admin_token):
        r = requests.get(f"{API}/hotel/settings", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "api_key_masked" in data
        assert "api_key_set" in data
        # never leak raw key
        assert "api_key" not in data or data.get("api_key") in (None, "")
        assert "api_key_enc" not in data

    def test_settings_sales_403(self, sales_token):
        r = requests.get(f"{API}/hotel/settings", headers=_h(sales_token), timeout=15)
        assert r.status_code == 403

    def test_logs_admin_200(self, admin_token):
        r = requests.get(f"{API}/hotel/logs", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_logs_sales_403(self, sales_token):
        r = requests.get(f"{API}/hotel/logs", headers=_h(sales_token), timeout=15)
        assert r.status_code == 403

    def test_search_history_any_user(self, sales_token):
        r = requests.get(f"{API}/hotel/search-history", headers=_h(sales_token), timeout=15)
        assert r.status_code == 200


# ---------- Settings save + masking ----------
class TestHotelSettingsMasking:
    def test_put_settings_encrypts_and_masks(self, admin_token):
        payload = {
            "provider": "agoda", "site_id": "1234567",
            "api_key": "SUPER_SECRET_KEY_9876",
            "endpoint": "https://affiliateapi7643.agoda.com/affiliateservice/lt_v1",
            "language": "id-id", "currency": "IDR", "active": True,
        }
        r = requests.put(f"{API}/hotel/settings", headers=_h(admin_token), json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        body = r.text
        assert "SUPER_SECRET_KEY_9876" not in body
        assert data.get("api_key_set") is True
        masked = data.get("api_key_masked", "")
        assert "9876" in masked or "•" in masked or "*" in masked
        assert data.get("site_id") == "1234567"

    def test_get_after_put_persists(self, admin_token):
        r = requests.get(f"{API}/hotel/settings", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("site_id") == "1234567"
        assert d.get("api_key_set") is True
        assert "SUPER_SECRET_KEY_9876" not in r.text


# ---------- Graceful failure ----------
class TestHotelGracefulFailure:
    def test_connection_returns_json_not_500(self, admin_token):
        r = requests.post(f"{API}/hotel/test-connection", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "success" in d
        # With fake creds we expect failure but graceful
        assert isinstance(d.get("success"), bool)

    def test_search_graceful(self, sales_token):
        from datetime import date, timedelta
        ci = (date.today() + timedelta(days=30)).isoformat()
        co = (date.today() + timedelta(days=32)).isoformat()
        body = {"checkIn": ci, "checkOut": co, "cityId": 9395,
                "occupancy": {"numberOfAdult": 2, "numberOfChildren": 0}, "maxResult": 5}
        r = requests.post(f"{API}/hotel/search", headers=_h(sales_token), json=body, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "results" in d and isinstance(d["results"], list)


# ---------- Logs do not leak secrets ----------
class TestHotelLogsNoLeak:
    def test_logs_have_no_api_key(self, admin_token):
        r = requests.get(f"{API}/hotel/logs", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        text = r.text.lower()
        assert "super_secret_key_9876" not in text
        assert "authorization" not in text or "api_key\"" not in text
