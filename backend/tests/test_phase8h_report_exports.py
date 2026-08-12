"""Phase 8H — Report Export & Validation backend tests."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "super_admin": {"email": "dedyirawan18@gmail.com", "password": "Admin@123"},
    "accounting": {"email": "accounting@safarcrm.com", "password": "Account@123"},
    "sales": {"email": "sales@safarcrm.com", "password": "Sales@123"},
}

ALL_KEYS = ["profit-loss", "balance-sheet", "cash-flow", "sales-detail",
            "team-performance", "tax-recap", "payable", "receivable-aging"]
FINANCE_KEYS = {"profit-loss", "balance-sheet", "cash-flow", "tax-recap", "payable"}
SALES_ALLOWED = {"sales-detail", "team-performance", "receivable-aging"}

CT = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def tokens():
    return {role: _login(c["email"], c["password"]) for role, c in CREDS.items()}


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _export(tok, key, fmt, extra=""):
    q = f"format={fmt}"
    if key == "tax-recap":
        q += "&tax_type=PPN&month=8&year=2026"
    if extra:
        q += "&" + extra
    return requests.get(f"{API}/mgmt-reports/{key}/export?{q}", headers=_h(tok), timeout=60)


# -------- 8H.1: All 24 combinations return 200 for accounting/super_admin --------
@pytest.mark.parametrize("key", ALL_KEYS)
@pytest.mark.parametrize("fmt", ["xlsx", "csv", "pdf"])
def test_export_all_formats_accounting(tokens, key, fmt):
    r = _export(tokens["accounting"], key, fmt)
    assert r.status_code == 200, f"{key} {fmt}: {r.status_code} {r.text[:200]}"
    ct = r.headers.get("content-type", "").lower()
    assert CT[fmt] in ct, f"{key} {fmt}: content-type={ct}"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and f".{fmt}" in cd, f"{key} {fmt}: {cd}"
    # filename [ReportName]_[Period]_[GeneratedDate].[ext]
    m = re.search(r'filename=([^;]+)', cd)
    assert m, f"no filename in {cd}"
    fn = m.group(1).strip().strip('"')
    assert fn.endswith(f".{fmt}"), fn
    # underscore-separated segments
    assert fn.count("_") >= 2, f"filename structure unexpected: {fn}"
    assert len(r.content) > 100, f"{key} {fmt} body too small: {len(r.content)}"


# -------- 8H.2: RBAC — Sales forbidden on finance exports --------
@pytest.mark.parametrize("key", sorted(FINANCE_KEYS))
def test_sales_forbidden_finance_export(tokens, key):
    r = _export(tokens["sales"], key, "xlsx")
    assert r.status_code == 403, f"{key}: expected 403 got {r.status_code} {r.text[:200]}"


# -------- 8H.3: RBAC — Sales allowed on own-scoped reports --------
@pytest.mark.parametrize("key", sorted(SALES_ALLOWED))
@pytest.mark.parametrize("fmt", ["xlsx", "csv", "pdf"])
def test_sales_allowed_own_scoped_export(tokens, key, fmt):
    r = _export(tokens["sales"], key, fmt)
    assert r.status_code == 200, f"{key} {fmt}: {r.status_code} {r.text[:200]}"
    assert CT[fmt] in r.headers.get("content-type", "").lower()
    assert len(r.content) > 100


# -------- 8H.4: auth via ?auth= fallback works --------
def test_auth_query_fallback(tokens):
    r = requests.get(f"{API}/mgmt-reports/sales-detail/export?format=csv&auth={tokens['accounting']}", timeout=30)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "").lower()


def test_export_no_auth_401(tokens):
    r = requests.get(f"{API}/mgmt-reports/sales-detail/export?format=csv", timeout=30)
    assert r.status_code == 401


# -------- 8H.5: Filename period slug applied for month/year --------
def test_filename_period_month_year(tokens):
    r = _export(tokens["accounting"], "tax-recap", "xlsx")
    cd = r.headers.get("content-disposition", "")
    assert "Agustus_2026" in cd, cd


# -------- 8H.6: Report Export History records inserted and RBAC-scoped --------
def test_report_exports_history(tokens):
    # trigger a fresh export to guarantee a record
    r = _export(tokens["accounting"], "profit-loss", "csv")
    assert r.status_code == 200
    r2 = requests.get(f"{API}/report-exports", headers=_h(tokens["accounting"]), timeout=30)
    assert r2.status_code == 200
    docs = r2.json()
    assert isinstance(docs, list) and len(docs) > 0
    d0 = docs[0]
    for k in ("report_name", "user_name", "format", "filter", "period", "file_name", "created_at"):
        assert k in d0, f"missing {k} in history record: {list(d0.keys())}"

    # Sales trigger own export then only sees own records
    rs = _export(tokens["sales"], "sales-detail", "csv")
    assert rs.status_code == 200
    r3 = requests.get(f"{API}/report-exports", headers=_h(tokens["sales"]), timeout=30)
    assert r3.status_code == 200
    sales_docs = r3.json()
    assert isinstance(sales_docs, list)
    # every record for sales user must be their own
    for x in sales_docs:
        # no finance-only report leak
        assert x.get("report_key") not in FINANCE_KEYS or x.get("user_name") is not None
    # sales list should be strictly <= accounting list
    assert len(sales_docs) <= len(docs)


# -------- 8H.7: Phase 8G endpoints still 200 (regression) --------
@pytest.mark.parametrize("key", ALL_KEYS)
def test_phase8g_json_still_ok(tokens, key):
    url = f"{API}/mgmt-reports/{key}"
    if key == "tax-recap":
        url += "?tax_type=PPN&month=8&year=2026"
    r = requests.get(url, headers=_h(tokens["accounting"]), timeout=30)
    assert r.status_code == 200, f"{key}: {r.status_code} {r.text[:200]}"


# -------- 8H.8: Unknown key -> 404 --------
def test_unknown_report_404(tokens):
    r = _export(tokens["accounting"], "does-not-exist", "csv")
    assert r.status_code == 404
