"""Phase 8E — Commission by Package & Monthly Payout backend tests.
Tests via public REACT_APP_BACKEND_URL. Uses seeded users.
"""
import os
import pytest
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import asyncio

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
MONGO = os.environ["MONGO_URL"]
DBN = os.environ["DB_NAME"]

SUPER = ("dedyirawan18@gmail.com", "Admin@123")
SALES = ("sales@safarcrm.com", "Sales@123")
ACC = ("accounting@safarcrm.com", "Account@123")

# Test period: pick a future period so it doesn't collide with real data.
PERIOD = "2027-03"       # commission month
PAYOUT = "2027-04"       # expected payout month
NOW = datetime.now(timezone.utc)
CUR_MONTH = f"{NOW.year:04d}-{NOW.month:02d}"


def _tok(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def super_tok():
    return _tok(*SUPER)


@pytest.fixture(scope="module")
def sales_tok():
    return _tok(*SALES)


@pytest.fixture(scope="module")
def acc_tok():
    return _tok(*ACC)


# -------------------- MASTER PACKAGES --------------------
def test_master_packages_super_ok(super_tok):
    r = requests.get(f"{BASE}/commissions/master-packages", headers=_h(super_tok), timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        p0 = data[0]
        for k in ["id", "name", "product_type"]:
            assert k in p0


def test_master_packages_rbac_sales(sales_tok):
    r = requests.get(f"{BASE}/commissions/master-packages", headers=_h(sales_tok), timeout=30)
    assert r.status_code == 403


def test_master_packages_rbac_accounting(acc_tok):
    r = requests.get(f"{BASE}/commissions/master-packages", headers=_h(acc_tok), timeout=30)
    assert r.status_code == 403


# -------------------- SEED (async helpers to prep bookings & schemes) --------------------
async def _seed():
    cl = AsyncIOMotorClient(MONGO)
    db = cl[DBN]
    # cleanup
    await db.commission_items.delete_many({"period": {"$in": [PERIOD, PAYOUT]}})
    await db.commission_lines.delete_many({"period": {"$in": [PERIOD, PAYOUT]}})
    await db.commission_closings.delete_many({"period": {"$in": [PERIOD, PAYOUT]}})
    await db.commission_schemes.delete_many({"scheme_name": {"$regex": "^P8E-"}})
    await db.bookings.delete_many({"booking_number": {"$regex": "^P8E-"}})
    await db.travelers.delete_many({"full_name": {"$regex": "^P8E "}})
    await db.packages.delete_many({"package_name": {"$regex": "^P8E-PKG"}})
    await db.invoices.delete_many({"invoice_number": {"$regex": "^P8E-INV"}})
    await db.payments.delete_many({"payment_number": {"$regex": "^P8E-PAY"}})

    pkg_a = (await db.packages.insert_one({"package_name": "P8E-PKG-A", "name": "P8E-PKG-A",
        "product_type": "UMROH", "selling_price": 1, "status": "ACTIVE", "created_at": "2027-01-01"})).inserted_id
    pkg_b = (await db.packages.insert_one({"package_name": "P8E-PKG-B", "name": "P8E-PKG-B",
        "product_type": "UMROH", "selling_price": 1, "status": "ACTIVE", "created_at": "2027-01-01"})).inserted_id

    sales = await db.users.find_one({"email": SALES[0]})
    sid, sname = str(sales["_id"]), sales["name"]

    async def make_booking(bnum, pkg_id, pax, paid_amount):
        b = {"booking_number": bnum, "status": "CONFIRMED", "booking_source": "SALES",
             "package_id": str(pkg_id), "package_name": "P8E Pkg", "pax": pax,
             "sales_pic_id": sid, "sales_pic_name": sname, "branch": "",
             "customer_name": f"Cust {bnum}",
             "created_at": f"{PERIOD}-05T00:00:00+00:00", "total": paid_amount}
        bid = str((await db.bookings.insert_one(b)).inserted_id)
        for i in range(pax):
            await db.travelers.insert_one({"booking_id": bid, "full_name": f"P8E {bnum}-{i}",
                                            "created_at": f"{PERIOD}-05T00:00:00+00:00"})
        # invoice + payment (fully paid inside PERIOD)
        inv = {"invoice_number": f"P8E-INV-{bnum}", "booking_id": bid, "amount": paid_amount,
               "total": paid_amount, "status": "Paid", "created_at": f"{PERIOD}-06T00:00:00+00:00"}
        iid = str((await db.invoices.insert_one(inv)).inserted_id)
        await db.payments.insert_one({"payment_number": f"P8E-PAY-{bnum}", "invoice_id": iid,
                                       "amount": paid_amount, "payment_date": f"{PERIOD}-15",
                                       "created_at": f"{PERIOD}-15T00:00:00+00:00"})
        return bid

    # 3 bookings on pkg A (fully paid) totaling 12 pax => tier 10-19
    await make_booking("P8E-A1", pkg_a, 5, 5_000_000)
    await make_booking("P8E-A2", pkg_a, 4, 5_000_000)
    await make_booking("P8E-A3", pkg_a, 3, 5_000_000)
    # 1 booking pkg B fully paid 6 pax
    await make_booking("P8E-B1", pkg_b, 6, 5_000_000)
    # 1 booking pkg A partial paid (DP) => not eligible
    b_part = {"booking_number": "P8E-A-PART", "status": "CONFIRMED", "booking_source": "SALES",
              "package_id": str(pkg_a), "package_name": "P8E Pkg", "pax": 2,
              "sales_pic_id": sid, "sales_pic_name": sname, "branch": "",
              "customer_name": "Cust Partial",
              "created_at": f"{PERIOD}-05T00:00:00+00:00", "total": 5_000_000}
    bidp = str((await db.bookings.insert_one(b_part)).inserted_id)
    for i in range(2):
        await db.travelers.insert_one({"booking_id": bidp, "full_name": f"P8E PART-{i}",
                                        "created_at": f"{PERIOD}-05T00:00:00+00:00"})
    inv_p = {"invoice_number": "P8E-INV-PART", "booking_id": bidp, "amount": 5_000_000,
             "total": 5_000_000, "status": "Unpaid",
             "created_at": f"{PERIOD}-06T00:00:00+00:00"}
    iidp = str((await db.invoices.insert_one(inv_p)).inserted_id)
    await db.payments.insert_one({"payment_number": "P8E-PAY-PART", "invoice_id": iidp,
                                   "amount": 1_000_000, "payment_date": f"{PERIOD}-15",
                                   "created_at": f"{PERIOD}-15T00:00:00+00:00"})

    # Schemes: default ALL, product UMROH, and package-specific for pkg A
    common = {"effective_from": f"{PERIOD}-01", "effective_until": "",
              "calculation_basis": "PAID", "auto_sales": False, "status": "ACTIVE",
              "created_at": "2027-01-01"}
    await db.commission_schemes.insert_one({"scheme_name": "P8E-DEFAULT", "product_type": "ALL",
        "package_id": "", "tiers": [{"min_pax": 0, "max_pax": None, "rate_per_pax": 50000}],
        **common})
    await db.commission_schemes.insert_one({"scheme_name": "P8E-UMROH", "product_type": "UMROH",
        "package_id": "", "tiers": [{"min_pax": 0, "max_pax": None, "rate_per_pax": 100000}],
        **common})
    await db.commission_schemes.insert_one({"scheme_name": "P8E-PKG-A", "product_type": "UMROH",
        "package_id": str(pkg_a),
        "tiers": [{"min_pax": 0, "max_pax": 9, "rate_per_pax": 200000},
                  {"min_pax": 10, "max_pax": 19, "rate_per_pax": 300000},
                  {"min_pax": 20, "max_pax": None, "rate_per_pax": 500000}],
        **common})

    cl.close()
    return {"pkg_a": str(pkg_a), "pkg_b": str(pkg_b), "sid": sid}


@pytest.fixture(scope="module")
def seeded():
    return asyncio.get_event_loop().run_until_complete(_seed())


# -------------------- CALCULATE & PRIORITY & TIERS --------------------
def test_calculate_and_priority_tiers(super_tok, seeded):
    r = requests.post(f"{BASE}/commissions/closings/{PERIOD}/calculate",
                      headers=_h(super_tok), timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["period"] == PERIOD
    # 12 pax pkg A (tier 10-19 -> 300000) + 6 pax pkg B (UMROH default 100000)
    # Real DB may also have other bookings for sales; so use lower bound assertion.
    assert body["total_pax"] >= 18

    # Detail: verify closing doc has payout_month & sa_approval
    d = requests.get(f"{BASE}/commissions/closings/{PERIOD}", headers=_h(super_tok), timeout=30).json()
    c = d["closing"]
    assert c["payout_month"] == PAYOUT
    assert c["sa_approval"] == "PENDING"
    assert c["status"] == "REVIEW"

    # Fetch items to verify tier assignment for pkg A bookings (300000) & pkg B (100000)
    async def _check():
        cl = AsyncIOMotorClient(MONGO); db = cl[DBN]
        a_items = await db.commission_items.find({"period": PERIOD,
            "booking_number": {"$in": ["P8E-A1", "P8E-A2", "P8E-A3"]}}).to_list(200)
        b_items = await db.commission_items.find({"period": PERIOD,
            "booking_number": "P8E-B1"}).to_list(200)
        part_items = await db.commission_items.find({"period": PERIOD,
            "booking_number": "P8E-A-PART"}).to_list(200)
        cl.close()
        return a_items, b_items, part_items
    a_items, b_items, part_items = asyncio.get_event_loop().run_until_complete(_check())
    assert len(a_items) == 12
    for it in a_items:
        assert it["commission_amount"] == 200000 or it["commission_amount"] == 300000
    # multiple groups; per-pkg tier: pkg A alone has 12 pax => rate 300000
    for it in a_items:
        assert it["commission_amount"] == 300000, f"pkg A tier mismatch: {it}"
    assert len(b_items) == 6
    for it in b_items:
        assert it["commission_amount"] == 100000  # UMROH default
    # partial paid must NOT be eligible
    assert len(part_items) == 0


# -------------------- PAYOUT GATING --------------------
def test_payout_gating(super_tok):
    # Not CLOSED yet -> reject
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/status",
                       json={"status": "PAID"}, headers=_h(super_tok), timeout=30)
    assert r.status_code == 400

    # Close it
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/status",
                       json={"status": "CLOSED"}, headers=_h(super_tok), timeout=30)
    assert r.status_code == 200

    # sa_approval still PENDING -> reject
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/status",
                       json={"status": "PAID"}, headers=_h(super_tok), timeout=30)
    assert r.status_code == 400
    assert "approval" in r.text.lower() or "APPROVED" in r.text


