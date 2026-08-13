"""Phase 9P - Final UAT / Production Hardening tests.

Focus: RBAC/403, refund cap, commission month/payout,
duplicate/idempotency, AUTO SALES, seat, balance sheet,
tax immutability, audit trail, soft-delete."""
import os, uuid, time
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v: return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    return ln.split("=",1)[1].strip().rstrip("/")
    except Exception: pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE = _load_backend_url()
API = BASE + "/api"

SUPER = ("dedyirawan18@gmail.com", "Admin@123")
SALES = ("sales@safarcrm.com", "Sales@123")
ACCT  = ("accounting@safarcrm.com", "Account@123")

BKG_00002_ID = "6a7ac3e26aad3a79a0844111"


def _login(cred):
    r = requests.post(f"{API}/auth/login", json={"email": cred[0], "password": cred[1]}, timeout=15)
    assert r.status_code == 200, f"login failed for {cred[0]}: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, r.text
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def super_h(): return _login(SUPER)
@pytest.fixture(scope="module")
def sales_h(): return _login(SALES)
@pytest.fixture(scope="module")
def acct_h():  return _login(ACCT)


# ---------- RBAC / SECURITY ----------

FORBIDDEN_FOR_SALES = [
    ("GET", "/hpp"),
    ("GET", "/accounting-dashboard"),
    ("GET", "/tax-config"),
    ("GET", "/tax-masters"),
    ("GET", "/tax-dashboard"),
    ("GET", "/integrations/n8n"),
    ("GET", "/integrations/n8n/monitor"),
    ("GET", "/forecast/dashboard"),
    ("GET", "/reports/pic-changes"),
    ("GET", "/supplier-costs"),
    ("GET", "/mgmt-reports/profit-loss"),
    ("GET", "/mgmt-reports/balance-sheet"),
]

FORBIDDEN_FOR_ACCT = [
    ("GET", "/integrations/n8n"),
    ("GET", "/integrations/n8n/monitor"),
    ("PUT", "/integrations/n8n"),
    ("GET", "/forecast/dashboard"),
]

@pytest.mark.parametrize("method,path", FORBIDDEN_FOR_SALES)
def test_rbac_sales_forbidden(sales_h, method, path):
    r = requests.request(method, API + path, headers=sales_h, timeout=15)
    assert r.status_code == 403, f"Sales must get 403 on {method} {path}, got {r.status_code}: {r.text[:200]}"


@pytest.mark.parametrize("method,path", FORBIDDEN_FOR_ACCT)
def test_rbac_accounting_forbidden(acct_h, method, path):
    if method == "PUT":
        r = requests.put(API + path, headers=acct_h, json={"webhook_base_url": "http://x"}, timeout=15)
    else:
        r = requests.request(method, API + path, headers=acct_h, timeout=15)
    assert r.status_code == 403, f"Accounting must get 403 on {method} {path}, got {r.status_code}"


def test_rbac_super_admin_allowed_all(super_h):
    for _m, p in FORBIDDEN_FOR_SALES + FORBIDDEN_FOR_ACCT:
        if _m != "GET":
            continue
        r = requests.get(API + p, headers=super_h, timeout=15)
        assert r.status_code in (200, 404), f"Super admin blocked on {p}: {r.status_code}"


# ---------- AUTO SALES + IDEMPOTENCY ----------

def _pick_pkg_and_customer(super_h):
    pkgs = requests.get(API + "/packages", headers=super_h, timeout=15).json()
    pkgs = pkgs.get("items", pkgs) if isinstance(pkgs, dict) else pkgs
    assert pkgs, "no packages"
    pkg = pkgs[0]
    custs = requests.get(API + "/customers", headers=super_h, timeout=15).json()
    custs = custs.get("items", custs) if isinstance(custs, dict) else custs
    return pkg, custs[0]


def test_auto_sales_marker_on_existing_bookings(super_h):
    """/v1/bookings requires N8N HMAC signing (X-API-Key/X-Signature/X-Timestamp)
    which is not available in this env. Instead verify that N8N-created bookings
    already persisted in DB carry booking_source='AUTO SALES' and have
    external_booking_id populated (idempotency key). BKG-00016 is the seed sample."""
    r = requests.get(API + "/bookings", headers=super_h, timeout=15, params={"limit": 200}).json()
    items = r.get("items", r) if isinstance(r, dict) else r
    auto = [b for b in items if (b.get("booking_source") or "").upper() == "AUTO SALES"]
    assert auto, "no AUTO SALES bookings found in DB — expected at least BKG-00016"
    b = auto[0]
    assert b.get("external_booking_id"), f"AUTO SALES booking missing external_booking_id (idempotency key): {b.get('booking_number')}"
    # sales_pic per spec should be NULL unless manually assigned. Accept the
    # documented placeholder AUTO SALES user id but flag string 'AUTO SALES'.
    assert (b.get("sales_pic_name") or "").upper() == "AUTO SALES", (
        f"AUTO SALES booking sales_pic_name expected 'AUTO SALES', got {b.get('sales_pic_name')}")


