"""Pipeline stage move permission tests (Phase 2 enhancement).

Verifies PATCH /api/leads/{id}/stage RBAC:
- Owner (Sales A) can move own lead -> 200
- Super Admin can move any lead -> 200
- Non-owner Sales B moving Sales A's lead -> 403
- Move persists (verified via GET)
"""
import os
import pytest
import requests

def _read_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("REACT_APP_BACKEND_URL", "")

BASE = _read_frontend_env().rstrip("/") + "/api"

CRED = {
    "admin": ("dedyirawan18@gmail.com", "Admin@123"),
    "sales_a": ("sales@safarcrm.com", "Sales@123"),
    "sales_b": ("salesb@safarcrm.com", "SalesB@123"),
}


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    j = r.json()
    return j.get("token") or j.get("access_token")


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def tokens():
    return {k: login(*v) for k, v in CRED.items()}


@pytest.fixture(scope="module")
def sales_a_lead(tokens):
    # Fetch first lead owned by Sales A
    r = requests.get(f"{BASE}/leads", headers=H(tokens["sales_a"]), timeout=15)
    assert r.status_code == 200
    leads = r.json()
    assert leads, "Sales A has no leads to test with"
    return leads[0]


def test_owner_can_move(tokens, sales_a_lead):
    lid = sales_a_lead["_id"]
    original = sales_a_lead["status"]
    target = "CONTACTED" if original != "CONTACTED" else "QUALIFIED"
    r = requests.patch(f"{BASE}/leads/{lid}/stage", json={"stage": target}, headers=H(tokens["sales_a"]), timeout=15)
    assert r.status_code == 200, r.text
    # Verify persistence
    g = requests.get(f"{BASE}/leads/{lid}", headers=H(tokens["sales_a"]), timeout=15)
    assert g.status_code == 200
    assert g.json()["status"] == target
    # Restore
    requests.patch(f"{BASE}/leads/{lid}/stage", json={"stage": original}, headers=H(tokens["sales_a"]), timeout=15)


def test_super_admin_can_move_any(tokens, sales_a_lead):
    lid = sales_a_lead["_id"]
    original = sales_a_lead["status"]
    target = "QUOTATION" if original != "QUOTATION" else "NEGOTIATION"
    r = requests.patch(f"{BASE}/leads/{lid}/stage", json={"stage": target}, headers=H(tokens["admin"]), timeout=15)
    assert r.status_code == 200, r.text
    g = requests.get(f"{BASE}/leads/{lid}", headers=H(tokens["admin"]), timeout=15)
    assert g.json()["status"] == target
    # Restore
    requests.patch(f"{BASE}/leads/{lid}/stage", json={"stage": original}, headers=H(tokens["admin"]), timeout=15)


def test_other_sales_cannot_move_403(tokens, sales_a_lead):
    lid = sales_a_lead["_id"]
    r = requests.patch(f"{BASE}/leads/{lid}/stage", json={"stage": "BOOKING"}, headers=H(tokens["sales_b"]), timeout=15)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_hpp_still_forbidden_for_sales(tokens):
    r = requests.get(f"{BASE}/hpp", headers=H(tokens["sales_a"]), timeout=15)
    assert r.status_code == 403


def test_create_lead_regression(tokens):
    payload = {
        "source": "WhatsApp",
        "interested_package": "TEST_PIPELINE_regression",
        "destination": "Mekkah",
        "pax": 2,
        "budget": 50000000,
        "status": "NEW",
        "notes": "regression",
    }
    r = requests.post(f"{BASE}/leads", json=payload, headers=H(tokens["sales_a"]), timeout=15)
    assert r.status_code in (200, 201), r.text
    lid = r.json()["_id"]
    assert r.json()["status"] == "NEW"
    # cleanup
    requests.delete(f"{BASE}/leads/{lid}", headers=H(tokens["sales_a"]), timeout=15)