# -------------------- APPROVAL ENDPOINT --------------------
def test_approval_requires_reason(super_tok):
    # REJECTED requires reason
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/approval",
                       json={"decision": "REJECTED"}, headers=_h(super_tok), timeout=30)
    assert r.status_code == 400
    # REVISION requires reason
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/approval",
                       json={"decision": "REVISION"}, headers=_h(super_tok), timeout=30)
    assert r.status_code == 400
    # Invalid decision
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/approval",
                       json={"decision": "YES"}, headers=_h(super_tok), timeout=30)
    assert r.status_code == 400
    # APPROVED without reason OK
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/approval",
                       json={"decision": "APPROVED"}, headers=_h(super_tok), timeout=30)
    assert r.status_code == 200
    assert r.json()["sa_approval"] == "APPROVED"


def test_payout_gating_future_month(super_tok):
    # After APPROVED, still gated because PAYOUT (2027-04) > current month
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/status",
                       json={"status": "PAID"}, headers=_h(super_tok), timeout=30)
    if PAYOUT > CUR_MONTH:
        assert r.status_code == 400
        assert PAYOUT in r.text
    else:
        assert r.status_code in (200, 400)


# -------------------- SUPER ADMIN LINE ADJUSTMENT ON CLOSED --------------------
def test_super_admin_can_adjust_closed(super_tok):
    async def _get_line():
        cl = AsyncIOMotorClient(MONGO); db = cl[DBN]
        ln = await db.commission_lines.find_one({"period": PERIOD})
        cl.close()
        return str(ln["_id"]) if ln else None
    lid = asyncio.get_event_loop().run_until_complete(_get_line())
    assert lid
    r = requests.patch(f"{BASE}/commissions/lines/{lid}/adjustment",
                       json={"adjustment": -50000, "notes": "P8E test"},
                       headers=_h(super_tok), timeout=30)
    assert r.status_code == 200
    assert r.json()["adjustment"] == -50000