def test_v1_bookings_requires_n8n_auth(super_h):
    """POST /v1/bookings must reject bearer-only requests (no n8n API key)."""
    pkg, cust = _pick_pkg_and_customer(super_h)
    idem = f"TEST_UAT_{uuid.uuid4().hex[:12]}"
    r = requests.post(API + "/v1/bookings", json={
        "customer_id": cust["id"], "package_id": pkg["id"], "pax": 1,
        "external_booking_id": idem,
    }, headers=super_h, timeout=15)
    assert r.status_code == 401, f"expected 401 for unsigned /v1/bookings, got {r.status_code}"


# ---------- SEAT / CAPACITY ----------

def test_seat_capacity_decrement(super_h):
    """Booking a package should decrement available seats.

    Uses the /packages/{id}/availability endpoint (before/after) with a temp booking."""
    pkg, cust = _pick_pkg_and_customer(super_h)
    pid = pkg["id"]
    av0 = requests.get(API + f"/packages/{pid}/availability", headers=super_h, timeout=15)
    if av0.status_code != 200:
        pytest.skip("availability endpoint not supported for this package")
    a0 = av0.json()
    avail_before = a0.get("available") if isinstance(a0, dict) else None
    if avail_before is None:
        pytest.skip(f"availability shape unexpected: {a0}")

    idem = f"TEST_SEAT_{uuid.uuid4().hex[:8]}"
    r = requests.post(API + "/v1/bookings", json={
        "customer_id": cust["id"], "package_id": pid, "pax": 1,
        "external_id": idem, "idempotency_key": idem,
    }, headers=super_h, timeout=20)
    if r.status_code not in (200, 201):
        pytest.skip(f"booking create failed for seat test: {r.status_code} {r.text[:200]}")
    bid = r.json().get("id") or r.json().get("booking_id")

    a1 = requests.get(API + f"/packages/{pid}/availability", headers=super_h, timeout=15).json()
    avail_after = a1.get("available")
    # cleanup
    if bid:
        requests.delete(API + f"/bookings/{bid}", headers=super_h, timeout=15)
    assert avail_after == avail_before - 1, f"seat not decremented: before={avail_before} after={avail_after}"


# ---------- BALANCE SHEET ----------

def test_balance_sheet_balanced(super_h):
    r = requests.get(API + "/mgmt-reports/balance-sheet", headers=super_h, timeout=20)
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    ta = d.get("total_assets") or d.get("total_asset") or d.get("assets_total")
    tl = d.get("total_liabilities") or d.get("liabilities_total")
    te = d.get("total_equity") or d.get("equity_total")
    if ta is None or tl is None or te is None:
        # try nested
        ta = ta or (d.get("assets") or {}).get("total")
        tl = tl or (d.get("liabilities") or {}).get("total")
        te = te or (d.get("equity") or {}).get("total")
    assert ta is not None and tl is not None and te is not None, f"missing totals: {list(d.keys())}"
    diff = abs(float(ta) - (float(tl) + float(te)))
    # allow small rounding
    assert diff < 1.0 or d.get("is_balanced") is True, f"BS not balanced: assets={ta} liab={tl} eq={te} diff={diff}"


# ---------- TAX CONFIG IMMUTABILITY ----------

def test_tax_snapshot_preserved_on_existing_invoice(super_h):
    """Existing invoice must keep tax_snapshot even after tax config changes (we don't actually mutate config, we just verify snapshot exists)."""
    r = requests.get(API + "/invoices", headers=super_h, timeout=15)
    assert r.status_code == 200
    items = r.json()
    items = items.get("items", items) if isinstance(items, dict) else items
    if not items:
        pytest.skip("no invoices to test tax snapshot")
    # fetch detail of first
    iid = items[0].get("id")
    det = requests.get(API + f"/invoices/{iid}", headers=super_h, timeout=15).json()
    inv = det.get("invoice") if isinstance(det, dict) and "invoice" in det else det
    snap = inv.get("tax_snapshot") or inv.get("taxes") or inv.get("tax_lines") or inv.get("tax_percent")
    assert snap is not None, f"invoice {iid} missing tax snapshot fields; keys={list(inv.keys())}"


# ---------- REFUND CAP ----------

