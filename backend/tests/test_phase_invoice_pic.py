"""E2E backend tests for iteration_38: PIC change activity, Bulk reassign PIC,
Invoice pax-based nominal, Edit/Delete/Regenerate invoice, RBAC (sales 403)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://github-workflow-14.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES = {"email": "sales@safarcrm.com", "password": "Sales@123"}
BOOKING_ID = "6a7ac3e26aad3a79a0844111"   # BKG-00002 pax=2, 1 traveler, per_pax 50jt
CUSTOMER_ID = "6a7a88415cad6f678e729b10"
RINA_PIC_ID = "6a7a7e21e764e17be548e40c"  # Rina Sales


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(SUPER)}"}


@pytest.fixture(scope="module")
def sales_h():
    return {"Authorization": f"Bearer {_login(SALES)}"}


# ---------- RBAC ----------
class TestRBAC:
    def test_sales_cannot_change_pic(self, sales_h):
        # find any sales user id
        r = requests.get(f"{API}/users", headers=sales_h, timeout=20)
        # sales list users may or may not be permitted, so use hardcoded RINA
        r2 = requests.put(f"{API}/customers/{CUSTOMER_ID}",
                          headers=sales_h,
                          json={"sales_pic_id": RINA_PIC_ID}, timeout=20)
        assert r2.status_code == 403, f"expected 403, got {r2.status_code} {r2.text}"

    def test_sales_cannot_bulk_reassign(self, sales_h):
        r = requests.post(f"{API}/customers/bulk-reassign-pic",
                          headers=sales_h,
                          json={"customer_ids": [CUSTOMER_ID], "sales_pic_id": RINA_PIC_ID},
                          timeout=20)
        assert r.status_code == 403


# ---------- Invoice CRUD on BKG-00002 ----------
@pytest.fixture(scope="module")
def created_invoice_id(admin_h):
    """Create invoice for BKG-00002 and yield id; deleted at teardown."""
    # cleanup pre-existing test invoices on this booking
    lst = requests.get(f"{API}/invoices", headers=admin_h, timeout=20).json()
    for inv in lst:
        if inv.get("booking_id") == BOOKING_ID and float(inv.get("paid_amount") or 0) == 0:
            requests.delete(f"{API}/invoices/{inv['id']}", headers=admin_h, timeout=20)

    r = requests.post(f"{API}/bookings/{BOOKING_ID}/invoice",
                      headers=admin_h, json={"due_date": "2026-12-31"}, timeout=30)
    assert r.status_code == 200, r.text
    inv = r.json()
    yield inv
    # Teardown
    iid = inv.get("id")
    if iid:
        requests.delete(f"{API}/invoices/{iid}", headers=admin_h, timeout=20)


class TestInvoiceFlow:
    def test_create_invoice_nominal(self, created_invoice_id):
        inv = created_invoice_id
        # 1 traveler → 50jt subtotal, total 48,610,000
        assert inv["pax"] == 1, f"expected pax=1 got {inv.get('pax')}"
        assert float(inv["per_pax_price"]) == 50000000.0
        assert float(inv["subtotal"]) == 50000000.0
        assert float(inv["total"]) == 48610000.0, f"got total {inv.get('total')}"

    def test_edit_invoice(self, admin_h, created_invoice_id):
        iid = created_invoice_id["id"]
        r = requests.put(f"{API}/invoices/{iid}", headers=admin_h,
                         json={"pax": 3, "per_pax_price": 10000000,
                               "discount_amount": 0, "tax_amount": 0,
                               "due_date": "2026-12-31"},
                         timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["pax"] == 3
        assert float(d["subtotal"]) == 30000000.0
        assert float(d["total"]) == 30000000.0
        # verify GET persistence
        g = requests.get(f"{API}/invoices/{iid}", headers=admin_h, timeout=20).json()
        assert float(g["invoice"]["total"]) == 30000000.0

    def test_regenerate_reverts(self, admin_h, created_invoice_id):
        iid = created_invoice_id["id"]
        r = requests.post(f"{API}/invoices/{iid}/regenerate", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["pax"] == 1
        assert float(d["subtotal"]) == 50000000.0
        assert float(d["total"]) == 48610000.0

    def test_delete_blocked_when_payment_exists(self, admin_h, created_invoice_id):
        iid = created_invoice_id["id"]
        # Add a payment
        p = requests.post(f"{API}/invoices/{iid}/payments", headers=admin_h,
                         json={"payment_date": "2026-01-15", "amount": 1000000,
                               "payment_method": "Transfer", "bank": "BCA",
                               "reference_number": "TEST-DEL-1"}, timeout=20)
        if p.status_code == 200:
            pay_id = p.json().get("id")
            # try delete → should be 400
            r = requests.delete(f"{API}/invoices/{iid}", headers=admin_h, timeout=20)
            assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text}"
            # void payment to allow teardown delete
            if pay_id:
                # VOID via dedicated endpoint so booking-teardown can delete invoice
                requests.post(f"{API}/payments/{pay_id}/void",
                              headers=admin_h, json={"reason": "TEST cleanup"}, timeout=20)
        else:
            pytest.skip(f"Could not add payment ({p.status_code}); skipping delete-block test")


# ---------- PIC change activity ----------
class TestPicChangeActivity:
    def test_pic_change_logs_timeline(self, admin_h):
        # find another sales id different from current
        users = requests.get(f"{API}/users", headers=admin_h, timeout=20).json()
        sales_users = [u for u in users if u.get("role") == "sales" and not u.get("is_deleted")]
        assert len(sales_users) >= 2, "need at least 2 sales users"
        cust = requests.get(f"{API}/customers/{CUSTOMER_ID}", headers=admin_h, timeout=20).json()
        current_pic = str(cust.get("sales_pic_id") or "")
        original_pic = current_pic or RINA_PIC_ID
        other = next((u for u in sales_users if u["id"] != current_pic), None)
        assert other
        # change to other
        r = requests.put(f"{API}/customers/{CUSTOMER_ID}",
                         headers=admin_h, json={"sales_pic_id": other["id"]}, timeout=20)
        assert r.status_code == 200, r.text
        # check activities
        c360 = requests.get(f"{API}/customers/{CUSTOMER_ID}/360",
                            headers=admin_h, timeout=20).json()
        timeline = c360.get("timeline") or []
        assert any(t.get("kind") == "pic_change" for t in timeline), \
            f"no pic_change entry in timeline (kinds seen: {set(t.get('kind') for t in timeline)})"
        # revert
        rev = requests.put(f"{API}/customers/{CUSTOMER_ID}",
                           headers=admin_h, json={"sales_pic_id": original_pic}, timeout=20)
        assert rev.status_code == 200


# ---------- Bulk reassign ----------
class TestBulkReassign:
    def test_bulk_reassign_and_revert(self, admin_h):
        # pick 2 customers of Rina
        custs = requests.get(f"{API}/customers", headers=admin_h, timeout=20).json()
        if isinstance(custs, dict):
            custs = custs.get("data") or custs.get("items") or []
        rina_custs = [c for c in custs if str(c.get("sales_pic_id") or "") == RINA_PIC_ID][:2]
        assert len(rina_custs) >= 1, "need at least 1 Rina customer"
        # find another sales user
        users = requests.get(f"{API}/users", headers=admin_h, timeout=20).json()
        other = next((u for u in users if u.get("role") == "sales" and u["id"] != RINA_PIC_ID and not u.get("is_deleted")), None)
        assert other
        ids = [c["id"] for c in rina_custs]
        r = requests.post(f"{API}/customers/bulk-reassign-pic", headers=admin_h,
                         json={"customer_ids": ids, "sales_pic_id": other["id"]}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("reassigned") == len(ids)
        # verify
        for cid in ids:
            c = requests.get(f"{API}/customers/{cid}", headers=admin_h, timeout=20).json()
            assert str(c.get("sales_pic_id")) == other["id"]
        # revert
        rev = requests.post(f"{API}/customers/bulk-reassign-pic", headers=admin_h,
                           json={"customer_ids": ids, "sales_pic_id": RINA_PIC_ID}, timeout=30)
        assert rev.status_code == 200
        for cid in ids:
            c = requests.get(f"{API}/customers/{cid}", headers=admin_h, timeout=20).json()
            assert str(c.get("sales_pic_id")) == RINA_PIC_ID