# -------------------- PENDING APPROVAL --------------------
def test_pending_approval_lists(super_tok):
    r = requests.get(f"{BASE}/commissions/pending-approval", headers=_h(super_tok), timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_pending_approval_rbac_sales(sales_tok):
    r = requests.get(f"{BASE}/commissions/pending-approval", headers=_h(sales_tok), timeout=30)
    assert r.status_code == 403


def test_pending_approval_rbac_accounting(acc_tok):
    r = requests.get(f"{BASE}/commissions/pending-approval", headers=_h(acc_tok), timeout=30)
    assert r.status_code == 403


def test_approval_endpoint_rbac_accounting(acc_tok):
    r = requests.patch(f"{BASE}/commissions/closings/{PERIOD}/approval",
                       json={"decision": "APPROVED"}, headers=_h(acc_tok), timeout=30)
    assert r.status_code == 403


# -------------------- ACCOUNTING SUMMARY --------------------
def test_accounting_summary_groups(super_tok, acc_tok):
    for tok in (super_tok, acc_tok):
        r = requests.get(f"{BASE}/commissions/accounting-summary", headers=_h(tok), timeout=30)
        assert r.status_code == 200
        data = r.json()
        for k in ["current", "upcoming_payout", "pending_approval", "paid"]:
            assert k in data
        # our PERIOD is CLOSED+APPROVED with payout in future => should be in upcoming_payout
        found = any(row["period"] == PERIOD for row in data["upcoming_payout"])
        assert found, f"PERIOD not in upcoming_payout: {data['upcoming_payout']}"


def test_accounting_summary_sales_forbidden(sales_tok):
    r = requests.get(f"{BASE}/commissions/accounting-summary", headers=_h(sales_tok), timeout=30)
    # Sales has no commission.manage — expect 403
    assert r.status_code == 403


# -------------------- SCHEME CREATE RBAC --------------------
def test_scheme_create_rbac_accounting(acc_tok):
    body = {"scheme_name": "P8E-TRY-ACC", "product_type": "ALL", "package_id": "",
            "effective_from": "2027-01-01", "effective_until": "",
            "calculation_basis": "PAID", "tiers": [{"min_pax": 0, "max_pax": None, "rate_per_pax": 1000}],
            "auto_sales": False, "status": "ACTIVE"}
    r = requests.post(f"{BASE}/commissions/schemes", json=body, headers=_h(acc_tok), timeout=30)
    assert r.status_code == 403


# -------------------- SALES MY COMMISSION --------------------
def test_sales_my_commission_shape(sales_tok):
    r = requests.get(f"{BASE}/commissions/my", headers=_h(sales_tok), timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ["current", "period", "bookings", "previous"]:
        assert k in d
    # bookings for our PERIOD should include our A1/A2/A3/B1 (fully paid) with proper payout_month
    ours = [b for b in d["bookings"] if b.get("booking_number", "").startswith("P8E-")]
    if ours:
        for b in ours:
            for k in ["booking_number", "customer_name", "package_name", "pax",
                      "commission_month", "payout_month", "tier", "status"]:
                assert k in b, f"missing {k} in {b}"
            if b["booking_number"] in ("P8E-A1", "P8E-A2", "P8E-A3", "P8E-B1"):
                assert b["payout_month"] == PAYOUT
                assert b["commission_month"] == PERIOD


# -------------------- CLEANUP --------------------
def test_zzz_cleanup():
    async def _cleanup():
        cl = AsyncIOMotorClient(MONGO); db = cl[DBN]
        await db.commission_items.delete_many({"period": {"$in": [PERIOD, PAYOUT]}})
        await db.commission_lines.delete_many({"period": {"$in": [PERIOD, PAYOUT]}})
        await db.commission_closings.delete_many({"period": {"$in": [PERIOD, PAYOUT]}})
        await db.commission_schemes.delete_many({"scheme_name": {"$regex": "^P8E-"}})
        await db.bookings.delete_many({"booking_number": {"$regex": "^P8E-"}})
        await db.travelers.delete_many({"full_name": {"$regex": "^P8E "}})
        await db.packages.delete_many({"package_name": {"$regex": "^P8E-PKG"}})
        await db.invoices.delete_many({"invoice_number": {"$regex": "^P8E-INV"}})
        await db.payments.delete_many({"payment_number": {"$regex": "^P8E-PAY"}})
        cl.close()
    asyncio.get_event_loop().run_until_complete(_cleanup())
    assert True
