"""Phase 6: n8n WhatsApp integration tests."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://git-continue-5.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_ADMIN = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES = {"email": "sales@safarcrm.com", "password": "Sales@123"}
ACCT = {"email": "accounting@safarcrm.com", "password": "Account@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def sa_headers():
    return {"Authorization": f"Bearer {_login(SUPER_ADMIN)}"}


@pytest.fixture(scope="module")
def sales_headers():
    return {"Authorization": f"Bearer {_login(SALES)}"}


@pytest.fixture(scope="module")
def acct_headers():
    return {"Authorization": f"Bearer {_login(ACCT)}"}


# --- Config GET ---
def test_get_n8n_config(sa_headers):
    r = requests.get(f"{API}/integrations/n8n", headers=sa_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "webhook_url" in data
    assert "enabled" in data
    assert "events" in data and isinstance(data["events"], dict)
    assert len(data["events"]) >= 7, f"expected >=7 events, got {list(data['events'].keys())}"
    assert "whatsapp_templates" in data
    for k in ("payment.reminder", "booking.created", "payment.recorded"):
        assert k in data["whatsapp_templates"], f"missing template {k}"


def test_get_n8n_events_catalog(sa_headers):
    r = requests.get(f"{API}/integrations/n8n/events", headers=sa_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "events" in data
    assert len(data["events"]) >= 7
    assert "default_templates" in data


# --- Config PUT persistence ---
def test_put_n8n_config_persists(sa_headers):
    # Save with disabled + empty URL (safe reset target after tests)
    payload = {
        "webhook_url": "https://example.invalid/n8n-test-hook",
        "enabled": False,
        "events": {
            "quotation.created": True,
            "quotation.status_changed": True,
            "booking.created": True,
            "invoice.created": True,
            "payment.recorded": True,
            "payment.reminder": True,
            "trip.reminder": False,
        },
        "whatsapp_templates": {
            "payment.reminder": "TEST reminder {{customer_name}} {{amount}}",
            "booking.created": "TEST booking {{booking_code}}",
            "payment.recorded": "TEST payment {{amount}}",
        },
    }
    r = requests.put(f"{API}/integrations/n8n", headers=sa_headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text

    # Verify persistence
    r2 = requests.get(f"{API}/integrations/n8n", headers=sa_headers, timeout=30)
    assert r2.status_code == 200
    d = r2.json()
    assert d["webhook_url"] == payload["webhook_url"]
    assert d["enabled"] is False
    assert d["whatsapp_templates"]["payment.reminder"] == "TEST reminder {{customer_name}} {{amount}}"
    assert d["events"]["trip.reminder"] is False


# --- Test endpoint (disabled path) ---
def test_n8n_test_when_disabled(sa_headers):
    r = requests.post(f"{API}/integrations/n8n/test", headers=sa_headers, json={"event": "payment.reminder"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # When disabled or empty url, expect ok False + skipped True
    assert data.get("ok") is False
    assert data.get("skipped") is True or "reason" in data


# --- Logs endpoint ---
def test_n8n_logs_serializable(sa_headers):
    r = requests.get(f"{API}/integrations/n8n/logs", headers=sa_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # Response should be JSON list or dict with logs
    if isinstance(data, dict):
        logs = data.get("logs", data.get("items", []))
    else:
        logs = data
    assert isinstance(logs, list)
    for entry in logs[:5]:
        # No ObjectId leak
        if "_id" in entry:
            assert isinstance(entry["_id"], str)


# --- Payment reminders dispatch ---
def test_payment_reminders_dispatch(sa_headers):
    r = requests.post(f"{API}/payment-reminders/dispatch", headers=sa_headers, json={}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "total" in data
    assert "dispatched" in data
    assert "n8n_enabled" in data


# --- RBAC 403 for Sales & Accounting ---
@pytest.mark.parametrize("path,method", [
    ("/integrations/n8n", "GET"),
    ("/integrations/n8n/events", "GET"),
    ("/integrations/n8n/logs", "GET"),
    ("/integrations/n8n/test", "POST"),
])
def test_rbac_sales_forbidden(sales_headers, path, method):
    if method == "GET":
        r = requests.get(f"{API}{path}", headers=sales_headers, timeout=30)
    else:
        r = requests.post(f"{API}{path}", headers=sales_headers, json={"event": "payment.reminder"}, timeout=30)
    assert r.status_code == 403, f"expected 403 for sales on {path}, got {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("path,method", [
    ("/integrations/n8n", "GET"),
    ("/integrations/n8n/events", "GET"),
    ("/integrations/n8n/logs", "GET"),
    ("/integrations/n8n/test", "POST"),
])
def test_rbac_accounting_forbidden(acct_headers, path, method):
    if method == "GET":
        r = requests.get(f"{API}{path}", headers=acct_headers, timeout=30)
    else:
        r = requests.post(f"{API}{path}", headers=acct_headers, json={"event": "payment.reminder"}, timeout=30)
    assert r.status_code == 403, f"expected 403 for accounting on {path}, got {r.status_code} {r.text[:200]}"


# --- Event auto-trigger: create quotation writes a log ---
def test_quotation_created_triggers_n8n_log(sa_headers):
    # Fetch logs before
    r_before = requests.get(f"{API}/integrations/n8n/logs", headers=sa_headers, timeout=30)
    before = r_before.json() if isinstance(r_before.json(), list) else r_before.json().get("logs", r_before.json().get("items", []))
    before_ids = {e.get("id") or e.get("_id") for e in before}

    # Need a customer id -- try to fetch existing
    cust_r = requests.get(f"{API}/customers", headers=sa_headers, timeout=30)
    if cust_r.status_code != 200:
        pytest.skip(f"cannot fetch customers: {cust_r.status_code}")
    customers = cust_r.json()
    if not customers:
        pytest.skip("no customers seeded")
    cust_id = customers[0].get("id") or customers[0].get("_id")

    # Need a package_id too
    pkg_r = requests.get(f"{API}/packages", headers=sa_headers, timeout=30)
    if pkg_r.status_code != 200 or not pkg_r.json():
        pytest.skip("no packages available")
    pkg_id = pkg_r.json()[0].get("id") or pkg_r.json()[0].get("_id")

    payload = {
        "customer_id": cust_id,
        "package_id": pkg_id,
        "pax": 1,
    }
    q = requests.post(f"{API}/quotations", headers=sa_headers, json=payload, timeout=30)
    if q.status_code not in (200, 201):
        pytest.skip(f"quotation create failed with schema {q.status_code}: {q.text[:200]}")

    time.sleep(1.5)
    r_after = requests.get(f"{API}/integrations/n8n/logs", headers=sa_headers, timeout=30)
    after = r_after.json() if isinstance(r_after.json(), list) else r_after.json().get("logs", r_after.json().get("items", []))
    quotation_logs = [e for e in after if e.get("event") == "quotation.created"]
    assert len(quotation_logs) > 0, "expected at least one quotation.created log entry"


# --- Cleanup: reset config to empty + disabled ---
def test_zzz_cleanup_reset_config(sa_headers):
    payload = {
        "webhook_url": "",
        "enabled": False,
    }
    r = requests.put(f"{API}/integrations/n8n", headers=sa_headers, json=payload, timeout=30)
    assert r.status_code == 200
    r2 = requests.get(f"{API}/integrations/n8n", headers=sa_headers, timeout=30)
    d = r2.json()
    assert d.get("webhook_url", "") == ""
    assert d.get("enabled") is False
