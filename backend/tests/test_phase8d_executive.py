"""Phase 8D - Executive Dashboard tests"""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

SUPER = {"email_or_username": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES = {"email_or_username": "sales@safarcrm.com", "password": "Sales@123"}
ACCT = {"email_or_username": "accounting@safarcrm.com", "password": "Account@123"}


def login(creds):
    # Try common login payload keys
    for key in ("email_or_username", "email", "username"):
        payload = {key: creds["email_or_username"], "password": creds["password"]}
        r = requests.post(f"{API}/auth/login", json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            token = data.get("access_token") or data.get("token")
            return token, r.cookies
    pytest.fail(f"Login failed for {creds['email_or_username']}: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="module")
def super_token():
    tok, _ = login(SUPER)
    return tok


@pytest.fixture(scope="module")
def sales_token():
    tok, _ = login(SALES)
    return tok


@pytest.fixture(scope="module")
def acct_token():
    tok, _ = login(ACCT)
    return tok


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_super_admin_200_and_keys(super_token):
    r = requests.get(f"{API}/executive-dashboard", headers=h(super_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    required = ["sales", "financial", "profitability", "tax", "refund",
                "trend", "funnel", "receivable_aging", "revenue_by_package",
                "sales_performance", "payment_status", "outstanding", "period"]
    missing = [k for k in required if k not in data]
    assert not missing, f"Missing keys: {missing}"
    # trend has 6 months
    assert isinstance(data["trend"], list)
    assert len(data["trend"]) == 6, f"trend has {len(data['trend'])} entries"


def test_month_filter(super_token):
    now = datetime.utcnow()
    current = now.strftime("%Y-%m")
    # pick a different month
    other_month = "2024-01" if current != "2024-01" else "2024-02"

    r1 = requests.get(f"{API}/executive-dashboard?month={current}", headers=h(super_token), timeout=20)
    r2 = requests.get(f"{API}/executive-dashboard?month={other_month}", headers=h(super_token), timeout=20)
    assert r1.status_code == 200 and r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert d1["period"] == current, f"period={d1['period']} vs {current}"
    assert d2["period"] == other_month, f"period={d2['period']} vs {other_month}"


def test_profitability_consistency(super_token):
    r = requests.get(f"{API}/executive-dashboard", headers=h(super_token), timeout=20)
    assert r.status_code == 200
    prof = r.json()["profitability"]
    rev = prof.get("revenue", 0)
    hpp = prof.get("hpp", 0)
    gp = prof.get("gross_profit", 0)
    gm = prof.get("gross_margin", 0)
    assert gp == rev - hpp, f"gross_profit {gp} != revenue {rev} - hpp {hpp}"
    if rev > 0:
        expected = round(gp / rev * 100, 1)
        assert gm == expected, f"gross_margin {gm} != expected {expected}"
    else:
        assert gm == 0


def test_rbac_sales_403(sales_token):
    r = requests.get(f"{API}/executive-dashboard", headers=h(sales_token), timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"


def test_rbac_accounting_403(acct_token):
    r = requests.get(f"{API}/executive-dashboard", headers=h(acct_token), timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"
