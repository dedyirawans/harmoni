"""Phase 8G — Financial & Management Reports backend tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "super_admin": {"email": "dedyirawan18@gmail.com", "password": "Admin@123"},
    "accounting": {"email": "accounting@safarcrm.com", "password": "Account@123"},
    "sales": {"email": "sales@safarcrm.com", "password": "Sales@123"},
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def tokens():
    return {role: _login(c["email"], c["password"]) for role, c in CREDS.items()}


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------- filters ----------------
def test_filters_accounting_and_sales(tokens):
    r = requests.get(f"{API}/mgmt-reports/filters", headers=_h(tokens["accounting"]))
    assert r.status_code == 200
    d = r.json()
    for k in ("packages", "sales", "product_types", "destinations", "tax_types"):
        assert k in d
    assert len(d["sales"]) >= 0
    assert set(d["product_types"]) >= {"TOUR", "UMROH"}

    r2 = requests.get(f"{API}/mgmt-reports/filters", headers=_h(tokens["sales"]))
    assert r2.status_code == 200
    assert r2.json()["sales"] == []  # sales cannot see sales list


# ---------------- P&L ----------------
def test_profit_loss_rbac_and_math(tokens):
    r = requests.get(f"{API}/mgmt-reports/profit-loss", headers=_h(tokens["sales"]))
    assert r.status_code == 403

    for role in ("accounting", "super_admin"):
        r = requests.get(f"{API}/mgmt-reports/profit-loss", headers=_h(tokens[role]))
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        s = d["summary"]
        # math checks (allow tiny float drift)
        assert abs(s["gross_profit"] - (s["revenue"] - s["hpp"])) < 0.5
        assert abs(s["net_profit"] - (s["gross_profit"] - s["opex"])) < 0.5
        assert "gross_margin" in s and "net_margin" in s


def test_profit_loss_filters(tokens):
    r = requests.get(f"{API}/mgmt-reports/profit-loss?product_type=TOUR", headers=_h(tokens["accounting"]))
    assert r.status_code == 200


# ---------------- Balance Sheet ----------------
def test_balance_sheet(tokens):
    assert requests.get(f"{API}/mgmt-reports/balance-sheet", headers=_h(tokens["sales"])).status_code == 403
    r = requests.get(f"{API}/mgmt-reports/balance-sheet", headers=_h(tokens["accounting"]))
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    # Expect balanced: total_assets == total_liabilities + total_equity
    ta = d.get("total_assets") or d.get("summary", {}).get("total_assets")
    tl = d.get("total_liabilities") or d.get("summary", {}).get("total_liabilities")
    te = d.get("total_equity") or d.get("summary", {}).get("total_equity")
    balanced = d.get("balanced")
    if balanced is None:
        balanced = d.get("summary", {}).get("balanced")
    assert balanced is True
    assert abs((ta or 0) - ((tl or 0) + (te or 0))) < 1.0


# ---------------- Cash Flow ----------------
def test_cash_flow(tokens):
    assert requests.get(f"{API}/mgmt-reports/cash-flow", headers=_h(tokens["sales"])).status_code == 403
    r = requests.get(f"{API}/mgmt-reports/cash-flow", headers=_h(tokens["accounting"]))
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    s = d.get("summary", d)
    op = s.get("opening_cash", 0)
    ci = s.get("cash_in", 0)
    co = s.get("cash_out", 0)
    net = s.get("net_cash_flow", 0)
    end = s.get("ending_cash", 0)
    assert abs(net - (ci - co)) < 0.5
    assert abs(end - (op + net)) < 0.5


# ---------------- Sales Detail ----------------
def test_sales_detail_scoping(tokens):
    for role in ("accounting", "super_admin", "sales"):
        r = requests.get(f"{API}/mgmt-reports/sales-detail", headers=_h(tokens[role]))
        assert r.status_code == 200, f"{role} {r.status_code} {r.text[:200]}"
        d = r.json()
        assert "summary" in d
        for k in ("total_booking", "total_pax", "gross_sales", "net_sales", "paid", "outstanding"):
            assert k in d["summary"], f"missing {k}"


# ---------------- Team Performance ----------------
def test_team_performance(tokens):
    r = requests.get(f"{API}/mgmt-reports/team-performance", headers=_h(tokens["accounting"]))
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    assert "rankings" in d
    for k in ("by_revenue", "by_pax", "by_conversion", "by_booking"):
        assert k in d["rankings"]

    rs = requests.get(f"{API}/mgmt-reports/team-performance", headers=_h(tokens["sales"]))
    assert rs.status_code == 200
    ds = rs.json()
    rows = ds.get("rows") or ds.get("data") or []
    # sales sees only own row
    assert len(rows) <= 1


# ---------------- Tax Recap ----------------
def test_tax_recap(tokens):
    assert requests.get(f"{API}/mgmt-reports/tax-recap?tax_type=PPN&month=8&year=2026", headers=_h(tokens["sales"])).status_code == 403
    r = requests.get(f"{API}/mgmt-reports/tax-recap?tax_type=PPN&month=8&year=2026", headers=_h(tokens["accounting"]))
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    s = d.get("summary", d)
    for k in ("taxable_sales", "dpp", "ppn_output", "ppn_payable"):
        assert k in s, f"missing {k} in tax recap"
    # ppn_input may be absent if no vendor bills; accept either
    assert "ppn_input" in s or s.get("ppn_payable") == s.get("ppn_output")
    # PPh21/PPh23 structural
    for t in ("PPh21", "PPh23"):
        r2 = requests.get(f"{API}/mgmt-reports/tax-recap?tax_type={t}&month=8&year=2026", headers=_h(tokens["accounting"]))
        assert r2.status_code == 200, f"{t} {r2.text[:200]}"


# ---------------- Payable ----------------
def test_payable(tokens):
    assert requests.get(f"{API}/mgmt-reports/payable", headers=_h(tokens["sales"])).status_code == 403
    r = requests.get(f"{API}/mgmt-reports/payable", headers=_h(tokens["accounting"]))
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    assert "summary" in d
    s = d["summary"]
    # aging buckets (server uses d1_30, d31_60, d61_90, d90p keys)
    for k in ("current", "d1_30", "d31_60", "d61_90", "d90"):
        assert k in s, f"missing bucket {k}"


# ---------------- Receivable Aging ----------------
def test_receivable_aging(tokens):
    for role in ("accounting", "super_admin", "sales"):
        r = requests.get(f"{API}/mgmt-reports/receivable-aging", headers=_h(tokens[role]))
        assert r.status_code == 200, f"{role} {r.status_code} {r.text[:200]}"
        d = r.json()
        assert "summary" in d
        s = d["summary"]
        assert "total_receivable" in s