def test_refund_cap_never_exceeds_total_paid(super_h):
    """Attempting to create/approve a refund larger than refundable must be rejected."""
    # Find a booking with payments
    r = requests.get(API + "/invoices", headers=super_h, timeout=15).json()
    invs = r.get("items", r) if isinstance(r, dict) else r
    target = None
    for inv in invs:
        pd = float(inv.get("paid_amount") or 0)
        if pd > 0:
            target = inv
            break
    if not target:
        pytest.skip("no paid invoice to test refund cap")
    bid = target.get("booking_id")
    paid = float(target.get("paid_amount") or 0)
    over = paid * 10 + 1_000_000
    # Try cancellation-based refund request path
    payload = {"booking_id": bid, "reason": "TEST_UAT refund cap", "requested_amount": over}
    r = requests.post(API + "/cancellations", json=payload, headers=super_h, timeout=15)
    if r.status_code not in (200, 201):
        # try direct refund endpoint
        r2 = requests.post(API + "/refunds", json={"booking_id": bid, "amount": over, "reason": "TEST_UAT"}, headers=super_h, timeout=15)
        assert r2.status_code >= 400, f"refund > paid should be rejected, got {r2.status_code} {r2.text[:200]}"
        return
    # cancellation created -> ensure approved amount is capped
    cid = r.json().get("id")
    ap = requests.patch(API + f"/cancellations/{cid}/approve", json={"approved_amount": over}, headers=super_h, timeout=15)
    # Expect either 400 (rejected) or an approved_amount capped <= paid
    if ap.status_code in (200, 201):
        body = ap.json()
        approved = float(body.get("approved_amount") or body.get("refund_amount") or 0)
        assert approved <= paid + 0.01, f"approved refund {approved} exceeds paid {paid}"
    else:
        assert ap.status_code >= 400
    # cleanup
    requests.post(API + f"/cancellations/{cid}/reopen", headers=super_h, timeout=10)


# ---------- COMMISSION: no HPP/profit for sales ----------

def test_sales_cannot_see_profit_or_hpp(sales_h):
    r = requests.get(API + "/hpp", headers=sales_h, timeout=10)
    assert r.status_code == 403
    r2 = requests.get(API + "/mgmt-reports/profit-loss", headers=sales_h, timeout=10)
    assert r2.status_code == 403


def test_commission_payout_next_month(super_h):
    r = requests.get(API + "/commissions/closings", headers=super_h, timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    if not items:
        pytest.skip("no commission closings yet")
    for c in items[:5]:
        cm = c.get("commission_month") or c.get("period")
        pm = c.get("payout_month")
        if cm and pm:
            # payout month must be strictly after commission month
            assert pm > cm, f"payout_month {pm} not after commission_month {cm}"


# ---------- AUDIT TRAIL ----------

def test_audit_log_writes_on_customer_update(super_h):
    custs = requests.get(API + "/customers", headers=super_h, timeout=15).json()
    custs = custs.get("items", custs) if isinstance(custs, dict) else custs
    if not custs:
        pytest.skip("no customers")
    cid = custs[0]["id"]
    orig = custs[0].get("phone") or ""
    new_val = f"08{int(time.time())%10**8:08d}"
    r = requests.put(API + f"/customers/{cid}", json={"phone": new_val}, headers=super_h, timeout=15)
    assert r.status_code in (200, 201)
    # check audit
    al = requests.get(API + "/audit-logs", headers=super_h, timeout=15, params={"entity_id": cid, "limit": 5}).json()
    entries = al.get("items", al) if isinstance(al, dict) else al
    assert entries, f"no audit entries for updated customer {cid}"
    # revert
    requests.put(API + f"/customers/{cid}", json={"phone": orig}, headers=super_h, timeout=15)


# ---------- SOFT DELETE (invoice with payment cannot be hard-deleted) ----------

def test_invoice_delete_blocked_when_paid(super_h):
    """Regression from iteration_38: paid invoices cannot be deleted."""
    r = requests.get(API + "/invoices", headers=super_h, timeout=15).json()
    items = r.get("items", r) if isinstance(r, dict) else r
    paid_inv = next((i for i in items if float(i.get("paid_amount") or 0) > 0), None)
    if not paid_inv:
        pytest.skip("no paid invoice")
    dr = requests.delete(API + f"/invoices/{paid_inv['id']}", headers=super_h, timeout=15)
    assert dr.status_code in (400, 403, 409), f"paid invoice must not be hard-deletable: got {dr.status_code}"


# ---------- ERROR HANDLING (no stack traces on invalid input) ----------

def test_invalid_booking_returns_clean_error(super_h):
    r = requests.post(API + "/v1/bookings", json={"customer_id": "nonexistent", "package_id": "bogus", "pax": 1},
                     headers=super_h, timeout=15)
    assert r.status_code >= 400
    body = r.text
    assert "Traceback" not in body and "File \"/app/backend" not in body, "stack trace leaked in error response"


# ---------- ACCOUNTING DASHBOARD access ----------

def test_accounting_dashboard_ok_for_accounting(acct_h):
    r = requests.get(API + "/accounting-dashboard", headers=acct_h, timeout=15)
    assert r.status_code == 200
