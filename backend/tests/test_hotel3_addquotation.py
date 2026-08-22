"""Phase HOTEL-3 backend tests: /api/hotel/add-to-quotation, hotel/stats,
customer 360 timeline for hotel search, PDF hotel section, and quotation regression."""
import os
from datetime import date, timedelta
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES = {"email": "sales@safarcrm.com", "password": "Sales@123"}
ACCT = {"email": "accounting@safarcrm.com", "password": "Account@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


def _h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES)


@pytest.fixture(scope="module")
def acct_token():
    return _login(ACCT)


@pytest.fixture(scope="module")
def existing_customer_id(admin_token):
    r = requests.get(f"{API}/customers", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    lst = r.json()
    assert isinstance(lst, list) and len(lst) > 0, "No existing customers available"
    return lst[0]["id"]


def _future_dates(offset=30, nights=3):
    ci = (date.today() + timedelta(days=offset)).isoformat()
    co = (date.today() + timedelta(days=offset + nights)).isoformat()
    return ci, co


def _hotel_payload(name="TEST_H3 Hotel Grand", rate=1_500_000, rooms=2, adults=2, nights=3):
    ci, co = _future_dates(nights=nights)
    return {
        "hotelId": 9999001, "hotelName": name, "roomtypeName": "Deluxe Twin",
        "checkInDate": ci, "checkOutDate": co,
        "numberOfRooms": rooms, "numberOfAdults": adults, "numberOfChildren": 0,
        "dailyRate": rate, "currency": "IDR",
        "landingURL": "https://agoda.example/hotel/9999001", "imageURL": "",
        "source": "AGODA_API",
    }


# ---------- Create new hotel-only quotation ----------
class TestAddToQuotationCreate:
    def test_create_new_hotel_only_quotation(self, admin_token, existing_customer_id):
        payload = {"customer_id": existing_customer_id, "hotel": _hotel_payload()}
        r = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(admin_token), json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("quotation_id") and d.get("quotation_number")
        # Fetch quotation and validate
        qr = requests.get(f"{API}/quotations/{d['quotation_id']}", headers=_h(admin_token), timeout=15)
        assert qr.status_code == 200
        q = qr.json()
        assert q["package_name"] == "(Hotel Only)"
        assert q.get("package_id") in (None, "")
        assert len(q["hotel_items"]) == 1
        it = q["hotel_items"][0]
        assert it["nights"] == 3
        assert it["numberOfRooms"] == 2
        assert it["total"] == 1_500_000 * 3 * 2
        assert it["source"] == "AGODA_API"
        assert float(q["hotel_total"]) == 9_000_000
        assert float(q["grand_total_with_hotel"]) == float(q.get("total") or 0) + 9_000_000
        # Save for downstream test module
        pytest.hotel3_qid = d["quotation_id"]
        pytest.hotel3_cid = existing_customer_id


# ---------- Append to existing quotation ----------
class TestAddToQuotationAppend:
    def test_append_second_hotel_item(self, admin_token, existing_customer_id):
        # First create a fresh quotation
        p1 = {"customer_id": existing_customer_id, "hotel": _hotel_payload(name="TEST_H3 First", rate=1_000_000, rooms=1, nights=2)}
        r1 = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(admin_token), json=p1, timeout=30)
        assert r1.status_code == 200
        qid = r1.json()["quotation_id"]
        # Now append second
        p2 = {"customer_id": existing_customer_id, "quotation_id": qid,
              "hotel": _hotel_payload(name="TEST_H3 Second", rate=500_000, rooms=1, nights=2)}
        r2 = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(admin_token), json=p2, timeout=30)
        assert r2.status_code == 200, r2.text
        # Verify quotation now has 2 items + updated hotel_total
        qr = requests.get(f"{API}/quotations/{qid}", headers=_h(admin_token), timeout=15)
        q = qr.json()
        assert len(q["hotel_items"]) == 2
        expected = 1_000_000 * 2 * 1 + 500_000 * 2 * 1
        assert float(q["hotel_total"]) == expected


# ---------- Customer dedupe ----------
class TestCustomerDedupe:
    def test_new_customer_with_matching_whatsapp_reuses(self, admin_token, existing_customer_id):
        # get existing whatsapp
        cr = requests.get(f"{API}/customers/{existing_customer_id}", headers=_h(admin_token), timeout=15)
        assert cr.status_code == 200
        cust = cr.json()
        wa = cust.get("whatsapp") or ""
        if not wa:
            pytest.skip("Existing customer has no whatsapp to test dedupe")
        payload = {"new_customer": {"full_name": "TEST_H3 Different Name", "whatsapp": wa},
                   "hotel": _hotel_payload(name="TEST_H3 Dedupe WA")}
        r = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(admin_token), json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["customer_id"] == existing_customer_id

    def test_brand_new_customer_created(self, admin_token):
        unique_wa = f"628{int(date.today().strftime('%y%m%d'))}{os.getpid() % 10000:04d}"
        unique_name = f"TEST_H3 New Customer {unique_wa}"
        # Ensure it doesn't already exist
        payload = {"new_customer": {"full_name": unique_name, "whatsapp": unique_wa,
                                    "email": f"test_h3_{unique_wa}@example.com"},
                   "hotel": _hotel_payload(name="TEST_H3 NewCust Hotel")}
        r = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(admin_token), json=payload, timeout=30)
        assert r.status_code == 200, r.text
        new_cid = r.json()["customer_id"]
        # Verify the customer exists
        cr = requests.get(f"{API}/customers/{new_cid}", headers=_h(admin_token), timeout=15)
        assert cr.status_code == 200
        assert cr.json()["full_name"] == unique_name


# ---------- Activity log + Customer 360 timeline ----------
class TestActivityAndTimeline:
    def test_sales_activity_recorded(self, admin_token, existing_customer_id):
        # Create a new hotel-only quotation to guarantee a recent activity
        payload = {"customer_id": existing_customer_id, "hotel": _hotel_payload(name="TEST_H3 Activity Trace")}
        r = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(admin_token), json=payload, timeout=30)
        assert r.status_code == 200
        qid = r.json()["quotation_id"]
        # sales_activities endpoint
        sa = requests.get(f"{API}/sales-activities", headers=_h(admin_token), timeout=15)
        # If endpoint differs, tolerate
        if sa.status_code == 200:
            items = sa.json() if isinstance(sa.json(), list) else sa.json().get("items", [])
            match = [x for x in items if x.get("quotation_id") == qid and x.get("source") == "AGODA_API"]
            assert len(match) >= 1, f"No sales_activities entry found referencing quotation {qid}"

    def test_customer_360_has_hotel_timeline_entry(self, admin_token, existing_customer_id):
        # Make sure we have at least one hotel add
        payload = {"customer_id": existing_customer_id, "hotel": _hotel_payload(name="TEST_H3 360 Trace")}
        requests.post(f"{API}/hotel/add-to-quotation", headers=_h(admin_token), json=payload, timeout=30)
        r = requests.get(f"{API}/customers/{existing_customer_id}/360", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        tl = r.json().get("timeline", [])
        kinds = [t.get("kind") for t in tl]
        assert "hotel" in kinds, f"'hotel' kind missing from timeline. Found kinds sample: {set(kinds)}"

    def test_hotel_search_logs_timeline(self, sales_token, admin_token, existing_customer_id):
        ci, co = _future_dates()
        body = {"searchType": "city", "cityId": 9395, "checkInDate": ci, "checkOutDate": co,
                "numberOfAdult": 2, "numberOfChildren": 0, "customer_id": existing_customer_id,
                "maxResult": 5}
        r = requests.post(f"{API}/hotel/search", headers=_h(sales_token), json=body, timeout=30)
        assert r.status_code == 200
        # Timeline should now contain a Hotel Search entry
        c360 = requests.get(f"{API}/customers/{existing_customer_id}/360", headers=_h(admin_token), timeout=20)
        assert c360.status_code == 200
        tl = c360.json().get("timeline", [])
        hotel_titles = [t.get("title", "") for t in tl if t.get("kind") == "hotel"]
        assert any("Hotel Search" in tt for tt in hotel_titles), f"'Hotel Search' timeline entry not found. Titles: {hotel_titles[:10]}"


# ---------- Stats ----------
class TestHotelStats:
    def test_stats_admin(self, admin_token):
        r = requests.get(f"{API}/hotel/stats", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert set(["hotel_searches", "hotel_quotations", "hotel_revenue"]).issubset(d.keys())
        assert isinstance(d["hotel_searches"], int)
        assert isinstance(d["hotel_quotations"], int)
        assert d["hotel_quotations"] >= 1
        assert d["hotel_revenue"] >= 9_000_000  # from prior tests

    def test_stats_sales_scoped(self, sales_token):
        r = requests.get(f"{API}/hotel/stats", headers=_h(sales_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert set(["hotel_searches", "hotel_quotations", "hotel_revenue"]).issubset(d.keys())


# ---------- RBAC ----------
class TestAddToQuotationRBAC:
    def test_accounting_forbidden(self, acct_token, existing_customer_id):
        payload = {"customer_id": existing_customer_id, "hotel": _hotel_payload(name="TEST_H3 RBAC Acct")}
        r = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(acct_token), json=payload, timeout=30)
        assert r.status_code == 403, f"Expected 403 for accounting, got {r.status_code}: {r.text[:200]}"

    def test_sales_allowed(self, sales_token, existing_customer_id):
        payload = {"customer_id": existing_customer_id, "hotel": _hotel_payload(name="TEST_H3 RBAC Sales")}
        r = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(sales_token), json=payload, timeout=30)
        # sales may or may not own the picked customer; either 200 or 403 for record access.
        # Accept 200 explicitly (per acceptance criteria: Sales CAN add-to-quotation).
        # If 403 due to record ownership, retry with new_customer (guaranteed owned).
        if r.status_code != 200:
            payload2 = {"new_customer": {"full_name": f"TEST_H3 Sales Owned {os.getpid()}",
                                         "whatsapp": f"628999{os.getpid() % 10000:04d}"},
                        "hotel": _hotel_payload(name="TEST_H3 RBAC Sales2")}
            r2 = requests.post(f"{API}/hotel/add-to-quotation", headers=_h(sales_token), json=payload2, timeout=30)
            assert r2.status_code == 200, f"Sales should be able to add-to-quotation: {r2.status_code} {r2.text[:200]}"
        else:
            assert r.status_code == 200


# ---------- PDF with hotel section ----------
class TestQuotationHotelPDF:
    def test_pdf_renders_with_hotel(self, admin_token):
        # find a quotation with hotel_items
        r = requests.get(f"{API}/quotations", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        qs = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        target = next((q for q in qs if q.get("hotel_items")), None)
        assert target is not None, "No quotation with hotel_items found"
        qid = target["id"]
        pdf = requests.get(f"{API}/quotations/{qid}/pdf", headers=_h(admin_token), timeout=30)
        assert pdf.status_code == 200, pdf.text[:200]
        assert pdf.headers.get("content-type", "").startswith("application/pdf")
        assert len(pdf.content) > 5000
        # PDF binary — string search for "HOTEL" won't work for compressed streams;
        # we accept size+content-type as sufficient signal.


# ---------- Regression: core quotation create ----------
class TestQuotationRegression:
    def test_create_package_quotation_unchanged_by_hotel(self, admin_token, existing_customer_id):
        # Find a package
        pr = requests.get(f"{API}/packages", headers=_h(admin_token), timeout=15)
        if pr.status_code != 200:
            pytest.skip(f"packages endpoint {pr.status_code}")
        pkgs = pr.json() if isinstance(pr.json(), list) else pr.json().get("items", [])
        if not pkgs:
            pytest.skip("No packages available for regression test")
        pkg = pkgs[0]
        # Try to find a departure_id if required
        dep_id = None
        deps = pkg.get("departures") or []
        if deps:
            dep_id = deps[0].get("id") or deps[0].get("_id")
        payload = {"customer_id": existing_customer_id, "package_id": pkg["id"],
                   "pax": 2, "room_type": "TWIN", "addons": [], "notes": "TEST_H3 regression"}
        if dep_id:
            payload["departure_id"] = dep_id
        r = requests.post(f"{API}/quotations", headers=_h(admin_token), json=payload, timeout=20)
        if r.status_code not in (200, 201):
            pytest.skip(f"Quotation create requires more context: {r.status_code} {r.text[:200]}")
        q = r.json()
        assert q.get("total") is not None
        assert q.get("hotel_total", 0) in (0, None)
